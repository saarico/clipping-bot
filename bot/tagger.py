"""Visual Tagger (makeover release 7, board review 3, approved by rico 2026-11-04).

Why: the moment picker had no eyes (deck slide 13). Talk was picked from words, music from loudness; nothing knew
whether a moment showed a close-up, the crowd singing, a light or pyro burst, or an empty wide shot.

What it does: tags the picture once per sample, on CPU, with the face detector the Camera already uses plus cheap
pixel measures:
  face    biggest face, share of the picture's width (0 = none)
  close   a face 10%+ of the width (a close-up)
  crowd   three or more small faces low in the picture, or a lower half full of small bright points (phone lights)
  lights  a brightness jump or a hot, saturated frame (pyro, strobes, a light cue)
  motion  mean frame-to-frame change (0-1)
  dark    the picture is too dark to use

  tag_windows(src, ranges)  -> {(a, b): [tags per second]}     1 sample per second inside each window
  tag_keyframes(src, cache) -> [tags]                           every keyframe of the whole file (fast: no full decode)
"""
import json
import re
import subprocess
from pathlib import Path

import numpy as np

import analyze_shots

W, H = 640, 360


def _tag(frame, prev):
    import cv2
    faces = analyze_shots.detect_faces(frame, min_conf=0.55)
    small_low = [f for f in faces if f[2] < 0.05 and f[1] > 0.5]
    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    bright = float(g.mean()) / 255
    low = g[H // 2:, :]
    # small isolated bright points (phone lights, a lit crowd): what an opening with a 5x5 kernel removes
    spots = int(((low - cv2.morphologyEx(low, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))) > 80).sum())
    motion = float(np.abs(g - prev).mean()) / 255 if prev is not None else 0.0
    jump = (bright - float(prev.mean()) / 255) if prev is not None else 0.0
    sat_hot = float(((hsv[..., 1] > 150) & (hsv[..., 2] > 200)).mean())
    face = max((f[2] for f in faces), default=0.0)
    return {"face": round(face, 3), "nf": len(faces), "close": face >= 0.10,
            "crowd": len(small_low) >= 3 or spots >= 60,
            "lights": jump > 0.12 or sat_hot > 0.08,
            "motion": round(motion, 3), "bright": round(bright, 3), "dark": bright < 0.06}, g


def _decode(src, a, b, fps=1):
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(src),
                        "-vf", f"fps={fps},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True)
    n = len(r.stdout) // (W * H * 3)
    return np.frombuffer(r.stdout[: n * W * H * 3], np.uint8).reshape(n, H, W, 3)


def tag_windows(src, ranges):
    """{(a, b): [{"t", ...tags}]} at one sample per second inside each window."""
    out = {}
    for a, b in ranges:
        prev, tags = None, []
        for i, f in enumerate(_decode(src, a, b)):
            t, prev = _tag(f, prev)
            t["t"] = round(a + i, 2)
            tags.append(t)
        out[(a, b)] = tags
    return out


def tag_keyframes(src, cache=None):
    """Tags at every keyframe of the whole file (the decoder skips everything else: an hour takes about a minute)."""
    if cache and Path(cache).exists():
        return json.loads(Path(cache).read_text())
    p = subprocess.Popen(["ffmpeg", "-loglevel", "info", "-skip_frame", "nokey", "-i", str(src), "-an", "-vf",
                          f"scale={W}:{H},showinfo", "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    raw, err = p.communicate()
    times = [float(x) for x in re.findall(r"pts_time:([\d.]+)", err.decode(errors="ignore"))]
    n = min(len(times), len(raw) // (W * H * 3))
    frames = np.frombuffer(raw[: n * W * H * 3], np.uint8).reshape(n, H, W, 3)
    tags, prev = [], None
    for t, f in zip(times, frames):
        tg, prev = _tag(f, prev)
        tg["t"] = round(t, 2)
        tags.append(tg)
    if cache:
        Path(cache).write_text(json.dumps(tags))
    return tags


def tag_show(src, cache=None, every=2.0, long_s=2400):
    """Cutaway material for the Montage Editor: one sample every `every` s for a show up to `long_s` long (a full
    decode, a few minutes for 40 min), every keyframe for anything longer."""
    if cache and Path(cache).exists():
        return json.loads(Path(cache).read_text())
    try:
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)],
                                   capture_output=True, text=True).stdout.strip() or 0)
    except ValueError:
        dur = 0
    if not dur or dur > long_s:
        return tag_keyframes(src, cache)
    tags, prev = [], None
    for i, f in enumerate(_decode(src, 0, dur, 1 / every)):
        tg, prev = _tag(f, prev)
        tg["t"] = round(i * every, 2)
        tags.append(tg)
    if cache:
        Path(cache).write_text(json.dumps(tags))
    return tags


def summary(tags):
    """Shares of a window's samples: close-ups, crowd, lights, faces, dark, and the mean motion."""
    n = max(len(tags), 1)
    return {"close": sum(t["close"] for t in tags) / n, "crowd": sum(t["crowd"] for t in tags) / n,
            "lights": sum(t["lights"] for t in tags) / n, "faces": sum(t["face"] > 0.04 for t in tags) / n,
            "dark": sum(t["dark"] for t in tags) / n, "motion": sum(t["motion"] for t in tags) / n}
