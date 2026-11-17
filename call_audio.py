"""Route delayed microphone audio or the censor tone to a virtual cable."""

from collections import deque
from time import monotonic

import numpy as np


CALL_DELAY = 0.9
CAMERA_TIMEOUT = 1.0


def find_cable(devices):
    return next((index for index, device in enumerate(devices)
                 if device["max_output_channels"] > 0
                 and device["name"].casefold().startswith("cable input")), None)


class CallAudio:
    def __init__(self, state, rate):
        self.state = state
        self.frames = rate // 10
        self.delay = deque(maxlen=24)
        self.tone = (np.sin(2 * np.pi * 1000 * np.arange(self.frames) / rate)
                     * 4200).astype("<i2").tobytes()

    def capture(self, when, pcm):
        self.delay.append((when, pcm, self.state.camera_alarm))

    def output(self, now, frames):
        if frames != self.frames or not self.delay or self.delay[0][0] > now - CALL_DELAY:
            return bytes(frames * 4)
        captured, pcm, camera_alarm = self.delay.popleft()
        if (now - self.state.camera_checked_at > CAMERA_TIMEOUT or
                self.state.error or len(pcm) != frames * 2 or now - captured > CALL_DELAY + 0.6):
            return bytes(frames * 4)
        word_from, word_until = self.state.word_window
        if camera_alarm or self.state.camera_alarm or word_from <= captured <= word_until:
            pcm = self.tone
        return np.repeat(np.frombuffer(pcm, dtype="<i2"), 2).tobytes()

    def callback(self, outdata, frames, _time, _status):
        outdata[:] = self.output(monotonic(), frames)
