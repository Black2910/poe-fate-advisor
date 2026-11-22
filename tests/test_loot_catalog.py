import unittest
from app import normalize_analysis_result, SYSTEM_RULES
from reward_catalog import REWARD_ICONS, classify_tooltip, icon_label
from fate_engine import Fate, score_fate


class LootTests(unittest.TestCase):
    def test_real_user_screenshot_currency_override_wrong_armour(self):
        screenshot_result = {
            "screen_type": "selection", "best_number": 2, "confidence": "hoch",
            "recommendation": "Mitte Crowkeeper wegen seltener Rüstung wählen.",
            "cards": [
                {"number": 1, "name": "Conjurer", "rewards": "seltene Rüstung", "reward_tooltip": "", "reward_icon": "unknown", "danger": "hoch"},
                {"number": 2, "name": "Crowkeeper", "rewards": "seltene Rüstung",
                 "reward_tooltip": "Empowered Monster will drop additional Currency Items",
                 "reward_icon": "Currency", "reward_icon_confidence": "hoch", "danger": "niedrig", "notes": "erzeugt Projektile"},
            ]
        }
        actual = normalize_analysis_result(screenshot_result)
        card = actual["cards"][1]
        self.assertEqual(card["rewards"], "zusätzliche Währungsgegenstände")
        self.assertEqual(card["loot_evidence"], "tooltip")
        self.assertNotIn("Rüstung", actual["recommendation"])
        self.assertIn("Währungsgegenstände", actual["cards"][1]["rewards"])
        self.assertEqual(actual["best_number"],2)

    def test_never_assign_crowkeeper_fixed_loot(self):
        result = normalize_analysis_result({
            "screen_type": "selection", "best_number": 1,
            "cards": [{"number": 1, "name": "Crowkeeper", "rewards": "seltener Helm",
                       "reward_tooltip": "", "reward_icon": "unknown", "danger": "mittel"}]})
        self.assertIn("unbekannt", result["cards"][0]["rewards"])
        self.assertNotIn("seltener Helm", result["cards"][0]["rewards"])
        self.assertIn("KEINE", SYSTEM_RULES)

    def test_icon_only_is_labelled_uncertain(self):
        result = normalize_analysis_result({
            "screen_type": "selection", "best_number": 2,
            "cards": [{"number": 2, "name": "Crowkeeper", "rewards": "seltene Rüstung",
                       "reward_tooltip": "", "reward_icon": "Currency", "reward_icon_confidence": "hoch", "danger": "niedrig"}]})
        self.assertEqual(result["cards"][0]["loot_evidence"], "icon")
        self.assertIn("zusätzliche Währungsgegenstände", result["cards"][0]["rewards"])
        self.assertNotIn("Rüstung", result["cards"][0]["rewards"])

    def test_tiny_icon_unreadable_must_be_unknown(self):
        result = normalize_analysis_result({
            "screen_type": "selection", "best_number": 3,
            "cards": [{"number": 3, "name": "Wildfire", "rewards": "Mirror Shard",
                       "reward_tooltip": "", "reward_icon": "unknown", "danger": "mittel"}]})
        self.assertNotIn("Mirror Shard", result["cards"][0]["rewards"])
        self.assertIn("unbekannt", result["cards"][0]["rewards"])

    def test_catalog_coverage(self):
        self.assertGreaterEqual(len(REWARD_ICONS), 40)
        for k in ("Currency", "RareArmour", "RareRanged", "Gems", "ExceptionalGems",
                  "Threads", "Divination", "Gold", "Maps", "RareJewellery", "Bow", "Quiver"):
            self.assertIsNotNone(icon_label(k))

    def test_patch_gem_and_guaranteed_modifiers(self):
        samples = [
            ("Empowered Monster will drop additional Rare Boots Boots dropped by Empowered Monster will have a Speed modifier", "Tempo-Mod"),
            ("Empowered Monster will drop additional Rare Sceptres Sceptres dropped by Empowered Monster will have no Physical modifiers", "ohne physisch-Mods"),
            ("Empowered Monster will drop an additional Exceptional Gem", "außergewöhnliches Gem"),
            ("Empowered Monster has a chance to drop additional Bows", "Chance auf"),
            ("Empowered Monster will drop an additional Divine Orb", "Divine Orb"),
            ("Empowered Monster will drop additional Armour items with Dexterity requirements", "Rüstungsgegenstände"),
            ("Empowered Monster will drop additional Stacked Decks", "Stacked Decks"),
            ("Empowered Monster has greatly increased Item Rarity", "Seltenheit"),
        ]
        for line, expected in samples:
            with self.subTest(line=line):
                self.assertIn(expected, classify_tooltip(line))

    def test_empowered_word_does_not_mean_empower_gem(self):
        score = score_fate(Fate("Crowkeeper", "Empowered Monster will drop additional Currency Items"))
        self.assertNotIn("Exceptional Gem", score.summary)
        self.assertIn("Currency", score.summary)

    def test_invoke_never_selects_new_fate(self):
        result = normalize_analysis_result({"screen_type": "invocation", "best_number": 1,
            "cards": [{"number": 1, "name": "Crowkeeper", "reward_tooltip": "Empowered Monster will drop additional Currency Items"}]})
        self.assertEqual(result["best_number"], 0)
        self.assertEqual(result["selected_numbers"], [])

if __name__ == "__main__":
    unittest.main()
