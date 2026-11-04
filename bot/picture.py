"""Picture Engineer (makeover release 5, board review 3, approved by rico 2026-11-04 02:57 UTC).

Why: a 9:16 window of a 1920x1080 episode is 607 pixels wide; every clip was upscaled 1.8x, up to 4.4x on a
punch-in, and then encoded three or four times. The board saw a soft picture. Measured on a 4K test image
(deck slide 11): today's chain 1,327 (Laplacian detail), one clean encode at 1080p 1,746, the window cut from the
native 4K original 5,711.

What this module does:
  master          the campaign's original file at its own resolution (up to 2160 lines), when the episode is
                  one file or one link whose timeline equals the 1080p episode. The 1080p episode stays the
                  analysis copy (faces, shots, words); the Camera crops the picture from the master instead.
  norm_filter     ffmpeg filters that turn the raw master into the episode's geometry at k x 1920 by k x 1080
                  (the same black-bar crop and 16:9 centre crop as run.convert_part).
  scale_graph     a Camera filter graph written in 1920x1080 coordinates -> the same graph on the master.
  zoom_cap        the biggest punch-in that keeps at least MIN_SRC_PX real pixels across the window.
  src_px          the real source pixels across a window (QA's "Picture detail" row).
  detail          Laplacian detail score of a few frames of a finished clip.
"""
import json
import re
import subprocess
from pathlib import Path

SRC_W, SRC_H = 1920, 1080
OUT_W, OUT_H = 1080, 1920
WIN_W1 = SRC_H * OUT_W / OUT_H          # 607.5: the 9:16 window's width in 1080p pixels at zoom 1
MIN_SRC_PX = 480                         # never upscale a window more than 2.25x (1080 / 480)
MASTER_MAX_H = 2160                      # 4K is enough; 8K masters are scaled down to 2160 lines
MASTER_MIN_K = 1.15                      # a master under ~1240 lines is not worth the decode time
MASTER_MAX_BYTES = 9e9                   # bigger raw files are not downloaded to a render machine


def zoom_cap(k=1.0, min_px=MIN_SRC_PX):
    """Largest zoom whose window keeps min_px real pixels across. 1080p: 1.27; 1440p: 1.69; 4K: 2.53."""
    return max(1.0, WIN_W1 * k / min_px)


def src_px(zoom, k=1.0):
    """Real source pixels across the 9:16 window at this zoom."""
    return int(WIN_W1 * k / max(zoom, 1e-6))


def norm_filter(w, h, crop=None):
    """(filter, k) that maps a raw w x h master (optionally cut by cropdetect 'crop=W:H:X:Y') onto the episode's
    16:9 geometry at k times 1080p; (None, 1.0) when the master is not sharper than the episode."""
    cw, ch = w, h
    m = re.match(r"crop=(\d+):(\d+):(\d+):(\d+)", crop or "")
    if m:
        cw, ch = int(m.group(1)), int(m.group(2))
    if ch <= 0 or cw <= 0:
        return None, 1.0
    # the episode scales to 1080 lines and centre-crops to 1920 wide (pads when narrower): keep the same shape
    lines = min(ch, MASTER_MAX_H) // 2 * 2
    k = lines / SRC_H
    if k < MASTER_MIN_K:
        return None, 1.0
    tw, th = int(round(SRC_W * k / 2)) * 2, int(round(SRC_H * k / 2)) * 2
    f = ((crop + ",") if crop else "") + (f"scale=-2:{th}:flags=lanczos,crop='min(iw,{tw})':{th},"
                                          f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2,setsar=1")
    return f, round(th / SRC_H, 4)


_CROP4 = re.compile(r"crop=(\d+):(\d+):('[^']*'|[^:,;\[\]']+):(\d+)")


def _ev(n, k):
    return int(round(int(n) * k / 2)) * 2


def scale_graph(graph, k, norm):
    """The Camera's filter graph (1920x1080 coordinates, input [0:v]) -> the same graph on a master that is k times
    bigger: every 4-number crop (window, panel, card) is multiplied by k, and the master's normalising filter runs
    first. Crops after a scale (the blurred backdrop: 'crop=1080:1920') have 2 numbers and are left alone; output
    sizes (scale=1080:1920) never change."""
    def one(m):
        w, h, x, y = m.groups()
        if x.startswith("'"):
            x = f"'({x[1:-1]})*{k}'"
        else:
            try:
                x = str(_ev(x, k) if float(x) == int(float(x)) else f"'({x})*{k}'")
            except ValueError:
                x = f"'({x})*{k}'"
        return f"crop={_ev(w, k)}:{_ev(h, k)}:{x}:{_ev(y, k)}"
    out = _CROP4.sub(one, graph)
    if norm:
        out = out.replace("[0:v]", f"[0:v]{norm},", 1)
    return out


def probe(path):
    """(width, height, duration) of a video file; zeros when unreadable."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
                        "-of", "json", str(path)], capture_output=True, text=True)
    try:
        j = json.loads(r.stdout)
        s = (j.get("streams") or [{}])[0]
        return int(s.get("width", 0)), int(s.get("height", 0)), float(j["format"]["duration"])
    except Exception:
        return 0, 0, 0.0


def master_spec(raw, episode_dur, crop=None, log=print):
    """{"path", "k", "norm"} for a raw file that can stand in for the episode's picture, else None. The raw file's
    timeline must be the episode's (same length within a second): a joined or re-cut episode never uses it."""
    w, h, dur = probe(raw)
    if not h or h > w:
        return None
    if episode_dur and abs(dur - episode_dur) > 1.0:
        log(f"master {Path(raw).name[:50]}: {dur:.0f} s vs the episode's {episode_dur:.0f} s, not the same timeline: not used")
        return None
    norm, k = norm_filter(w, h, crop)
    if not norm:
        log(f"master {Path(raw).name[:50]} is {w}x{h}: no sharper than the 1080p episode")
        return None
    log(f"master {Path(raw).name[:50]} is {w}x{h}: windows cut at {k:.2f}x the 1080p episode's pixels")
    return {"path": str(raw), "k": k, "norm": norm, "size": [w, h]}


def detail(mp4, n=5):
    """Mean Laplacian variance of n frames spread over the clip, at the delivered 1080x1920 (higher = sharper).
    None when OpenCV or the frames are not available."""
    try:
        import cv2
    except ImportError:
        return None
    cap = cv2.VideoCapture(str(mp4))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    vals = []
    for i in range(n):
        if total:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * (i + 0.5) / n))
        ok, fr = cap.read()
        if ok:
            g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
            vals.append(float(cv2.Laplacian(g, cv2.CV_64F).var()))
    cap.release()
    return round(sum(vals) / len(vals), 1) if vals else None
