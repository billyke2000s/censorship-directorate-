"""Decision logic independent of the camera and graphical interface."""

from math import dist


OPEN_THRESHOLD = 0.30
CLOSED_THRESHOLD = 0.22
COVER_DELAY = 0.35
STILL_SECONDS = 5
WARNING_DELAYS = {
    "FACE NOT VISIBLE": 1.0,
    "MULTIPLE FACES": 1.0,
    "HEAD TURNED AWAY": 2.0,
}

LIP_OUTLINE = (61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291,
               375, 321, 405, 314, 17, 84, 181, 91, 146)


def mouth_ratio(points):
    width = dist(points[78], points[308])
    if width < 1:
        return None
    gaps = ((82, 87), (13, 14), (312, 317))
    return sum(dist(points[top], points[bottom]) for top, bottom in gaps) / (3 * width)


def mouth_open_alarm(ratio, hand_over_mouth, was_open):
    threshold = CLOSED_THRESHOLD if was_open else OPEN_THRESHOLD
    return not hand_over_mouth and ratio is not None and ratio >= threshold


def head_turned(points):
    left, right, nose = points[33], points[263], points[1]
    eye_x, eye_y = right[0] - left[0], right[1] - left[1]
    width_squared = eye_x ** 2 + eye_y ** 2
    if width_squared < 1:
        return False
    projection = ((nose[0] - left[0]) * eye_x + (nose[1] - left[1]) * eye_y) / width_squared
    return not 0.18 <= projection <= 0.82


class Monitor:
    def __init__(self):
        self.cover_started = None
        self.warning_since = {}
        self.still_since = None

    def observe_stillness(self, now, stable):
        if not stable:
            self.still_since = None
            return
        if self.still_since is None:
            self.still_since = now

    def camera_warnings(self, now, face_count, turned):
        observed = {
            "FACE NOT VISIBLE": face_count == 0,
            "MULTIPLE FACES": face_count > 1,
            "HEAD TURNED AWAY": face_count == 1 and turned,
        }
        active = []
        for name, delay in WARNING_DELAYS.items():
            if observed[name]:
                since = self.warning_since.setdefault(name, now)
                if now - since >= delay:
                    active.append(name)
            else:
                self.warning_since.pop(name, None)
        if self.still_since is not None and now - self.still_since >= STILL_SECONDS:
            active.append("FACE IMAGE STILL")
        return active

    def mouth_covered(self, now, hand_over_mouth):
        if hand_over_mouth:
            if self.cover_started is None:
                self.cover_started = now
        else:
            self.cover_started = None
        return self.cover_started is not None and now - self.cover_started >= COVER_DELAY
