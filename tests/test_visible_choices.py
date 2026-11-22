"""Regression cases from two live user bugs: wrong loot and nonexistent Fate."""
import unittest
import json
import sys
import types
from unittest.mock import MagicMock, patch
from app import normalize_analysis_result, apply_visual_verification, analyse_image, SYSTEM_RULES, CARD_READER_RULES
from selection_validation import verify_card_names, position_label
from card_marker import validated_card_box
from overlay import overlay_summary


def model_result(names, best):
    return normalize_analysis_result({
        "screen_type": "selection", "best_number": best, "selected_numbers": [best],
        "confidence": "hoch", "recommendation": "Nimm unbedingt Crowkeeper!",
        "cards": [
            {"number": i, "name": n, "reward_tooltip": "", "reward_icon": "unknown",
             "box": [60+(i-1)*220, 260, 215+(i-1)*220, 650], "danger": "niedrig"}
            for i, n in enumerate(names, 1)
        ],
    })


class IndependentVisionSafetyTests(unittest.TestCase):
    def test_nonexistent_crowkeeper_is_never_marked_or_stored(self):
        # First model hallucinates a Fate absent from actual screenshot.
        bad = model_result(["Crowkeeper", "Wildfire", "Murderous"], 1)
        result = apply_visual_verification(bad, {
            "screen_type": "selection", "visible_names": ["Dryad", "Wildfire", "Murderous"],
            "confidence": "hoch"})
        self.assertEqual(result["best_number"], 0)
        self.assertEqual(result["selected_numbers"], [])
        self.assertEqual(result["visual_verification"], "mismatch")
        self.assertNotIn("Crowkeeper", result["recommendation"])
        self.assertNotIn("Crowkeeper", [c["name"] for c in result["cards"]])
        self.assertIsNone(validated_card_box(result))
        self.assertFalse(overlay_summary(result)["can_save"])
        self.assertIn("nicht sicher", overlay_summary(result)["title"])

    def test_same_hallucination_in_duplicate_prior_is_not_allowed(self):
        bad = model_result(["Conjurer", "Crowkeeper"], 2)
        result = apply_visual_verification(bad, {
            "screen_type": "selection", "visible_names": ["Conjurer", "Doomsayer"], "confidence": "hoch"})
        self.assertEqual(result["best_number"], 0)
        self.assertIsNone(validated_card_box(result))

    def test_correct_card_names_pass_and_marker_allowed(self):
        original = model_result(["Conjurer", "Murderous", "Doomsayer"], 3)
        result = apply_visual_verification(original, {
            "screen_type": "selection", "visible_names": ["Conjurer", "Murderous", "Doomsayer"],
            "confidence": "hoch"})
        self.assertEqual(result["visual_verification"], "confirmed")
        self.assertEqual(result["best_number"], 3)
        self.assertEqual(result["selected_numbers"], [3])
        self.assertIsNotNone(validated_card_box(result))
        self.assertTrue(overlay_summary(result)["can_save"])

    def test_incomplete_verification_fails_closed(self):
        result = model_result(["Conjurer", "Wildfire"], 2)
        checked = apply_visual_verification(result, {
            "screen_type": "selection", "visible_names": ["Conjurer"], "confidence": "hoch"})
        self.assertEqual(checked["best_number"], 0)

    def test_low_confidence_fails_closed(self):
        result = model_result(["Conjurer", "Wildfire"], 2)
        checked = apply_visual_verification(result, {
            "screen_type": "selection", "visible_names": ["Conjurer", "Wildfire"], "confidence": "niedrig"})
        self.assertEqual(checked["best_number"], 0)

    def test_boss_altar_never_becomes_new_selection(self):
        source = normalize_analysis_result({"screen_type": "invocation", "best_number": 1, "cards": [
            {"number": 1, "name": "Crowkeeper", "reward_icon": "unknown"}]})
        checked = apply_visual_verification(source, {
            "screen_type": "selection", "visible_names": ["Crowkeeper"], "confidence": "hoch"})
        self.assertEqual(checked["best_number"], 0)

    def test_two_card_position_is_right_not_middle(self):
        self.assertEqual(position_label(2,2),"RECHTS")
        self.assertEqual(position_label(2,3),"MITTE")

    def test_one_api_scan_new_contract(self):
        from test_top_row_isolation import fake_game, mock_card_result
        from PIL import Image
        response_client=MagicMock()
        response_client.responses.create.return_value=MagicMock(output_text=json.dumps(mock_card_result()))
        with patch.dict(sys.modules,{"openai":types.SimpleNamespace(OpenAI=lambda **kw:response_client)}):
            answer=analyse_image(fake_game(),"key","Kampagne","Loot",[])
        self.assertEqual(response_client.responses.create.call_count,1)
        self.assertIn(answer["best_number"],(1,2))
        self.assertEqual(answer["visual_verification"],"geometry_confirmed")
        self.assertEqual(len(answer['cards']),2)
        self.assertTrue(all(c['loot_evidence']=='unknown' for c in answer['cards']))

    def test_uncertain_picture_fails_closed(self):
        from PIL import Image
        response_client=MagicMock()
        response_client.responses.create.return_value=MagicMock(output_text=json.dumps({
            'screen_type':'selection','confidence':'hoch','cards':[
                {'number':1,'name':'Conjurer','reward_icon':'unknown'}]}))
        with patch.dict(sys.modules,{"openai":types.SimpleNamespace(OpenAI=lambda **kw:response_client)}):
            answer=analyse_image(Image.new('RGB',(900,700),'black'),"key","Kampagne","Sicher",[])
        self.assertEqual(answer['best_number'],0)
        self.assertIsNone(validated_card_box(answer))

    def test_catalog_has_known_fates_not_reward_by_name(self):
        from app import VISION_RULES
        self.assertIn('Fate-Namen sind KEINE Loot-Information', VISION_RULES)
        self.assertIn('Currency=',VISION_RULES)


if __name__ == '__main__':
    unittest.main()
