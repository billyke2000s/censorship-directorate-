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

    def test_isolated_noise_frame_does_not_trigger_alarm(self):
        state = SpeechState()
        state.update(1.0, True)
        state.update(1.02, False)
        self.assertFalse(state.active(1.02))

    def test_brief_voice_activity_triggers_then_expires(self):
        state = SpeechState()
        state.update(1, True)
        state.update(1.02, True)
        self.assertTrue(state.active(1.02))
        state.update(1.04, False)
        self.assertFalse(state.active(1.33))

    def test_continuous_voice_extends_alarm(self):
        state = SpeechState()
        for index in range(20):
            state.update(1 + index * 0.02, True)
        self.assertTrue(state.active(1.6))
        self.assertFalse(state.active(1.7))
