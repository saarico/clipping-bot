"""The audience read: the second grading pass (rico, 2026-10-30: "the clip cuts out in a horrible position, the
speaker can't talk, boring and hard to understand; improve grading quality and entertainment, add a second phase of
engagement scoring").

Reads a clip the way a stranger scrolling past does, from its spoken words and their timing only, so the same
read runs three times: on a candidate before it is rendered (pitch), on the finished clip (after judge_clip) and on
the edges when a cut is chosen (plan.refine picks the sentence window with the best read). 100 points, bar 70,
and four hard gates that fail a clip whatever its score:

  cold open   /25  the first 4 s: no host preamble or pointer back ("I do just want to go back to part of the
                   story"), a number, a stake, a name, a claim or a question inside those 4 s, no long question
  clarity     /20  restarts ("it took us... or it took"), fillers, run-on sentences, racing speech. Gate: restarts
                   and fillers over 8% of the words = hard to follow
  payoff      /20  the last line is the answer: not an aside ("By the way, Jason asked this in May"), not a hanging
                   question, not a one-word "Yes.", carries a stake or a number
  retention   /20  every 5 s window has something to hold on to (a number, a stake, a name, a question, a
                   contrast, a laugh); two dead windows in a row or 40% dead = gate
  focus       /15  one idea: at most two host questions, the guest holds the floor

    python3 bot/engage.py <clip folder>              # writes <clip folder>/engage_report.md
    python3 bot/engage.py words.json <start> <end>   # read a moment of the episode
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import find_moments as fm  # noqa: E402
import profiles  # noqa: E402

BAR = 70
MAXES = {"open": 25, "clarity": 20, "payoff": 20, "retention": 20, "focus": 15}
LEAD = r"(?:(?:and|so|but|okay|ok|well|yeah|right|now|um|uh|look|listen)[, ]+)*"
OPEN_BAD = re.compile(r"^" + LEAD + r"(?:i (?:do |did )?(?:just |also )?want(?:ed)? to|let me|let's|we were|going back|go back|"
                      r"coming back|come back to|to go back|as (?:i|we|you) (?:said|mentioned|talked|discussed)|like i said|"
                      r"before we|one more|last question|final question|part of the story|the other thing|you mentioned|"
                      r"you said|you talked about|we talked about|we're (?:chatting|talking) about|(?:chatting|talking) about (?:that|this)|earlier|speaking of|on that note|moving on|"
                      r"that's (?:a )?(?:great|good|interesting)|which is|and that's|this is why|that's why)\b", re.I)
ASIDE_END = re.compile(r"^" + LEAD + r"(?:by the way|anyway|anyways|also|and then|but yeah|yeah|right|okay|exactly|absolutely|"
                       r"totally|sure|of course|i think so|we'll see|you know|i don't know|we'll get to that|"
                       r"we can talk about|let's talk about|we'll come back|you're|you are|you have|you've|you guys|let's|"
                       r"tell me|walk me|talk to me|i want to|i'd love to|i'm curious|can you|could you|what about|"
                       r"we'll talk|we will talk|coming up|next question|final question|last question)\b", re.I)
POINTER = re.compile(r"^" + LEAD + r"(?:this|that|these|those|it|which|he|she|they)\b", re.I)


def bad_open(t):
    """Why a sentence cannot open a clip (None when it can): host preamble / pointer back, or a pointer start
    ("This industry still gonna be very valuable") with no number, name or question in it."""
    if OPEN_BAD.match(t):
        return "opens on host preamble or a pointer back"
    if POINTER.match(t) and not (re.search(fm.NUMBER, t, re.I) or "?" in t or re.search(r"\b[A-Z][a-z]{2,}\b", t[1:])):
        return "opens on a pointer to something the viewer did not see"
    return None


def bad_end(t, n):
    """Why a sentence cannot end a clip (None when it can): an aside or the host's next lead-in, a hanging question,
    a one-word answer, an unfinished line."""
    t = t.rstrip('"\')')
    if ASIDE_END.match(t) or re.search(r"\b(by the way|(great|good|best|interesting|fair) question|we'll get to|let's come back)\b", t, re.I):
        return "ends on an aside or the host's next lead-in"
    if t.endswith("?"):
        return "ends on a hanging question"
    if n < 3:
        return "ends on a one-word answer"
    if not t.endswith((".", "!")):
        return "ends mid-sentence"
    return None
LIFE = r"\b(mom|mother|dad|father|parents?|son|daughter|wife|husband|kids?|children|family|home|childhood|grew up|poor|hungry|" \
       r"died|death|dying|sick|hospital|scared|alone|dream\w*|sacrific\w*|cost me|regret\w*|cried|tears|war|refugee\w*|immigra\w+)\b"
INTEREST = "|".join([fm.NUMBER, fm.MONEY, fm.FAIL, fm.SURPRISE, fm.EMOTION, fm.FAMOUS, fm.CONTRAST, LIFE])
LAUGH = r"\b(ha ?ha|haha|lol|laugh(s|ing|ed)?)\b"
SMALL = {"the", "and", "a", "to", "of", "in", "it", "is", "that", "i", "you", "we", "so", "like", "but", "or", "on", "at"}


def words_in(words, parts):
    out = []
    for a, b in parts:
        out += [w for w in words if w["end"] > a and w["start"] < b]
    return out


def clip_time(words, parts):
    """Each word's time on the finished clip's clock (the parts play back to back)."""
    out, acc = [], 0.0
    for a, b in parts:
        for w in words:
            if w["end"] > a and w["start"] < b:
                out.append(dict(w, t=acc + max(w["start"], a) - a))
        acc += b - a
    return out, acc


def _sent_text(s):
    return s["text"].strip()


def read(words, parts, style=None):
    """{"total", "areas", "fails", "notes", "fix": {"start": s|None, "end": s|None}} for the words inside `parts`."""
    prof = profiles.profile(style)
    ws, dur = clip_time(words, parts)
    if not ws:
        return {"total": 0, "areas": {k: 0 for k in MAXES}, "fails": ["no words"], "notes": {}, "fix": {}}
    sents = fm.sentences(ws)
    body = " ".join(w["text"] for w in ws)
    low = body.lower()
    n = len(ws)
    areas, fails, notes, fix = {}, [], {}, {}
    talk = prof["clarity"]   # a talking show; movies and streams are read lighter

    # cold open
    o = 25
    first = _sent_text(sents[0])
    open_words = [w for w in ws if w["t"] < 4.0]
    open_txt = " ".join(w["text"] for w in open_words)
    bo = bad_open(first)
    if talk and bo:
        o -= 15; fails.append(f"{bo}: \"{first[:60]}\"")
    if talk and not (re.search(INTEREST, open_txt, re.I) or "?" in open_txt or re.search(r"\b(I|we|my)\b", open_txt)):
        o -= 8; notes.setdefault("open", []).append("nothing to grab in the first 4 s")
    if len(sents[0]["text"].split()) > 18 and first.endswith("?"):
        o -= 5; notes.setdefault("open", []).append("opens on a long question")
    if fm.count(fm.FILLER, open_txt.lower()) >= 2:
        o -= 4; notes.setdefault("open", []).append("fillers in the first 4 s")
    notes.setdefault("open", []).insert(0, f"first 4 s: \"{open_txt[:70]}\"")
    areas["open"] = max(0, o)

    # clarity
    c = 20
    toks = [w["text"].strip('",.?!()\'').lower() for w in ws]
    restarts = sum(1 for i in range(len(toks) - 1) if len(toks[i]) > 2 and toks[i] not in SMALL
                   and (toks[i] == toks[i + 1] or (i + 2 < len(toks) and toks[i] == toks[i + 2])))
    fill = fm.count(fm.FILLER, low) if prof["filler"] else 0
    frag = sum(1 for s in sents if s["n"] <= 2 and not _sent_text(s).endswith("?"))
    mean_len = n / max(len(sents), 1)
    wps = n / max(dur, 1)
    c -= min(8, 2 * restarts)
    c -= min(6, round(100 * fill / max(n, 1)))
    if talk and mean_len > 26:
        c -= 4; notes.setdefault("clarity", []).append(f"run-on sentences ({mean_len:.0f} words each)")
    if wps > prof["wps"][1]:
        c -= 3; notes.setdefault("clarity", []).append(f"racing: {wps:.1f} words/s")
    if frag >= 3:
        c -= 2; notes.setdefault("clarity", []).append(f"{frag} one- or two-word fragments")
    muddle = (restarts + fill) / max(n, 1)
    notes.setdefault("clarity", []).insert(0, f"{restarts} restart(s), {fill} filler(s) in {n} words ({muddle:.0%})")
    if talk and muddle > 0.08:
        fails.append(f"hard to follow: {restarts} restarts and {fill} fillers in {n} words")
    areas["clarity"] = max(0, c)

    # payoff
    p = 20
    last = sents[-1]
    last_txt = _sent_text(last).rstrip('"\')')
    be = bad_end(last_txt, last["n"])
    if be == "ends mid-sentence":
        p -= 6; notes.setdefault("payoff", []).append("ends mid-sentence")
    elif be:
        p -= 12; fails.append(f"{be}: \"{last_txt[:60]}\"")
    tail = " ".join(w["text"] for w in ws if w["t"] > dur - 8)
    if not re.search(INTEREST, tail, re.I):
        p -= 4; notes.setdefault("payoff", []).append("nothing lands in the last 8 s")
    # a question in the last 10 s with fewer than 6 words after it was never answered
    # sentence times on the clip's clock (fm.sentences keeps source times; the words carry t)
    qs = [s for s in sents if _sent_text(s).endswith("?") and s["words"][0]["t"] > dur - 10]
    if qs and talk:
        after = sum(1 for w in ws if w["t"] > qs[-1]["words"][-1]["t"] + 0.01)
        if after < 6 and not fails:
            p -= 6; fails.append(f"a question in the last 10 s is left hanging: \"{_sent_text(qs[-1])[:60]}\"")
    notes.setdefault("payoff", []).insert(0, f"last line: \"{last_txt[:70]}\"")
    areas["payoff"] = max(0, p)

    # retention
    r = 20
    wins = int(dur // 5) + (1 if dur % 5 > 2 else 0)
    dead = []
    for k in range(max(wins, 1)):
        seg = " ".join(w["text"] for w in ws if k * 5 <= w["t"] < (k + 1) * 5)
        if not (re.search(INTEREST, seg, re.I) or "?" in seg or re.search(LAUGH, seg, re.I)):
            dead.append(k)
    r -= min(20, 4 * max(0, len(dead) - 1))
    two = any(a + 1 == b for a, b in zip(dead, dead[1:]))
    share = len(dead) / max(wins, 1)
    notes["retention"] = [f"{len(dead)} of {wins} five-second windows carry nothing" + (f" (at {', '.join(str(5 * k) + 's' for k in dead[:5])})" if dead else "")]
    if talk and (two or share > 0.4):
        fails.append(f"flat stretch: {len(dead)} of {wins} windows with nothing to hold on to" + (" (two in a row)" if two else ""))
    areas["retention"] = max(0, r)

    # focus
    f = 15
    qn = sum(1 for s in sents if _sent_text(s).endswith("?"))
    if qn > 2:
        f -= min(10, 5 * (qn - 2)); notes.setdefault("focus", []).append(f"{qn} questions: more than one idea")
    spk = {}
    for w in ws:
        spk[w.get("speaker", "s0")] = spk.get(w.get("speaker", "s0"), 0) + 1
    top = max(spk.values()) / n
    if talk and len(spk) > 1 and top < 0.55:
        f -= 5; notes.setdefault("focus", []).append(f"nobody holds the floor (top speaker {top:.0%} of the words)")
    notes.setdefault("focus", []).insert(0, f"{qn} question(s), top speaker {top:.0%}")
    areas["focus"] = max(0, f)

    # the fix: where the clip should start and end instead (used by the re-edit and by plan.refine)
    for i, s in enumerate(sents[:4]):
        t = _sent_text(s)
        if not bad_open(t) and (re.search(INTEREST, t, re.I) or t.endswith("?") or re.search(r"\b(I|we|my)\b", t)):
            if i:
                fix["start"] = s["start"]
            break
    for j in range(len(sents) - 1, max(len(sents) - 6, 0) - 1, -1):
        if not bad_end(_sent_text(sents[j]), sents[j]["n"]):
            if j != len(sents) - 1:
                fix["end"] = sents[j]["end"]
            break
    total = sum(areas.values())
    return {"total": total, "areas": areas, "fails": fails, "notes": notes, "fix": fix, "dur": round(dur, 1)}


def to_source(words, parts, fix):
    """fix times are on the clip's clock (fm.sentences keeps the source start/end though): map back to source."""
    return fix


def report(res):
    out = ["# Audience read", "", "The second grading pass (bot/engage.py): the clip as a stranger hears it.", "",
           "| Area | Points | Notes |", "|---|---|---|"]
    for k, v in res["areas"].items():
        out.append(f"| {k} | {v}/{MAXES[k]} | {'; '.join(res['notes'].get(k, []))} |")
    out += ["", f"**Audience score: {res['total']}/100** (bar {BAR})", ""]
    out += ["Gates: " + ("; ".join(res["fails"]) if res["fails"] else "all passed"), ""]
    return "\n".join(out)


def read_folder(folder):
    folder = Path(folder)
    det = json.loads((folder / "cut_details.json").read_text())
    words = json.loads((folder / "words.json").read_text())
    res = read(words, det["cuts"], det.get("spec", {}).get("style"))
    (folder / "engage_report.md").write_text(report(res))
    return res


if __name__ == "__main__":
    if len(sys.argv) == 4:
        w = json.load(open(sys.argv[1]))
        r = read(w, [[float(sys.argv[2]), float(sys.argv[3])]])
        print(report(r)); print("fix", r["fix"])
    else:
        r = read_folder(sys.argv[1])
        print(f"audience {r['total']}/100 " + " ".join(f"{k} {v}" for k, v in r["areas"].items()) + (" | " + "; ".join(r["fails"]) if r["fails"] else ""))
