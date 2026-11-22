"""UI smoke and single-capture tests (run under Xvfb on Linux)."""
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
import unittest
from unittest.mock import MagicMock, patch

from app import AdvisorApp


@unittest.skipUnless(sys.platform == "win32" or os.environ.get("DISPLAY"), "Tk GUI requires a display")
class GUIOverlayTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.config_patch = patch("app.CONFIG_FILE", Path(self.home.name) / "app.json")
        self.config_patch.start()
        self.root = tk.Tk()
        self.app = AdvisorApp(self.root)
        self.root.update()

    def tearDown(self):
        if self.root.winfo_exists():
            self.app.close()
        self.config_patch.stop()
        self.home.cleanup()

    def test_result_stays_in_overlay_when_main_hidden(self):
        self.app.enter_game_mode()
        self.root.update()
        self.assertEqual(self.root.state(), "withdrawn")
        self.app.show_analysis({"screen_type": "selection", "best_number": 1,
                                "selected_numbers": [1],
                                "cards": [{"number": 1, "name": "Crowkeeper", "rewards": "seltene Rüstung"}],
                                "recommendation": "Nimm Crowkeeper.", "confidence": "hoch"})
        self.root.update()
        self.assertEqual(self.root.state(), "withdrawn")
        self.assertEqual(self.app.overlay.save_btn.cget("state"), "normal")
        self.app.confirm_ai_choice(silent=True)
        self.assertEqual(len(self.app.prior), 1)
        self.assertEqual(self.app.overlay.save_btn.cget("state"), "disabled")
        self.app.show_analysis({"screen_type": "invocation", "invocation_state": "merged",
                                "cards": [], "best_number": 0, "selected_numbers": [],
                                "recommendation": "Am Bossaltar einsetzen.", "confidence": "hoch"})
        self.assertEqual(len(self.app.prior), 1)
        self.assertEqual(self.app.overlay.save_btn.cget("state"), "disabled")

    def test_one_manual_capture_one_grab(self):
        from PIL import Image
        class FakeShot:
            width, height = 10, 10
            rgb = Image.new("RGB", (10, 10), "green").tobytes()
        ctx = MagicMock()
        ctx.__enter__.return_value.monitors = [None, {"left": 0, "top": 0, "width": 10, "height": 10}]
        ctx.__enter__.return_value.grab.return_value = FakeShot()
        fake = MagicMock(mss=MagicMock(return_value=ctx))
        self.app.api_key.set("test-placeholder-key")
        with patch.dict(sys.modules, {"mss": fake}), patch.object(self.app, "start_analysis") as callback:
            self.app.capture()
            self.assertTrue(self.app._capture_pending)
            self.app.capture()
            # Trigger the scheduled callback synchronously for a deterministic test.
            self.root.after_cancel(self.app._capture_after_id)
            self.app._capture_once()
            callback.assert_called_once()
            self.assertEqual(ctx.__enter__.return_value.grab.call_count, 1)
            self.assertFalse(self.app._capture_pending)
            self.assertTrue(self.app.overlay.is_visible)

    def test_selected_card_gets_frame_only_for_live_capture(self):
        result = {"screen_type": "selection", "best_number": 3,
                  "selected_numbers": [3], "confidence": "hoch",
                  "cards": [{"number": 3, "name": "Crowkeeper", "box": [700, 250, 840, 650]}],
                  "recommendation": "Nimm die rechte Karte."}
        self.app._pending_capture_region = (0, 0, 1000, 800)
        self.app.show_analysis(result)
        self.assertTrue(self.app.marker.is_visible)
        self.assertEqual(self.app.marker._box, (700, 200, 140, 320))
        self.app.toggle_overlay()  # F9 hides both
        self.assertFalse(self.app.overlay.is_visible)
        self.assertFalse(self.app.marker.is_visible)
        self.app.toggle_overlay()  # F9 shows both
        self.assertTrue(self.app.marker.is_visible)
        self.app.confirm_ai_choice(silent=True)  # F6 clears the frame
        self.assertFalse(self.app.marker.is_visible)
        self.assertIsNone(self.app.marker._box)
        self.app.show_analysis(result)  # old image / no live capture region
        self.assertFalse(self.app.marker.is_visible)

    def test_overlay_minimize_button_hides_frame_too(self):
        self.app._pending_capture_region = (0, 0, 1000, 800)
        self.app.show_analysis({"screen_type": "selection", "best_number": 1,
                                "selected_numbers": [1], "confidence": "hoch",
                                "cards": [{"number": 1, "name": "Crowkeeper", "box": [100, 250, 300, 650]}],
                                "recommendation": "Nimm links."})
        self.assertTrue(self.app.marker.is_visible)
        self.app.overlay.hide()  # Actual small — button callback
        self.assertFalse(self.app.marker.is_visible)
        self.app.overlay.show()
        self.assertTrue(self.app.marker.is_visible)
        # No stale green frame appears on new scan before next result arrives.
        self.app.api_key.set("test-placeholder-key")
        self.app.capture()
        self.assertFalse(self.app.marker.is_visible)
        if self.app._capture_after_id is not None:
            self.root.after_cancel(self.app._capture_after_id)
            self.app._capture_after_id = None
            self.app._capture_pending = False
            self.app.overlay.resume_after_capture()

    def test_no_frame_for_boss_altar_and_uncertain_results(self):
        self.app._pending_capture_region = (0, 0, 1000, 800)
        self.app.show_analysis({"screen_type": "invocation", "invocation_state": "merged",
                                "best_number": 0, "selected_numbers": [], "cards": [],
                                "recommendation": "Zusammengefuehrt.", "confidence": "hoch"})
        self.assertFalse(self.app.marker.is_visible)
        self.app._pending_capture_region = (0, 0, 1000, 800)
        self.app.show_analysis({"screen_type": "selection", "best_number": 1,
                                "selected_numbers": [1], "confidence": "niedrig",
                                "cards": [{"number": 1, "name": "Murderous", "box": [100, 150, 250, 550]}],
                                "recommendation": "Unsicher."})
        self.assertFalse(self.app.marker.is_visible)

    def test_undo_visibility_and_history_persistence(self):
        self.app.overlay.hide()
        self.assertFalse(self.app.overlay.is_visible)
        self.app.overlay.toggle_visibility()
        self.assertTrue(self.app.overlay.is_visible)
        self.app.prior.append(__import__("fate_engine").Fate("Crowkeeper", "seltene Rüstung"))
        self.app._save_config()
        self.assertIn("Crowkeeper", Path(self.home.name).joinpath("app.json").read_text())
        self.assertNotIn("test-placeholder-key", Path(self.home.name).joinpath("app.json").read_text())


if __name__ == "__main__":
    unittest.main()
