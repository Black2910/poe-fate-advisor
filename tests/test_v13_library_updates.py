from __future__ import annotations
import hashlib
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile

from PIL import Image
from icon_database import IconDatabase
from app_updates import (VERSION, inspect_package, stage_package, is_newer,
                         verify_sha256)
from updater_worker import install_from_stage


def zip_release(path, *, version='1.4.0', prefix='PoE_Fate_Advisor_v1.4/'):
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as out:
        for name,contents in {
            'app.py':'print("testing")\n',
            'start_windows.bat':'@echo off\n',
            'version.json':json.dumps({'app_id':'poe-fate-advisor','version':version}),
            'README.md':'Updated release',
            'assets/verified_icons/Wand_01.png':b'illustration',
        }.items():out.writestr(prefix+name,contents)


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name)
        self.db=IconDatabase(self.home/'library')

    def test_45_categories_and_empty_labels(self):
        cats=self.db.list_categories()
        self.assertGreaterEqual(len(cats),45)
        self.assertTrue(any(c.icon_id=='Wand' for c in cats))
        self.assertTrue(all(c.samples==0 for c in cats))

    def test_learning_is_persistent_and_needs_known_category(self):
        art=Image.new('RGB',(64,64),(160,70,20))
        self.assertTrue(self.db.add_sample('Gold',art))
        self.assertTrue(self.db.add_sample('Gold',art))  # erneute ausdrückliche Bestätigung
        self.assertEqual([c for c in IconDatabase(self.home/'library').list_categories()
                          if c.icon_id=='Gold'][0].user_confirmed,1)
        with self.assertRaises(ValueError):self.db.add_sample('Wand',art)
        with self.assertRaises(ValueError):self.db.add_sample('NotFate',art)

    def test_backup_export_and_import(self):
        self.db.add_sample('Currency', Image.new('RGB',(60,60),(60,70,120)))
        path=self.home/'saved_library.zip'
        self.db.export_backup(path)
        imported=IconDatabase(self.home/'restored')
        self.assertEqual(imported.import_backup(path),1)
        self.assertEqual([x for x in imported.list_categories() if x.icon_id=='Currency'][0].samples,1)
        self.assertEqual([x for x in imported.list_categories() if x.icon_id=='Currency'][0].user_confirmed,0)

    def test_bad_library_category_rejected(self):
        bad=self.home/'bad.zip'
        with zipfile.ZipFile(bad,'w') as out:
            out.writestr('icon_library.json', json.dumps({'format':'poe-fate-icon-library-v1',
                'samples':[{'id':'Foo','file':'x.png'}]}))
            out.writestr('samples/x.png','123')
        with self.assertRaises(ValueError):self.db.import_backup(bad)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name)

    def test_default_release_repository(self):
        from app_updates import DEFAULT_GITHUB_REPO
        self.assertEqual(DEFAULT_GITHUB_REPO, 'Black2910/poe-fate-advisor')

    def test_version_check(self):
        self.assertTrue(is_newer('v1.4.0'))
        self.assertFalse(is_newer('1.2.9'))
        self.assertFalse(is_newer(VERSION))

    def test_valid_zip_version_and_stage(self):
        z=self.dir/'good.zip';zip_release(z)
        res=inspect_package(z)
        self.assertEqual(res['version'],'1.4.0')
        stage=self.dir/'stage';stage_package(z,stage)
        self.assertTrue((stage/'app.py').is_file())
        self.assertTrue((stage/'assets/verified_icons/Wand_01.png').is_file())

    def test_old_version_denied(self):
        z=self.dir/'old.zip';zip_release(z,version='1.2.0')
        with self.assertRaises(ValueError):inspect_package(z)

    def test_traversal_and_symlink_denied(self):
        z=self.dir/'traversal.zip';zip_release(z,prefix='')
        with zipfile.ZipFile(z,'a') as out:out.writestr('../escape.py','evil')
        with self.assertRaises(ValueError):inspect_package(z)
        symlink=self.dir/'symlink.zip';zip_release(symlink,prefix='')
        with zipfile.ZipFile(symlink,'a') as out:
            info=zipfile.ZipInfo('assets/danger')
            info.create_system=3
            info.external_attr=0o120777<<16
            out.writestr(info,'/etc/passwd')
        with self.assertRaises(ValueError):inspect_package(symlink)

    def test_sha256_verification(self):
        package=self.dir/'good.zip';zip_release(package)
        h=hashlib.sha256(package.read_bytes()).hexdigest()
        self.assertTrue(verify_sha256(package,'sha256:'+h))
        with self.assertRaises(ValueError):verify_sha256(package,'0'*64)

    def test_install_preserves_users_files_and_rollback(self):
        install=self.dir/'installed';install.mkdir()
        (install/'app.py').write_text('old program')
        (install/'.poe_fate_advisor_config.json').write_text('keep personal')
        stage=self.dir/'stage';stage.mkdir()
        (stage/'app.py').write_text('new program')
        (stage/'version.json').write_text('new version')
        backup=self.dir/'backup'
        install_from_stage(stage,install,backup)
        self.assertEqual((install/'app.py').read_text(),'new program')
        self.assertEqual((backup/'app.py').read_text(),'old program')
        self.assertEqual((install/'.poe_fate_advisor_config.json').read_text(),'keep personal')

if __name__=='__main__':unittest.main()
