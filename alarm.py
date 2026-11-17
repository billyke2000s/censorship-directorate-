"""Decision logic independent of the camera and graphical interface."""

from math import dist
from secrets import choice


OPEN_THRESHOLD = 0.30
CLOSED_THRESHOLD = 0.22
COVER_DELAY = 0.35
POSE_SECONDS = 0.45
CHALLENGE_SECONDS = 15

LIP_OUTLINE = (78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308,
               324, 318, 402, 317, 14, 87, 178, 88, 95)


def mouth_ratio(points):
    width = dist(points[78], points[308])
    if width < 1:
        return None
    gaps = ((82, 87), (13, 14), (312, 317))
    return sum(dist(points[top], points[bottom]) for top, bottom in gaps) / (3 * width)


class Monitor:
    def __init__(self):
        self.cover_started = None
        self.steps = []
        self.deadline = None
        self.held_since = None
        self.result = None

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
