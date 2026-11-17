"""Read the named OBS DirectShow feed without using camera indexes."""

from shutil import which
from subprocess import CREATE_NO_WINDOW, PIPE, Popen, TimeoutExpired
from tempfile import TemporaryFile
from threading import Condition, Thread

import cv2
import numpy as np


OBS_CAMERA_NAME = "OBS Virtual Camera"


class ObsCamera:
    def __init__(self, resolution=None):
        ffmpeg = which("ffmpeg")
        if ffmpeg is None:
            raise RuntimeError("FFmpeg is required for OBS capture. Install FFmpeg and reopen this launcher.")
        command = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
                   "-f", "dshow", "-rtbufsize", "32M"]
        if resolution is not None:
            width, height = resolution
            command += ["-video_size", f"{width}x{height}"]
        command += ["-i", f"video={OBS_CAMERA_NAME}", "-an", "-fpsmax", "30",
                    "-c:v", "bmp", "-pix_fmt", "bgr24", "-f", "image2pipe", "pipe:1"]
        self.errors = TemporaryFile()
        try:
            self.process = Popen(command, stdout=PIPE, stderr=self.errors,
                                 creationflags=CREATE_NO_WINDOW)
        except OSError:
            self.errors.close()
            raise
        self.ready = Condition()
        self.packet = None
        self.finished = False
        self.reader = Thread(target=self._read_latest, daemon=True)
        self.reader.start()

    def _read_latest(self):
        pipe = self.process.stdout
        try:
            while True:
                header = pipe.read(14)
                if len(header) != 14 or header[:2] != b"BM":
                    break
                size = int.from_bytes(header[2:6], "little")
                if not 54 <= size <= 128 * 1024 * 1024:
                    break
                payload = pipe.read(size - len(header))
                if len(payload) != size - len(header):
                    break
                with self.ready:
                    self.packet = header + payload
                    self.ready.notify()
        finally:
            with self.ready:
                self.finished = True
                self.ready.notify_all()

    def read(self):
        with self.ready:
            self.ready.wait_for(lambda: self.packet is not None or self.finished, timeout=5)
            packet = self.packet
            self.packet = None
        if packet is not None:
            frame = cv2.imdecode(np.frombuffer(packet, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is not None:
                return True, frame
        self.errors.seek(0)
        detail = self.errors.read(4096).decode(errors="replace").strip()
        message = "No frames from OBS Virtual Camera. Start it in OBS and leave OBS open."
        if detail:
            message += f"\n{detail}"
        raise RuntimeError(message)

    def release(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.reader.join()
        self.process.stdout.close()
        self.errors.close()
