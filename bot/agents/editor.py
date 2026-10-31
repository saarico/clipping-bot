"""Editor: decides the cut before anyone renders.

In:  the spec (teaser, parts, tighten, max_gap, teaser_exact, style) + the words file.
Out: edits.json = {"ranges": [[s, e], ...] source seconds, "pieces": [[s, e, offset], ...]} with every
     piece a whole number of frames, so picture and sound line up exactly.
Owns: dead-air removal, snapping edges to the quietest moment, moving edges onto camera cuts, trimming
burned-in credit cards (talking shows keep theirs).
"""
from render_clip import FPS, check_source, profiles, snap, tighten, trim_cards, trim_to_cuts


def cut(spec, src, words):
    """Returns (ranges, pieces)."""
    has_teaser = bool(spec.get("teaser"))
    ranges = ([spec["teaser"]] if has_teaser else []) + spec["parts"]
    check_source(src)
    if spec.get("tighten", True):
        n_before = len(ranges)
        ranges = tighten(ranges, words, spec.get("max_gap", 0.7))
        if len(ranges) > n_before:
            print(f"dead air: {len(ranges) - n_before} pause(s) cut")
    ranges = snap(src, ranges, words)
    if has_teaser and spec.get("teaser_exact"):
        ranges[0] = list(spec["teaser"])   # hand-checked cut (e.g. the next speaker starts mid-word)
    ranges = trim_to_cuts(src, ranges, words)
    if not profiles.profile(spec.get("style"))["cards"]:
        ranges = trim_cards(src, ranges, words, spec)

    pieces, off = [], 0
    for s, e in ranges:
        n = round((e - s) * FPS)
        pieces.append((s, s + n / FPS, off))
        off += n / FPS
    return ranges, pieces
