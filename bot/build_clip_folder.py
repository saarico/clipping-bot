"""Build (or refresh) a clip folder from a render_clip.py output.

Usage:
  python3 build_clip_folder.py <render out .mp4> <clip folder> [spec.json]

Copies the video in as <folder name>.mp4, the .ass as captions.ass, the .layout.json (+ the spec) as
cut_details.json, and writes captions.txt (title, then one line per cut) for reading end to end.
Then run qa_check.py on the folder.
"""
import json, re, shutil, sys
from pathlib import Path
out, folder = Path(sys.argv[1]), Path(sys.argv[2])      # out9/ICH-005.mp4, 4_APPROVED/.../ICH-005_...
name = folder.name
mp4 = folder / f"{name}.mp4"
shutil.copy(out, mp4)
shutil.copy(out.with_suffix(".ass"), folder / "captions.ass")
lay = json.loads(out.with_suffix(".layout.json").read_text())
old = json.loads((folder / "cut_details.json").read_text())
lay["spec"] = json.loads(Path(sys.argv[3]).read_text()) if len(sys.argv) > 3 else old.get("spec")
(folder / "cut_details.json").write_text(json.dumps(lay, indent=1))
# captions.txt: title + one line per cut, in output order
def ts(s):
    h, m, sec = s.split(":"); return int(h) * 3600 + int(m) * 60 + float(sec)
evs, cards = [], []
for l in (folder / "captions.ass").read_text().splitlines():
    if not l.startswith("Dialogue:"): continue
    p = l.split(",", 9)
    if p[3] not in ("Default", "Cap", "Caption", "Captions") and "Title" in p[3]: continue
    if p[3] == "Label": continue
    txt = re.sub(r"\{[^}]*\}", "", p[9]).replace("\\N", " ").strip()
    if p[3] == "Callout":          # our own text card: listed separately, never inside the spoken line
        cards.append((ts(p[1]), ts(p[2]), txt)); continue
    evs.append((ts(p[1]), p[3], txt))
title = " ".join(t for _, st, t in evs if "Title" in st or st == "Hook")
caps = [(a, t) for a, st, t in evs if not ("Title" in st or st == "Hook")]
caps.sort()
# a caption split at a layout edge (same words, new position) is one caption
caps = [c for i, c in enumerate(caps) if i == 0 or c[1] != caps[i - 1][1]]
joins, acc = [], 0.0
for a, b in lay["cuts"][:-1]:
    acc += b - a; joins.append(acc)
lines, cur, j = [], [], 0
for a, t in caps:
    while j < len(joins) and a >= joins[j] - 0.05:
        lines.append(" ".join(cur)); cur = []; j += 1
    cur.append(t)
lines.append(" ".join(cur))
spec_title = lay["spec"].get("hook", title)
card_txt = ("\n\nCARDS ON SCREEN (our own text cards, shown beside the captions):\n"
            + "\n".join(f"{a:.1f}-{b:.1f}s  {t}" for a, b, t in sorted(set(cards)))) if cards else ""
(folder / "captions.txt").write_text(f"TITLE: {spec_title}\n\nCAPTIONS AS SHOWN (one line per cut):\n" + "\n".join(l for l in lines if l) + card_txt + "\n")
print("built", folder.name, "lines", len([l for l in lines if l]))
