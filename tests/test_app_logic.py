import unittest
from pathlib import Path
import ast
from app import normalize_analysis_result

class TestAppGuidance(unittest.TestCase):
    def test_invocation_does_not_create_new_fate(self):
        data = normalize_analysis_result({"screen_type": "invocation", "invocation_state": "merged",
                "best_number": 1, "selected_numbers": [1],
                "cards": [{"number": 1, "name": "Crowkeeper", "rewards": "seltene Rüstung"}]})
        self.assertEqual(data["best_number"], 0)
        self.assertEqual(data["selected_numbers"], [])

    def test_coven_selection_is_single_card(self):
        data = normalize_analysis_result({"screen_type": "selection", "best_number": 2,
                "selected_numbers": [1, 2], "cards": [{"number": 2, "name": "Dryad"}]})
        self.assertEqual(data["selected_numbers"], [2])

    def test_prompt_distinguishes_invocation_states(self):
        source = Path(__file__).resolve().parents[1].joinpath("app.py").read_text(encoding="utf-8")
        self.assertIn("invocation_state", source)
        self.assertIn("2/2 BERICHTET den Kartenbestand", source)
        self.assertIn("Fate-Name=Loot-Regeln sind FALSCH", source)
        ast.parse(source)

if __name__ == "__main__":
    unittest.main()
