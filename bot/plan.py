"""Pick the moments and write the render specs for one campaign.

Two sources of truth, in this order:
  1. campaigns/<c>/plan.json written by the reviewer (Claude reading the whole transcript and rico's
     critiques): {"clips": [render_clip spec, ...], "why": "..."}  -> used as is.
  2. otherwise the entertainment scorecard (find_moments.py) picks the top moments automatically and
     this file turns them into plain specs (one cut, auto framing, no callouts).
Max 3 clips per campaign (rico, 2026-10-27). Under-the-bar clips are replaced by the next moment,
never re-cut in a loop; at most MAX_TRIES renders per campaign per run.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import audio_energy  # noqa: E402
import find_moments as fm  # noqa: E402
import genres  # noqa: E402
import profiles  # noqa: E402

MAX_CLIPS, MAX_TRIES = 3, 6
STAKES = fm.MONEY + "|" + fm.FAIL + "|" + fm.SURPRISE + "|" + fm.EMOTION + "|" + fm.FAMOUS


def slug(s, n=28):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:n].rstrip("-") or "clip"


def hook_text(c):
    """Title band: the strongest sentence of the moment, 4-12 words, ends clean."""
    h = c["hook"].rstrip(".…")
    h = re.sub(r"^((and|so|but|like|yeah|um|uh|okay|ok|right|well|i mean)[, ]+)+", "", h, flags=re.I).strip()
    if h.endswith("..."):
        h = h[:-3]
    return (h[:1].upper() + h[1:]).strip() + "."


def auto_specs(words_path, gfx_path, source, brief, campaign, out_dir, used=()):
    prof_name = brief.get("style") or "podcast"
    energy = None
    if profiles.profile(prof_name)["energy"]:
        ep = Path(out_dir).parent / "energy.json"
        if not ep.exists():
            json.dump(audio_energy.energy(source), open(ep, "w"))
        energy = json.load(open(ep))
    cands = fm_candidates(words_path, gfx_path, brief, prof_name, energy)
    mix = genre_mix(brief, json.load(open(words_path)))
    specs = []
    for c in cands:
        if any(min(c["end"], b) - max(c["start"], a) > 0 for a, b in used):
            continue
        text = c["text"]
        emph = sorted({w.strip(".,?!\"'").lower() for w in re.findall(r"[A-Za-z$][\w$,.']*", text)
                       if re.search(STAKES, w.lower())}, key=len, reverse=True)[:14]
        specs.append({
            "campaign": campaign, "source": str(source), "words": str(words_path),
            "parts": [[c["start"], c["end"]]], "hook": hook_text(c), "emphasis": emph,
            "focus": [], "overlays": [], "callouts": [], "sfx": False,
            "wide_split": [[0.25, 0.40, 0.06], [0.75, 0.40, 0.06]],   # generic two-shot seats; the reviewer's plan.json overrides
            "disclosure": brief.get("disclosure", ""), "style": brief.get("style", ""), "genres": mix,
            "out": str(Path(out_dir) / f"{slug(c['hook'])}.mp4"),
            "_why": f"score {c['score']}: " + ", ".join(f"{k} {v}" for k, v in c["reasons"].items() if v and k != "genres") + f" [{c['reasons'].get('genres', '')}]",
        })
        if len(specs) >= MAX_TRIES:
            break
    return specs


def genre_mix(brief, words):
    """The campaign's genres: reviewer's list (plan.json brief_overrides "genres"), else brief + transcript."""
    g = brief.get("genres")
    if isinstance(g, dict) and g:
        return g
    if isinstance(g, list) and g:
        return {x: round(1 / len(g), 2) for x in g}
    text = (brief.get("text", "") or "") + " " + " ".join(brief.get("rules", []))
    return genres.detect_mix(text, " ".join(w["text"] for w in words))


def fm_candidates(words_path, gfx_path, brief, prof_name="podcast", energy=None):
    words = json.load(open(words_path))
    gfx = json.load(open(gfx_path)) if gfx_path and Path(gfx_path).exists() else []
    prof = profiles.profile(prof_name)
    mix = genre_mix(brief, words)
    sents = fm.sentences(words)
    lo, hi = brief.get("min_s", 20), brief.get("max_s", 60)
    cands = []
    for i in range(len(sents)):
        for j in range(i + 1, min(i + 40, len(sents))):
            dur = sents[j]["end"] - sents[i]["start"]
            if dur < lo:
                continue
            if dur > hi + 2:
                break
            total, reasons, text, g = fm.score_window(sents[i:j + 1], gfx, prof, energy, mix)
            cands.append({"start": round(sents[i]["start"], 2), "end": round(sents[j]["end"], 2), "dur": round(dur, 1),
                          "score": total, "reasons": reasons, "first_line": sents[i]["text"],
                          "hook": fm.hook_from(sents[i:j + 1], prof), "graphics": g, "text": text})
    cands.sort(key=lambda c: -c["score"])
    picked = []
    for c in cands:
        if any(p["first_line"] == c["first_line"] or p["hook"] == c["hook"] for p in picked):
            continue   # run 1 of DIGGER rendered the same opening line twice at two lengths
        if all(min(c["end"], p["end"]) - max(c["start"], p["start"]) < 0.4 * min(c["dur"], p["dur"]) for p in picked):
            picked.append(c)
        if len(picked) >= 20:
            break
    return picked


def load(campaign_dir, words_path, gfx_path, source, brief, campaign, out_dir, used=()):
    if brief.get("style") not in profiles.PROFILES:   # no reviewer override: read the brief, then the footage
        try:
            words = json.load(open(words_path))
            dur = words[-1]["end"] if words else 0
        except Exception:
            words, dur = [], 0
        brief["style"] = profiles.resolve(brief, words, dur)
    plan = Path(campaign_dir) / "plan.json"
    if plan.exists() and json.loads(plan.read_text()).get("clips"):   # a plan without clips (overrides only) = auto picks
        p = json.loads(plan.read_text())
        specs = p.get("clips", [])[:MAX_CLIPS]
        try:
            mix = genre_mix(brief, json.load(open(words_path)))
        except Exception:
            mix = {"drama": 0.5, "business": 0.5}
        for s in specs:
            s.setdefault("genres", mix)
            s.setdefault("campaign", campaign); s.setdefault("source", str(source)); s.setdefault("words", str(words_path))
            s.setdefault("out", str(Path(out_dir) / f"{slug(s.get('hook', 'clip'))}.mp4"))
            s.setdefault("_why", p.get("why", "reviewer's plan"))
            s.setdefault("disclosure", brief.get("disclosure", ""))
            s.setdefault("style", brief.get("style", ""))
        return specs, "plan.json (reviewer)"
    return auto_specs(words_path, gfx_path, source, brief, campaign, out_dir, used=used), "entertainment scorecard (auto)"
