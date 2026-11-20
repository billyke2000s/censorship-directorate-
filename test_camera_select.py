"""Camera discovery tests use fake video devices: no webcam required."""
import unittest
from unittest.mock import patch
import numpy as np

from camera_select import choose_camera, read_working_frame


class FakeCamera:
    def __init__(self, frame):
        self.frame = frame
        self.closed = False
        self.calls = 0

    def isOpened(self):
        return self.frame is not None

    def read(self):
        self.calls += 1
        return self.frame is not None, self.frame

    def release(self):
        self.closed = True


class CameraSelectionTests(unittest.TestCase):
    def test_prefers_a_face_over_first_usable_camera(self):
        blank = np.zeros((8, 8, 3), dtype=np.uint8)
        person = np.ones((8, 8, 3), dtype=np.uint8)
        devices = []
        def factory(index, backend):
            dev = FakeCamera(blank if index == 0 else person)
            devices.append(dev)
            return dev
        with patch("camera_select.available_backends", return_value=(1,)):
            cap, frame, index, backend = choose_camera(
                lambda frame: bool(frame[0, 0, 0]),
                capture_factory=factory, max_index=1, preference=(0, 1),
            )
        self.assertEqual((index, backend), (1, 1))
        self.assertEqual(int(frame[0, 0, 0]), 1)
        self.assertTrue(devices[0].closed)
        self.assertFalse(cap.closed)
        cap.release()

    def test_falls_back_to_working_feed_if_no_face(self):
        blank = np.zeros((5, 5, 3), dtype=np.uint8)
        with patch("camera_select.available_backends", return_value=(1,)):
            cap, _, index, _ = choose_camera(
                lambda frame: False, capture_factory=lambda *_: FakeCamera(blank),
                max_index=1, preference=(0, 1),
            )
        self.assertEqual(index, 0)
        cap.release()

    def test_unusable_cameras_raise_a_helpful_error(self):
        with patch("camera_select.available_backends", return_value=(1,)):
            with self.assertRaisesRegex(RuntimeError, "No usable camera feed"):
                choose_camera(lambda frame: False, capture_factory=lambda *_: FakeCamera(None),
                              max_index=1, preference=None)

    def test_rejects_out_of_range_override(self):
        with self.assertRaises(ValueError):
            choose_camera(lambda frame: False, requested_index=15)


if __name__ == "__main__":
    unittest.main()
