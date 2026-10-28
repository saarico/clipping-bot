"""The judge, part 1 of 2: measure a finished clip the way a scroller feels it, before rico sees it
(RULES.md 27, scorecards/judgment.md).

Usage:
  python3 judge_clip.py <clip folder>        # writes <clip folder>/judge_report.md (machine half)

Part 2 is a separate Claude agent that has NOT seen the editing: it reads captions.txt and this
report, looks at qa_sheet.png, scores the rubric in scorecards/judgment.md and appends its verdict to the same
file. Under 75 overall = re-cut, not sent.

Machine measures (0-100):
  hook      /20  first 2.5 s: a name, a number or an "I/we" claim; no pronoun start; title <= 14 words
  pace      /15  2.2-3.3 words per second; no silence over 0.8 s; filler words under 3.5%
  variety   /20  a visual change (camera cut, card, split, punch-in) at least every 8 s; share of
                 time with a card or b-roll on screen
  framing   /15  face centred (qa_report), no letterbox, no segment under 0.5 s
  story     /20  stakes words (money, fame, failure, surprise, emotion), a contrast or a question,
                 ends on a finished sentence, no podcast back-references
  length    /10  30-55 s
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import find_moments as fm  # noqa: E402
import profiles  # noqa: E402


def silence(mp4):
    log = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(mp4), "-af", "silencedetect=n=-45dB:d=0.8",
                          "-vn", "-f", "null", "-"], capture_output=True, text=True).stderr
    return [float(x) for x in re.findall(r"silence_duration: ([\d.]+)", log)]


def main(folder):
    folder = Path(folder)
    mp4 = next(folder.glob("*.mp4"))
    det = json.loads((folder / "cut_details.json").read_text())
    spec = det.get("spec", {})
    caps = (folder / "captions.txt").read_text()
    spoken = caps.split("CARDS ON SCREEN")[0]          # our text cards are listed after the spoken lines
    body = "\n".join(l for l in spoken.splitlines()[2:] if l.strip() and not l.startswith("CAPTIONS AS SHOWN"))
    low = body.lower()
    words = body.split()
    dur = sum(b - a for a, b in det["cuts"])
    shots = det["shots"]
    rep, notes = {}, {}
    prof = profiles.profile(spec.get("style"))

    # hook
    first = body.splitlines()[0] if body.splitlines() else ""
    head = " ".join(first.split()[:8])
    h = 20
    if prof["clarity"] and re.match(fm.BACKREF, head.strip(), flags=re.I):
        h -= 8; notes.setdefault("hook", []).append("first line starts on a pointer word")
    # captions are upper case: a proper name is a word the transcript itself capitalises mid-sentence
    wj = json.loads((folder / "words.json").read_text()) if (folder / "words.json").exists() else []
    proper = set()
    for prev, w in zip([None] + wj[:-1], wj):
        t = w["text"].strip('",.?!()\'')
        if t[:1].isupper() and len(t) > 2 and prev and not prev["text"].rstrip('"\'').endswith((".", "?", "!")):
            proper.add(t.lower())
    has_name = any(t.strip('",.?!()\'').lower() in proper for t in head.split()[1:])
    if prof["clarity"] and not (re.search(fm.NUMBER, head, re.I) or has_name or re.search(r"\b(I|we|my)\b", head, re.I)):
        h -= 5; notes.setdefault("hook", []).append("first line names no one and nothing")
    title = spec.get("hook", "")
    if len(title.split()) > 14:
        h -= 3; notes.setdefault("hook", []).append("title over 14 words")
    if prof["back_refs"] and re.search(fm.PODCAST_TALK, " ".join(words[:25]).lower()):
        h -= 6; notes.setdefault("hook", []).append("opens with podcast talk")
    rep["hook"] = max(0, h)

    # pace
    wps = len(words) / max(dur, 1)
    p = 15
    lo_wps, hi_wps = prof["wps"]
    if wps < lo_wps * 0.8: p -= 7
    elif wps < lo_wps: p -= 4
    elif wps > hi_wps: p -= 2
    sil = silence(mp4) if prof["pause_penalty"] else []
    p -= min(6, 3 * len(sil))
    fill = fm.count(fm.FILLER, low) / max(len(words), 1) if prof["filler"] else 0
    if fill > 0.06: p -= 4
    elif fill > 0.035: p -= 2
    notes["pace"] = [f"{wps:.1f} words/s", f"{len(sil)} silence(s) over 0.8 s", f"filler {fill:.1%}"]
    rep["pace"] = max(0, p)

    # variety
    # callouts (our own number cards) are visual changes too: map their source times onto the output
    offs, acc = [], 0.0
    for a, b in det["cuts"]:
        offs.append((a, b, acc)); acc += b - a
    call = []
    for c in spec.get("callouts", []):
        for a, b, off in offs:
            lo, hi = max(c["from"], a), min(c["to"], b)
            if hi - lo > 0.3:
                call.append((off + lo - a, off + hi - a))
    changes = sorted([s["from"] for s in shots] + [c[0] for c in call])
    gaps = [b - a for a, b in zip(changes, changes[1:] + [dur])]
    longest = max(gaps) if gaps else dur
    cards = sum(s["to"] - s["from"] for s in shots if s["layout"].split("+")[0] in ("side", "bottom", "fit", "banner")) + sum(b - a for a, b in call)
    zooms = sum(1 for s in shots if "zoom" in s["layout"])
    v = 20
    if longest > 12: v -= 8
    elif longest > 8: v -= 4
    share = cards / max(dur, 1)
    if prof["cards"]:   # podcasts need b-roll; trailers and streams carry their own visual change
        if share < 0.1: v -= 6
        elif share < 0.2: v -= 3
        if zooms == 0: v -= 2
    notes["variety"] = [f"longest stretch without a visual change {longest:.1f} s", f"cards/b-roll/callouts {share:.0%} of the clip", f"{zooms} punch-in(s)", f"{len(call)} callout(s)"]
    rep["variety"] = max(0, v)

    # framing (from qa_report.md)
    qa = (folder / "qa_report.md").read_text() if (folder / "qa_report.md").exists() else ""
    f = 15
    m = re.search(r"\| Speaker centred \| (\w+) \| ([^|]*)", qa)
    if m:
        if m.group(1) == "FAIL": f -= 10
        elif m.group(1) == "WARN": f -= 4
        notes["framing"] = [m.group(2).strip()]
    if any(s["layout"].split("+")[0] == "center" for s in shots):
        f -= 5; notes.setdefault("framing", []).append("letterboxed segment")
    if any(s["to"] - s["from"] < 0.5 for s in shots):
        f -= 2; notes.setdefault("framing", []).append("segment under 0.5 s")
    rep["framing"] = max(0, f)

    # story
    st = 0
    stakes = fm.count(fm.MONEY, low) + fm.count(fm.FAIL, low) + fm.count(fm.SURPRISE, low) + fm.count(fm.EMOTION, low) + 2 * fm.count(fm.FAMOUS, low)
    st += min(8, stakes)
    if fm.count(fm.CONTRAST, low) or "?" in body[:300]: st += 4
    last = body.strip().splitlines()[-1].strip().rstrip('"\')') if body.strip() else ""
    st += 5 if last.endswith((".", "!", "?")) else 0
    back = fm.count(fm.PODCAST_TALK, low) if prof["back_refs"] else 0
    st += 3 if back == 0 else 0
    if prof["reactions"] > 1:
        st += min(4, fm.count(profiles.HYPE, low))
    notes["story"] = [f"{stakes} stakes word(s)", f"{back} podcast back-reference(s)", "ends on a finished sentence" if last.endswith((".", "!", "?")) else "ends mid-sentence"]
    rep["story"] = min(20, st)

    (l0, l1), (o0, o1) = prof["length"], prof["ok_len"]
    rep["length"] = 10 if l0 <= dur <= l1 else 6 if o0 <= dur <= o1 else 0
    total = sum(rep.values())
    out = [f"# Judge report: {folder.name}", "", f"Profile: {spec.get('style') or 'podcast'}", "",
           "Part 1, measured by bot/judge_clip.py. Part 2 (below) is the judge agent's blind read (scorecards/judgment.md).", "",
           "| Area | Points | Notes |", "|---|---|---|"]
    maxes = {"hook": 20, "pace": 15, "variety": 20, "framing": 15, "story": 20, "length": 10}
    for k, v in rep.items():
        out.append(f"| {k} | {v}/{maxes[k]} | {'; '.join(notes.get(k, []))} |")
    out += ["", f"**Machine score: {total}/100** (length {dur:.1f} s, {len(words)} words)", "",
            "## Part 2: judge agent", "", "_not yet graded_", ""]
    # keep the judge agent's Part 2 if it has already been written for this render
    rp = folder / "judge_report.md"
    if rp.exists() and "_not yet graded_" not in rp.read_text() and "## Part 2: judge agent" in rp.read_text():
        part2 = rp.read_text().split("## Part 2: judge agent", 1)[1]
        out = out[:out.index("## Part 2: judge agent")] + ["## Part 2: judge agent" + part2]
    rp.write_text("\n".join(out))
    print(f"{folder.name}: machine {total}/100  " + "  ".join(f"{k} {v}" for k, v in rep.items()))
    return total


if __name__ == "__main__":
    main(sys.argv[1])
