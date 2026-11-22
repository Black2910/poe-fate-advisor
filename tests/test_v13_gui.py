import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import tkinter as tk

from PIL import Image
from app import AdvisorApp

class GUINewTabTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=tk.Tk()
        self.root.withdraw()
        from icon_database import IconDatabase
        testdb=IconDatabase(Path(self.tmp.name)/'library')
        with patch('app.AdvisorApp._install_hotkey'),patch('app.TrayController.start'),patch('app.start_icon_prefetch'),patch('app.IconDatabase',return_value=testdb),patch('app.AdvisorApp._load_config'):
            self.app=AdvisorApp(self.root)

    def tearDown(self):
        if self.root.winfo_exists():self.app.close()

    def test_icon_learning_current_screenshot(self):
        base=Path(__file__).resolve().parents[1]/'assets'/'verified_icons'
        self.app.last_icon_crops=[Image.open(base/'RareArmour_01.png').convert('RGB'),
                                  Image.open(base/'Currency_01.png').convert('RGB'),
                                  Image.open(base/'Axe_01.png').convert('RGB')]
        self.assertEqual(len(self.app.last_icon_crops),3)
        self.app.learn_card.set('2')
        self.app.show_training_crop()
        self.app.learn_category.set('Currency – zusätzliche Währungsgegenstände')
        with patch('app.messagebox.askyesno',return_value=True):
            self.app.confirm_training_icon()
        self.assertTrue('Währungsgegenstände' in self.app.learn_status.get() or 'gespeichert' in self.app.learn_status.get())

    def test_github_setting_is_present(self):
        self.assertEqual(self.app.update_status.get(),'Bereit')
        self.app.github_repo.set('example/release-repo')
        self.assertEqual(self.app.github_repo.get(),'example/release-repo')

if __name__=='__main__':unittest.main()
