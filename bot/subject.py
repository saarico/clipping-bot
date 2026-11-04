"""Subject Finder (makeover release 6, board review 3, approved by rico 2026-11-04).

Why: on stage and movie footage the Camera took a face only from 2.5% of the width; a performer on a concert stage
is smaller than that most of the time, so the window fell back to the middle of the stage (deck slide 12:
"the middle of the stage, not the artist"). Nothing measured whether the subject was in the crop.

What it does: follows the ONE person who matters in a stretch of footage, by face (any size YuNet finds), by body
(HOG person detector) when no face shows, and by the lit, moving part of the picture (a spotlit performer) when
neither shows. Every sample scores its candidates on size, confidence, height in the picture (a crowd's heads sit
along the bottom edge) and continuity with the subject a moment before, so the window stays on the artist instead of
jumping to the biggest head in the front row.

  track(src, a, b)  -> [(t, cx, cy, size, kind)]   kind: face / body / light / none
  pan(src, a, b)    -> {"keys": [(t_rel, cx)], "cy", "size", "kind", "cover"} or None, in the Camera's pan-key form
  cover(frames)     -> share of a clip's seconds with the subject in the window (QA "Subject in crop")
"""
import numpy as np

import analyze_shots

FPS = 2
SEARCH = (1280, 720)
CROWD_Y = 0.78        # a small face lower than this is a head in the audience
NEAR = 0.08           # continuity: a candidate this close to the last subject keeps the camera on it


def _light(frame, prev):
    """(cx, cy) of the brightest moving region (a spotlit performer), or None on a flat / static picture."""
    import cv2
    g = cv2.cvtColor(cv2.resize(frame, (64, 36), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(float)
    m = np.abs(g - prev) if prev is not None else np.zeros_like(g)
    heat = (g / 255.0) ** 2 * (0.3 + np.minimum(m / 25.0, 1.0))
    heat[-5:, :] *= 0.4                     # the crowd's phones and heads at the bottom
    if heat.max() < 0.08 or heat.max() < 2.5 * heat.mean():
        return None, g
    ys, xs = np.nonzero(heat >= 0.6 * heat.max())
    w = heat[ys, xs]
    return (float((xs * w).sum() / w.sum() + 0.5) / 64, float((ys * w).sum() / w.sum() + 0.5) / 36), g


def _candidates(frame, prev_g):
    out = []
    for cx, cy, size, conf in analyze_shots.detect_faces(frame, min_conf=0.55):
        crowd = cy > CROWD_Y and size < 0.04
        out.append(((2.0 + 12 * size + conf) * (0.3 if crowd else 1.0), cx, cy, size, "face"))
    if not any(c[4] == "face" and c[0] > 2.4 for c in out):
        import cv2
        for cx, cy, bw in analyze_shots.persons(cv2.resize(frame, (640, 360), interpolation=cv2.INTER_AREA)):
            out.append((1.6 + 4 * bw, cx, cy, bw * 0.35, "body"))
    lt, g = _light(frame, prev_g)
    if lt:
        out.append((0.9, lt[0], lt[1], 0.05, "light"))
    return out, g


def track(src, a, b, fps=FPS):
    """[(t, cx, cy, size, kind)] at `fps` over [a, b] on the source clock."""
    frames = analyze_shots._frames_at(src, a, b, fps, *SEARCH)
    out, last, prev_g = [], None, None
    for i, f in enumerate(frames):
        cands, prev_g = _candidates(f, prev_g)
        if last is not None:
            cands = [(s + (1.5 if abs(cx - last[0]) < NEAR and abs(cy - last[1]) < 0.15 else 0), cx, cy, sz, k)
                     for s, cx, cy, sz, k in cands]
        if cands:
            _, cx, cy, sz, k = max(cands)
            last = (cx, cy)
            out.append((a + i / fps, cx, cy, sz, k))
        else:
            out.append((a + i / fps, last[0] if last else 0.5, last[1] if last else 0.45, 0.0, "none"))
    return out


def pan(src, a, b, dead=0.05, hold=1):
    """Camera pan keys that follow the subject: [(t_rel, cx)] with a dead zone (no constant re-centring, rico
    2026-10-31) and a median over a second. None when nothing in the stretch is a subject (empty stage, black)."""
    tr = track(src, a, b)
    real = [p for p in tr if p[4] != "none"]
    if not real:
        return None
    xs = [p[1] for p in tr]
    sm = [float(np.median(xs[max(0, i - 1):i + 2])) for i in range(len(xs))]
    cur = float(np.median(sm[:3]))
    keys, out = [(0.0, cur)], 0
    for i, x in enumerate(sm):
        if abs(x - cur) > dead:
            out += 1
            if out > hold:
                cur = float(np.median(sm[i:i + 3]))
                keys.append((max(0.0, (i - hold) / FPS), cur))
                out = 0
        else:
            out = 0
    kinds = [p[4] for p in real]
    kind = max(set(kinds), key=kinds.count)
    return {"keys": keys[:40], "cy": float(np.median([p[2] for p in real])), "size": float(np.median([p[3] for p in real])),
            "kind": kind, "cover": round(sum(1 for p in tr if p[4] in ("face", "body")) / len(tr), 2)}


def cover(frames):
    """Share of the clip's seconds whose window holds a subject (face or body), from the Camera's frame records."""
    total = sum(f["to"] - f["from"] for f in frames) or 1.0
    held = 0.0
    for f in frames:
        d = f["to"] - f["from"]
        if f.get("subject") is not None:
            held += d * float(f["subject"])
        elif f.get("layout") in ("face", "hide", "side", "banner", "bottom") and f.get("face"):
            held += d
    return held / total
