import unittest

from alarm import Monitor, head_turned, mouth_ratio


class MonitorTests(unittest.TestCase):
    def test_still_face_prompts_then_flags_failed_check(self):
        monitor = Monitor()
        monitor.observe_stillness(0, True)
        monitor.observe_stillness(4.9, True)
        self.assertFalse(monitor.steps)
        monitor.observe_stillness(5, True)
        self.assertTrue(monitor.steps)
        self.assertTrue(monitor.still_check)
        monitor.update(20, 0.1, False)
        self.assertTrue(monitor.failed)

    def test_motion_interrupts_still_face_timer(self):
        monitor = Monitor()
        monitor.observe_stillness(0, True)
        monitor.observe_stillness(4, False)
        monitor.observe_stillness(5, True)
        self.assertFalse(monitor.steps)

    def test_visibility_warnings_wait_and_clear(self):
        monitor = Monitor()
        self.assertEqual(monitor.camera_warnings(0, 0, False), [])
        self.assertEqual(monitor.camera_warnings(1, 0, False), ["FACE NOT VISIBLE"])
        self.assertEqual(monitor.camera_warnings(2, 2, False), [])
        self.assertEqual(monitor.camera_warnings(3, 2, False), ["MULTIPLE FACES"])
        self.assertEqual(monitor.camera_warnings(4, 1, True), [])
        self.assertEqual(monitor.camera_warnings(6, 1, True), ["HEAD TURNED AWAY"])
        self.assertEqual(monitor.camera_warnings(7, 1, False), [])

    def test_head_turn_uses_nose_position_along_eye_line(self):
        points = [(0, 0)] * 468
        points[33], points[263] = (10, 10), (50, 10)
        points[1] = (30, 25)
        self.assertFalse(head_turned(points))
        points[1] = (48, 25)
        self.assertTrue(head_turned(points))

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
