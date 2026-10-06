import sys
import unittest
from pathlib import Path


GUI_DIR = Path(__file__).resolve().parents[1] / "gui"
sys.path.insert(0, str(GUI_DIR))

from app import initial_window_size


class ResponsiveLayoutTests(unittest.TestCase):
    def test_uses_default_size_when_screen_has_room(self):
        self.assertEqual(initial_window_size(1920, 1080, 1.0), (1040, 660))

    def test_scales_available_space_for_high_dpi_displays(self):
        self.assertEqual(initial_window_size(1920, 1080, 2.0), (896, 444))

    def test_caps_window_to_a_small_screen(self):
        self.assertEqual(initial_window_size(1280, 720, 1.25), (960, 480))

    def test_rejects_invalid_display_scale(self):
        with self.assertRaises(ValueError):
            initial_window_size(1920, 1080, 0)


if __name__ == "__main__":
    unittest.main()
