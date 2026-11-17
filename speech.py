"""Classify microphone frames locally without saving or transcribing them."""

from collections import deque
from time import monotonic


class SpeechState:
    def __init__(self):
        self.recent = deque(maxlen=5)
        self.active_until = 0.0
        self.muted_until = 0.0

    def update(self, now, voiced):
        if now < self.muted_until:
            return
        self.recent.append(voiced)
        if voiced and sum(self.recent) >= 3:
            self.active_until = now + 0.45

    def active(self, now):
        return now < self.active_until


def microphone(device, state):
    import sounddevice as sd
    import webrtcvad

    try:
        settings = sd.query_devices(device, "input")
    except sd.PortAudioError as error:
        raise RuntimeError(f"Could not find microphone: {error}") from error
    supported_rates = (16000, 48000, 32000, 8000)
    preferred = int(settings["default_samplerate"])
    rates = tuple(dict.fromkeys(
        ((preferred,) if preferred in supported_rates else ()) + supported_rates
    ))
    last_error = None
    for rate in rates:
        detector = webrtcvad.Vad(2)
        frame_size = rate // 50

        def callback(data, frames, _time, status):
            now = monotonic()
            if not status and frames == frame_size and now >= state.muted_until:
                state.update(now, detector.is_speech(bytes(data), rate))

        stream = None
        try:
            stream = sd.RawInputStream(device=device, channels=1, samplerate=rate,
                                       dtype="int16", blocksize=frame_size,
                                       callback=callback)
            stream.start()
            return stream
        except sd.PortAudioError as error:
            if stream is not None:
                stream.close()
            last_error = error
    raise RuntimeError(f"Could not start microphone: {last_error}")
