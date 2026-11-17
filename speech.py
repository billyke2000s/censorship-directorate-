"""Classify microphone frames locally without saving or transcribing them."""

from collections import deque
from time import monotonic
import numpy as np


def remove_alarm_tone(data, rate):
    samples = np.frombuffer(data, dtype="<i2")
    bins = np.fft.rfft(samples)
    frequencies = np.fft.rfftfreq(len(samples), 1 / rate)
    bins[abs(frequencies - 1000) <= 100] = 0
    cleaned = np.fft.irfft(bins, n=len(samples))
    return np.clip(np.rint(cleaned), -32768, 32767).astype("<i2").tobytes()


def has_voice_energy(data, rate):
    """Reject very quiet frames and narrow tones before accepting a VAD vote."""
    samples = np.frombuffer(data, dtype="<i2").astype(np.float32)
    samples -= samples.mean()
    if np.mean(samples * samples) < 45 ** 2:
        return False
    power = np.abs(np.fft.rfft(samples * np.hanning(len(samples)))) ** 2
    frequencies = np.fft.rfftfreq(len(samples), 1 / rate)
    voice_band = power[(frequencies >= 150) & (frequencies <= 3500)]
    in_band = voice_band.sum()
    if in_band < 0.40 * power.sum():
        return False
    # A steady whistle or electronic beep concentrates energy in adjacent bins.
    strongest = np.convolve(voice_band, np.ones(3), mode="valid").max()
    return strongest < 0.85 * in_band


class SpeechState:
    def __init__(self):
        self.recent = deque(maxlen=13)
        self.active_until = 0.0
        self.muted_until = 0.0
        self.alarm_playing = False

    def update(self, now, voiced):
        if now < self.muted_until:
            return
        self.recent.append(voiced)
        votes_needed = 4 if self.active(now) else 8
        if voiced and sum(self.recent) >= votes_needed:
            self.active_until = now + 0.30

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
        detector = webrtcvad.Vad(3)
        frame_size = rate // 50

        def callback(data, frames, _time, status):
            now = monotonic()
            if not status and frames == frame_size and now >= state.muted_until:
                pcm = bytes(data)
                if state.alarm_playing:
                    pcm = remove_alarm_tone(pcm, rate)
                state.update(now, detector.is_speech(pcm, rate) and has_voice_energy(pcm, rate))

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
