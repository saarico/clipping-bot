"""Motion & Graphics: everything drawn over the footage that is not a caption.

In:  the spec (overlays, callouts, watermark, hold_end_from, disclosure).
Out: cards.json = {"overlays": [...], "callouts": [...], "watermark": path or null, "wm_h": px, "hold_end_from": s}.
Owns: the watermark's size (the Caption Designer keeps the hook clear of it), the show's own cards that the
Camera Operator lays out, our number callouts, and the end hold. Never moves a face.
"""
from pathlib import Path

from render_clip import WM_W


def plan(spec):
    """Sets spec["_wm_h"] when the watermark exists (build_ass reads it). Returns the cards.json dict."""
    wm = spec.get("watermark")
    if wm and Path(wm).exists():
        from PIL import Image
        iw, ih = Image.open(wm).size
        spec["_wm_h"] = int(WM_W * ih / iw) // 2 * 2
    else:
        wm = None
    return {"overlays": spec.get("overlays", []), "callouts": spec.get("callouts", []), "watermark": wm,
            "wm_h": spec.get("_wm_h", 0), "hold_end_from": spec.get("hold_end_from")}
