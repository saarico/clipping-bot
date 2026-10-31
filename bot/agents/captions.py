"""Caption Designer: the hook, the who-line and the word-timed captions, in ONE spot (rico 2026-10-31).

In:  the spec (hook, hook_hi, tag, emphasis, look, profanity), edits.json pieces, the Camera Operator's
     layouts (where faces are while the hook shows) and cards.json (watermark height).
Out: captions.ass (also kept next to the clip as <name>.ass for qa_check.py and the layout inspector).
"""
from pathlib import Path

from render_clip import build_ass


def write(spec, pieces, layouts, tmp):
    """Returns (ass_path, total_seconds)."""
    layouts_simple = [(a, b, l.split("+")[0]) for a, b, l in layouts]
    ass, total = build_ass(spec, pieces, layouts_simple)
    (tmp / "caps.ass").write_text(ass)
    Path(spec["out"]).with_suffix(".ass").write_text(ass)   # kept for qa_check.py
    return tmp / "caps.ass", total
