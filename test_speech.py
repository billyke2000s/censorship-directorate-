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

    def test_no_recognized_words_does_not_trigger_alarm(self):
        state = SpeechState()
        state.update(1.0, "")
        state.update(1.02, "[noise]")
        self.assertFalse(state.active(1.02))

    def test_new_words_trigger_and_repeated_result_does_not_extend_alarm(self):
        state = SpeechState()
        state.update(1, "hello")
        self.assertTrue(state.active(1))
        state.update(1.4, "hello")
        state.update(1.5, "hello", final=True)
        self.assertFalse(state.active(1.7))
        state.update(1.8, "don't", final=True)
        self.assertTrue(state.active(1.8))

    def test_additional_recognized_word_extends_alarm(self):
        state = SpeechState()
        state.update(1, "hello")
        state.update(1.5, "hello there")
        self.assertTrue(state.active(1.8))
        self.assertFalse(state.active(2.2))
