"""The judge, part 1 of 2: measure a finished clip the way a scroller feels it, before rico sees it
(RULES.md 27, scorecards/judgment.md).

Usage:
  python3 judge_clip.py <clip folder>        # writes <clip folder>/judge_report.md (machine half)

Part 2 is a separate Claude agent that has NOT seen the editing: it reads captions.txt and this
report, looks at qa_sheet.png, scores the rubric in scorecards/judgment.md and appends its verdict to the same
file. Under 75 overall = re-cut, not sent.

Machine measures (0-100), rebalanced 2026-10-28 (rico: "ensure captions are read and judged",
"ensure comedy grade is also present"):
  hook          /20  first 2.5 s: a name, a number or an "I/we" claim; no pronoun start; title <= 14 words
  pace          /10  words per second in the profile's band; no silence over 0.8 s; filler under 3.5%
  variety       /15  a visual change (camera cut, card, split, punch-in) at least every 8 s
  framing       /10  face centred (qa_report), no letterbox, no segment under 0.5 s, no footage text cut off
  story         /10  stakes words, a contrast or a question, ends on a finished sentence, no back-references
  entertainment /10  genres.py: the campaign's genre mix scored on what is actually said in the clip
  comedy        /5   genres.comedy: setup + punch, retorts, absurd numbers, insults, laughter (always graded)
  captions      /10  read like a person: 2-6 words per caption, nothing flashing, numbers whole, no
                     unknown words, no cut-off fragments, swearing masked
  length        /10  inside the profile's sweet spot
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import find_moments as fm  # noqa: E402
import genres  # noqa: E402
import pitch  # noqa: E402
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

    # hook (shared with the pitch, bot/pitch.py: one rule, graded before and after the render)
    title = spec.get("hook", "")
    first = body.splitlines()[0] if body.splitlines() else ""
    wj = json.loads((folder / "words.json").read_text()) if (folder / "words.json").exists() else []
    rep["hook"], hw = pitch.hook_points(title, first, pitch.proper_names(wj), prof, body)
    if hw:
        notes["hook"] = hw

    # pace
    wps = len(words) / max(dur, 1)
    p = 10
    lo_wps, hi_wps = prof["wps"]
    if wps < lo_wps * 0.8: p -= 5
    elif wps < lo_wps: p -= 3
    elif wps > hi_wps: p -= 2
    sil = silence(mp4) if prof["pause_penalty"] else []
    p -= min(4, 2 * len(sil))
    fill = fm.count(fm.FILLER, low) / max(len(words), 1) if prof["filler"] else 0
    if fill > 0.06: p -= 3
    elif fill > 0.035: p -= 1
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
    v = 15
    if longest > 12: v -= 6
    elif longest > 8: v -= 3
    lens = sorted(s["to"] - s["from"] for s in shots)
    if len(lens) >= 6 and lens[len(lens) // 2] < 1.2 and sum(1 for l in lens if l < 1.0) > 0.6 * len(lens):
        v -= 6; notes.setdefault("variety", []).append("montage: most shots under a second, no scene to follow")
    share = cards / max(dur, 1)
    if prof["cards"]:   # podcasts need b-roll; trailers and streams carry their own visual change
        if share < 0.1: v -= 5
        elif share < 0.2: v -= 2
        if zooms == 0: v -= 2
    notes["variety"] = [f"longest stretch without a visual change {longest:.1f} s", f"cards/b-roll/callouts {share:.0%} of the clip", f"{zooms} punch-in(s)", f"{len(call)} callout(s)"]
    rep["variety"] = max(0, v)

    # framing (from qa_report.md)
    qa = (folder / "qa_report.md").read_text() if (folder / "qa_report.md").exists() else ""
    f = 10
    m = re.search(r"\| Speaker centred \| (\w+) \| ([^|]*)", qa)
    if m:
        if m.group(1) == "FAIL": f -= 6
        elif m.group(1) == "WARN": f -= 3
        notes["framing"] = [m.group(2).strip()]
    m = re.search(r"\| Footage text cut off \| (\w+) \| ([^|]*)", qa)
    if m and m.group(1) != "PASS":
        f -= 6 if m.group(1) == "FAIL" else 3; notes.setdefault("framing", []).append(m.group(2).strip())
    m = re.search(r"\| Actors fill the frame \| (\w+) \| ([^|]*)", qa)
    if m and m.group(1) != "PASS":
        f -= 6 if m.group(1) == "FAIL" else 3; notes.setdefault("framing", []).append(m.group(2).strip())
    m = re.search(r"\| Crop jumps \| (\w+) \| ([^|]*)", qa)
    if m and m.group(1) != "PASS":
        f -= 5 if m.group(1) == "FAIL" else 2; notes.setdefault("framing", []).append(m.group(2).strip()[:80])
    m = re.search(r"\| Somebody in frame \| (\w+) \| ([^|]*)", qa)
    if m and m.group(1) != "PASS":
        f -= 4 if m.group(1) == "FAIL" else 2; notes.setdefault("framing", []).append(m.group(2).strip()[:80])
    if any(s["layout"].split("+")[0] in ("center", "fit") for s in shots):
        f -= 6; notes.setdefault("framing", []).append("format switch (16:9 picture shown whole)")
    if any(s["to"] - s["from"] < 0.5 for s in shots):
        f -= 2; notes.setdefault("framing", []).append("segment under 0.5 s")
    rep["framing"] = max(0, f)

    # story (shared with the pitch)
    rep["story"], notes["story"], _ = pitch.story_points(body, prof)

    # entertainment + comedy: the genre scorecard read on the clip's own lines (never on the plan)
    sents = [{"text": t, "n": len(t.split())} for t in re.split(r"(?<=[.?!])\s+|\n", body) if t.strip()]
    mix = spec.get("genres") or genres.detect_mix(spec.get("hook", ""), low)
    if isinstance(mix, list):   # a reviewer's plain list of genres (plan.json): equal weights
        mix = {g: round(1 / len(mix), 2) for g in mix}
    ent, gs = genres.entertainment(sents, low, mix)
    rep["entertainment"] = min(10, round(ent * 10 / 25))
    rep["comedy"] = min(5, round(gs["comedy"] / 3))
    topg = sorted(((g, v) for g, v in gs.items() if v), key=lambda kv: -kv[1])[:4]
    notes["entertainment"] = [f"mix {', '.join(f'{g} {w:.0%}' for g, w in mix.items())}", "genres " + ", ".join(f"{g} {v}/20" for g, v in topg)]
    notes["comedy"] = [f"comedy {gs['comedy']}/20"]

    # captions: what the scroller reads, from qa_report's caption rows
    c = 10
    cn = []
    m = re.search(r"\| Captions readable \| (\w+) \| ([^|]*)", qa)
    if m and m.group(1) != "PASS":
        c -= 5 if m.group(1) == "FAIL" else 2; cn.append(m.group(2).strip()[:90])
    m = re.search(r"\| Caption spelling \| (\w+) \| ([^|]*)", qa)
    if m and m.group(1) != "PASS" and "not installed" not in m.group(2):
        nbad = len(re.findall(r"\(did you mean", m.group(2)))
        c -= min(3, nbad); cn.append(f"{nbad} unknown word(s)")
    m = re.search(r"\| Caption text reads clean \| (\w+) \| ([^|]*)", qa)
    if m and m.group(1) != "PASS":
        c -= 2; cn.append(m.group(2).strip()[:60])
    m = re.search(r"\| Captions cover the whole clip \| (\w+) \| ([^|]*)", qa)
    if m and m.group(1) != "PASS":
        c -= 3 if m.group(1) == "FAIL" else 1; cn.append("coverage: " + m.group(2).strip()[:60])
    rep["captions"] = max(0, c)
    notes["captions"] = cn or ["read clean"]

    rep["length"], _ = pitch.length_points(dur, prof, spec.get("brief"))
    total = sum(rep.values())
    out = [f"# Judge report: {folder.name}", "", f"Profile: {spec.get('style') or 'podcast'}", "",
           "Part 1, measured by bot/judge_clip.py. Part 2 (below) is the judge agent's blind read (scorecards/judgment.md).", "",
           "| Area | Points | Notes |", "|---|---|---|"]
    maxes = {"hook": 20, "pace": 10, "variety": 15, "framing": 10, "story": 10, "entertainment": 10, "comedy": 5, "captions": 10, "length": 10}
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
