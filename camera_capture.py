"""Read the default webcam continuously and discard superseded frames."""

from threading import Condition, Event, Thread


class LatestCamera:
    def __init__(self, capture):
        self.capture = capture
        self.frame = None
        self.ready = Condition()
        self.stop = Event()
        self.finished = False
        self.reader = Thread(target=self._capture_frames, daemon=True)
        self.reader.start()

    def _capture_frames(self):
        try:
            while not self.stop.is_set():
                ok, frame = self.capture.read()
                if not ok:
                    break
                with self.ready:
                    self.frame = frame
                    self.ready.notify()
        finally:
            with self.ready:
                self.finished = True
                self.ready.notify_all()
            self.capture.release()

    def read(self):
        with self.ready:
            self.ready.wait_for(lambda: self.frame is not None or self.finished, timeout=5)
            frame, self.frame = self.frame, None
        return frame is not None, frame

    def release(self):
        self.stop.set()
        self.reader.join(timeout=1)
