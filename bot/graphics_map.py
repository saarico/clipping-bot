"""Map every on-screen graphic in an episode (the show's cards, photos, bottom strips), so clips
can be picked where the show already gives us b-roll (PLAYBOOK 26).

Usage:
  python3 graphics_map.py <episode.mp4> <out.json>

Scans at 2 fps (480x270). Finds:
  card    the show's yellow-highlight text cards ("2,500 balls a day.")   -> yellow pixel blobs
  photo   a bright framed picture over the set (the Mike Agassi card)      -> big bright rectangle
  strip   a citation / caption strip along the bottom                       -> bright text rows at the bottom
Writes [{"type", "from", "to", "box": [x, y, w, h] in 1920x1080}] merged over consecutive frames.
"""
import json
import subprocess
import sys

import numpy as np

W, H, FPS = 480, 270, 2
SX, SY = 1920 / W, 1080 / H


def frames(src):
    cmd = ["ffmpeg", "-loglevel", "error", "-i", src, "-vf", f"fps={FPS},scale={W}:{H}", "-f", "rawvideo",
           "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = W * H * 3
    i = 0
    while True:
        raw = p.stdout.read(n)
        if len(raw) < n:
            break
        yield i / FPS, np.frombuffer(raw, np.uint8).reshape(H, W, 3)
        i += 1


def bbox(mask):
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    return [int(xs.min() * SX), int(ys.min() * SY), int((xs.max() - xs.min() + 1) * SX), int((ys.max() - ys.min() + 1) * SY)]


def detect(f):
    r, g, b = f[..., 0].astype(int), f[..., 1].astype(int), f[..., 2].astype(int)
    found = []
    yellow = (r > 170) & (g > 190) & (b < 130)
    if yellow.sum() > 40:
        found.append(("card", bbox(yellow)))
    bottom = f[int(H * 0.9):]
    white_b = (bottom.min(axis=2) > 200)
    if white_b.sum() > 120:
        found.append(("strip", [0, 972, 1920, 108]))
    # a framed photo: a large bright (white border) rectangle above the table, not the whole frame
    white = (f.min(axis=2) > 225)
    col = white.sum(axis=0)
    cols = np.where(col > H * 0.25)[0]
    if 2 <= len(cols) <= W * 0.6:
        x0, x1 = cols.min(), cols.max()
        if 40 < x1 - x0 < W * 0.5:
            rows = np.where(white[:, x0:x1 + 1].sum(axis=1) > (x1 - x0) * 0.5)[0]
            if len(rows) >= 2 and rows.max() - rows.min() > 60:
                found.append(("photo", [int(x0 * SX), int(rows.min() * SY), int((x1 - x0) * SX), int((rows.max() - rows.min()) * SY)]))
    return found


def main(src, out):
    open_items, done = {}, []
    for t, f in frames(src):
        seen = set()
        for typ, box in detect(f):
            seen.add(typ)
            if typ in open_items:
                o = open_items[typ]
                o["to"] = t + 1 / FPS
                # the box grows with the graphic (a card adding a line): keep the union
                x0 = min(o["box"][0], box[0]); y0 = min(o["box"][1], box[1])
                x1 = max(o["box"][0] + o["box"][2], box[0] + box[2]); y1 = max(o["box"][1] + o["box"][3], box[1] + box[3])
                o["box"] = [x0, y0, x1 - x0, y1 - y0]
            else:
                open_items[typ] = {"type": typ, "from": t, "to": t + 1 / FPS, "box": box}
        for typ in list(open_items):
            if typ not in seen:
                done.append(open_items.pop(typ))
    done += open_items.values()
    done = [d for d in done if d["to"] - d["from"] >= 1.0]
    done.sort(key=lambda d: d["from"])
    json.dump(done, open(out, "w"), indent=1)
    print(f"{len(done)} graphics -> {out}")
    for d in done:
        print(f"  {d['type']:5s} {d['from']:7.1f}-{d['to']:7.1f}  box {d['box']}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
