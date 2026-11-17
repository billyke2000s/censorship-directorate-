"""Decision logic independent of the camera and graphical interface."""

from math import dist
from secrets import choice


OPEN_THRESHOLD = 0.30
CLOSED_THRESHOLD = 0.22
COVER_DELAY = 0.35
POSE_SECONDS = 0.45
CHALLENGE_SECONDS = 15
WARNING_DELAYS = {
    "FACE NOT VISIBLE": 1.0,
    "MULTIPLE FACES": 1.0,
    "HEAD TURNED AWAY": 2.0,
}

LIP_OUTLINE = (78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308,
               324, 318, 402, 317, 14, 87, 178, 88, 95)


def mouth_ratio(points):
    width = dist(points[78], points[308])
    if width < 1:
        return None
    gaps = ((82, 87), (13, 14), (312, 317))
    return sum(dist(points[top], points[bottom]) for top, bottom in gaps) / (3 * width)


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
        self.steps = []
        self.deadline = None
        self.held_since = None
        self.result = None
        self.warning_since = {}

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
        return active

    def challenge(self, now, first=None):
        first = first or choice(("open", "closed"))
        second = "closed" if first == "open" else "open"
        self.steps = [first, second, first]
        self.deadline = now + CHALLENGE_SECONDS
        self.held_since = None
        self.result = None

    def update(self, now, ratio, hand_over_mouth):
        if hand_over_mouth:
            if self.cover_started is None:
                self.cover_started = now
        else:
            self.cover_started = None
        covered = self.cover_started is not None and now - self.cover_started >= COVER_DELAY

        if self.steps:
            expected = self.steps[0]
            if now >= self.deadline:
                self.steps.clear()
                self.result = "CHEATING? | Mouth movement not verified"
            elif hand_over_mouth or ratio is None:
                self.held_since = None
            elif (expected == "open" and ratio >= OPEN_THRESHOLD or
                  expected == "closed" and ratio <= CLOSED_THRESHOLD):
                if self.held_since is None:
                    self.held_since = now
                elif now - self.held_since >= POSE_SECONDS:
                    self.steps.pop(0)
                    self.held_since = None
                    if not self.steps:
                        self.result = "Mouth movement verified"
            else:
                self.held_since = None

        return covered
