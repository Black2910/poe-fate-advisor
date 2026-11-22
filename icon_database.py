"""Durable, opt-in training database of visible Fate reward icons.

Only explicit user confirmation may label new gameplay screenshots. Public
PoEDB artworks and bundled examples are imported with source provenance.
This module never sends pixels to a server and never modifies game files.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, timezone
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import threading

from PIL import Image

from reward_catalog import REWARD_ICONS

DATA_HOME = Path(os.environ.get('POE_FATE_DATA_DIR', Path.home() / '.poe_fate_advisor_data'))
DB_PATH = DATA_HOME / 'reward_icons.sqlite3'
SAMPLE_DIR = DATA_HOME / 'samples'
BUNDLED = Path(__file__).resolve().parent / 'assets' / 'verified_icons'
OLD_CACHE = Path.home() / '.poe_fate_advisor_icons'
DB_SCHEMA = 1


@dataclass(frozen=True)
class IconCategory:
    icon_id: str
    description: str
    samples: int
    user_confirmed: int


class IconDatabase:
    """Short-lived SQLite connections: callers may run in Tk or worker threads."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else DATA_HOME
        self.images = self.root / 'samples'
        self.path = self.root / 'reward_icons.sqlite3'
        self.root.mkdir(parents=True, exist_ok=True)
        self.images.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=8)
        db.execute('PRAGMA busy_timeout=8000')
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def _initialize(self):
        with self._connect() as con:
            con.executescript('''
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS categories (
                icon_id TEXT PRIMARY KEY,
                label_de TEXT NOT NULL,
                source TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS samples (
                hash TEXT PRIMARY KEY,
                icon_id TEXT NOT NULL REFERENCES categories(icon_id),
                file_name TEXT NOT NULL,
                origin TEXT NOT NULL,
                confirmed INTEGER NOT NULL CHECK (confirmed IN (0,1)),
                created_utc TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_icon_samples_cat ON samples(icon_id);
            ''')
            con.execute('INSERT OR IGNORE INTO metadata(key,value) VALUES(?,?)', ('schema', str(DB_SCHEMA)))
            for icon_id, label in REWARD_ICONS.items():
                con.execute('INSERT INTO categories(icon_id,label_de,source) VALUES(?,?,?) '
                            'ON CONFLICT(icon_id) DO UPDATE SET label_de=excluded.label_de '
                            'WHERE categories.label_de<>excluded.label_de',
                            (icon_id, label, 'PoEDB 3.30 Rewards'))

    @staticmethod
    def _normal_image(img: Image.Image) -> bytes:
        # Always store encoded pixels rather than user-supplied file bytes.
        image = img.convert('RGB')
        if image.width < 12 or image.height < 12 or image.width > 2000 or image.height > 2000:
            raise ValueError('Icon-Bildausschnitt muss 12–2000 Pixel groß sein.')
        buf = BytesIO()
        image.save(buf, format='PNG', optimize=True)
        return buf.getvalue()

    def add_sample(self, icon_id: str, image: Image.Image, *, origin='user_confirmed', confirmed=True):
        if icon_id not in REWARD_ICONS:
            raise ValueError('Unbekannte Icon-Kategorie.')
        if confirmed and origin != 'user_confirmed':
            raise ValueError('Nur explizit vom Nutzer bestätigte Screenshots sind Trainingsdaten.')
        payload = self._normal_image(image)
        digest = hashlib.sha256(payload).hexdigest()
        path = self.images / f'{digest}.png'
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self._connect() as con:
                existing = con.execute('SELECT icon_id FROM samples WHERE hash=?', (digest,)).fetchone()
                if existing:
                    if existing[0] != icon_id:
                        raise ValueError('Dieses Bild ist bereits einer anderen Kategorie zugeordnet. '
                                         'Bitte zuerst den bestehenden Datensatz prüfen.')
                    if confirmed:
                        con.execute('UPDATE samples SET origin=?,confirmed=1,created_utc=? WHERE hash=?',
                                    ('user_confirmed',now,digest))
                        return True
                    return False
                tmp = self.images / f'.{digest}.tmp'
                tmp.write_bytes(payload)
                os.replace(tmp, path)
                try:
                    con.execute('INSERT INTO samples VALUES(?,?,?,?,?,?)',
                                (digest, icon_id, path.name, origin, int(confirmed), now))
                except Exception:
                    path.unlink(missing_ok=True)
                    raise
        return True

    def add_public_sample(self, icon_id: str, path: Path, origin='poedb'):
        if icon_id not in REWARD_ICONS:
            return False
        try:
            with Image.open(path) as img:
                return self.add_sample(icon_id, img, origin=origin, confirmed=False)
        except (OSError, ValueError, sqlite3.Error):
            return False

    def import_existing_sources(self):
        """Import v1.2 examples and the CDN cache; no API/network needed."""
        added = 0
        for p in sorted(BUNDLED.glob('*.png')):
            cat = p.stem.split('_')[0]
            added += bool(self.add_public_sample(cat, p, origin='bundled_example'))
        for p in sorted(OLD_CACHE.glob('*.webp')):
            added += bool(self.add_public_sample(p.stem, p, origin='poedb_cache'))
        return added

    def remove_user_samples(self, icon_id: str) -> int:
        """Only delete samples explicitly trained by this user, never PoEDB art."""
        if icon_id not in REWARD_ICONS:
            raise ValueError('Unbekannte Icon-Kategorie.')
        with self._lock:
            with self._connect() as con:
                rows=con.execute('SELECT file_name FROM samples WHERE icon_id=? AND origin=?',
                                 (icon_id,'user_confirmed')).fetchall()
                con.execute('DELETE FROM samples WHERE icon_id=? AND origin=?',
                            (icon_id,'user_confirmed'))
            for (file_name,) in rows:
                if Path(file_name).name==file_name:
                    (self.images/file_name).unlink(missing_ok=True)
        return len(rows)

    def list_categories(self) -> list[IconCategory]:
        with self._connect() as con:
            rows = con.execute('''SELECT c.icon_id,c.label_de,COUNT(s.hash),
                COALESCE(SUM(CASE WHEN s.confirmed=1 THEN 1 ELSE 0 END),0)
                FROM categories c LEFT JOIN samples s ON c.icon_id=s.icon_id
                GROUP BY c.icon_id,c.label_de ORDER BY c.label_de COLLATE NOCASE''').fetchall()
        return [IconCategory(*r) for r in rows]

    def reference_files(self):
        """Read-only index, skip missing/invalid filenames."""
        with self._connect() as con:
            rows = con.execute('SELECT icon_id,file_name,origin FROM samples').fetchall()
        for cat, filename, source in rows:
            if not filename.endswith('.png') or Path(filename).name != filename:
                continue
            file = self.images / filename
            if file.is_file():
                yield cat, file, source

    def export_backup(self, destination: Path):
        """Portable ZIP backup includes category metadata and verified image samples."""
        import zipfile
        destination = Path(destination)
        with self._lock:
            with self._connect() as con:
                rows = [(cat, src, int(confirmed), fname) for cat, src, confirmed, fname in
                        con.execute('SELECT icon_id,origin,confirmed,file_name FROM samples').fetchall()]
            manifest = {'format': 'poe-fate-icon-library-v1', 'categories': list(REWARD_ICONS),
                        'samples': [{'id': cat,'origin': src,'confirmed': confirmed,'file': fname}
                                    for cat,src,confirmed,fname in rows]}
            with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as out:
                out.writestr('icon_library.json',json.dumps(manifest,ensure_ascii=False,indent=2))
                for _,_,_, fname in rows:
                    if Path(fname).name == fname and (self.images/fname).is_file():
                        out.write(self.images/fname, 'samples/'+fname)
        return destination

    def import_backup(self, archive: Path):
        """Validate all paths/canonical categories; never execute archive content."""
        import zipfile
        added = 0
        with zipfile.ZipFile(archive) as zf:
            if zf.getinfo('icon_library.json').file_size>200_000:
                raise ValueError('Bibliothek-Metadaten zu groß.')
            manifest=json.loads(zf.read('icon_library.json'))
            if manifest.get('format') != 'poe-fate-icon-library-v1':
                raise ValueError('Keine unterstützte Icon-Bibliothek.')
            samples=manifest.get('samples',[])
            if not isinstance(samples,list) or len(samples)>2000:
                raise ValueError('Ungültige Anzahl Icons.')
            for sample in samples:
                cat=sample.get('id'); fname=sample.get('file','')
                if cat not in REWARD_ICONS or not isinstance(fname,str) or not fname.endswith('.png'):
                    raise ValueError('Ungültiger Datensatz.')
                if Path(fname).name != fname or len(fname)>100:
                    raise ValueError('Ungültiger Dateiname.')
                info=zf.getinfo('samples/'+fname)
                if info.file_size>1_000_000:
                    raise ValueError('Trainingsbild ist zu groß.')
                with Image.open(BytesIO(zf.read(info))) as image:
                    # Imported samples keep a non-verified provenance until
                    # actively confirmed on this device.
                    added += bool(self.add_sample(cat, image, origin='imported_backup', confirmed=False))
        return added


def reference_files():
    """Get a durable DB view without any app/UI dependency."""
    try:
        yield from IconDatabase().reference_files()
    except (OSError, sqlite3.Error):
        return
