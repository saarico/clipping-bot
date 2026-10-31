"""The pitch: judge a candidate moment from its WORDS before any rendering (rico, 2026-10-29: "reading the
script / captions and the bot deciding if it's good or entertaining enough per the campaign's style, so we
aren't wasting time making clips").

Every candidate (reviewer pick or scorecard moment) is read against the campaign's profile and genre mix the
way the finished clip would be judged (judge_clip.py), minus what needs a picture: hook, story, entertainment,
comedy, pace and length. Under PITCH_BAR the moment is not rendered; the SUMMARY lists every pitch with its
verdict and reasons. When nothing passes, the best pitch is rendered anyway, marked, so a campaign still gets
one try and rico sees why the material is thin.

    python3 bot/pitch.py <words.json> <spec.json | plan.json> [brief.json]
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import engage  # noqa: E402
import find_moments as fm  # noqa: E402
import genres  # noqa: E402
import plan as planner  # noqa: E402
import profiles  # noqa: E402

PITCH_BAR = 60
MAXES = {"hook": 20, "story": 10, "entertainment": 10, "comedy": 5, "pace": 10, "length": 10}   # 65 word-judgeable points


def words_in(words, parts):
    out = []
    for a, b in parts:
        out += [w for w in words if w["end"] > a and w["start"] < b]
    return out


def proper_names(words):
    """Names the transcript itself capitalises mid-sentence (captions are upper case, so this is the only tell)."""
    names = set()
    for prev, w in zip([None] + words[:-1], words):
        t = w["text"].strip('",.?!()\'')
        if t[:1].isupper() and len(t) > 2 and prev and not prev["text"].rstrip('"\'').endswith((".", "?", "!")):
            names.add(t.lower())
    return names


def hook_points(title, first_line, names, prof, opening_text):
    """(0-20, reasons): the title and the first line, as judge_clip and the pitch both grade them (one place)."""
    h, why = 20, []
    head = " ".join(first_line.split()[:8])
    if prof["clarity"] and re.match(fm.BACKREF, head.strip(), flags=re.I):
        h -= 8; why.append("first line starts on a pointer word")
    has_name = any(t.strip('",.?!()\'').lower() in names for t in head.split()[1:])
    if prof["clarity"] and not (re.search(fm.NUMBER, head, re.I) or has_name or re.search(r"\b(I|we|my)\b", head, re.I)):
        h -= 5; why.append("first line names no one and nothing")
    # every profile (2026-10-29, rico: "heavy increase in judgement"): a title carries a name, a number, a question or a quote
    if not (re.search(fm.NUMBER, title, re.I) or "?" in title or '"' in title or re.search(fm.FAMOUS, title, re.I)
            or any(t.strip('",.?!()\'').lower() in names for t in title.split()) or re.search(r"\b(I|we|my|you)\b", title, re.I)):
        h -= 5; why.append("title has no name, number, question or quote")
    if len(title.split()) > 14:
        h -= 3; why.append("title over 14 words")
    if prof["back_refs"] and re.search(fm.PODCAST_TALK, " ".join(opening_text.split()[:25]).lower()):
        h -= 6; why.append("opens with podcast talk")
    return max(0, h), why


def story_points(body, prof):
    """(0-10, notes, reasons): stakes, a contrast or question, a finished ending, no podcast back-references."""
    low = body.lower()
    st, why = 0, []
    stakes = fm.count(fm.MONEY, low) + fm.count(fm.FAIL, low) + fm.count(fm.SURPRISE, low) + fm.count(fm.EMOTION, low) + 2 * fm.count(fm.FAMOUS, low)
    st += min(4, stakes)
    if fm.count(fm.CONTRAST, low) or "?" in body[:300]:
        st += 2
    last = body.strip().splitlines()[-1].strip().rstrip('"\')') if body.strip() else ""
    finished = last.endswith((".", "!", "?"))
    st += 2 if finished else 0
    if not finished:
        why.append("ends mid-sentence")
    back = fm.count(fm.PODCAST_TALK, low) if prof["back_refs"] else 0
    st += 2 if back == 0 else 0
    if back:
        why.append(f"{back} podcast back-reference(s)")
    if prof["reactions"] > 1:
        st += min(2, fm.count(profiles.HYPE, low))
    if stakes == 0:
        why.append("no stakes: no money, failure, surprise, emotion or famous name")
    notes = [f"{stakes} stakes word(s)", f"{back} podcast back-reference(s)", "ends on a finished sentence" if finished else "ends mid-sentence"]
    return min(10, st), notes, why


def length_points(dur, prof, brief=None):
    """10 inside the profile's sweet spot, 6 inside the wider window, which the brief's own min/max extend."""
    (l0, l1), (o0, o1) = prof["length"], prof["ok_len"]
    if brief:
        o0, o1 = min(o0, brief.get("min_s", o0)), max(o1, brief.get("max_s", o1))
        l0, l1 = min(l0, brief.get("min_s", l0)), max(l1, min(brief.get("max_s", l1), o1))
    return (10 if l0 <= dur <= l1 else 6 if o0 <= dur <= o1 else 0), (o0, o1)


def score(spec, words, brief=None):
    """{"total": 0-100, "verdict": "PASS"|"REJECT", "areas": {...}, "why": [...]} for one candidate."""
    brief = brief or {}
    prof = profiles.profile(spec.get("style") or brief.get("style"))
    parts = spec.get("parts") or []
    part_words = [words_in(words, [pt]) for pt in parts]
    ws = [w for pw in part_words for w in pw]
    body = " ".join(w["text"] for w in ws)
    low = body.lower()
    dur = sum(b - a for a, b in parts)
    title = spec.get("hook", "")
    areas, why = {}, []

    areas["hook"], w1 = hook_points(title, " ".join(w["text"] for w in ws[:8]), proper_names(ws), prof, body)
    why += w1
    areas["story"], _notes, w2 = story_points(body, prof)
    why += w2

    # entertainment + comedy on the campaign's mix
    sents = [{"text": t, "n": len(t.split())} for t in re.split(r"(?<=[.?!])\s+", body) if t.strip()]
    mix = spec.get("genres") or brief.get("genres") or genres.detect_mix(title, low)
    if isinstance(mix, list):
        mix = {g: round(1 / len(mix), 2) for g in mix}
    ent, gs = genres.entertainment(sents, low, mix)
    areas["entertainment"] = min(10, round(ent * 10 / 25))
    areas["comedy"] = min(5, round(gs["comedy"] / 3))
    if areas["entertainment"] <= 3:
        why.append("little for this campaign's genres (" + ", ".join(f"{g} {gs[g]}" for g in sorted(mix, key=mix.get, reverse=True)[:3] if g in gs) + ")")

    # pace: pauses are measured inside each part (the jump between two parts is a cut, not a pause)
    n = len(ws)
    wps = n / max(dur, 1)
    pc = 10
    lo_wps, hi_wps = prof["wps"]
    if wps < lo_wps * 0.8:
        pc -= 5; why.append(f"slow: {wps:.1f} words/s")
    elif wps < lo_wps:
        pc -= 3
    elif wps > hi_wps:
        pc -= 2
    long_pauses = 0
    if prof["pause_penalty"]:
        for pw in part_words:
            long_pauses += sum(1 for a, b in zip(pw, pw[1:]) if b["start"] - a["end"] > 1.2)
    pc -= min(4, 2 * long_pauses)
    fill = fm.count(fm.FILLER, low) / max(n, 1) if prof["filler"] else 0
    if fill > 0.06:
        pc -= 3; why.append(f"filler {fill:.0%}")
    elif fill > 0.035:
        pc -= 1
    areas["pace"] = max(0, pc)

    areas["length"], (o0, o1) = length_points(dur, prof, brief)
    if areas["length"] == 0:
        why.append(f"{dur:.0f} s is outside {o0}-{o1} s")

    total = round(sum(areas.values()) * 100 / sum(MAXES.values()))
    # the audience read (engage.py, 2026-10-30): the second pass; its gates reject a moment whatever the pitch says
    aud = engage.read(words, parts, spec.get("style") or brief.get("style"), title)
    areas["audience"] = aud["total"]
    why += ["audience: " + f for f in aud["fails"]]
    if aud["total"] < engage.BAR and not aud["fails"]:
        why.append(f"audience read {aud['total']} under {engage.BAR}")
    ok = total >= PITCH_BAR and not aud["fails"] and aud["total"] >= engage.BAR
    return {"total": total, "verdict": "PASS" if ok else "REJECT", "areas": areas, "why": why, "dur": round(dur, 1), "audience": aud}


def line(tag, r):
    return (f"PITCH {tag}: {r['total']}/100 {r['verdict']} ("
            + " ".join(f"{k} {v}" for k, v in r["areas"].items()) + ")" + (" | " + "; ".join(r["why"]) if r["why"] else ""))


def gate(specs, words, brief=None, log=print):
    """Pitch every spec. Returns (specs to render, notes). Passing specs keep their order (reviewer picks first);
    rejects are dropped. Nothing passes -> the best reject is rendered, marked."""
    notes, scored = [], []
    for i, sp in enumerate(specs):
        r = score(sp, words, brief)
        sp["_pitch"] = r
        tag = f"c{i + 1:02d}_" + planner.slug(sp.get("hook", ""))
        notes.append(line(tag, r))
        scored.append((r, sp))
    keep = [sp for r, sp in scored if r["verdict"] == "PASS"]
    # thin material (2026-10-31: 5 passes for 4 render lanes, so a lane had no second moment to fall back on): the best
    # near-misses that failed no audience gate follow the passes as marked fallbacks
    near = sorted(((r, sp) for r, sp in scored if r["verdict"] != "PASS" and not r.get("audience", {}).get("fails") and r["total"] >= 50),
                  key=lambda x: -x[0]["total"])
    for r, sp in near[:max(0, 8 - len(keep))]:
        sp["_why"] = f"PITCH UNDER THE BAR ({r['total']} < {PITCH_BAR}, fallback) | " + sp.get("_why", "")
        keep.append(sp)
    if not keep and scored:
        best = max(scored, key=lambda x: x[0]["total"])[1]
        best["_why"] = f"PITCH UNDER THE BAR ({best['_pitch']['total']} < {PITCH_BAR}) | " + best.get("_why", "")
        keep = [best]
        notes.append(f"no pitch reached {PITCH_BAR}: rendering the best one anyway, marked, so you can see what the material gives")
    notes.append(f"{len(keep)} of {len(specs)} pitches go to render")
    for n in notes:
        log(n)
    return keep, notes


if __name__ == "__main__":
    words = json.loads(Path(sys.argv[1]).read_text())
    src = json.loads(Path(sys.argv[2]).read_text())
    brief = json.loads(Path(sys.argv[3]).read_text()) if len(sys.argv) > 3 else {}
    if isinstance(src, dict):
        brief = {**brief, **src.get("brief_overrides", {})}       # what plan.load applies: style, genres, look
        specs = src.get("clips")
        if not specs and "parts" not in src:
            sys.exit("this plan.json has no clips (overrides only): the scorecard picks them at run time, nothing to pitch here")
        specs = specs or [src]
    else:
        specs = src
    for i, sp in enumerate(specs):
        sp.setdefault("style", brief.get("style"))
        sp.setdefault("genres", brief.get("genres"))
        print(line(f"c{i + 1:02d}_{planner.slug(sp.get('hook', ''))}", score(sp, words, brief)))
