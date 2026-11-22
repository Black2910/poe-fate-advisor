"""v1.3.2: one artwork can have multiple text outcomes; never infer one from a crop."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import tkinter as tk
from PIL import Image
from reward_variants import normalise_icon_id, variants_for, get_variant, match_tooltip, VARIANTS
from icon_database import IconDatabase
from app import AdvisorApp

ASSETS=Path(__file__).resolve().parents[1]/'assets'/'verified_icons'


class VariantCatalogueTests(unittest.TestCase):
    def test_rare_shields_is_existing_shield_artwork_with_six_buff_choices(self):
        self.assertEqual(normalise_icon_id('RareShields'),'Shield')
        ids={v.variant_id for v in variants_for('RareShields')}
        self.assertEqual(ids,{
            'Shield.GuaranteedLife','Shield.GuaranteedDefence','Shield.GuaranteedResistance',
            'Shield.ChanceLife','Shield.ChanceDefence','Shield.ChanceResistance'})

    def test_rare_armour_has_three_distinct_requirements_for_same_icon(self):
        vs=variants_for('RareArmour')
        self.assertEqual({v.variant_id for v in vs},
            {'RareArmour.Strength','RareArmour.Dexterity','RareArmour.Intelligence'})
        self.assertGreaterEqual(len(VARIANTS),140)

    def test_specific_tooltip_matches_but_icon_alone_does_not(self):
        self.assertIsNone(match_tooltip('','RareArmour'))
        strength=match_tooltip('Empowered Monster will drop additional Armour items with Strength requirements','RareArmour')
        self.assertIsNotNone(strength)
        self.assertEqual(strength.variant_id,'RareArmour.Strength')
        shield=match_tooltip('Empowered Monster will drop additional Rare Shields Shields dropped by Empowered Monster will have a Defence modifier','RareShields')
        self.assertEqual(shield.variant_id,'Shield.GuaranteedDefence')
        self.assertIsNone(match_tooltip('Empowered Monster will drop additional Rare Armour','RareShields'))


class PersistVariantTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.db=IconDatabase(self.root/'persist')

    def test_icon_and_variant_are_separate_and_backward_compatible(self):
        img=Image.open(ASSETS/'RareArmour_01.png').convert('RGB')
        self.assertTrue(self.db.add_sample('RareArmour',img))
        self.assertTrue(self.db.record_variant('RareArmour',img,'RareArmour.Strength'))
        self.assertFalse(self.db.record_variant('RareArmour',img,'RareArmour.Strength'))
        # Same visual image can correspond to another observed textual outcome:
        self.assertTrue(self.db.record_variant('RareArmour',img,'RareArmour.Dexterity'))
        self.assertEqual(len(self.db.variant_observations('RareArmour')),2)
        self.assertEqual(IconDatabase(self.root/'persist').list_categories()[0].__class__.__name__,'IconCategory')
        with self.assertRaises(ValueError):
            self.db.record_variant('RareArmour',img,'Shield.GuaranteedLife')

    def test_variant_round_trip_backup_and_old_backup(self):
        img=Image.open(ASSETS/'RareArmour_01.png').convert('RGB')
        self.db.add_sample('RareArmour',img)
        self.db.record_variant('RareArmour',img,'RareArmour.Strength','Strength requirements')
        zip_file=self.root/'saved.zip'
        self.db.export_backup(zip_file)
        restored=IconDatabase(self.root/'restored')
        restored.import_backup(zip_file)
        self.assertEqual(restored.variant_observations('RareArmour')[0][0],'RareArmour.Strength')
        self.assertEqual(restored.variant_observations('RareArmour')[0][2],'imported_backup')
        # Legacy ZIP archives lacking the observations section must still import.
        import json,zipfile
        old=self.root/'old.zip'
        with zipfile.ZipFile(zip_file) as src, zipfile.ZipFile(old,'w') as dst:
            for name in src.namelist():
                data=src.read(name)
                if name=='icon_library.json':
                    payload=json.loads(data);payload.pop('observations',None)
                    data=json.dumps(payload).encode()
                dst.writestr(name,data)
        fresh=IconDatabase(self.root/'oldrestore')
        fresh.import_backup(old)
        self.assertEqual(fresh.variant_observations(),[])


class VariantUITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=tk.Tk();self.root.withdraw()
        self.db=IconDatabase(Path(self.temp.name)/'db')
        with patch('app.AdvisorApp._install_hotkey'),patch('app.TrayController.start'),patch('app.start_icon_prefetch'),patch('app.IconDatabase',return_value=self.db),patch('app.AdvisorApp._load_config'):
            self.app=AdvisorApp(self.root)

    def tearDown(self):
        if self.root.winfo_exists():self.app.close()

    def test_shield_option_and_variant_selection(self):
        self.assertTrue(any(v.startswith('RareShields – ') for v in self.app.learn_cat_select['values']))
        self.app.learn_category.set(next(v for v in self.app.learn_cat_select['values'] if v.startswith('RareShields – ')))
        self.assertIn('Shield.GuaranteedDefence',str(self.app.learn_variant_select['values']))
        self.app.learn_category.set('RareArmour – Rüstungsgegenstände (genauer Slot unbekannt)')
        self.assertIn('RareArmour.Strength',str(self.app.learn_variant_select['values']))
        self.app.learn_tooltip.set('Empowered Monster will drop additional Armour items with Strength requirements')
        self.app.suggest_variant_from_tooltip()
        self.assertTrue(self.app.learn_variant.get().startswith('RareArmour.Strength'))
        self.app.last_icon_crops=[Image.open(ASSETS/'RareArmour_01.png').convert('RGB')]
        self.app.learn_card.set('1')
        with patch('app.messagebox.askyesno',return_value=True):
            self.app.confirm_training_icon()
        self.assertEqual(self.db.variant_observations('RareArmour')[0][0],'RareArmour.Strength')
        self.assertIn('NICHT per Icon',self.app.learn_status.get())


if __name__=='__main__':unittest.main()
