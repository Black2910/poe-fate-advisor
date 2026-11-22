"""Build a complete ZIP compatible with the Fate Advisor updater."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app_updates import APP_FILES, inspect_package

def build():
    version=json.loads((ROOT/'version.json').read_text(encoding='utf-8'))['version']
    tag=os.environ.get('RELEASE_TAG','')
    if tag and tag != 'v'+version:
        raise SystemExit(f'Tag {tag} stimmt nicht mit version.json v{version} überein')
    dist=ROOT/'dist'
    dist.mkdir(exist_ok=True)
    path=dist/f'PoE_Fate_Advisor_v{version}.zip'
    candidates=[ROOT/p for p in sorted(APP_FILES)]
    candidates += sorted(p for p in (ROOT/'assets').rglob('*') if p.is_file())
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as bundle:
        for src in candidates:
            if not src.is_file():
                raise FileNotFoundError(f'Pflichtdatei fehlt: {src}')
            bundle.write(src,src.relative_to(ROOT).as_posix())
    info=inspect_package(path,allow_equal=True)
    if info['version']!=version:
        raise RuntimeError('Falsche Paketversion')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    (dist/'SHA256SUMS.txt').write_text(f'{digest}  {path.name}\n',encoding='utf-8')
    print(f'{path} SHA256={digest}; {len(info["members"])} Dateien')
    return path

if __name__=='__main__': build()
