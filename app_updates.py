"""Conservative ZIP updater for explicit user-approved desktop releases.

No background download or automatic code execution. All installs are initiated
from the GUI after the user selects a local ZIP or trusted GitHub release.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import zipfile

VERSION = '1.3.1'
DEFAULT_GITHUB_REPO = 'Black2910/poe-fate-advisor'
MAX_DOWNLOAD = 20 * 1024 * 1024
MAX_UNPACKED = 45 * 1024 * 1024
REPOSITORY_PATTERN = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
APP_FILES = {'app.py','app_updates.py','updater_worker.py','icon_database.py',
             'icon_reference.py','fate_engine.py','reward_catalog.py',
             'icon_ranking.py','image_regions.py','vision_sheet.py',
             'selection_validation.py','card_marker.py','overlay.py',
             'tray.py','requirements.txt','start_windows.bat',
             'PoE Fate Advisor - leiser Start.vbs','README.md','version.json',
             'install_windows.py','Einmal_installieren.bat'}
PROTECTED_SEGMENTS = {'.venv', '__pycache__', '.git', '.env', '.poe_fate_advisor_data'}


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    url: str
    sha256: str
    name: str
    notes: str = ''


def parse_version(value: str) -> tuple[int,int,int]:
    value=str(value).strip().lstrip('vV')
    match=re.fullmatch(r'(\d+)\.(\d+)(?:\.(\d+))?',value)
    if not match:
        raise ValueError('Versionsnummer muss wie 1.3.0 aussehen.')
    return int(match[1]),int(match[2]),int(match[3] or 0)


def is_newer(version: str, current=VERSION) -> bool:
    return parse_version(version)>parse_version(current)


def _safe_member(member: zipfile.ZipInfo, prefix: str) -> str:
    # Paths are validated before zip content reaches the disk.
    raw = member.filename
    if '\\' in raw or raw.startswith('/') or ':' in raw or '\x00' in raw:
        raise ValueError('Unsicherer Dateipfad im ZIP.')
    path=PurePosixPath(raw)
    if '..' in path.parts or any(part.startswith('.') and part not in ('.',) for part in path.parts):
        raise ValueError('Unerlaubter Pfad im Update.')
    if (member.external_attr >> 16) & 0o170000 == 0o120000:
        raise ValueError('Symlinks sind im Update unzulässig.')
    parts=list(path.parts)
    if prefix:
        if not parts or parts[0]!=prefix:
            raise ValueError('Mehrere Wurzelordner im Update.')
        parts=parts[1:]
    if not parts:
        return ''
    if any(p in PROTECTED_SEGMENTS for p in parts):
        raise ValueError('Update darf keine geschützten Programm-/Nutzerdaten ändern.')
    if parts[0] not in APP_FILES | {'assets','tests'}:
        raise ValueError('Unbekannte Datei im Update: '+parts[0])
    if parts[0] in APP_FILES and len(parts)!=1:
        raise ValueError('Ungültige Unterordnerstruktur: '+parts[0])
    if len(parts)>5 or len('/'.join(parts))>160:
        raise ValueError('Zu tiefer Dateipfad.')
    return '/'.join(parts)


def inspect_package(filename: Path, *, allow_equal=False) -> dict:
    """Validate relative paths/version, block nested archives, symlinks, bombs."""
    with zipfile.ZipFile(filename) as z:
        names=[x.filename.rstrip('/') for x in z.infolist() if not x.is_dir()]
        if not names or len(names)>300:
            raise ValueError('Ungültiges oder zu großes Release-Paket.')
        prefix=''
        if 'version.json' not in names:
            roots={name.split('/')[0] for name in names}
            if len(roots)!=1:
                raise ValueError('Release enthält keine version.json im Hauptordner.')
            prefix=next(iter(roots))
        entries={}
        total=0
        for member in z.infolist():
            sub=_safe_member(member,prefix)
            if not sub or member.is_dir():
                continue
            if sub.lower().endswith(('.zip','.exe','.dll','.pyd','.bat~')):
                raise ValueError('Ausführbare Zusatzdateien/Archive nicht zugelassen.')
            if sub in entries:
                raise ValueError('Doppelte Dateinamen im ZIP.')
            if member.file_size>12_000_000:
                raise ValueError('Eine Datei ist ungewöhnlich groß.')
            entries[sub]=member
            total+=member.file_size
        if total>MAX_UNPACKED:
            raise ValueError('Das Paket ist entpackt zu groß.')
        if not {'version.json','app.py','start_windows.bat'}.issubset(entries):
            raise ValueError('Kein vollständiges Fate-Advisor-Release.')
        ver=json.loads(z.read(entries['version.json']))
        if ver.get('app_id')!='poe-fate-advisor':
            raise ValueError('Dieses ZIP gehört nicht zum Fate Advisor.')
        new_version=str(ver.get('version',''))
        if not allow_equal and not is_newer(new_version):
            raise ValueError(f'Neue Version {new_version} muss neuer sein als {VERSION}.')
        parse_version(new_version)
        return {'version':new_version,'members':sorted(entries),'prefix':prefix,'size':total}


def stage_package(filename: Path, stage_root: Path, *, allow_equal=False) -> dict:
    desc=inspect_package(filename,allow_equal=allow_equal)
    stage_root=Path(stage_root)
    stage_root.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(filename) as z:
        prefix=desc['prefix']
        for member in z.infolist():
            path=_safe_member(member,prefix)
            if not path or member.is_dir():continue
            destination=stage_root.joinpath(*path.split('/'))
            destination.parent.mkdir(parents=True,exist_ok=True)
            with z.open(member,'r') as source, destination.open('wb') as target:
                shutil.copyfileobj(source,target,1024*1024)
    return desc


def verify_sha256(filename: Path, expected: str):
    expected=expected.removeprefix('sha256:').lower()
    if not re.fullmatch(r'[0-9a-f]{64}',expected):
        raise ValueError('Kein gültiger SHA-256-Prüfwert.')
    digest=hashlib.sha256()
    with Path(filename).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            digest.update(block)
    if digest.hexdigest()!=expected:
        raise ValueError('Update-Prüfsumme stimmt nicht überein!')
    return True


def query_github_release(repo: str) -> UpdateInfo | None:
    """Look up a user-specified or configured public GitHub Releases source."""
    if not REPOSITORY_PATTERN.fullmatch(repo or ''):
        raise ValueError('Bitte GitHub-Repository als Besitzer/Repository eintragen.')
    url=f'https://api.github.com/repos/{repo}/releases/latest'
    req=Request(url,headers={'User-Agent':'PoE-Fate-Advisor/'+VERSION,
                              'Accept':'application/vnd.github+json'})
    with urlopen(req, timeout=12) as response:
        data=json.load(response)
    version=data.get('tag_name','')
    if not is_newer(version):
        return None
    matching=[asset for asset in data.get('assets',[]) if
              asset.get('name','').lower().endswith('.zip') and
              ('fate' in asset.get('name','').lower() or 'advisor' in asset.get('name','').lower())]
    if not matching:
        raise ValueError('Release enthält keine Fate-Advisor-ZIP-Datei.')
    item=matching[0]
    remote=str(item.get('browser_download_url',''))
    parsed=urlparse(remote)
    if parsed.scheme!='https' or parsed.netloc!='github.com' or not parsed.path.startswith('/'+repo+'/releases/download/'):
        raise ValueError('Download-URL liegt nicht im angegebenen GitHub-Repository.')
    digest=str(item.get('digest') or '')
    if not digest.startswith('sha256:'):
        raise ValueError('GitHub hat für dieses Release keine SHA-256-Prüfsumme bereitgestellt. '
                         'Bitte ZIP manuell vom vertrauenswürdigen Release laden.')
    return UpdateInfo(version,remote,digest,str(item.get('name')),str(data.get('body') or '')[:1500])


def download_verified_release(info: UpdateInfo, directory: Path) -> Path:
    folder=Path(directory)
    folder.mkdir(parents=True,exist_ok=True)
    name=re.sub(r'[^A-Za-z0-9._-]','_',info.name)
    path=folder/name
    req=Request(info.url,headers={'User-Agent':'PoE-Fate-Advisor/'+VERSION})
    size=0
    with urlopen(req,timeout=25) as response, path.open('wb') as target:
        for chunk in iter(lambda:response.read(1024*1024),b''):
            size+=len(chunk)
            if size>MAX_DOWNLOAD:
                path.unlink(missing_ok=True)
                raise ValueError('Download überschreitet die maximale Größe.')
            target.write(chunk)
    verify_sha256(path, info.sha256)
    inspect_package(path)
    return path


def backup_root():
    root=Path.home()/'.poe_fate_advisor_updates'
    root.mkdir(parents=True,exist_ok=True)
    return root
