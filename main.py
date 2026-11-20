import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
import wave
import winsound

import cv2
import mediapipe as mp
import numpy as np

from alarm import LIP_OUTLINE, OPEN_THRESHOLD, Monitor, head_turned, mouth_open_alarm, mouth_ratio
from camera_capture import LatestCamera
from camera_select import choose_camera
from console_ui import render_console
from speech import SpeechState, microphone


WINDOW = "Censorship Directorate"
MODELS = ("face_landmarker.task", "hand_landmarker.task")
RED = (58, 61, 255)
GREEN = (110, 235, 125)


def write_tv_tone(path):
    rate = 16000
    time = np.arange(rate * 2) / rate
    samples = (np.sin(2 * np.pi * 1000 * time) * 8500).astype("<i2")
    with wave.open(str(path), "wb") as audio:
        audio.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        audio.writeframes(samples.tobytes())


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
    mouth_width = right - left
    margin = max(4, mouth_width * 0.16)
    for hand in hands:
        points = pixel_points(hand, width, height)
        hulls = [
            cv2.convexHull(np.float32([points[index] for index in group]))
            for group in groups
        ]
        distances = [max(cv2.pointPolygonTest(hull, probe, True) for hull in hulls)
                     for probe in probes]
        if sum(distance >= -margin for distance in distances) >= 2 or distances[1] >= 0:
            return True
        # Curled fingertips and foreshortened joints can shrink the individual hulls.
        mouth_height = max(bottom - top, mouth_width * 0.24)
        mouth_box = np.float32([
            (left, center[1] - mouth_height / 2), (right, center[1] - mouth_height / 2),
            (right, center[1] + mouth_height / 2), (left, center[1] + mouth_height / 2),
        ])
        hand_hull = cv2.convexHull(np.float32(points))
        if len(hand_hull) >= 3 and mouth_width > 0:
            area, _ = cv2.intersectConvexConvex(mouth_box, hand_hull)
            if area >= 0.35 * mouth_width * mouth_height:
                return True
    return False


def project_mouth(lips, previous_eyes, eyes):
    """Move the last clear lip position with the current eye line."""
    old_left, old_right = map(complex_point, previous_eyes)
    left, right = map(complex_point, eyes)
    if abs(old_right - old_left) < 1 or abs(right - left) < 1:
        return lips
    scale_rotation = (right - left) / (old_right - old_left)
    projected = [left + (complex_point(point) - old_left) * scale_rotation for point in lips]
    return [(point.real, point.imag) for point in projected]


def complex_point(point):
    return complex(float(point[0]), float(point[1]))


def draw_face_corners(frame, points, active):
    height, width = frame.shape[:2]
    bounds = np.asarray([points[index] for index in (10, 152, 234, 454)])
    left, top = bounds.min(axis=0)
    right, bottom = bounds.max(axis=0)
    # FaceMesh landmarks follow the face, not the outer hairstyle.
    # Expand the tracking frame to include the forehead, hair and chin.
    horizontal = max(6, (right - left) * 0.17)
    vertical = max(6, (bottom - top) * 0.20)
    left, top = max(0, round(left - horizontal)), max(0, round(top - vertical * 1.4))
    right = min(width - 1, round(right + horizontal))
    bottom = min(height - 1, round(bottom + vertical * 0.45))
    length = round(min(right - left, bottom - top) * 0.19)
    if length < 3:
        return
    color = RED if active else (90, 100, 225)
    thickness = max(2, width // 600)
    for x, y, dx, dy in ((left, top, 1, 1), (right, top, -1, 1),
                         (left, bottom, 1, -1), (right, bottom, -1, -1)):
        cv2.polylines(frame, [np.int32([(x + dx * length, y), (x, y),
                                      (x, y + dy * length)])],
                      False, color, thickness, cv2.LINE_AA)


def face_sample(gray_frame, points):
    outline = np.array([points[index] for index in (10, 152, 234, 454)])
    height, width = gray_frame.shape
    left, top = np.maximum(outline.min(axis=0), (0, 0)).astype(int)
    right, bottom = np.minimum(outline.max(axis=0), (width, height)).astype(int)
    if right - left < 16 or bottom - top < 16:
        return None
    crop = gray_frame[top:bottom, left:right]
    return cv2.resize(crop, (48, 48), interpolation=cv2.INTER_AREA)


def lens_likely_covered(frame):
    preview = cv2.resize(frame, (96, 54), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(preview, cv2.COLOR_BGR2GRAY)
    # Ignore dark borders and small bright spots around the edge of a cover.
    center = gray[5:-5, 9:-9].astype(np.float32)
    low, high = np.percentile(center, (5, 95))
    if high <= 24:
        return True
    texture = (np.abs(np.diff(center, axis=0)).mean() +
               np.abs(np.diff(center, axis=1)).mean()) / 2
    return high - low <= 13 and texture <= 1.6


def side_profile_visible(detector, frame):
    height, width = frame.shape[:2]
    scale = min(1, 480 / max(width, height))
    small = cv2.resize(frame, (max(1, round(width * scale)), max(1, round(height * scale))),
                       interpolation=cv2.INTER_AREA)
    gray = cv2.equalizeHist(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))
    options = dict(scaleFactor=1.15, minNeighbors=5, minSize=(42, 42))
    return (len(detector.detectMultiScale(gray, **options)) > 0 or
            len(detector.detectMultiScale(cv2.flip(gray, 1), **options)) > 0)


def create_landmarkers(directory, stack):
    from mediapipe.tasks.python import BaseOptions, vision

    mode = vision.RunningMode.VIDEO
    face = stack.enter_context(vision.FaceLandmarker.create_from_options(
        vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(directory / MODELS[0])),
            running_mode=mode,
            num_faces=2,
            output_facial_transformation_matrixes=True,
        )))
    hands = stack.enter_context(vision.HandLandmarker.create_from_options(
        vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(directory / MODELS[1])),
            running_mode=mode,
            num_hands=2,
            min_hand_detection_confidence=0.40,
            min_hand_presence_confidence=0.40,
        )))
    return face, hands


def tracking_frame(frame, limit=960):
    height, width = frame.shape[:2]
    if max(height, width) <= limit:
        return frame
    scale = limit / max(height, width)
    return cv2.resize(frame, (round(width * scale), round(height * scale)),
                      interpolation=cv2.INTER_AREA)


def camera_resolution(value):
    try:
        width, height = (int(part) for part in value.lower().split("x"))
        if width > 0 and height > 0:
            return width, height
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("Use WIDTHxHEIGHT, for example 3840x2160")


def first_camera_frame(camera, requested, fallback=None):
    default = (int(camera.get(cv2.CAP_PROP_FRAME_WIDTH)),
               int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    modes = ((requested, default) if requested else sorted(
        ((3840, 2160), (2560, 1440), (1920, 1080), default),
        key=lambda mode: mode[0] * mode[1], reverse=True))
    best = None
    for width, height in dict.fromkeys(modes):
        if width > 0 and height > 0:
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        ok, frame = camera.read()
        if not ok:
            continue
        received = (frame.shape[1], frame.shape[0])
        if received == (width, height) and (best is None or
                                             received[0] * received[1] >= best[0]):
            return frame
        area = received[0] * received[1]
        if best is None or area > best[0]:
            best = (area, (width, height))
    if best is not None:
        width, height = best[1]
        if width > 0 and height > 0:
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        ok, frame = camera.read()
        if ok:
            return frame
    if fallback is not None:
        # OBS and other virtual cameras may ignore resolution negotiation but
        # have already provided a valid frame during device discovery.
        return fallback
    raise RuntimeError("The webcam did not send frames at the requested or default resolution.")


def run_camera(resolution, face, hands, speech, audio_stream, cable, tone,
               camera_index=None, camera_backend=None):
    # Keep timestamps increasing across camera discovery and normal tracking.
    probe_timestamp = -1

    def face_present(candidate):
        nonlocal probe_timestamp
        frame = cv2.flip(candidate, 1)
        probe_timestamp = max(probe_timestamp + 1, int(monotonic() * 1000))
        sample = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=cv2.cvtColor(tracking_frame(frame), cv2.COLOR_BGR2RGB)
        )
        return bool(face.detect_for_video(sample, probe_timestamp).face_landmarks)

    camera, first_image, selected_index, selected_backend = choose_camera(
        face_present, requested_index=camera_index,
        requested_backend=camera_backend,
    )
    print(f"Using camera {selected_index} (OpenCV backend {selected_backend}).")

    monitor = Monitor()
    profile_detector = cv2.CascadeClassifier(
        str(Path(cv2.data.haarcascades) / "haarcascade_profileface.xml"))
    next_profile_check = 0.0
    last_lips = None
    last_eyes = None
    last_lips_at = 0.0
    cover_in_progress = False
    still_reference = None
    last_sample_at = 0.0
    is_open = False
    timestamp = probe_timestamp
    started = monotonic()
    try:
        image = first_camera_frame(camera, resolution, first_image)
        camera = LatestCamera(camera)
        ok = True
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW, 1280, 853)
        window_size = (1280, 853)
        while True:
            if audio_stream is not None and not audio_stream.active:
                raise RuntimeError("The microphone stopped. Reconnect it and restart.")
            if cable is not None and not cable.active:
                raise RuntimeError("The virtual cable stopped. Restart the app.")
            if speech.error is not None:
                raise RuntimeError(f"Voice detection stopped: {speech.error}")
            if not ok:
                raise RuntimeError("The webcam stopped sending frames.")
            frame = cv2.flip(image, 1)
            height, width = frame.shape[:2]
            now = monotonic()
            timestamp = max(timestamp + 1, int(now * 1000))
            sample = mp.Image(image_format=mp.ImageFormat.SRGB,
                              data=cv2.cvtColor(tracking_frame(frame), cv2.COLOR_BGR2RGB))
            face_result = face.detect_for_video(sample, timestamp)
            faces = face_result.face_landmarks
            detected_hands = hands.detect_for_video(sample, timestamp).hand_landmarks
            ratio = None
            turned = False
            current_lips = None
            eyes = None
            if len(faces) == 1:
                points = pixel_points(faces[0], width, height)
                ratio = mouth_ratio(points)
                transforms = face_result.facial_transformation_matrixes
                turned = head_turned(points, transforms[0] if transforms else None)
                current_lips = [points[index] for index in LIP_OUTLINE]
                eyes = (points[33], points[263])

            # Keep the last clear outline while the model is fitting landmarks to a hand.
            previous_lips = last_lips if cover_in_progress or now - last_lips_at <= 1.25 else None
            if previous_lips is not None and eyes is not None and not turned:
                previous_lips = project_mouth(previous_lips, last_eyes, eyes)
            overlap = len(faces) < 2 and any(
                hand_overlaps_mouth(detected_hands, lips, width, height)
                for lips in (current_lips, previous_lips) if lips is not None
            )
            covered = monitor.mouth_covered(now, overlap)
            cover_in_progress = overlap or covered
            if current_lips is not None and not cover_in_progress:
                last_lips = current_lips
                last_eyes = eyes
                last_lips_at = now
            overlap = cover_in_progress
            if current_lips is None or overlap or turned:
                still_reference = None
                monitor.observe_stillness(now, False)
            elif now - last_sample_at >= 0.25:
                last_sample_at = now
                sample = face_sample(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), points)
                stable = sample is not None and still_reference is not None and (
                    cv2.mean(cv2.absdiff(sample, still_reference))[0] <= 1.2)
                if not stable:
                    still_reference = sample
                monitor.observe_stillness(now, stable)
            is_open = mouth_open_alarm(ratio, overlap, is_open)
            speaking = speech.active(now)
            lens_obscured = not faces and lens_likely_covered(frame)
            profile = False
            if not faces and not lens_obscured and now >= next_profile_check:
                next_profile_check = now + 0.30
                if not profile_detector.empty():
                    profile = side_profile_visible(profile_detector, frame)
            reasons = monitor.camera_warnings(now, len(faces), turned, lens_obscured, profile)
            if covered:
                reasons.append("MOUTH COVERED")
            if is_open:
                reasons.append("MOUTH OPEN")
            speech.camera_alarm = bool(reasons)
            speech.camera_checked_at = monotonic()
            if speaking:
                reasons.append("MIC: VOICE DETECTED")
            if cable is None and bool(reasons) != speech.alarm_playing:
                speech.muted_until = now + 0.10
                speech.alarm_playing = bool(reasons)
                if reasons:
                    winsound.PlaySound(str(tone), winsound.SND_FILENAME | winsound.SND_ASYNC |
                                       winsound.SND_LOOP | winsound.SND_NODEFAULT)
                else:
                    winsound.PlaySound(None, 0)

            color = RED if is_open or covered else GREEN
            for face_landmarks in faces:
                face_points = points if len(faces) == 1 else pixel_points(face_landmarks, width, height)
                draw_face_corners(frame, face_points, bool(reasons))
            if len(faces) == 1:
                outline = np.int32([points[index] for index in LIP_OUTLINE])
                cv2.polylines(frame, [outline], True, color, max(2, width // 450), cv2.LINE_AA)
            status = "Mouth open" if is_open else (
                "Mouth closed" if ratio is not None else f"Faces tracked: {len(faces)}")
            if "HEAD TURNED AWAY" in reasons:
                status = "Head turned away"
            reading = "--" if ratio is None else f"{ratio:.2f}"
            mic_status = "Mic disabled" if audio_stream is None else "Mic: Voice detection"
            if cable is not None:
                mic_status = "Virtual mic -> CABLE Output"
            cv2.imshow(WINDOW, render_console(frame, reasons, status, mic_status, reading,
                                               window_size, audio_history=speech.waveform))
            cv2.waitKey(1)
            if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break
            _, _, window_width, window_height = cv2.getWindowImageRect(WINDOW)
            window_size = (window_width, window_height)
            ok, image = camera.read()
    finally:
        speech.camera_checked_at = 0.0
        if speech.alarm_playing:
            winsound.PlaySound(None, 0)
        camera.release()
        cv2.destroyAllWindows()


def main():
    from contextlib import ExitStack

    parser = argparse.ArgumentParser(description="Webcam mouth alarm for Windows")
    parser.add_argument("--resolution", type=camera_resolution,
                        help="Request WIDTHxHEIGHT; defaults to trying up to 3840x2160")
    parser.add_argument("--camera", type=int,
                        help="Force a camera index (0-9), rather than scan for a face")
    parser.add_argument("--camera-backend", choices=("dshow", "msmf", "auto"),
                        help="Force a Windows capture backend (default: scan them all)")
    parser.add_argument("--mic", type=int, help="Use this microphone device index")
    parser.add_argument("--no-mic", action="store_true", help="Run webcam checks only")
    parser.add_argument("--virtual-mic", action="store_true", help="Send filtered audio to VB-CABLE")
    parser.add_argument("--cable-device", type=int, help="Override the virtual cable output device index")
    parser.add_argument("--models", type=Path, default=Path.cwd() / "models")
    parser.add_argument("--check-models", action="store_true",
                        help="Load both models without opening the camera")
    args = parser.parse_args()
    if args.virtual_mic and args.no_mic:
        parser.error("--virtual-mic requires an input microphone")
    if args.cable_device is not None and not args.virtual_mic:
        parser.error("--cable-device requires --virtual-mic")
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
                stream = cable = None
                if not args.no_mic:
                    try:
                        stream, cable = stack.enter_context(microphone(
                            args.mic, speech,
                            virtual_mic=args.virtual_mic, cable_device=args.cable_device))
                    except (RuntimeError, OSError, ValueError, ImportError) as error:
                        raise RuntimeError(f"{error}. Check Windows microphone access or use --no-mic.") from error
                temp_dir = stack.enter_context(TemporaryDirectory(prefix="mouth-alarm-"))
                tone = Path(temp_dir) / "alarm.wav"
                write_tv_tone(tone)
                run_camera(
                    args.resolution, face, hands, speech, stream, cable, tone,
                    camera_index=args.camera,
                    camera_backend={"dshow": cv2.CAP_DSHOW,
                                    "msmf": cv2.CAP_MSMF,
                                    "auto": cv2.CAP_ANY}.get(args.camera_backend),
                )
    except (RuntimeError, OSError, ValueError, ImportError) as error:
        parser.exit(1, f"Mouth Alarm: {error}\n")


if __name__ == "__main__":
    main()
