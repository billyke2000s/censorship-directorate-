import argparse
from pathlib import Path
from threading import Thread
from time import monotonic
import winsound

import cv2
import mediapipe as mp
import numpy as np

from alarm import LIP_OUTLINE, OPEN_THRESHOLD, Monitor, mouth_ratio
from speech import SpeechState, microphone


WINDOW = "Mouth Alarm"
MODELS = ("face_landmarker.task", "hand_landmarker.task")


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
        )))
    hands = stack.enter_context(vision.HandLandmarker.create_from_options(
        vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(directory / MODELS[1])),
            running_mode=mode,
            num_hands=2,
        )))
    return face, hands


def draw_label(frame, label, y, color=(240, 240, 240), size=0.60):
    cv2.putText(frame, label, (16, y), cv2.FONT_HERSHEY_SIMPLEX, size, color, 2,
                cv2.LINE_AA)


def run_camera(camera_index, face, hands, speech, audio_stream):
    camera = cv2.VideoCapture(camera_index)
    if not camera.isOpened():
        camera.release()
        raise RuntimeError("Could not open webcam. Check Windows camera access or try --camera 1.")

    monitor = Monitor()
    last_lips = None
    last_lips_at = last_beep = 0.0
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
            if faces:
                points = pixel_points(faces[0], 640, 480)
                ratio = mouth_ratio(points)
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
            if (covered or speaking) and now - last_beep >= 0.75:
                speech.muted_until = now + 0.35
                Thread(target=winsound.Beep, args=(1000, 130), daemon=True).start()
                last_beep = now

            red = (75, 85, 255)
            green = (110, 235, 125)
            color = red if is_open or covered else green
            if faces:
                cv2.polylines(frame, [np.int32(last_lips)], True, color, 2, cv2.LINE_AA)
            status = "MOUTH COVERED" if covered else "MOUTH OPEN - ALARM" if is_open else (
                "Mouth closed" if ratio is not None else "Face not tracked")
            frame[:92] = (22, 22, 22)
            frame[-60:] = (22, 22, 22)
            draw_label(frame, status, 30, color if ratio is not None or covered else (235, 235, 235))
            reading = "--" if ratio is None else f"{ratio:.2f}"
            draw_label(frame, f"MAR {reading}   |   Open threshold {OPEN_THRESHOLD:.2f}", 59)
            if monitor.steps:
                pose = "Open your mouth" if monitor.steps[0] == "open" else "Close your mouth"
                draw_label(frame, f"{pose} and hold  |  {max(0, monitor.deadline - now):.0f}s",
                           84)
            elif monitor.result:
                draw_label(frame, monitor.result, 84,
                           red if monitor.result.startswith("CHEATING") else green)
            mic_status = "Mic disabled" if audio_stream is None else (
                "SPEECH DETECTED" if speaking else "Mic listening")
            draw_label(frame, mic_status, 477, red if speaking else (240, 240, 240))
            draw_label(frame, "L  Mouth movement check   |   R  Reset   |   Esc  Exit", 454)
            cv2.imshow(WINDOW, frame)
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
