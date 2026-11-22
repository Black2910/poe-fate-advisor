import unittest
from fate_engine import Fate, rank_fates, score_fate

class TestEngine(unittest.TestCase):
    def test_doomsayer_safer_than_houndmaster(self):
        names = rank_fates([Fate("Houndmaster"), Fate("Doomsayer")], goal="Sicher")
        self.assertEqual(names[0].name, "Doomsayer")

    def test_double_fate_synergy(self):
        single = score_fate(Fate("Dryad", "currency"), [])
        duplicate = score_fate(Fate("Dryad", "currency"), [Fate("Dryad", "Viscera")])
        self.assertGreater(duplicate.score, single.score)

    def test_generic_rare_armour_not_helmet(self):
        rating = score_fate(Fate("Crowkeeper", "seltene Rüstung"))
        self.assertIn("Seltene Rüstung (Slot offen)", rating.summary)
        self.assertNotIn("Seltener Helm", rating.summary)

    def test_duplicates_have_warning(self):
        rating = score_fate(Fate("Crowkeeper", "seltene Rüstung"),
                            [Fate("Crowkeeper", "seltene Rüstung")], goal="Sicher")
        self.assertIn("stärkerer Boss", rating.summary)

    def test_rewards_matter(self):
        data = rank_fates([Fate("Dryad", "Gold"), Fate("Houndmaster", "Exceptional Gem")], phase="Frühe Maps", goal="Loot")
        self.assertEqual(data[0].name, "Houndmaster")

if __name__ == "__main__":
    unittest.main()
