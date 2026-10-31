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
    if has_teaser and spec.get("teaser_exact"):
        ranges = ranges[:1] + guard_edges(src, ranges[1:], words)   # the hand-checked teaser cut stays as given
    else:
        ranges = guard_edges(src, ranges, words)

    pieces, off = [], 0
    for s, e in ranges:
        n = round((e - s) * FPS)
        pieces.append((s, s + n / FPS, off))
        off += n / FPS
    return ranges, pieces


# ---------- edge guard (Studio v2 release 4, experiment "cut edges") ----------
# The re-edit of run 41216937690 (Spotlight, 2026-10-31) cut inside words: start 8908.77 cut "it", 12283.12 cut
# "think", the end 12321.18 cut "That's". snap() picks the quietest 30 ms near an edge, and the moves after it (onto a
# camera cut, past a credit card) can land an edge back inside a word. The guard runs last: an edge inside a word
# moves into the silence on the side that keeps sentences whole, at the quietest point of that gap.
EDGE_PAD = (0.05, 0.02)   # transcript word starts run late: a word "starts" 50 ms before its stamp


def _sentence_start(words, i):
    w = words[i]["text"].strip()
    prev = words[i - 1]["text"].strip() if i > 0 else "."
    return prev.endswith((".", "?", "!")) or (w[:1].isupper() and w[:2] not in ("I ", "I'") and w != "I")


CORE = 0.03              # only the core of a stamped word counts: its stamped edges are +-30 ms guesses


def inside(words, t):
    """Index of the word whose core holds t, or None. Words stamped shorter than 0.1 s (whisper's zero-length
    fillers between run-on words) carry no timing to trust and never move an edge."""
    for i, w in enumerate(words):
        if w["end"] - w["start"] >= 0.1 and w["start"] + CORE < t < w["end"] - CORE:
            return i
    return None


def guard_edges(src, ranges, words, audio_fn=None):
    """Returns ranges whose every edge sits in silence between words. A start inside a word: before it when the word
    opens a sentence, else after it. An end inside a word: before it when the word opens the next sentence, else
    after it. The new edge is the quietest 30 ms of that gap (audio_fn(lo, hi) -> t), or the gap's middle."""
    words = sorted(words, key=lambda w: w["start"])
    if audio_fn is None:
        def audio_fn(lo, hi):
            try:
                from render_clip import load_audio, quietest
                return quietest(load_audio(src, lo, hi), lo, lo, hi)
            except Exception:
                return (lo + hi) / 2

    def gap_before(i):
        lo = words[i - 1]["end"] + 0.01 if i > 0 else words[i]["start"] - 0.4
        return lo, max(words[i]["start"] - EDGE_PAD[0], lo + 0.02)

    def gap_after(i):
        hi = words[i + 1]["start"] - EDGE_PAD[0] if i + 1 < len(words) else words[i]["end"] + 0.4
        return words[i]["end"] + EDGE_PAD[1], max(hi, words[i]["end"] + EDGE_PAD[1] + 0.02)

    out = []
    for s0, e0 in ranges:
        s, e = s0, e0
        i = inside(words, s)
        if i is not None:
            lo, hi = gap_before(i) if _sentence_start(words, i) else gap_after(i)
            s = audio_fn(lo, hi)
        j = inside(words, e)
        if j is not None:
            lo, hi = gap_before(j) if _sentence_start(words, j) and j > 0 else gap_after(j)
            e = audio_fn(lo, hi)
        out.append([s, e] if e - s > 0.3 else [s0, e0])
    return out
