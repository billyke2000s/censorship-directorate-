import argparse
from io import BytesIO
from pathlib import Path
from threading import Thread
from time import monotonic
import wave
import winsound

import cv2
import mediapipe as mp
import numpy as np

from alarm import LIP_OUTLINE, OPEN_THRESHOLD, Monitor, head_turned, mouth_ratio
from speech import SpeechState, microphone


WINDOW = "Censorship System"
MODELS = ("face_landmarker.task", "hand_landmarker.task")
RED = (80, 89, 255)
GREEN = (110, 235, 125)
PANEL = (23, 24, 30)


def tv_tone():
    rate = 16000
    time = np.arange(int(rate * 0.28)) / rate
    fade = np.clip(np.minimum(time, 0.28 - time) * 180, 0, 1)
    samples = (np.sin(2 * np.pi * 1000 * time) * fade * 8500).astype("<i2")
    output = BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        audio.writeframes(samples.tobytes())
    return output.getvalue()


def pixel_points(landmarks, width, height):
    return [(point.x * width, point.y * height) for point in landmarks]


def hand_overlaps_mouth(hands, lips, width, height):
    outline = np.asarray(lips, dtype=np.float32)
    left, top = outline.min(axis=0)
    right, bottom = outline.max(axis=0)
    center = ((left + right) / 2, (top + bottom) / 2)
    probes = [
        (float(left + (right - left) * fraction), float(center[1]))
        for fraction in (0.25, 0.5, 0.75)
    ]
    # Use the palm and each finger separately to avoid filling gaps between fingers.
    groups = ((0, 1, 2, 5, 9, 13, 17), (1, 2, 3, 4), (5, 6, 7, 8),
              (9, 10, 11, 12), (13, 14, 15, 16), (17, 18, 19, 20))
    margin = max(3, (right - left) * 0.07)
    for hand in hands:
        points = pixel_points(hand, width, height)
        hulls = [
            cv2.convexHull(np.float32([points[index] for index in group]))
            for group in groups
        ]
        if sum(any(cv2.pointPolygonTest(hull, probe, True) >= -margin
                   for hull in hulls) for probe in probes) >= 2:
            return True
    return False


def create_landmarkers(directory, stack):
    from mediapipe.tasks.python import BaseOptions, vision

    mode = vision.RunningMode.VIDEO
    face = stack.enter_context(vision.FaceLandmarker.create_from_options(
        vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(directory / MODELS[0])),
            running_mode=mode,
            num_faces=2,
        )))
    hands = stack.enter_context(vision.HandLandmarker.create_from_options(
        vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(directory / MODELS[1])),
            running_mode=mode,
            num_hands=2,
        )))
    return face, hands


def draw_label(frame, label, y, color=(240, 240, 240), size=0.60, x=16):
    cv2.putText(frame, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, size, color, 1,
                cv2.LINE_AA)


def render_console(frame, reasons, prompt, status, mic_status, reading, result):
    screen = np.full((610, 950, 3), PANEL, dtype=np.uint8)
    screen[72:552, 16:656] = frame
    cv2.rectangle(screen, (15, 71), (656, 552), RED if reasons else (80, 83, 91), 1)
    cv2.rectangle(screen, (672, 72), (934, 552), (38, 40, 48), -1)
    color = RED if reasons else GREEN
    draw_label(screen, "CENSORSHIP SYSTEM", 39, RED, 0.95)
    draw_label(screen, "LIVE MONITOR", 38, (185, 186, 198), 0.58, 785)
    draw_label(screen, "ALARM ACTIVE" if reasons else "MONITORING", 110, color, 0.70, 688)
    for index, reason in enumerate(reasons):
        draw_label(screen, reason, 145 + index * 26, RED, 0.54, 688)
    if prompt:
        draw_label(screen, prompt, 342, (125, 218, 255), 0.49, 688)
    elif result:
        draw_label(screen, "MOUTH CHECK PASSED" if not result.startswith("CHEATING")
                   else "MOVEMENT NOT VERIFIED", 342, color, 0.52, 688)
    draw_label(screen, status, 411, size=0.56, x=688)
    draw_label(screen, f"MAR {reading}  /  {OPEN_THRESHOLD:.2f}", 448, size=0.54, x=688)
    draw_label(screen, mic_status, 482, size=0.54, x=688)
    draw_label(screen, "L  Movement check     R  Reset     Esc  Exit", 586, (205, 205, 215))
    return screen


def run_camera(camera_index, face, hands, speech, audio_stream):
    camera = cv2.VideoCapture(camera_index)
    if not camera.isOpened():
        camera.release()
        raise RuntimeError("Could not open webcam. Check Windows camera access or try --camera 1.")

    monitor = Monitor()
    tone = tv_tone()
    last_lips = None
    last_lips_at = last_beep = 0.0
    beep_reasons = []
    open_since = None
    timestamp = -1
    started = monotonic()
    try:
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        while True:
            if audio_stream is not None and not audio_stream.active:
                raise RuntimeError("The microphone stopped. Reconnect it and restart.")
            ok, image = camera.read()
            if not ok:
                raise RuntimeError("The webcam stopped sending frames.")
            frame = cv2.resize(cv2.flip(image, 1), (640, 480))
            now = monotonic()
            timestamp = max(timestamp + 1, int((now - started) * 1000))
            sample = mp.Image(image_format=mp.ImageFormat.SRGB,
                              data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            faces = face.detect_for_video(sample, timestamp).face_landmarks
            detected_hands = hands.detect_for_video(sample, timestamp).hand_landmarks
            ratio = None
            turned = False
            if len(faces) == 1:
                points = pixel_points(faces[0], 640, 480)
                ratio = mouth_ratio(points)
                turned = head_turned(points)
                last_lips = [points[index] for index in LIP_OUTLINE]
                last_lips_at = now

            overlap = (last_lips is not None and now - last_lips_at <= 0.8 and
                       hand_overlaps_mouth(detected_hands, last_lips, 640, 480))
            covered = monitor.update(now, ratio, overlap)
            is_open = ratio is not None and ratio >= OPEN_THRESHOLD
            if is_open and not overlap and not monitor.steps and monitor.result is None:
                if open_since is None:
                    open_since = now
                elif now - open_since >= 3:
                    monitor.challenge(now)
                    open_since = None
            else:
                open_since = None
            speaking = speech.active(now)
            reasons = monitor.camera_warnings(now, len(faces), turned)
            if covered:
                reasons.append("MOUTH COVERED")
            if speaking:
                reasons.append("SPEECH DETECTED")
            if monitor.result and monitor.result.startswith("CHEATING"):
                reasons.append("CHEATING? CHECK FAILED")
            if reasons and now - last_beep >= 0.9:
                speech.muted_until = now + 0.42
                Thread(target=winsound.PlaySound, args=(tone, winsound.SND_MEMORY),
                       daemon=True).start()
                last_beep = now
                beep_reasons = reasons.copy()
            if now - last_beep < 0.30:
                reasons = list(dict.fromkeys(beep_reasons + reasons))

            color = RED if is_open or covered else GREEN
            if len(faces) == 1:
                cv2.polylines(frame, [np.int32(last_lips)], True, color, 2, cv2.LINE_AA)
            status = "Mouth open" if is_open else (
                "Mouth closed" if ratio is not None else f"Faces tracked: {len(faces)}")
            reading = "--" if ratio is None else f"{ratio:.2f}"
            prompt = None
            if monitor.steps:
                pose = "Open" if monitor.steps[0] == "open" else "Close"
                prompt = f"{pose} mouth and hold  {max(0, monitor.deadline - now):.0f}s"
            mic_status = "Mic disabled" if audio_stream is None else "Mic listening"
            cv2.imshow(WINDOW, render_console(frame, reasons, prompt, status, mic_status,
                                               reading, monitor.result))
            key = cv2.waitKey(1) & 0xFF
            if key == 27 or cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break
            if key in (ord("l"), ord("L")):
                monitor.challenge(now)
            if key in (ord("r"), ord("R")):
                monitor = Monitor()
                open_since = None
    finally:
        camera.release()
        cv2.destroyAllWindows()


def main():
    from contextlib import ExitStack

    parser = argparse.ArgumentParser(description="Webcam mouth alarm for Windows")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--mic", type=int, help="Use this microphone device index")
    parser.add_argument("--no-mic", action="store_true", help="Run webcam checks only")
    parser.add_argument("--models", type=Path, default=Path.cwd() / "models")
    parser.add_argument("--check-models", action="store_true",
                        help="Load both models without opening the camera")
    args = parser.parse_args()
    try:
        missing = [name for name in MODELS if not (args.models / name).is_file()]
        if missing:
            raise RuntimeError("Missing models. Run setup-models.ps1 from the app folder.")
        with ExitStack() as stack:
            face, hands = create_landmarkers(args.models.resolve(), stack)
            if args.check_models:
                print("Face and hand landmark models loaded.")
            else:
                speech = SpeechState()
                stream = None
                if not args.no_mic:
                    try:
                        stream = microphone(args.mic, speech)
                    except (RuntimeError, OSError, ValueError, ImportError) as error:
                        raise RuntimeError(f"{error}. Check Windows microphone access or use --no-mic.") from error
                    stack.callback(stream.close)
                run_camera(args.camera, face, hands, speech, stream)
    except (RuntimeError, OSError, ValueError) as error:
        parser.exit(1, f"Mouth Alarm: {error}\n")


if __name__ == "__main__":
    main()
