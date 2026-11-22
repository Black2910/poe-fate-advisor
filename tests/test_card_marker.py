"""Safe positioning checks: the frame must never guess a screen location."""
import unittest

from card_marker import validated_card_box, screen_card_rect


class MarkerGeometryTests(unittest.TestCase):
    def setUp(self):
        self.result = {
            "screen_type": "selection", "confidence": "hoch", "best_number": 3,
            "cards": [
                {"number": 1, "name": "Murderous", "box": [100, 250, 240, 650]},
                {"number": 2, "name": "Wildfire", "box": [400, 250, 540, 650]},
                {"number": 3, "name": "Crowkeeper", "box": [700, 250, 840, 650]},
            ],
        }

    def test_live_capture_maps_card_to_real_screen(self):
        self.assertEqual(screen_card_rect(self.result, (200, 100, 1000, 800)), (900, 300, 140, 320))

    def test_negative_monitor_origin(self):
        self.assertEqual(screen_card_rect(self.result, (-1600, -200, 1000, 800)), (-900, 0, 140, 320))

    def test_imported_image_has_no_live_position(self):
        self.assertIsNone(screen_card_rect(self.result, None))

    def test_invocation_never_looks_like_a_choice(self):
        self.result["screen_type"] = "invocation"
        self.assertIsNone(validated_card_box(self.result))

    def test_uncertain_scan_does_not_get_a_frame(self):
        self.result["confidence"] = "niedrig"
        self.assertIsNone(validated_card_box(self.result))

    def test_missing_wrong_and_out_of_range_boxes_are_rejected(self):
        for box in (None, [], [0, 0, 20, 1000], [0, 0, 900, 1000],
                    [0, 0, -2, 200], [0, 0, 1001, 200], [0, 0, float("nan"), 200],
                    [True, 0, 500, 500]):
            with self.subTest(box=box):
                self.result["cards"][2]["box"] = box
                self.assertIsNone(validated_card_box(self.result))

    def test_best_fate_only_not_neighbour(self):
        self.assertEqual(validated_card_box(self.result), [700., 250., 840., 650.])
        self.result["best_number"] = 1
        self.assertEqual(validated_card_box(self.result), [100., 250., 240., 650.])


if __name__ == "__main__":
    unittest.main()
