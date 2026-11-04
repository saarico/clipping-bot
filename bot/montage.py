"""Montage Editor (makeover release 7, board review 3, approved by rico 2026-11-04).

rico, 2026-11-04: "have the music playing and throw in snippets of the clips or make it into b-roll". The song-bed
format: the song plays without a break (one window of the performance, never cut, so the sound is the real show) and
the picture cuts away ON THE BEAT to the show's strongest other shots: the crowd singing, a light or pyro burst, a
wide of the stage. The performer's own close-ups stay in sync with the song: a cutaway is never a close-up from
another part of the show (the lips would not match).

  beats(src, a, b)              -> beat times (source seconds) in [a, b], from the sound's onset strength
  build(spec, tags, cut_times)  -> a copy of the spec with "video_swap" cutaways, or None when the show has no shots
                                   worth cutting to

The cutaways reuse the Camera's video_swap (the audio stays, the picture shows other frames), so the whole render,
QA and judge line works unchanged.
"""
import json
import subprocess
from pathlib import Path

import numpy as np

SR = 11025
HOP = 256
MAX_SHARE = 0.35      # cutaways never carry more than a third of the clip: the performance is the clip
MIN_GAP_S = 3.0       # at least this much of the song's own picture between two cutaways
FIRST_S = 2.5         # the first seconds are the hook: the performance itself, no cutaway


def _audio(src, a, b):
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(src), "-vn",
                        "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768


def beats(src, a, b):
    """Beat times in [a, b]: spectral-flux onset strength, the tempo (70-180 BPM) from its autocorrelation, and the
    beat grid's phase where the onsets line up best. [] for silence."""
    y = _audio(src, a, b)
    if len(y) < SR:
        return []
    n = (len(y) - 1024) // HOP
    frames = np.lib.stride_tricks.as_strided(y, (n, 1024), (y.strides[0] * HOP, y.strides[0]))
    spec = np.abs(np.fft.rfft(frames * np.hanning(1024), axis=1))
    flux = np.maximum(np.diff(np.log1p(spec), axis=0), 0).sum(axis=1)
    if flux.max() <= 0:
        return []
    flux = (flux - flux.mean()) / (flux.std() + 1e-9)
    fps = SR / HOP
    lags = np.arange(int(fps * 60 / 180), int(fps * 60 / 70) + 1)
    ac = np.array([np.dot(flux[:-l], flux[l:]) for l in lags])
    period = lags[int(np.argmax(ac))]
    phase = max(range(period), key=lambda p: flux[p::period].sum())
    # walk the grid, each beat snapped to the strongest onset within 4 frames of where it is expected (the period is
    # only whole frames: a fixed step drifts 10 ms a beat)
    out, i, step = [], phase, float(period)
    while i < len(flux):
        lo, hi = max(0, int(i) - 4), min(len(flux), int(i) + 5)
        j = lo + int(np.argmax(flux[lo:hi]))
        if out and flux[j] > 0.5:
            step = 0.8 * step + 0.2 * (j - out[-1])
        out.append(j if flux[j] > 0.5 else int(i))
        i = out[-1] + step
    return [round(a + ((j + 1) * HOP + 512) / SR, 3) for j in out]


def _snap(t, grid):
    return min(grid, key=lambda g: abs(g - t)) if grid else t


def _pick_inserts(tags, cut_times, avoid, need, lo=1.0, hi=2.5):
    """Source moments worth cutting to: crowd, lights, a wide stage; never a close-up (lip sync), never dark, never
    inside the song's own window. Each one sits inside one shot for at least `lo` s."""
    good = []
    for t in tags:
        if t["dark"] or t["close"] or avoid[0] - 10 <= t["t"] <= avoid[1] + 10:
            continue
        score = 3 * t["crowd"] + 2 * t["lights"] + min(t["motion"] * 20, 1.5)
        if score < 1.5:
            continue
        nxt = next((c for c in cut_times if c > t["t"] + 0.15), t["t"] + hi)
        room = nxt - t["t"] - 0.2
        if room >= lo:
            good.append((score, t["t"] + 0.1, min(room, hi), "crowd" if t["crowd"] else "lights" if t["lights"] else "stage"))
    good.sort(key=lambda g: -g[0])
    picked = []
    for g in good:
        if all(abs(g[1] - p[1]) > 6 for p in picked):
            picked.append(g)
        if len(picked) >= need:
            break
    return picked


def build(spec, tags, cut_times, beat_times=None, own_tags=None):
    """The song-bed version of a music spec. own_tags: the window's own per-second tags (cutaways go where its picture
    is weakest: no close-up, no crowd). Returns None when fewer than 2 cutaways are worth making."""
    a, b = spec["parts"][0]
    dur = b - a
    grid = [t for t in (beat_times or []) if a + FIRST_S <= t <= b - 1.0]
    slots_n = max(2, min(6, int(dur * MAX_SHARE / 1.8)))
    ins = _pick_inserts(tags, cut_times, (a, b), slots_n)
    if len(ins) < 2:
        return None
    # where to cut away: spread evenly after the hook, each moved to the window's weakest second nearby (no close-up,
    # no crowd of its own), then onto the beat
    own = {round(t["t"]): t for t in (own_tags or [])}
    weak = lambda t: (own[round(t)]["close"] * 2 + own[round(t)]["crowd"] + own[round(t)]["lights"]) if round(t) in own else 1
    starts = []
    span = b - 2.0 - (a + FIRST_S)
    for k in range(len(ins)):
        target = a + FIRST_S + span * (k + 0.5) / len(ins)
        near = min((target + d for d in (-1.5, -0.75, 0, 0.75, 1.5)), key=lambda t: (weak(t), abs(t - target)))
        s = _snap(near, grid)
        if a + FIRST_S <= s <= b - 2.0 and all(abs(s - x) >= MIN_GAP_S for x in starts):
            starts.append(s)
    starts.sort()
    swaps, used = [], 0.0
    for s, (_, src_t, room, kind) in zip(starts, ins):
        ln = room
        if grid:
            ends = [g for g in grid if s + 0.9 <= g <= s + room]
            ln = (ends[-1] - s) if ends else min(room, 1.5)
        ln = min(ln, b - 1.0 - s)
        if ln < 0.8 or used + ln > MAX_SHARE * dur:
            continue
        swaps.append([round(s, 3), round(s + ln, 3), round(src_t, 3), kind])
        used += ln
    if len(swaps) < 2:
        return None
    v = json.loads(json.dumps(spec))
    v["video_swap"] = sorted(v.get("video_swap", []) + swaps)
    v["concept"] = "song-bed"
    v["out"] = str(Path(spec["out"]).with_name(Path(spec["out"]).stem + "-songbed.mp4"))
    kinds = ", ".join(sorted({s[3] for s in swaps}))
    v["_why"] = (f"concept song-bed: the song plays whole, {len(swaps)} cutaways on the beat to the show's {kinds} shots "
                 f"({used:.0f} s of {dur:.0f} s) | " + spec.get("_why", ""))
    return v
