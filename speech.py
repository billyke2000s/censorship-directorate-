"""Classify microphone frames locally without saving or transcribing them."""

from collections import deque
from contextlib import contextmanager
from queue import Empty, Full, Queue
from threading import Event, Thread
from time import monotonic
import numpy as np

from call_audio import CallAudio, find_cable


def remove_alarm_tone(data, rate):
    samples = np.frombuffer(data, dtype="<i2")
    bins = np.fft.rfft(samples)
    frequencies = np.fft.rfftfreq(len(samples), 1 / rate)
    bins[abs(frequencies - 1000) <= 100] = 0
    cleaned = np.fft.irfft(bins, n=len(samples))
    return np.clip(np.rint(cleaned), -32768, 32767).astype("<i2").tobytes()


class SpeechState:
    def __init__(self):
        self.active_until = 0.0
        self.muted_until = 0.0
        self.alarm_playing = False
        self.camera_alarm = False
        self.camera_checked_at = 0.0
        self.voice_window = (float("inf"), 0.0)
        self.voiced_frames = 0
        self.waveform = deque(maxlen=55)
        self.error = None

    def update(self, now, voiced):
        self.voiced_frames = min(self.voiced_frames + 1, 2) if voiced else 0
        if self.voiced_frames == 2:
            self.active_until = now + 0.30
            start = now - 0.25
            previous_start, previous_end = self.voice_window
            self.voice_window = (min(start, previous_start) if start <= previous_end else start,
                                 self.active_until)

    def active(self, now):
        return now < self.active_until


@contextmanager
def microphone(device, state, *, virtual_mic=False, cable_device=None):
    import sounddevice as sd
    import webrtcvad

    if virtual_mic and cable_device is None:
        cable_device = find_cable(sd.query_devices())
        if cable_device is None:
            raise RuntimeError("CABLE Input was not found. Install VB-CABLE and restart Windows.")
    try:
        settings = sd.query_devices(device, "input")
    except sd.PortAudioError as error:
        raise RuntimeError(f"Could not find microphone: {error}") from error
    if virtual_mic and settings["name"].casefold().startswith("cable output"):
        raise RuntimeError("Choose your physical microphone with --mic INDEX to avoid a feedback loop")
    supported_rates = (16000, 48000, 44100, 32000, 8000)
    preferred = int(settings["default_samplerate"])
    rates = tuple(dict.fromkeys(
        ((preferred,) if preferred in supported_rates else ()) + supported_rates
    ))
    pending = Queue(maxsize=8)
    stopped = Event()
    route = None

    def callback(data, _frames, _time, status):
        if not status:
            captured, pcm = monotonic(), bytes(data)
            # Store real, recent microphone peaks for the live console.
            samples = np.frombuffer(pcm, dtype="<i2").astype(np.int32)
            peak = float(np.max(np.abs(samples))) / 8192.0 if samples.size else 0.0
            state.waveform.append(min(1.0, peak))
            if route is not None:
                route.capture(captured, pcm)
            try:
                pending.put_nowait((captured, pcm))
            except Full:
                pass

    last_error = None
    for rate in rates:
        stream = cable = None
        try:
            if virtual_mic:
                route = CallAudio(state, rate)
                cable = sd.RawOutputStream(device=cable_device, channels=2, samplerate=rate,
                                           dtype="int16", blocksize=rate // 10,
                                           callback=route.callback)
            stream = sd.RawInputStream(device=device, channels=1, samplerate=rate,
                                       dtype="int16", blocksize=rate // 10,
                                       callback=callback)
            stream.start()
            if cable is not None:
                cable.start()
            break
        except sd.PortAudioError as error:
            if stream is not None:
                stream.close()
            if cable is not None:
                cable.close()
            last_error = error
    else:
        target = "microphone and virtual cable" if virtual_mic else "microphone"
        raise RuntimeError(f"Could not start {target}: {last_error}")

    def detect_voice():
        try:
            detector = webrtcvad.Vad(2)
            vad_rate = 16000 if rate == 44100 else rate
            frame_bytes = vad_rate // 50 * 2
            if rate != vad_rate:
                source_positions = np.arange(rate // 10)
                target_positions = np.arange(vad_rate // 10) * (rate / vad_rate)
            while not stopped.is_set():
                try:
                    captured, pcm = pending.get(timeout=0.1)
                except Empty:
                    continue
                if captured < state.muted_until:
                    state.update(captured, False)
                    continue
                if state.alarm_playing:
                    pcm = remove_alarm_tone(pcm, rate)
                if rate != vad_rate:
                    pcm = np.interp(target_positions, source_positions,
                                    np.frombuffer(pcm, dtype="<i2")).astype("<i2").tobytes()
                for offset in range(0, len(pcm) - frame_bytes + 1, frame_bytes):
                    frame = pcm[offset:offset + frame_bytes]
                    frame_time = captured - (len(pcm) - offset - frame_bytes) / (2 * vad_rate)
                    state.update(frame_time, detector.is_speech(frame, vad_rate))
        except Exception as error:
            state.error = str(error)

    worker = Thread(target=detect_voice, daemon=True)
    try:
        worker.start()
        yield stream, cable
    finally:
        stopped.set()
        if cable is not None:
            cable.close()
        stream.close()
        if worker.ident is not None:
            worker.join()
