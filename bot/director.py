"""Creative Director (makeover release 7, board review 3, approved by rico 2026-11-04).

rico, 2026-11-04: "ensure there is ways for the manufacturing of the clips to think outside the box and create a mind
of its own when deciding what to choose and to brainstorm ideas and reach for logic and reason when combining and
making clips." Before release 7 every candidate was one format: the moment as it happened.

What it does, after the Moment Hunter's picks and before anything is rendered:
  1. LOOK     the Visual Tagger tags every candidate window (one sample per second): close-ups, crowd, lights,
              faces, dark, motion. Stage shows also get the whole show tagged at its keyframes (cutaway material).
  2. BRAINSTORM for each moment, every format in FORMATS that fits the content type and can be built from this
              footage becomes a concept (the moment as it is, a song-bed montage with beat-cut cutaways, ...).
  3. REASON   each concept gets points: the picker's own rank, what the picture shows (visual_points, per content
              type), and the format's fit; and ONE line a viewer would care about, written into the SUMMARY.
  4. CHOOSE   the concepts are ordered best first, with the formats mixed, so the render machines try different
              ideas side by side instead of three versions of one.

FORMATS is the format library of the deck (slide 15); "builder" says which ones this release can make.
"""
import json
from pathlib import Path

import profiles
import tagger

FORMATS = {
    "straight":   dict(fits=set(profiles.PROFILES), builder=True, bonus=0,
                       idea="one strong moment, hook in the first seconds"),
    "song-bed":   dict(fits={"performance", "edit"}, builder=True, bonus=2,
                       idea="the song plays whole; the picture cuts on the beat to the crowd, the lights and the stage"),
    "cold-open":  dict(fits={"podcast", "talker", "cinematic", "serious"}, builder=False, bonus=0,
                       idea="the punchline first, then the story (plan.py teaser)"),
    "voice-over": dict(fits={"talker"}, builder=False, bonus=0, idea="the speaker's line over the best matching shots"),
    "reaction":   dict(fits={"stream"}, builder=False, bonus=0, idea="facecam on top, the action below"),
    "top-moments": dict(fits={"edit", "stream"}, builder=False, bonus=0, idea="three quick moments with a number card each"),
}
STAGE = {"performance", "edit"}


def visual_points(summ, style, music=False):
    """(0-10, reasons) for what a window SHOWS, by content type. summ = tagger.summary of its samples."""
    why = []
    if style in STAGE or music:
        p = 4 * min(summ["close"] / 0.4, 1) + 3 * min(summ["crowd"] / 0.2, 1) + 2 * min(summ["lights"] / 0.15, 1) \
            + min(summ["motion"] * 25, 1)
        if summ["close"] >= 0.2: why.append(f"close-ups {summ['close']:.0%}")
        if summ["crowd"] >= 0.1: why.append(f"crowd {summ['crowd']:.0%}")
        if summ["lights"] >= 0.08: why.append(f"light/pyro moments {summ['lights']:.0%}")
    elif style in ("cinematic", "stream"):
        p = 5 * min(summ["faces"] / 0.7, 1) + 3 * min(summ["close"] / 0.4, 1) + 2 * min(summ["motion"] * 25, 1)
        if summ["close"] >= 0.3: why.append(f"close-ups {summ['close']:.0%}")
    else:   # talking shows: a face on screen, big enough
        p = 7 * min(summ["faces"] / 0.85, 1) + 3 * min(summ["close"] / 0.6, 1)
        why.append(f"face on screen {summ['faces']:.0%}")
    if summ["dark"] > 0.2:
        p -= 4
        why.append(f"dark {summ['dark']:.0%}")
    return max(0, min(10, round(p))), why


def brainstorm(specs, source, brief, work, log=print, keep=8):
    """Concepts from the picker's specs: (ordered specs, notes). Never raises: a broken look keeps the picker's order."""
    style = brief.get("style") or "podcast"
    music = bool(specs and all(sp.get("music") for sp in specs))
    notes = []
    try:
        top = specs[:keep]
        ranges = [tuple(sp["parts"][0]) for sp in top if sp.get("parts")]
        tags = tagger.tag_windows(source, [(a, min(b, a + 60)) for a, b in ranges])
        show, cut_times = [], []
        if style in STAGE or music:
            import music_moments
            show = tagger.tag_show(source, Path(work) / "tags.json")
            cut_times = music_moments.cuts(source, Path(work) / "cuts.json")
        concepts = []
        for rank, sp in enumerate(top):
            a, b = sp["parts"][0]
            own = tags.get((a, min(b, a + 60)), [])
            vis, why = visual_points(tagger.summary(own), style, music)
            sp["visual"] = {"points": vis, "why": why}
            base = 10 - rank * 10 / max(len(top), 1)
            concepts.append((base + vis, "straight", sp, why))
            if (style in STAGE or music) and show:
                import montage
                v = montage.build(sp, show, cut_times, montage.beats(source, a, b), own)
                if v:
                    v["visual"] = {"points": min(10, vis + 2), "why": why + ["cutaways to the show's best shots"]}
                    concepts.append((base + vis + FORMATS["song-bed"]["bonus"], "song-bed", v, why))
        concepts.sort(key=lambda c: -c[0])
        # mix the formats: the first machines try different ideas, not three versions of one
        ordered, seen = [], set()
        for c in concepts:
            if c[1] not in seen:
                ordered.append(c)
                seen.add(c[1])
        ordered += [c for c in concepts if c not in ordered]
        out = []
        for score, fmt, sp, why in ordered:
            reason = f"concept {fmt} ({FORMATS[fmt]['idea']}); picture {sp['visual']['points']}/10" + (f": {', '.join(why)}" if why else "")
            if not sp.get("_why", "").startswith("concept"):
                sp["_why"] = reason + " | " + sp.get("_why", "")
            sp["concept"] = fmt
            out.append(sp)
            notes.append(f"CONCEPT {score:4.1f}  {fmt:9s} {sp.get('hook', '')[:50]} @ {sp['parts'][0][0]:.0f}s  {reason}")
        fits = [f for f, d in FORMATS.items() if style in d["fits"]]
        notes.insert(0, f"Creative Director: {len(concepts)} concept(s) from {len(top)} moment(s); formats for {style}: "
                        + ", ".join(f + ("" if FORMATS[f]["builder"] else " (planned)") for f in fits))
        for n in notes[:6]:
            log(n)
        return out + specs[keep:], notes
    except Exception as e:
        log(f"Creative Director skipped ({type(e).__name__}: {str(e)[:80]})")
        return specs, [f"Creative Director skipped ({type(e).__name__})"]


if __name__ == "__main__":
    import sys
    sp = json.loads(Path(sys.argv[1]).read_text())
    out, n = brainstorm(sp if isinstance(sp, list) else [sp], sys.argv[2], {"style": sys.argv[3] if len(sys.argv) > 3 else ""}, Path("."))
    print("\n".join(n))
