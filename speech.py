"""Classify microphone frames locally without saving or transcribing them."""

import json
from contextlib import contextmanager
from queue import Empty, Full, Queue
from threading import Event, Thread
from time import monotonic
import numpy as np


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
        self.partial = ()
        self.error = None

    def update(self, now, text, final=False):
        words = tuple(word for word in text.split() if word.replace("'", "").isalpha())
        if len(words) > len(self.partial):
            self.active_until = now + 0.65
        if final:
            self.partial = ()
        elif len(words) > len(self.partial):
            self.partial = words

    def active(self, now):
        return now < self.active_until


@contextmanager
def microphone(device, state, model_path):
    import sounddevice as sd
    from vosk import KaldiRecognizer, Model, SetLogLevel

    if not (model_path / "am" / "final.mdl").is_file():
        raise RuntimeError("Missing English speech model. Run Start-MouthAlarm.cmd")
    SetLogLevel(-1)
    model = Model(str(model_path))

    try:
        settings = sd.query_devices(device, "input")
    except sd.PortAudioError as error:
        raise RuntimeError(f"Could not find microphone: {error}") from error
    supported_rates = (16000, 48000, 44100, 32000)
    preferred = int(settings["default_samplerate"])
    rates = tuple(dict.fromkeys(
        ((preferred,) if preferred in supported_rates else ()) + supported_rates
    ))
    pending = Queue(maxsize=8)
    stopped = Event()

    def callback(data, _frames, _time, status):
        if not status:
            try:
                pending.put_nowait((monotonic(), bytes(data)))
            except Full:
                pass

    last_error = None
    for rate in rates:
        stream = None
        try:
            stream = sd.RawInputStream(device=device, channels=1, samplerate=rate,
                                       dtype="int16", blocksize=rate // 10,
                                       callback=callback)
            stream.start()
            break
        except sd.PortAudioError as error:
            if stream is not None:
                stream.close()
            last_error = error
    else:
        raise RuntimeError(f"Could not start microphone: {last_error}")

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
        yield stream
    finally:
        stopped.set()
        stream.close()
        if worker.ident is not None:
            worker.join()
