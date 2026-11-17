import unittest

import numpy as np

from call_audio import CallAudio, find_cable
from speech import SpeechState


class CallAudioTests(unittest.TestCase):
    def setUp(self):
        self.state = SpeechState()
        self.state.camera_checked_at = 2
        self.route = CallAudio(self.state, 16000)
        self.pcm = np.full(self.route.frames, 100, dtype="<i2").tobytes()

    def test_cable_selection_uses_playback_endpoint(self):
        self.assertEqual(find_cable([
            {"name": "CABLE Output", "max_output_channels": 0},
            {"name": "CABLE Input (VB-Audio Virtual Cable)", "max_output_channels": 2},
        ]), 1)

    def test_clear_audio_is_delayed_and_sent_to_both_channels(self):
        self.route.capture(1.1, self.pcm)
        self.assertEqual(self.route.output(1.9, self.route.frames), bytes(self.route.frames * 4))
        samples = np.frombuffer(self.route.output(2.01, self.route.frames), dtype="<i2")
        self.assertTrue(np.all(samples == 100))

    def test_camera_alarm_or_recognized_word_replaces_buffered_audio(self):
        self.state.camera_alarm = True
        self.route.capture(1.0, self.pcm)
        self.state.camera_alarm = False
        self.route.capture(1.1, self.pcm)
        self.state.update(1.5, "hello")
        tone = np.repeat(np.frombuffer(self.route.tone, dtype="<i2"), 2).tobytes()
        self.assertEqual(self.route.output(2.0, self.route.frames), tone)
        self.assertEqual(self.route.output(2.1, self.route.frames), tone)

    def test_stale_camera_yields_silence(self):
        self.route.capture(2.3, self.pcm)
        self.assertEqual(self.route.output(3.3, self.route.frames), bytes(self.route.frames * 4))
