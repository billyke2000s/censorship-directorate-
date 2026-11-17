import unittest

from alarm import Monitor, mouth_ratio


class MonitorTests(unittest.TestCase):
    def test_opening_ratio(self):
        points = [(0, 0)] * 468
        points[308] = (40, 0)
        for bottom in (87, 14, 317):
            points[bottom] = (0, 12)
        self.assertAlmostEqual(mouth_ratio(points), 0.30)
        points[308] = (0, 0)
        self.assertIsNone(mouth_ratio(points))

    def test_cover_is_debounced_and_clears(self):
        monitor = Monitor()
        self.assertFalse(monitor.update(1, 0.1, True))
        self.assertFalse(monitor.update(1.1, 0.1, True))
        self.assertTrue(monitor.update(1.4, None, True))
        self.assertFalse(monitor.update(1.5, None, False))

    def test_static_mouth_times_out(self):
        monitor = Monitor()
        monitor.challenge(0, first="open")
        for second in range(16):
            monitor.update(second, 0.40, False)
        self.assertIn("CHEATING?", monitor.result)

    def test_completing_all_poses(self):
        monitor = Monitor()
        monitor.challenge(0, first="closed")
        for second, ratio in enumerate((0.12, 0.40, 0.12)):
            monitor.update(second, ratio, False)
            monitor.update(second + 0.5, ratio, False)
        self.assertEqual(monitor.result, "Mouth movement verified")

    def test_covered_pose_does_not_count(self):
        monitor = Monitor()
        monitor.challenge(0, first="open")
        monitor.update(0, 0.40, False)
        monitor.update(0.5, 0.40, True)
        monitor.update(1, 0.40, False)
        self.assertEqual(monitor.steps, ["open", "closed", "open"])
