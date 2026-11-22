"""Regression: v1.3.1 must accept this release without any manual file copying."""
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from app_updates import APP_FILES, inspect_package
from reward_catalog import variants_for, normalise_icon_id

ROOT = Path(__file__).resolve().parents[1]

# Exact top-level allowlist shipped in the v1.3.1 updater. That updater rejected
# reward_variants.py even though it was part of a legitimate later release.
V131_ALLOWED = {
    'app.py', 'app_updates.py', 'updater_worker.py', 'icon_database.py',
    'icon_reference.py', 'fate_engine.py', 'reward_catalog.py',
    'icon_ranking.py', 'image_regions.py', 'vision_sheet.py',
    'selection_validation.py', 'card_marker.py', 'overlay.py',
    'tray.py', 'requirements.txt', 'start_windows.bat',
    'PoE Fate Advisor - leiser Start.vbs', 'README.md', 'version.json',
    'install_windows.py', 'Einmal_installieren.bat',
}

class LegacyCompatibilityTests(unittest.TestCase):
    def test_new_release_contains_only_files_under_v131_allowlist(self):
        from scripts.build_release import build
        package = build()
        with zipfile.ZipFile(package) as z:
            names = [n for n in z.namelist() if not n.endswith('/')]
            self.assertTrue(names)
            self.assertNotIn('reward_variants.py', names)
            for n in names:
                self.assertTrue(n in V131_ALLOWED or n.startswith('assets/'), n)
            self.assertEqual(json.loads(z.read('version.json'))['version'], '1.3.3')
        self.assertEqual(inspect_package(package, allow_equal=True)['version'], '1.3.3')
        self.assertEqual(normalise_icon_id('RareShields'), 'Shield')
        self.assertEqual(len(variants_for('RareArmour')), 3)
        self.assertEqual(len(variants_for('RareShields')), 6)

    def test_future_top_level_python_modules_are_accepted_but_other_files_rejected(self):
        def make_package(path, addition):
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('version.json', json.dumps({'app_id':'poe-fate-advisor','version':'1.4.0'}))
                z.writestr('app.py', 'print("ok")')
                z.writestr('start_windows.bat', '@echo off')
                z.writestr(addition, 'example')

        with tempfile.TemporaryDirectory() as td:
            d=Path(td)
            ok=d/'ok.zip';make_package(ok, 'new_helper_module.py')
            self.assertIn('new_helper_module.py', inspect_package(ok)['members'])
            for filename in ('malware.exe', 'dangerous.ps1', 'new_helper_module.py/child.py'):
                bad=d/(filename.split('.')[0]+'.zip');make_package(bad,filename)
                with self.subTest(filename=filename), self.assertRaises(ValueError):
                    inspect_package(bad)

if __name__ == '__main__':
    unittest.main()
