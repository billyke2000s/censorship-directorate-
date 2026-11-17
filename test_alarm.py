import unittest

from alarm import Monitor, head_turned, mouth_open_alarm, mouth_ratio


class MonitorTests(unittest.TestCase):
    def test_camera_cover_is_debounced_and_clears_on_uncover(self):
        monitor = Monitor()
        self.assertEqual(monitor.camera_warnings(0, 0, False, True), [])
        self.assertEqual(monitor.camera_warnings(0.6, 0, False, True), ["CAMERA COVERED"])
        self.assertEqual(monitor.camera_warnings(0.7, 0, False), [])
        self.assertEqual(monitor.camera_warnings(1.8, 0, False), ["FACE NOT VISIBLE"])
        self.assertEqual(monitor.camera_warnings(2, 1, False, True), [])

    def test_open_mouth_alarm_holds_until_closed_or_occluded(self):
        self.assertTrue(mouth_open_alarm(0.30, False, False))
        self.assertFalse(mouth_open_alarm(0.25, False, False))
        self.assertTrue(mouth_open_alarm(0.25, False, True))
        self.assertFalse(mouth_open_alarm(0.21, False, True))
        self.assertFalse(mouth_open_alarm(0.40, True, True))
        self.assertFalse(mouth_open_alarm(None, False, True))

    def test_still_face_raises_passive_warning_then_clears(self):
        monitor = Monitor()
        monitor.observe_stillness(0, True)
        monitor.observe_stillness(4.9, True)
        self.assertEqual(monitor.camera_warnings(4.9, 1, False), [])
        monitor.observe_stillness(5, True)
        self.assertEqual(monitor.camera_warnings(5, 1, False), ["FACE IMAGE STILL"])
        monitor.observe_stillness(6, False)
        self.assertEqual(monitor.camera_warnings(6, 1, False), [])

    def test_motion_interrupts_still_face_timer(self):
        monitor = Monitor()
        monitor.observe_stillness(0, True)
        monitor.observe_stillness(4, False)
        monitor.observe_stillness(5, True)
        self.assertEqual(monitor.camera_warnings(5, 1, False), [])

    def test_visibility_warnings_wait_and_clear(self):
        monitor = Monitor()
        self.assertEqual(monitor.camera_warnings(0, 0, False), [])
        self.assertEqual(monitor.camera_warnings(1, 0, False), ["FACE NOT VISIBLE"])
        self.assertEqual(monitor.camera_warnings(2, 2, False), [])
        self.assertEqual(monitor.camera_warnings(3, 2, False), ["MULTIPLE FACES"])
        self.assertEqual(monitor.camera_warnings(4, 1, True), [])
        self.assertEqual(monitor.camera_warnings(4.7, 1, True), ["HEAD TURNED AWAY"])
        self.assertEqual(monitor.camera_warnings(7, 1, False), [])

    def test_turn_stays_active_through_landmark_loss_and_profile_detection(self):
        monitor = Monitor()
        self.assertEqual(monitor.camera_warnings(0, 1, True), [])
        self.assertEqual(monitor.camera_warnings(0.7, 0, False), ["HEAD TURNED AWAY"])
        self.assertEqual(monitor.camera_warnings(1.3, 0, False, profile=True), ["HEAD TURNED AWAY"])
        self.assertEqual(monitor.camera_warnings(2.5, 0, False), ["HEAD TURNED AWAY"])
        self.assertEqual(monitor.camera_warnings(2.9, 0, False), [])
        self.assertEqual(monitor.camera_warnings(4, 0, False), ["FACE NOT VISIBLE"])

    def test_turn_can_be_detected_from_rotation_with_centered_nose(self):
        points = [(0, 0)] * 468
        points[33], points[263], points[1] = (10, 10), (50, 10), (30, 25)
        for sine, expected in ((0.5, True), (-0.5, True), (0.0, False)):
            transform = [[0.866, 0, sine], [0, 1, 0], [-sine, 0, 0.866]]
            self.assertEqual(head_turned(points, transform), expected)

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
        self.assertFalse(monitor.mouth_covered(1, True))
        self.assertFalse(monitor.mouth_covered(1.1, True))
        self.assertFalse(monitor.mouth_covered(1.18, False))
        self.assertTrue(monitor.mouth_covered(1.25, True))
        self.assertTrue(monitor.mouth_covered(1.39, False))
        self.assertFalse(monitor.mouth_covered(1.45, False))
