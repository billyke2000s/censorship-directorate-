import unittest

from speech import SpeechState


class SpeechStateTests(unittest.TestCase):
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
