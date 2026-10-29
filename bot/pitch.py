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
import find_moments as fm  # noqa: E402
import genres  # noqa: E402
import profiles  # noqa: E402

PITCH_BAR = 60
MAXES = {"hook": 20, "story": 10, "entertainment": 10, "comedy": 5, "pace": 10, "length": 10}   # 65 word-judgeable points


def words_in(words, parts):
    out = []
    for a, b in parts:
        out += [w for w in words if w["end"] > a and w["start"] < b]
    return out


def proper_names(words):
    names = set()
    for prev, w in zip([None] + words[:-1], words):
        t = w["text"].strip('",.?!()\'')
        if t[:1].isupper() and len(t) > 2 and prev and not prev["text"].rstrip('"\'').endswith((".", "?", "!")):
            names.add(t.lower())
    return names


def score(spec, words, brief=None):
    """{"total": 0-100, "verdict": "PASS"|"REJECT", "areas": {...}, "why": [...]} for one candidate."""
    brief = brief or {}
    prof = profiles.profile(spec.get("style") or brief.get("style"))
    parts = spec.get("parts") or []
    ws = words_in(words, parts)
    body = " ".join(w["text"] for w in ws)
    low = body.lower()
    dur = sum(b - a for a, b in parts)
    title = spec.get("hook", "")
    names = proper_names(ws)
    areas, why = {}, []

    # hook: the title and the first line
    h = 20
    first = " ".join(w["text"] for w in ws[:8])
    if prof["clarity"] and re.match(fm.BACKREF, first.strip(), flags=re.I):
        h -= 8; why.append("first line starts on a pointer word")
    has_name = any(t.strip('",.?!()\'').lower() in names for t in first.split()[1:])
    if prof["clarity"] and not (re.search(fm.NUMBER, first, re.I) or has_name or re.search(r"\b(I|we|my)\b", first, re.I)):
        h -= 5; why.append("first line names no one and nothing")
    if not (re.search(fm.NUMBER, title, re.I) or "?" in title or '"' in title or re.search(fm.FAMOUS, title, re.I)
            or any(t.strip('",.?!()\'').lower() in names for t in title.split()) or re.search(r"\b(I|we|my|you)\b", title)):
        h -= 5; why.append("title has no name, number, question or quote")
    if len(title.split()) > 14:
        h -= 3; why.append("title over 14 words")
    if prof["back_refs"] and re.search(fm.PODCAST_TALK, " ".join(body.split()[:25]).lower()):
        h -= 6; why.append("opens with podcast talk")
    areas["hook"] = max(0, h)

    # story
    st = 0
    stakes = fm.count(fm.MONEY, low) + fm.count(fm.FAIL, low) + fm.count(fm.SURPRISE, low) + fm.count(fm.EMOTION, low) + 2 * fm.count(fm.FAMOUS, low)
    st += min(4, stakes)
    if fm.count(fm.CONTRAST, low) or "?" in body[:300]:
        st += 2
    last = body.strip().rstrip('"\')')
    if last.endswith((".", "!", "?")):
        st += 2
    else:
        why.append("ends mid-sentence")
    back = fm.count(fm.PODCAST_TALK, low) if prof["back_refs"] else 0
    st += 2 if back == 0 else 0
    if back:
        why.append(f"{back} podcast back-reference(s)")
    if prof["reactions"] > 1:
        st += min(2, fm.count(profiles.HYPE, low))
    if stakes == 0:
        why.append("no stakes: no money, failure, surprise, emotion or famous name")
    areas["story"] = min(10, st)

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

    # pace
    n = len(ws)
    wps = n / max(dur, 1)
    p = 10
    lo_wps, hi_wps = prof["wps"]
    if wps < lo_wps * 0.8:
        p -= 5; why.append(f"slow: {wps:.1f} words/s")
    elif wps < lo_wps:
        p -= 3
    elif wps > hi_wps:
        p -= 2
    gaps = [b["start"] - a["end"] for a, b in zip(ws, ws[1:])]
    long_pauses = sum(1 for g in gaps if g > 1.2) if prof["pause_penalty"] else 0
    p -= min(4, 2 * long_pauses)
    fill = fm.count(fm.FILLER, low) / max(n, 1) if prof["filler"] else 0
    if fill > 0.06:
        p -= 3; why.append(f"filler {fill:.0%}")
    elif fill > 0.035:
        p -= 1
    areas["pace"] = max(0, p)

    (l0, l1), (o0, o1) = prof["length"], prof["ok_len"]
    areas["length"] = 10 if l0 <= dur <= l1 else 6 if o0 <= dur <= o1 else 0
    if areas["length"] == 0:
        why.append(f"{dur:.0f} s is outside {o0}-{o1} s")

    total = round(sum(areas.values()) * 100 / sum(MAXES.values()))
    return {"total": total, "verdict": "PASS" if total >= PITCH_BAR else "REJECT", "areas": areas, "why": why, "dur": round(dur, 1)}


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
        tag = f"c{i + 1:02d}_" + re.sub(r"[^a-z0-9]+", "-", sp.get("hook", "").lower())[:28].strip("-")
        notes.append(line(tag, r))
        scored.append((r, sp))
    keep = [sp for r, sp in scored if r["verdict"] == "PASS"]
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
    specs = src.get("clips", [src]) if isinstance(src, dict) else src
    for i, sp in enumerate(specs):
        sp.setdefault("style", (src.get("brief_overrides", {}) if isinstance(src, dict) else {}).get("style") or brief.get("style"))
        print(line(f"c{i + 1:02d}", score(sp, words, brief)))
