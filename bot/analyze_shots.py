"""Find camera cuts and faces in a stretch of a podcast video.

Usage (as a module): shots(source, start, end) -> list of
  {"start", "end", "faces": [(cx, cy, size, talk), ...]}   # source seconds; face centres in 0-1 of the
  frame; talk = mouth movement, higher for the person speaking
  cut_in(source, a, b) -> time of a camera cut inside [a, b], or None

Cuts are found where one frame differs sharply from the last (frames sampled at 10 fps).
Faces are found with YuNet (bot/models, OpenCV DNN) on a few frames per shot, then clustered so
each person counts once; people without a visible face come from the HOG people detector.
"""
import functools
import re
import subprocess

import cv2
import numpy as np

FPS = 10
W, H = 640, 360
_front = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
_prof = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")

# 2026-10-29 (rico: "faces are not in frame", "still not centering"): the Haar cascades missed profiles,
# dark faces and anything under 40 px. YuNet (OpenCV zoo, 230 KB, CPU) finds faces down to ~12 px at any
# angle; it is the detector for everything now. The Haar objects above stay only as a fallback when the
# model file is missing.
from pathlib import Path as _P
_YN_MODEL = str(_P(__file__).parent / "models" / "face_detection_yunet_2023mar.onnx")
_YN = {}


def _yunet(w, h):
    k = (w, h)
    if k not in _YN:
        try:
            _YN[k] = cv2.FaceDetectorYN.create(_YN_MODEL, "", (w, h), 0.55, 0.3, 5000)
        except Exception:
            _YN[k] = None
    return _YN[k]


def detect_faces(frame, min_conf=0.6):
    """[(cx, cy, size, conf)] in 0-1 of the frame (size = box width / frame width), biggest first."""
    h, w = frame.shape[:2]
    det = _yunet(w, h)
    out = []
    if det is not None:
        _, res = det.detect(frame)
        for r in (res if res is not None else []):
            x, y, bw, bh, conf = float(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[14])
            if conf >= min_conf and bw > 0:
                out.append(((x + bw / 2) / w, (y + bh / 2) / h, bw / w, conf))
    else:
        g = cv2.equalizeHist(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        for (x, y, bw, bh) in _front.detectMultiScale(g, 1.1, 6, minSize=(24, 24)):
            out.append(((x + bw / 2) / w, (y + bh / 2) / h, bw / w, 0.6))
    out.sort(key=lambda t: -t[2])
    return out


_HOG = None


def persons(frame):
    """Standing or seated people without a visible face (OpenCV's HOG people detector):
    [(cx, cy_top_third, width)] in 0-1, biggest first. Weak on close-ups; used only when no face is found."""
    global _HOG
    if _HOG is None:
        _HOG = cv2.HOGDescriptor()
        _HOG.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    h, w = frame.shape[:2]
    rects, weights = _HOG.detectMultiScale(frame, winStride=(8, 8), padding=(8, 8), scale=1.05)
    out = []
    for (x, y, bw, bh), wt in zip(rects, weights):
        if wt > 0.9:                       # 0.4 took a grandfather clock for a person (c01, 2026-10-29)
            out.append(((x + bw / 2) / w, (y + bh * 0.3) / h, bw / w))
    out.sort(key=lambda t: -t[2])
    return out[:2]


def people_in(source, start, end):
    """People (no face needed) seen in at least 2 of 3 frames of a stretch, at 1280x720."""
    frames = _frames_at(source, start, end, 2, 1280, 720)
    if len(frames) == 0:
        return []
    idx = np.linspace(0, len(frames) - 1, min(3, len(frames))).astype(int)
    hits = [p for i in idx for p in persons(frames[i])]
    groups = []
    for cx, cy, bw in sorted(hits):
        if groups and abs(cx - groups[-1][-1][0]) < 0.1:
            groups[-1].append((cx, cy, bw))
        else:
            groups.append([(cx, cy, bw)])
    keep = [g for g in groups if len(g) >= 2]
    out = [tuple(float(np.median([q[k] for q in g])) for k in range(3)) for g in keep]
    out.sort(key=lambda t: -t[2])
    return out[:2]


_DEC = []   # (source, start, end, fps, w, h, frames): decoded stretches, newest last


def _decode(source, start, end, fps, w, h):
    """Frames of [start, end] at fps, w x h. A stretch inside one decoded earlier is sliced from it:
    shots() decodes a whole piece, then faces_in() / track() / small_faces() ask for parts of it
    (2026-10-28 profiling: 35 decodes per render, most of them repeats)."""
    for s0, e0, f0, w0, h0, fr in _DEC:
        if f0 == fps and w0 == w and h0 == h and s0 - 1e-3 <= start and end <= e0 + 1e-3 and _DEC_SRC[0] == source:
            i, j = int(round((start - s0) * fps)), int(round((end - s0) * fps))
            if j - i >= 1:
                return fr[i:max(j, i + 1)]
    if end - start < 0.05:
        return np.zeros((0, h, w, 3), np.uint8)                        # a sliver (end before start after snapping): nothing to decode
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", source,
           "-vf", f"fps={fps},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    n = len(raw) // (w * h * 3)
    fr = np.frombuffer(raw[: n * w * h * 3], np.uint8).reshape(n, h, w, 3)
    if _DEC_SRC[0] != source:
        _DEC.clear(); _DEC_SRC[0] = source
    _DEC.append((start, end, fps, w, h, fr))
    while sum(x[5].nbytes for x in _DEC) > 600e6:   # keep the cache under ~600 MB
        _DEC.pop(0)
    return fr


_DEC_SRC = [None]


def _frames(source, start, end):
    return _decode(source, start, end, FPS, W, H)


def _hist(f):
    hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
    return cv2.normalize(h, h).flatten()


def _faces(f):
    found = [(cx, cy, sz) for cx, cy, sz, _ in detect_faces(f)]
    merged = []
    for cx, cy, sz in sorted(found, key=lambda t: -t[2]):
        if all(abs(cx - m[0]) > max(sz, m[2]) * 0.6 for m in merged):
            merged.append((cx, cy, sz))
    return merged


def shots(source, start, end, min_len=0.6):
    frames = _frames(source, start, end)
    small = [cv2.resize(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (64, 36)).astype(float) for f in frames]
    diff = [0.0] + [float(np.abs(small[i] - small[i - 1]).mean()) for i in range(1, len(small))]
    cuts = [0]
    for i in range(1, len(diff)):
        # threshold 20 (was 35): a podcast's cuts between a dark close-up and the wide room shot
        # only move the picture by 21-33 (2026-10-26); the 2.5x ratio still rules out motion
        # a cut is one big jump between two frames; a sliding overlay is several medium ones in a row
        around = max(diff[max(0, i - 2):i] + diff[i + 1:i + 3] or [0])
        if diff[i] > 20 and diff[i] > 2.5 * around and (i - cuts[-1]) / FPS >= min_len:
            cuts.append(i)
    cuts.append(len(frames))
    exact = [start + c / FPS for c in cuts]
    for j in range(1, len(cuts) - 1):
        exact[j] = _refine(source, exact[j])
    out = []
    for a, b in zip(cuts, cuts[1:]):
        idx = np.linspace(a, b - 1, min(6, b - a)).astype(int)
        out.append({"faces": _cluster([frames[i] for i in idx])})
    for j, o in enumerate(out):
        o["start"], o["end"] = exact[j], exact[j + 1]
    out[-1]["end"] = end
    return out


def _cluster(frames):
    """Faces seen across sample frames, clustered by x; people seen in at least a third of them.
    Each face is (cx, cy, size, talk): talk = how much the mouth area moves between the sample
    frames, so the person speaking can be told from the one listening."""
    hits = [h for f in frames for h in _faces(f)]
    people = []
    for cx, cy, s in sorted(hits):
        if people and abs(cx - people[-1][-1][0]) < 0.08:
            people[-1].append((cx, cy, s))
        else:
            people.append([(cx, cy, s)])
    keep = [p for p in people if len(p) >= max(1, len(frames) / 3)]
    faces = []
    for p in keep:
        cx, cy, s = (float(np.median([q[k] for q in p])) for k in range(3))
        faces.append((cx, cy, s, _mouth_motion(frames, cx, cy, s)))
    faces.sort(key=lambda t: -t[2])
    return faces[:3]


def _mouth_motion(frames, cx, cy, s):
    """Mean frame-to-frame change in the lower third of the face box (0 when only one frame)."""
    if len(frames) < 2:
        return 0.0
    fh, fw = frames[0].shape[:2]          # the frames' own size (720p for the movie search, 360p otherwise)
    w = int(s * fw)
    x0, x1 = max(int(cx * fw - w / 2), 0), min(int(cx * fw + w / 2), fw)
    y0, y1 = max(int(cy * fh + w * 0.15), 0), min(int(cy * fh + w * 0.6), fh)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return 0.0
    crops = [cv2.cvtColor(f[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype(float) for f in frames]
    return float(np.mean([np.abs(a - b).mean() for a, b in zip(crops, crops[1:])]))


def _frames_at(source, start, end, fps, w=W, h=H):
    return _decode(source, start, end, fps, w, h)


def track(source, start, end, fps=4, box=None, src_w=1920, src_h=1080, min_size=0.10, anchor=None, hi=False):
    """The speaker's face over time: [(t_source, (cx, cy, size) or None), ...] sampled at `fps`.
    One identity is followed: the first pick is the face nearest `anchor` (the person chosen for the
    segment) or else the biggest; after that the hit nearest the previous position wins, and a hit
    further than 15% of the width away is treated as somebody else (the position is held), so the
    crop never slides over to the other actor when the speaker's profile dips under the detector's
    confidence for a frame (c02 2026-10-29: the window drifted from Rockwell to the woman beside him).
    Faces inside `box` (an on-screen graphic, source px) are ignored."""
    out, prev = [], None
    for i, f in enumerate(_frames_at(source, start, end, fps, 1280, 720) if hi else _frames_at(source, start, end, fps)):
        hits = [(cx, cy, sz, c) for cx, cy, sz, c in detect_faces(f, 0.5)]
        ok = []
        for cx, cy, sz, c in hits:
            if not (min_size <= sz <= 0.5 and cy <= 0.7):
                continue
            if box and box[0] <= cx * src_w <= box[0] + box[2] and box[1] <= cy * src_h <= box[1] + box[3]:
                continue
            if c < 0.6 and prev is None and anchor is None:
                continue                      # a weak hit may only continue an identity, never start one
            ok.append((cx, cy, sz))
        pick = None
        if ok:
            ref = prev[0] if prev else anchor
            if ref is not None:
                cand = min(ok, key=lambda h: abs(h[0] - ref))
                pick = cand if abs(cand[0] - ref) <= 0.15 else None
                if pick is None and prev:
                    # the speaker turned away while somebody else's face is on screen: keep the window
                    # as close to the speaker as possible but with the other face inside it (c02
                    # 2026-10-29: she turned to the window and his face sat cut off at the edge)
                    pick = (min(max(prev[0], cand[0] - 0.07), cand[0] + 0.07), prev[1], prev[2])
            else:
                pick = max(ok, key=lambda h: h[2])
            if pick:
                prev = pick
        out.append((start + i / fps, pick))
    return out


def card_end(source, start, end):
    """When a dark title/credit card at `start` gives way to the picture: the first moment the mean
    brightness steps up by 12+ (checked at 10 fps, 320x180), or None when the stretch stays a card."""
    fr = _decode(source, start, end, 10, 320, 180)
    if len(fr) < 2:
        return None
    lum = [float(f.mean()) for f in fr]
    for i in range(1, len(lum)):
        if lum[i] - lum[i - 1] >= 12 and lum[i - 1] < 40:
            return start + i / 10
    return None


@functools.lru_cache(maxsize=32)
def small_faces(source, start, end):
    """People too small for the normal pass (the wide two-shot: faces ~45 px in 1080p). Runs the
    frontal + profile detectors on three 1280x720 frames (faces ~30 px). Returns [(cx, cy, size)]
    clustered by x, biggest first, in 0-1 of the frame.
    2026-10-28: this pass was 55% of a render (8 full-HD frames, scale step 1.06, called once per
    piece of the same shot); now 3 frames at 720p, step 1.1, cached per shot: ~15x cheaper."""
    SW, SH = 1280, 720
    frames = _frames_at(source, start, end, 2, SW, SH)
    if len(frames) == 0:
        return []
    idx = np.linspace(0, len(frames) - 1, min(3, len(frames))).astype(int)
    hits = []
    for i in idx:
        for cx, cy, sz, _ in detect_faces(frames[i], 0.5):
            if sz <= 0.14:
                hits.append((cx, cy, sz))
    people = []
    for cx, cy, sz in sorted(hits):
        if people and abs(cx - people[-1][-1][0]) < 0.06:
            people[-1].append((cx, cy, sz))
        else:
            people.append([(cx, cy, sz)])
    keep = [p for p in people if len(p) >= 2]
    faces = [tuple(float(np.median([q[k] for q in p])) for k in range(3)) for p in keep]
    faces = [f for f in faces if f[1] <= 0.7]
    faces.sort(key=lambda t: -t[2])
    return faces[:2]


def faces_in(source, start, end, hi=False):
    """Faces in one stretch, for when a graphic slides in mid-shot and changes the picture.
    hi=True searches 1280x720 frames (movies: an actor across the room is 20 px wide at 640)."""
    if hi:   # 720p frames are never cached from shots(): decode only the ~6 frames that are looked at
        frames = _frames_at(source, start, end, min(FPS, 6 / max(end - start, 0.6)), 1280, 720)
    else:
        frames = _frames(source, start, end)
    idx = np.linspace(0, len(frames) - 1, min(6, len(frames))).astype(int)
    return _cluster([frames[i] for i in idx])


def _native(source, a, dur):
    """Native-rate frames in [a, a+dur] with their real timestamps: (pts list, 64x36 gray frames).
    The old code assumed 29.97 fps; many podcasts are 23.976 fps, and the one-frame error let a frame of
    the wide shot slip in at a cut (2026-10-26)."""
    r = subprocess.run(["ffmpeg", "-loglevel", "info", "-nostats", "-ss", f"{a:.3f}", "-t", f"{dur:.3f}", "-i", source,
                        "-vf", "scale=64:36,format=gray,showinfo", "-f", "rawvideo", "-"], capture_output=True)
    pts = [float(x) for x in re.findall(r"pts_time:\s*([\d.]+)", r.stderr.decode(errors="ignore"))]
    n = min(len(r.stdout) // (64 * 36), len(pts))
    f = np.frombuffer(r.stdout[: n * 64 * 36], np.uint8).reshape(n, 36, 64).astype(float)
    # showinfo reports times relative to the seek point
    return [a + p for p in pts[:n]], f


def cut_in(source, a, b, thresh=20):
    """Time of the sharpest picture change in [a, b] at the source's own frame rate (the timestamp of
    the first frame of the new shot), or None if there is no cut. Used to keep a few frames of
    another camera from leaking in at the start or end of a piece."""
    pts, f = _native(source, a, b - a)
    if len(f) < 3:
        return None
    d = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))
    i = int(np.argmax(d))
    around = np.concatenate([d[max(0, i - 2):i], d[i + 1:i + 3]])
    if d[i] > thresh and d[i] > 2.5 * (around.max() if len(around) else 0):
        return pts[i + 1] + 0.002
    return None


def _refine(source, t):
    """Move a cut found at 10 fps to the exact source frame where the picture changes."""
    a = max(t - 0.2, 0)
    pts, f = _native(source, a, 0.4)
    if len(f) < 2:
        return t
    d = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))
    return pts[int(np.argmax(d)) + 1] + 0.002


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(shots(sys.argv[1], float(sys.argv[2]), float(sys.argv[3])), indent=1))


def _text_rows(gray):
    """Rows of letter-like connected components in a grayscale frame (both polarities):
    [(x0, y0, x1, y1, n_components)] in pixels of the frame given. Letters: thin strokes, similar
    heights, evenly spaced; that rules out window panes, keyboards and brick."""
    h, w = gray.shape
    rows = []
    for inv in (False, True):
        g = 255 - gray if inv else gray
        _, bw = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
        comps = []
        for i in range(1, n):
            x, y, cw, ch, area = stats[i]
            if not (h * 0.02 <= ch <= h * 0.35 and 2 <= cw <= ch * 1.8):
                continue
            if not (0.12 <= area / float(cw * ch) <= 0.9):
                continue
            m = (labels[y:y + ch, x:x + cw] == i).astype(np.uint8)
            stroke = cv2.distanceTransform(m, cv2.DIST_L2, 3).max()   # half the widest stroke
            if stroke > 0.24 * ch:
                continue                                              # a solid blob, not a letter
            comps.append((x, y, cw, ch))
        comps.sort(key=lambda c: c[1])
        used = [False] * len(comps)
        for i, (x, y, cw, ch) in enumerate(comps):
            if used[i]:
                continue
            cy = y + ch / 2
            line = [j for j, (x2, y2, cw2, ch2) in enumerate(comps)
                    if not used[j] and abs((y2 + ch2 / 2) - cy) < ch * 0.5 and 0.6 <= ch2 / ch <= 1.7]
            for j in line:
                used[j] = True
            hs = [comps[j][3] for j in line]
            if len(line) < 5:
                continue
            xs = sorted(comps[j][0] for j in line)
            gaps = np.diff(xs)
            ws = [comps[j][2] for j in line]
            if np.std(ws) / max(np.mean(ws), 1) < 0.12:
                continue                                               # identical glyph widths = window panes, a grid, a keyboard
            if sum(1 for j in line if comps[j][3] > 4 * comps[j][2]) > len(line) // 2:
                continue                                               # mostly thin bars: window mullions, railings, not letters
            if np.std(hs) / np.mean(hs) > 0.3 or (len(gaps) and np.max(gaps) > 3.0 * max(np.median(gaps), 1)):
                continue
            x1 = max(comps[j][0] + comps[j][2] for j in line)
            if x1 - xs[0] >= w * 0.12:
                rows.append((xs[0], min(comps[j][1] for j in line), x1, max(comps[j][1] + comps[j][3] for j in line), len(line)))
    return rows


def text_box(source, start, end):
    """Burned-in text (a title card, a credit, a lower third) in a stretch of the source: its box
    (x0, y0, x1, y1) in 0-1 of the frame, or None. Five frames are checked; text must show in two of
    them, or once as a long line (8+ letters: a card that is only up for a moment).
    rico (2026-10-28): the trailer's "A NEW FILM FROM ..." card was cropped through the middle."""
    frames = _frames(source, start, end)
    if len(frames) == 0:
        return None
    idx = sorted(set(np.linspace(0, len(frames) - 1, min(5, len(frames))).astype(int)))
    boxes, long_line = [], False
    for i in idx:
        rows = _text_rows(cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY))
        if rows:
            boxes.append((min(r[0] for r in rows) / W, min(r[1] for r in rows) / H,
                          max(r[2] for r in rows) / W, max(r[3] for r in rows) / H))
            long_line = long_line or max(r[4] for r in rows) >= 8
    if not boxes or (len(boxes) < 2 and not long_line):
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
