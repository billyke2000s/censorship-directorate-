"""Classify microphone frames locally without saving or transcribing them."""

import json
from contextlib import contextmanager
from queue import Empty, Full, Queue
from threading import Event, Thread
from time import monotonic
import numpy as np

from call_audio import CALL_DELAY, CallAudio, find_cable


def remove_alarm_tone(data, rate):
    samples = np.frombuffer(data, dtype="<i2")
    bins = np.fft.rfft(samples)
    frequencies = np.fft.rfftfreq(len(samples), 1 / rate)
    bins[abs(frequencies - 1000) <= 100] = 0
    cleaned = np.fft.irfft(bins, n=len(samples))
    return np.clip(np.rint(cleaned), -32768, 32767).astype("<i2").tobytes()


SPEECH_MODEL = "vosk-model-small-en-us-0.15"


class SpeechState:
    def __init__(self):
        self.active_until = 0.0
        self.muted_until = 0.0
        self.alarm_playing = False
        self.camera_alarm = False
        self.camera_checked_at = 0.0
        self.word_window = (float("inf"), 0.0)
        self.partial = ()
        self.error = None

    def update(self, now, text, final=False):
        words = tuple(word for word in text.split() if word.replace("'", "").isalpha())
        if len(words) > len(self.partial):
            self.active_until = now + 0.65
            start = now - CALL_DELAY
            previous_start, previous_end = self.word_window
            self.word_window = (min(start, previous_start) if start <= previous_end else start,
                                self.active_until)
        if final:
            self.partial = ()
        elif len(words) > len(self.partial):
            self.partial = words

    def active(self, now):
        return now < self.active_until


@contextmanager
def microphone(device, state, model_path, *, virtual_mic=False, cable_device=None):
    import sounddevice as sd
    from vosk import KaldiRecognizer, Model, SetLogLevel

    if virtual_mic and cable_device is None:
        cable_device = find_cable(sd.query_devices())
        if cable_device is None:
            raise RuntimeError("CABLE Input was not found. Install VB-CABLE and restart Windows.")
    if not (model_path / "am" / "final.mdl").is_file():
        raise RuntimeError("Missing English speech model. Run Start-MouthAlarm.cmd")
    SetLogLevel(-1)
    model = Model(str(model_path))

    try:
        settings = sd.query_devices(device, "input")
    except sd.PortAudioError as error:
        raise RuntimeError(f"Could not find microphone: {error}") from error
    if virtual_mic and settings["name"].casefold().startswith("cable output"):
        raise RuntimeError("Choose your physical microphone with --mic INDEX to avoid a feedback loop")
    supported_rates = (16000, 48000, 44100, 32000)
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

    def recognize():
        try:
            recognizer = KaldiRecognizer(model, rate)
            while not stopped.is_set():
                try:
                    captured, pcm = pending.get(timeout=0.1)
                except Empty:
                    continue
                if captured < state.muted_until:
                    pcm = bytes(len(pcm))
                elif state.alarm_playing:
                    pcm = remove_alarm_tone(pcm, rate)
                final = recognizer.AcceptWaveform(pcm)
                result = recognizer.Result() if final else recognizer.PartialResult()
                key = "text" if final else "partial"
                state.update(monotonic(), json.loads(result).get(key, ""), final)
        except Exception as error:
            state.error = str(error)

    worker = Thread(target=recognize, daemon=True)
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
