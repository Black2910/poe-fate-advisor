import unittest
from overlay import overlay_summary, short_text


class OverlayLogicTests(unittest.TestCase):
    def test_selection_position_and_reward(self):
        summary = overlay_summary({
            "screen_type": "selection", "best_number": 3, "confidence": "hoch",
            "cards": [{"number": 1, "name": "Conjurer"}, {"number": 2, "name": "Wildfire"}, {"number": 3, "name": "Crowkeeper", "rewards": "seltene Rüstung", "danger": "mittel"}],
            "recommendation": "Nimm die rechte Karte."})
        self.assertIn("RECHTS", summary["title"])
        self.assertIn("Crowkeeper", summary["title"])
        self.assertIn("seltene Rüstung", summary["sub"])
        self.assertNotIn("Helm", summary["sub"])
        self.assertTrue(summary["can_save"])

    def test_invocation_cannot_be_saved(self):
        result = overlay_summary({"screen_type": "invocation", "invocation_state": "merged",
                                  "recommendation": "Gleiche Karten verschmolzen."})
        self.assertFalse(result["can_save"])
        self.assertIn("verschmolzen", result["sub"])

    def test_no_card_no_save(self):
        result = overlay_summary({"screen_type": "selection", "best_number": 3,
                                  "cards": [], "recommendation": "Unklar"})
        self.assertFalse(result["can_save"])

    def test_low_confidence_has_warning(self):
        result = overlay_summary({"screen_type": "selection", "best_number": 1,
                                  "cards": [{"number": 1, "name": "Murderous"}], "confidence": "niedrig"})
        self.assertIn("Geringe", result["sub"])

    def test_length_limits(self):
        self.assertTrue(len(short_text("Z"*900, 100)) <= 100)


if __name__ == "__main__":
    unittest.main()
