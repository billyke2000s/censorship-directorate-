import unittest

import numpy as np

from speech import SpeechState, remove_alarm_tone


class SpeechStateTests(unittest.TestCase):
    def test_alarm_filter_preserves_audio_away_from_tone(self):
        rate = 16000
        time = np.arange(320) / rate
        voice = 2000 * np.sin(2 * np.pi * 400 * time)
        alarm = 8000 * np.sin(2 * np.pi * 1000 * time)
        mixed = np.rint(voice + alarm).astype("<i2")
        filtered = np.frombuffer(remove_alarm_tone(mixed.tobytes(), rate), dtype="<i2")
        np.testing.assert_allclose(filtered, voice, atol=2)

    def test_one_voice_frame_does_not_trigger_alarm(self):
        state = SpeechState()
        state.update(1.0, True)
        state.update(1.02, False)
        self.assertFalse(state.active(1.02))

    def test_sustained_voice_triggers_then_expires(self):
        state = SpeechState()
        for now in (1.0, 1.02, 1.04):
            state.update(now, True)
        self.assertTrue(state.active(1.04))
        self.assertFalse(state.active(1.50))

    def test_suppresses_frames_during_the_beep(self):
        state = SpeechState()
        state.muted_until = 2.0
        for now in (1.0, 1.02, 1.04):
            state.update(now, True)
        self.assertFalse(state.active(1.04))
        self.assertEqual(len(state.recent), 0)
