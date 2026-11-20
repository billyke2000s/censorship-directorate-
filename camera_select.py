"""Find a usable Windows webcam, preferring a feed that actually contains a face.

Probing is sequential; each unsuccessful capture is released before trying another.
No camera is required to contain a face: the first working camera is the fallback.
"""
import json
from pathlib import Path

import cv2


PREFERENCE_FILE = Path.home() / ".censorship-directorate-camera.json"


def available_backends():
    """DirectShow often sees OBS virtual cameras that Media Foundation doesn't."""
    return tuple(dict.fromkeys(
        (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY)
    ))


def read_working_frame(capture, attempts=4):
    for _ in range(attempts):
        ok, frame = capture.read()
        if ok and frame is not None and getattr(frame, "size", 0) > 0:
            return frame
    return None


def load_preferred(path=PREFERENCE_FILE):
    try:
        info = json.loads(Path(path).read_text(encoding="utf-8"))
        index = int(info["index"])
        backend = int(info["backend"])
        if 0 <= index <= 9 and backend in available_backends():
            return index, backend
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        pass
    return None


def save_preferred(index, backend, path=PREFERENCE_FILE):
    try:
        Path(path).write_text(
            json.dumps({"index": index, "backend": backend}), encoding="utf-8"
        )
    except OSError:
        pass  # Camera selection must work even if the home directory is read-only.


def choose_camera(face_present, *, requested_index=None, requested_backend=None,
                  capture_factory=None, max_index=9, preference=None):
    """Return (capture, first_frame, index, backend).

    face_present(frame) is called only for frames that actually arrived. A face
    match wins immediately; if no camera sees a face, retry working devices in
    discovery order. The caller owns and must release the selected capture.
    """
    if requested_index is not None and not 0 <= requested_index <= max_index:
        raise ValueError(f"Camera index must be between 0 and {max_index}.")
    factory = capture_factory or cv2.VideoCapture
    indexes = (requested_index,) if requested_index is not None else tuple(range(max_index + 1))
    backends = (requested_backend,) if requested_backend is not None else available_backends()
    pairs = [(idx, backend) for idx in indexes for backend in backends]
    if preference is None and requested_index is None and requested_backend is None:
        preference = load_preferred()
    if preference in pairs:
        pairs.remove(preference)
        pairs.insert(0, preference)

    working = []
    for index, backend in pairs:
        camera = None
        try:
            camera = factory(index, backend)
            if camera is None or not camera.isOpened():
                continue
            frame = read_working_frame(camera)
            if frame is None:
                continue
            working.append((index, backend))
            if face_present(frame):
                save_preferred(index, backend)
                selected = camera
                camera = None  # Keep the working capture open for the caller.
                return selected, frame, index, backend
        except (OSError, RuntimeError, cv2.error) as error:
            print(f"Camera {index} ({backend}) failed: {error}")
        finally:
            if camera is not None:
                camera.release()

    # Reopen candidates in case one backend can no longer acquire its device.
    for index, backend in working:
        camera = None
        try:
            camera = factory(index, backend)
            if camera is not None and camera.isOpened():
                frame = read_working_frame(camera)
                if frame is not None:
                    save_preferred(index, backend)
                    chosen = camera
                    camera = None
                    return chosen, frame, index, backend
        except (OSError, RuntimeError, cv2.error):
            pass
        finally:
            if camera is not None:
                camera.release()
    raise RuntimeError(
        "No usable camera feed found. Tried camera indexes "
        f"{indexes[0]}-{indexes[-1]} with Windows camera backends. "
        "Start OBS Virtual Camera first and check Windows camera permissions. "
        "You can also pass --camera INDEX."
    )
