"""Find camera cuts and faces in a stretch of a podcast video.

Usage (as a module): shots(source, start, end) -> list of
  {"start", "end", "faces": [(cx, cy, size, talk), ...]}   # source seconds; face centres in 0-1 of the
  frame; talk = mouth movement, higher for the person speaking
  cut_in(source, a, b) -> time of a camera cut inside [a, b], or None

Cuts are found where one frame differs sharply from the last (frames sampled at 10 fps).
Faces are found with OpenCV's bundled Haar detectors (frontal + profile) on
a few frames per shot, then clustered so each person counts once.
"""
import re
import subprocess

import cv2
import numpy as np

FPS = 10
W, H = 640, 360
_front = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
_prof = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")


def _frames(source, start, end):
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", source,
           "-vf", f"fps={FPS},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    n = len(raw) // (W * H * 3)
    return np.frombuffer(raw[: n * W * H * 3], np.uint8).reshape(n, H, W, 3)


def _hist(f):
    hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
    return cv2.normalize(h, h).flatten()


def _faces(f):
    g = cv2.equalizeHist(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
    found = []
    for det, flip in ((_front, False), (_prof, False), (_prof, True)):
        img = cv2.flip(g, 1) if flip else g
        for (x, y, w, h) in det.detectMultiScale(img, 1.1, 6, minSize=(40, 40)):
            if flip:
                x = W - x - w
            found.append(((x + w / 2) / W, (y + h / 2) / H, w / W))
    # merge overlapping hits from the different detectors
    merged = []
    for cx, cy, s in sorted(found, key=lambda t: -t[2]):
        if all(abs(cx - m[0]) > max(s, m[2]) * 0.6 for m in merged):
            merged.append((cx, cy, s))
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
    w = int(s * W)
    x0, x1 = max(int(cx * W - w / 2), 0), min(int(cx * W + w / 2), W)
    y0, y1 = max(int(cy * H + w * 0.15), 0), min(int(cy * H + w * 0.6), H)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return 0.0
    crops = [cv2.cvtColor(f[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype(float) for f in frames]
    return float(np.mean([np.abs(a - b).mean() for a, b in zip(crops, crops[1:])]))


def _frames_at(source, start, end, fps, w=W, h=H):
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", source,
           "-vf", f"fps={fps},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    n = len(raw) // (w * h * 3)
    return np.frombuffer(raw[: n * w * h * 3], np.uint8).reshape(n, h, w, 3)


def track(source, start, end, fps=4, box=None, src_w=1920, src_h=1080):
    """The speaker's face over time: [(t_source, (cx, cy, size) or None), ...] sampled at `fps`.
    The frontal detector goes first (the profile one invents faces on mics and ears); of several hits
    the one nearest the previous position wins, so the crop follows one person and never jumps to a
    stray hit. Faces inside `box` (an on-screen graphic, source px) are ignored. Added 2026-10-26 after
    rico's "horribly off centre" review: shot-median positions let the face drift to the edge."""
    out, prev = [], None
    for i, f in enumerate(_frames_at(source, start, end, fps)):
        g = cv2.equalizeHist(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
        hits = [((x + w / 2) / W, (y + h / 2) / H, w / W)
                for (x, y, w, h) in _front.detectMultiScale(g, 1.1, 5, minSize=(40, 40))]
        if not hits:
            for det, flip in ((_prof, False), (_prof, True)):
                img = cv2.flip(g, 1) if flip else g
                for (x, y, w, h) in det.detectMultiScale(img, 1.1, 6, minSize=(40, 40)):
                    if flip:
                        x = W - x - w
                    hits.append(((x + w / 2) / W, (y + h / 2) / H, w / W))
        ok = []
        for cx, cy, sz in hits:
            if not (0.10 <= sz <= 0.34 and cy <= 0.65):
                continue
            if box and box[0] <= cx * src_w <= box[0] + box[2] and box[1] <= cy * src_h <= box[1] + box[3]:
                continue
            ok.append((cx, cy, sz))
        pick = None
        if ok:
            pick = min(ok, key=lambda h: abs(h[0] - prev[0])) if prev else max(ok, key=lambda h: h[2])
            prev = pick
        out.append((start + i / fps, pick))
    return out


def small_faces(source, start, end):
    """People too small for the normal pass (the wide two-shot: faces ~45 px in 1080p). Runs the
    frontal + profile detectors on a few full-resolution frames. Returns [(cx, cy, size)] clustered
    by x, biggest first, in 0-1 of the frame."""
    frames = _frames_at(source, start, end, 2, 1920, 1080)
    if len(frames) == 0:
        return []
    idx = np.linspace(0, len(frames) - 1, min(8, len(frames))).astype(int)
    hits = []
    for i in idx:
        g = cv2.equalizeHist(cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY))
        for det, flip in ((_front, False), (_prof, False), (_prof, True)):
            img = cv2.flip(g, 1) if flip else g
            for (x, y, w, h) in det.detectMultiScale(img, 1.06, 3, minSize=(32, 32), maxSize=(220, 220)):
                if flip:
                    x = 1920 - x - w
                hits.append(((x + w / 2) / 1920, (y + h / 2) / 1080, w / 1920))
    people = []
    for cx, cy, sz in sorted(hits):
        if people and abs(cx - people[-1][-1][0]) < 0.06:
            people[-1].append((cx, cy, sz))
        else:
            people.append([(cx, cy, sz)])
    keep = [p for p in people if len(p) >= max(2, len(idx) // 3)]
    faces = [tuple(float(np.median([q[k] for q in p])) for k in range(3)) for p in keep]
    faces = [f for f in faces if f[1] <= 0.7]
    faces.sort(key=lambda t: -t[2])
    return faces[:2]


def faces_in(source, start, end):
    """Faces in one stretch, for when a graphic slides in mid-shot and changes the picture."""
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
