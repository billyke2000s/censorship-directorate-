"""Responsive, image-free live console renderer for Censorship Directorate.

The reference artwork is promotional; every label and bar shown here uses the
real camera/microphone state rather than compositing a prerecorded portrait.
"""
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1536, 1024
RED = (47, 45, 255)             # OpenCV uses BGR
RED_DIM = (25, 18, 135)
DARK = (8, 5, 8)
WHITE = (245, 242, 245)
MUTED = (193, 186, 198)
LEFT = (18, 114, 1060, 1002)
RIGHT = (1083, 115, 1520, 1003)
FONT = cv2.FONT_HERSHEY_DUPLEX


@lru_cache(maxsize=32)
def _font(size, bold=False):
    if bold:
        paths = ("C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    else:
        paths = ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    for path in paths:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


@lru_cache(maxsize=512)
def _text_sprite(value, size, rgb_color, bold):
    font = _font(size, bold)
    bounds = font.getbbox(value)
    w = max(1, bounds[2]-bounds[0]+4)
    h = max(1, bounds[3]-bounds[1]+4)
    sprite = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sprite).text((2-bounds[0], 2-bounds[1]), value, font=font,
                                fill=(*rgb_color, 255))
    rgba = np.asarray(sprite)
    return rgba[:,:,:3][:,:,::-1].copy(), rgba[:,:,3].copy()


def _label(image, text, x, baseline, size=1., color=WHITE, thickness=2):
    # Fonts are antialiased and cached as small sprites, not rendered anew each frame.
    value = str(text)
    point_size = max(12, round(32 * size))
    color_rgb = tuple(int(c) for c in reversed(color))
    glyph, alpha = _text_sprite(value, point_size, color_rgb, thickness >= 2)
    h,w = alpha.shape
    x = int(x)
    y = int(baseline - h + 2)
    x0,y0 = max(0,x),max(0,y)
    x1,y1 = min(image.shape[1],x+w),min(image.shape[0],y+h)
    if x1 <= x0 or y1 <= y0: return
    crop_g = glyph[y0-y:y1-y, x0-x:x1-x].astype(np.float32)
    crop_a = alpha[y0-y:y1-y, x0-x:x1-x].astype(np.float32)[:,:,None]/255.
    dst = image[y0:y1,x0:x1].astype(np.float32)
    image[y0:y1,x0:x1] = (crop_g*crop_a + dst*(1.-crop_a)).astype(np.uint8)


def _glowing_frame(image, left, top, right, bottom, *, active=True):
    # Localized overlays avoid blurring a 1536x1024 frame on every camera refresh.
    if not active:
        cv2.rectangle(image, (left, top), (right, bottom), (66, 60, 74), 2)
        return
    cv2.rectangle(image, (left - 3, top - 3), (right + 3, bottom + 3), RED_DIM, 7)
    cv2.rectangle(image, (left, top), (right, bottom), RED, 2, cv2.LINE_AA)
    cv2.rectangle(image, (left + 3, top + 3), (right - 3, bottom - 3), (31, 21, 84), 1)


def _eye(image, x=68, y=46):
    pts = np.array([(x-40,y),(x-22,y-24),(x,y-29),(x+23,y-23),(x+40,y),
                    (x+23,y+23),(x,y+29),(x-23,y+23)], np.int32)
    cv2.polylines(image, [pts], True, WHITE, 6, cv2.LINE_AA)
    cv2.circle(image, (x,y), 14, WHITE, -1, cv2.LINE_AA)
    cv2.circle(image, (x,y), 7, RED, -1, cv2.LINE_AA)


def _triangle(image, x, y):
    pts = np.array([(x, y-35), (x-39, y+32), (x+39,y+32)], np.int32)
    cv2.polylines(image, [pts], True, WHITE, 5, cv2.LINE_AA)
    _label(image, '!', x-6, y+19, 1.22, WHITE, 3)


def _crop_preview(frame, w, h):
    fh, fw = frame.shape[:2]
    # Fill the camera area, preserving the webcam aspect ratio.
    scale = max(w / fw, h / fh)
    outw, outh = max(w, round(fw*scale)), max(h, round(fh*scale))
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    result = cv2.resize(frame, (outw, outh), interpolation=interpolation)
    x, y = (outw - w)//2, (outh - h)//2
    return result[y:y+h, x:x+w]


@lru_cache(maxsize=1)
def _background():
    canvas = np.full((HEIGHT, WIDTH, 3), DARK, np.uint8)
    # Dark red chrome; generous fixed layout scales as one unit on resize.
    cv2.rectangle(canvas, (0,0), (WIDTH-1,93), (17, 3, 43), -1)
    _glowing_frame(canvas, 2, 2, 1533, 93)
    _eye(canvas)
    _label(canvas, 'CENSORSHIP DIRECTORATE', 134, 50, 1.28, WHITE, 2)
    _label(canvas, 'S P E E C H  /  E X P R E S S I O N  /  C O M P L I A N C E',
           137, 78, 0.48, MUTED, 1)
    cv2.rectangle(canvas, (963,20), (1269,76), (34, 8, 56), -1)
    _glowing_frame(canvas, 963, 20, 1269, 76)
    cv2.circle(canvas, (992,49), 11, RED, -1, cv2.LINE_AA)
    _label(canvas, 'LIVE SURVEILLANCE', 1009, 58, 0.66, WHITE, 2)
    # Status-bar style symbols are visual only; OS title-bar buttons remain native.
    cv2.line(canvas, (1340,46), (1366,46), WHITE, 3, cv2.LINE_AA)
    cv2.rectangle(canvas, (1403,33), (1425,55), WHITE, 2, cv2.LINE_AA)
    cv2.line(canvas, (1464,33), (1491,60), WHITE, 3, cv2.LINE_AA)
    cv2.line(canvas, (1491,33), (1464,60), WHITE, 3, cv2.LINE_AA)

    cv2.rectangle(canvas, (LEFT[0], LEFT[1]), (LEFT[2], LEFT[3]), (13,9,13), -1)
    _glowing_frame(canvas, *LEFT)
    cv2.rectangle(canvas, (RIGHT[0], RIGHT[1]), (RIGHT[2], RIGHT[3]), (10,8,12), -1)
    cv2.rectangle(canvas, (RIGHT[0], RIGHT[1]), (RIGHT[2], RIGHT[3]), (75,65,77), 2)

    # The warning heading is dynamic; draw its background here.
    cv2.rectangle(canvas, (1088,118), (1515,220), (19,5,80), -1)
    _glowing_frame(canvas, 1087, 117, 1516, 220)
    _triangle(canvas, 1133, 170)
    for yy in (467, 757):
        cv2.line(canvas, (1109,yy), (1494,yy), (101,95,105), 2, cv2.LINE_AA)
    cv2.rectangle(canvas, (1106,809), (1501,967), (27,5,30), -1)
    _glowing_frame(canvas, 1106,809,1501,967)
    return canvas


def render_console(frame, reasons, status, mic_status, reading, window_size=None,
                   audio_history=None):
    """Render the live camera and data; returns BGR frame for cv2.imshow."""
    display = _background().copy()
    x0,y0,x1,y1 = LEFT
    display[y0+5:y1-4, x0+5:x1-4] = _crop_preview(
        frame, x1-x0-9, y1-y0-9)
    # Border is red only for real warnings, gray at rest.
    _glowing_frame(display, *LEFT, active=bool(reasons))

    _label(display, 'ALARM ACTIVE' if reasons else 'UNDER OBSERVATION',
           1206, 177, 0.99, WHITE, 2)
    if reasons:
        for index, reason in enumerate(reasons[:6]):
            yy = 279 + index*39
            cv2.rectangle(display, (1118,yy-17), (1133,yy-2), RED, -1)
            _label(display, reason, 1148, yy, 0.67, RED, 2)
        if len(reasons) > 6:
            _label(display, f'+{len(reasons)-6} MORE', 1148, 279+6*39, .55, MUTED, 1)
    else:
        _label(display, 'NO ACTIVE ALARMS', 1122, 285, .77, MUTED, 2)

    _label(display, 'Mouth:', 1116, 527, .82, WHITE, 2)
    _label(display, f'{reading} / 0.30', 1263, 527, .91,
           RED if status == 'Mouth open' else WHITE, 2)
    _label(display, 'Mic:', 1116, 595, .82, WHITE, 2)
    # A narrow second column cannot accommodate long audio-routing strings.
    label = mic_status.replace('Mic: ', '')
    if len(label) > 23:
        label = label[:21] + '...'
    _label(display, label, 1212, 595, .64, WHITE, 2)
    _label(display, 'Status:', 1116, 656, .82, WHITE, 2)
    if len(status) > 23:
        status = status[:21] + '...'
    _label(display, status, 1232, 656, .64, WHITE, 2)
    height, width = frame.shape[:2]
    _label(display, 'Camera:', 1116, 720, .77, WHITE, 2)
    _label(display, f'{width} x {height}', 1252, 720, .73, WHITE, 2)

    history = list(audio_history or ())[-55:]
    # Real mic levels; no fabricated waveform when microphone is unavailable.
    if history:
        history = [0.] * max(0, 55-len(history)) + history
    else:
        history = [0.] * 55
    mid = 888
    for i, level in enumerate(history):
        amplitude = int(min(68, max(2, max(0.,float(level))*60)))
        bx = 1117 + i*7
        cv2.line(display, (bx,mid-amplitude), (bx,mid+amplitude), RED, 3,
                 cv2.LINE_AA)

    window_width, window_height = window_size or (1280, 853)
    if window_width < 64 or window_height < 64:
        window_width, window_height = 1280,853
    scale = min(window_width/WIDTH, window_height/HEIGHT)
    out_width, out_height = max(1,round(WIDTH*scale)), max(1,round(HEIGHT*scale))
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    reduced = cv2.resize(display, (out_width, out_height), interpolation=interpolation)
    result = np.full((window_height,window_width,3), DARK, np.uint8)
    px,py = (window_width-out_width)//2,(window_height-out_height)//2
    result[py:py+out_height,px:px+out_width] = reduced
    return result