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
import brief as briefmod  # noqa: E402
import engage  # noqa: E402
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
    h = (h[:1].upper() + h[1:]).strip().rstrip(" ,;:-\u2013\u2014")   # "10 billion in 12 months,." happened (Higgsfield, 2026-10-30)
    return h if h[-1:] in "!?." else h + "."   # "bang bang bang!." happened (2026-10-28)


FILLER_START = re.compile(r"^(because|and|so|but|like|yeah|yes|no|um|uh|okay|ok|right|well|i mean|you know)\b[,.]?", re.I)


def spec_for(c, why, source, words_path, brief, campaign, out_dir, mix):
    text = c["text"]
    emph = sorted({w.strip(".,?!\"'").lower() for w in re.findall(r"[A-Za-z$][\w$,.']*", text)
                   if re.search(STAKES, w.lower())}, key=len, reverse=True)[:14]
    return {
        "campaign": campaign, "source": str(source), "words": str(words_path),
        "parts": [[c["start"], c["end"]]], "hook": hook_text(c), "emphasis": emph,
        "focus": [], "overlays": [], "callouts": c.get("callouts", []), "sfx": False,
        "wide_split": [[0.25, 0.40, 0.06], [0.75, 0.40, 0.06]],   # generic two-shot seats; the reviewer's plan.json overrides
        "disclosure": brief.get("disclosure", ""), "style": brief.get("style", ""), "genres": mix, "look": brief.get("look") or {},
        "tag": brief.get("speaker_tag") or briefmod.speaker_tag(brief.get("text", "")),   # who is talking (on screen for the first seconds)
        "brief": brief_lengths(brief),
        "out": str(Path(out_dir) / f"{slug(c['hook'])}.mp4"),
        "_why": why,
    }


def refine(c, sents, lo, hi, style=None):
    """The edges of a cut chosen by the audience read (engage.read): among sentence windows that start up to 3
    sentences later and end up to 4 sentences earlier or 2 later, inside lo-hi seconds, take the one with the best
    read (a gate failure costs 40). rico 2026-10-30: clips opened on host preamble and ended on an aside."""
    inside = [i for i, s in enumerate(sents) if s["end"] > c["start"] + 0.3 and s["start"] < c["end"] - 0.3]
    if not inside:
        return c
    i0, i1 = inside[0], inside[-1]
    words = [w for s in sents[max(i0 - 5, 0):min(i1 + 6, len(sents))] for w in s.get("words", [])]
    if not words:
        return c

    def gap_before(k):   # silence between the previous word and this sentence's first word
        w0 = sents[k]["words"][0]
        prev = [w["end"] for w in words if w["end"] <= w0["start"] + 0.01 and w is not w0]
        return w0["start"] - max(prev) if prev else 1.0

    def gap_after(k):
        w1 = sents[k]["words"][-1]
        nxt = [w["start"] for w in words if w["start"] >= w1["end"] - 0.01 and w is not w1]
        return min(nxt) - w1["end"] if nxt else 1.0

    best = None
    for a in range(max(i0 - 3, 0), min(i0 + 7, i1 + 1)):
        for b in range(max(a, i1 - 5), min(i1 + 4, len(sents))):
            d = sents[b]["end"] - sents[a]["start"]
            if not (lo - 0.5 <= d <= hi + 0.5):
                continue
            r = engage.read(words, [[sents[a]["start"], sents[b]["end"]]], style, c.get("hook", ""))
            score = r["total"] - 40 * len(r["fails"]) - 2 * abs(a - i0) - abs(b - i1)
            # an edge needs a pause to cut in: whisper's sentence breaks with no gap ("...the same Did you know")
            # left clipped words at both ends of run 9's Yuri clip
            for g in (gap_before(a), gap_after(b)):
                score -= 45 if g < 0.12 else 10 if g < 0.25 else 0
            if best is None or score > best[0]:
                best = (score, a, b, r)
    if not best:
        return c
    _, a, b, r = best
    out = dict(c, start=round(sents[a]["start"], 2), end=round(sents[b]["end"], 2),
               text=" ".join(s["text"] for s in sents[a:b + 1]), audience=r["total"], audience_fails=r["fails"])
    return out


UNIT = re.compile(r"^(million|billion|thousand|percent|people|months?|years?|days?|weeks?|hours?|dollars?|bucks|x|k|m|b)\b[.,]?$", re.I)


def auto_callouts(words, start, end, limit=4, gap=5.0):
    """Big number cards for a talking show (rico 2026-10-30: "bump up editing"): every dollar figure or number the
    speaker says inside the cut becomes a 2.5 s callout ("$4 MILLION", "30% LOWER"), at most `limit` per clip and
    `gap` seconds apart. Words only, so it is allowed where outside footage is not."""
    out, last_t = [], -1e9
    ws = [w for w in words if start <= w["start"] < end]
    i = 0
    while i < len(ws) and len(out) < limit:
        t = ws[i]["text"].strip(",.?!")
        if re.match(r"^\$?\d[\d,.]*%?$", t) or t.lower() in ("million", "billion", "thousand"):
            # join whisper's "$10 ,000" and the unit that follows ("4 million", "30% lower", "400 people")
            phrase, j = [t], i + 1
            while j < len(ws) and (re.match(r"^,\d{3}$", ws[j]["text"].strip(".?!")) or ws[j]["text"].strip(".?!,") == "%" or UNIT.match(ws[j]["text"])):
                phrase.append(ws[j]["text"].strip(".?!")); j += 1
            if j < len(ws) and ws[j]["text"].strip(".?!,").lower() in ("lower", "higher", "more", "less", "margin", "margins", "churn", "growth", "revenue", "valuation", "a", "per"):
                phrase.append(ws[j]["text"].strip(".?!,"))
                if phrase[-1] in ("a", "per") and j + 1 < len(ws):
                    phrase.append(ws[j + 1]["text"].strip(".?!,"))
            text = re.sub(r"\s+%", "%", re.sub(r"\s+,", ",", " ".join(phrase))).upper().strip(", ")
            bare = re.fullmatch(r"\d{1,2}", text)   # "12" on its own says nothing on a card
            if ws[i]["start"] - last_t >= gap and len(text) <= 22 and not bare and not re.match(r"^(ONE|TWO|FIRST|SECOND|HALF)$", text):
                out.append({"from": round(ws[i]["start"] - 0.1, 2), "to": round(min(ws[i]["start"] + 2.5, end - 0.2), 2), "text": text})
                last_t = ws[i]["start"]
            i = j
            continue
        i += 1
    return [c for c in out if c["to"] - c["from"] >= 0.8]


def brief_specs(words_path, source, brief, campaign, out_dir, used=(), log=print):
    """The brief's own clip ideas (brief.moments) as specs, in the brief's order. Each idea's words must really sit
    at its time in OUR file (the brief's times are for its reference video): at least half of the hook's content
    words within the range, else the idea is looked up in the whole transcript and moved, else skipped. The cut
    snaps to sentence edges and is stretched or trimmed into the brief's length window."""
    ideas = brief.get("moments") or []
    if not ideas:
        return []
    words = json.load(open(words_path))
    sents = fm.sentences(words)
    mix = genre_mix(brief, words)
    lo, hi = brief.get("min_s", 20), brief.get("max_s", 60)
    norm = lambda s: re.sub(r"[^a-z0-9$% ]", "", s.lower())
    specs = []
    for idea in ideas:
        key = [w for w in norm(idea["hook"]).split() if len(w) > 3 or w.startswith("$") or w.isdigit()]
        if not key:
            continue
        def hits(a, b):
            seg = norm(" ".join(w["text"] for w in words if a - 1 <= w["start"] <= b + 1))
            return sum(1 for k in key if k in seg) / len(key)
        a, b = idea["start"], idea["end"]
        if hits(a - 20, b + 20) < 0.5:
            # not where the brief says: find the sentence run that holds the line, anywhere in the episode
            best, where = 0.0, None
            for i in range(len(sents)):
                h = hits(sents[i]["start"], sents[i]["start"] + (b - a))
                if h > best:
                    best, where = h, sents[i]["start"]
            if best < 0.6:
                log(f"brief idea skipped, its words are not in this file: {idea['hook'][:60]}")
                continue
            log(f"brief idea moved {a:.0f}s -> {where:.0f}s (times in the brief are for another cut): {idea['hook'][:50]}")
            a, b = where, where + (b - a)
        inside = [s for s in sents if s["end"] > a + 0.3 and s["start"] < b - 0.3]
        if not inside:
            continue
        i0, i1 = sents.index(inside[0]), sents.index(inside[-1])
        while i0 < i1 and FILLER_START.match(sents[i0]["text"]) and sents[i1]["end"] - sents[i0 + 1]["start"] >= lo:
            i0 += 1   # never open on "Because, I mean..."
        while sents[i1]["end"] - sents[i0]["start"] < lo and i1 + 1 < len(sents):
            i1 += 1
        while sents[i1]["end"] - sents[i0]["start"] > hi and i1 > i0:
            i1 -= 1
        start, end = sents[i0]["start"], sents[i1]["end"]
        if not (lo - 1 <= end - start <= hi + 1):
            log(f"brief idea skipped, cannot fit {lo}-{hi} s: {idea['hook'][:60]}")
            continue
        if any(min(end, ub) - max(start, ua) > 0 for ua, ub in used):
            continue
        c = {"start": round(start, 2), "end": round(end, 2), "hook": idea["hook"], "text": " ".join(s["text"] for s in sents[i0:i1 + 1])}
        c = refine(c, sents, lo, hi, brief.get("style"))
        if profiles.profile(brief.get("style"))["cards"]:
            c["callouts"] = auto_callouts(words, c["start"], c["end"])
        why = "the brief's own clip idea" + (f" ({idea['note']})" if idea.get("note") else "") + f" | audience {c.get('audience', '?')}"
        specs.append(spec_for(c, why, source, words_path, brief, campaign, out_dir, mix))
    return specs


def auto_specs(words_path, gfx_path, source, brief, campaign, out_dir, used=()):
    prof_name = brief.get("style") or "podcast"
    energy = None
    if profiles.profile(prof_name)["energy"]:
        ep = Path(out_dir).parent / "energy.json"
        if not ep.exists():
            json.dump(audio_energy.energy(source), open(ep, "w"))
        energy = json.load(open(ep))
    cands = fm_candidates(words_path, gfx_path, brief, prof_name, energy)
    all_words = json.load(open(words_path))
    mix = genre_mix(brief, all_words)
    sents = fm.sentences(all_words)
    lo, hi = brief.get("min_s", 20), brief.get("max_s", 60)
    specs = []
    for c in cands:
        if any(min(c["end"], b) - max(c["start"], a) > 0 for a, b in used):
            continue
        c = refine(c, sents, lo, hi, prof_name)
        if profiles.profile(prof_name)["cards"]:
            c["callouts"] = auto_callouts(all_words, c["start"], c["end"])
        why = f"score {c['score']}: " + ", ".join(f"{k} {v}" for k, v in c["reasons"].items() if v and k != "genres") + f" [{c['reasons'].get('genres', '')}]"
        specs.append(spec_for(c, why, source, words_path, brief, campaign, out_dir, mix))
        if len(specs) >= MAX_TRIES:
            break
    return specs


def brief_lengths(brief):
    """The campaign's own min/max seconds, carried in every spec so judge_clip grades length against the brief
    (the spec never held the brief: the judge used the profile's window alone)."""
    return {k: brief[k] for k in ("min_s", "max_s") if isinstance(brief.get(k), (int, float)) and brief[k]}


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
            if FILLER_START.match(sents[i]["text"]):
                continue   # a clip never opens on "Because, I mean..." (rico lost interest in 4 s, Higgsfield c01, 2026-10-30)
            total, reasons, text, g = fm.score_window(sents[i:j + 1], gfx, prof, energy, mix)
            cands.append({"start": round(sents[i]["start"], 2), "end": round(sents[j]["end"], 2), "dur": round(dur, 1),
                          "score": total, "reasons": reasons, "first_line": sents[i]["text"],
                          "ij": (i, j), "graphics": g, "text": text})
    cands.sort(key=lambda c: -c["score"])
    picked = []
    for c in cands:
        if "hook" not in c:   # the hook is only written for windows that reach the pick loop (thousands never do)
            i, j = c.pop("ij")
            c["hook"] = fm.hook_from(sents[i:j + 1], prof)
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
            if isinstance(s["genres"], list):
                s["genres"] = {g: round(1 / len(s["genres"]), 2) for g in s["genres"]}
            s.setdefault("brief", brief_lengths(brief))
            s.setdefault("campaign", campaign); s.setdefault("source", str(source)); s.setdefault("words", str(words_path))
            s.setdefault("out", str(Path(out_dir) / f"{slug(s.get('hook', 'clip'))}.mp4"))
            s.setdefault("_why", p.get("why", "reviewer's plan"))
            s.setdefault("disclosure", brief.get("disclosure", ""))
            s.setdefault("style", brief.get("style", ""))
            if brief.get("look"):
                s.setdefault("look", brief["look"])
        # behind the reviewer's picks: the scorecard's best other moments, for the grade-and-retry loop
        try:
            taken = tuple(used) + tuple((p[0], p[1]) for sp in specs for p in sp.get("parts", []))
            extra = auto_specs(words_path, gfx_path, source, brief, campaign, out_dir, used=taken)
        except Exception as e:
            extra = []
        for x in extra:
            x["_why"] = "fallback: " + x["_why"]
        return specs + extra[:MAX_TRIES - len(specs)], "plan.json (reviewer)"
    own = brief_specs(words_path, source, brief, campaign, out_dir, used=used)
    if own:   # the campaign wrote down what sells: those moments first, the scorecard's picks behind them
        taken = tuple(used) + tuple((p[0], p[1]) for sp in own for p in sp.get("parts", []))
        extra = auto_specs(words_path, gfx_path, source, brief, campaign, out_dir, used=taken)
        return (own + extra)[:MAX_TRIES * 2], f"the brief's clip ideas ({len(own)}) + scorecard"
    return auto_specs(words_path, gfx_path, source, brief, campaign, out_dir, used=used), "entertainment scorecard (auto)"
