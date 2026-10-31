"""Golden set (Release 1, board review 2): clips rico approved, kept as text fixtures (captions, cuts, QA report,
words; no video). Any change must keep their judge scores within GOLD_TOLERANCE of the recorded baseline.

  python3 tests/golden_tools.py --record     re-record tests/golden/baseline.json (only when a change is MEANT to move scores)
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot"))
GOLD = ROOT / "tests" / "golden"
BASELINE = GOLD / "baseline.json"
GOLD_TOLERANCE = 3


def judge(folder):
    """The judge's score and areas for one golden clip, without the video: silences are taken as none."""
    import judge_clip
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / folder.name
        shutil.copytree(folder, d)
        (d / f"{folder.name}.mp4").write_bytes(b"")   # judge_clip looks for the clip file; nothing reads it with silence stubbed
        real, judge_clip.silence = judge_clip.silence, lambda mp4: []
        try:
            total = judge_clip.main(d)
        finally:
            judge_clip.silence = real
        rep = (d / "judge_report.md").read_text()
    areas = {}
    for line in rep.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) > 3 and "/" in parts[2] and parts[2].split("/")[0].isdigit():
            areas[parts[1]] = int(parts[2].split("/")[0])
    return total, areas


def clips():
    return sorted(p for p in GOLD.iterdir() if p.is_dir())


if __name__ == "__main__" and "--record" in sys.argv:
    out = {c.name: dict(zip(("total", "areas"), judge(c))) for c in clips()}
    BASELINE.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
