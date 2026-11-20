"""Smoke checks for the console without a camera or Windows window manager."""
import unittest

import numpy as np

from console_ui import WIDTH, HEIGHT, render_console


class ConsoleUITests(unittest.TestCase):
    def setUp(self):
        self.camera = np.full((480, 640, 3), 75, dtype=np.uint8)

    def test_full_size_and_live_camera(self):
        screen = render_console(self.camera, ["MOUTH OPEN"], "Mouth open",
                                "Mic: Voice detection", "0.56", (WIDTH, HEIGHT), [0.5] * 55)
        self.assertEqual(screen.shape, (HEIGHT, WIDTH, 3))
        self.assertGreater(screen[600, 300].mean(), 40)

    def test_resize_with_no_mic(self):
        screen = render_console(self.camera, [], "Mouth closed",
                                "Mic disabled", "0.10", (900, 600))
        self.assertEqual(screen.shape, (600, 900, 3))

    def test_warning_overflow(self):
        screen = render_console(self.camera, ["WARNING"] * 12, "Unknown",
                                "Mic disabled", "--", (1280, 853))
        self.assertEqual(screen.shape, (853, 1280, 3))


if __name__ == "__main__":
    unittest.main()
