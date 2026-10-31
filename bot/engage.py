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
MAXES = {"open": 25, "story": 20, "payoff": 20, "retention": 20, "clarity": 15}
REASON = r"\b(because|that's why|the reason|which means|so that|what happened|turns out|the problem|here's why|the result)\b"
NUMWORD = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
           "ten": "10", "twenty": "20", "thirty": "30", "forty": "40", "fifty": "50", "hundred": "100", "thousand": "1000"}
SCALE = {"k": " thousand", "m": " million", "b": " billion", "bn": " billion"}
STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "at", "by", "with", "from", "is", "are", "was", "were", "be",
        "it", "its", "this", "that", "these", "those", "i", "we", "you", "he", "she", "they", "my", "our", "your", "his", "her",
        "their", "do", "does", "did", "not", "no", "so", "but", "if", "then", "than", "as", "about", "into", "over", "per", "how",
        "what", "why", "when", "where", "who", "will", "would", "can", "could", "have", "has", "had", "get", "got", "just", "very",
        "like", "really", "every", "all", "any", "some", "there", "here", "up", "out", "more", "most", "much", "many", "s"}


def norm(text):
    """Lower-case words with numbers spelled the same way in a title and in speech: "$4M" -> "4 million",
    "$10 ,000" -> "10000", "30%" -> "30 percent", "one" -> "1"."""
    t = text.lower().replace("\u2019", "'")
    t = re.sub(r"(\d) ,(\d{3})", r"\1\2", t)
    t = re.sub(r"(\d),(\d{3})", r"\1\2", t)
    t = re.sub(r"\$(\d[\d.]*)\s*([kmb]n?)\b", lambda m: m.group(1) + SCALE[m.group(2)], t)
    t = re.sub(r"(\d[\d.]*)\s*([kmb]n?)\b", lambda m: m.group(1) + SCALE[m.group(2)], t)
    t = re.sub(r"(\d[\d.]*)\s*%", r"\1 percent", t)
    t = t.replace("$", " ")
    toks = [NUMWORD.get(w, w) for w in re.findall(r"[a-z0-9']+", t)]
    return toks


def keywords(title):
    """The title's content words, normalised: what the speaker has to SAY for the viewer not to depend on the title."""
    return [w for w in norm(title) if w not in STOP and len(w) > 1]


def said(keys, toks):
    """Share of the title's keywords heard in these spoken tokens (a numeral matches its spoken form)."""
    if not keys:
        return 1.0
    bag = set(toks)
    hit = sum(1 for k in keys if k in bag or (k.isdigit() and len(k) >= 3 and any(x.startswith(k) for x in bag))
              or (len(k) >= 4 and any(x.startswith(k) or k.startswith(x) and len(x) >= 4 for x in bag)))
    return hit / len(keys)
LEAD = r"(?:(?:and|so|but|okay|ok|well|yeah|right|now|um|uh|look|listen)[, ]+)*"
OPEN_BAD = re.compile(r"^(?:(?:no|yes|yeah|yep|nope|exactly|correct|absolutely)[,.]\s*|" + LEAD + r"(?:i (?:do |did )?(?:just |also )?want(?:ed)? to|let me|let's|we were|going back|go back|"
                      r"coming back|come back to|to go back|as (?:i|we|you) (?:said|mentioned|talked|discussed)|like i said|"
                      r"before we|one more|last question|final question|part of the story|the other thing|you mentioned|"
                      r"you said|you talked about|we talked about|we're (?:chatting|talking) about|(?:chatting|talking) about (?:that|this)|earlier|speaking of|on that note|moving on|"
                      r"that's (?:a )?(?:great|good|interesting)|which is|and that's|this is why|that's why)\b)", re.I)
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


def read(words, parts, style=None, title=""):
    """{"total", "areas", "fails", "notes", "fix": {"start": s|None, "end": s|None}} for the words inside `parts`."""
    prof = profiles.profile(style)
    ws, dur = clip_time(words, parts)
    if not ws:
        return {"total": 0, "areas": {k: 0 for k in MAXES}, "fails": ["no words"], "notes": {}, "fix": {}, "dur": 0}
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
    # the hook line (RULES 41, rico 2026-10-31 "both clips yap for the first few seconds"): the headline is SAID in the
    # first 5 s: a number or a name from the title, or the first sentence is a short question that names the subject
    keys = keywords(title)
    head6_txt = " ".join(w["text"] for w in ws if w["t"] < 6.0)
    head6 = norm(head6_txt)
    names = [k for k in keys if re.search(r"\b" + re.escape(k).capitalize() + r"\b", title[1:])]   # capitalised inside the title = a name
    BIG = r"\$|\b\d{2,}\b|\b(million|billion|thousand|percent|hundred)\b|\d\s*%"
    # the hook sits in the first sentence; a first sentence of 8 words or fewer may hand over to the second (within 6 s)
    scope_txt = first if len(first.split()) > 8 or len(sents) < 2 else first + " " + _sent_text(sents[1])
    scope_txt = " ".join(scope_txt.split()[:len(head6_txt.split()) + 2]) if len(first.split()) <= 8 else first
    scope = norm(scope_txt)
    hook_said = bool(re.search(BIG, scope_txt, re.I)) or any(k in scope for k in names) or said(keys, scope) >= 0.4
    short_q = first.endswith("?") and len(first.split()) <= 12 and said(keys, norm(first)) >= 0.25
    if talk and keys and not (hook_said or short_q):
        o -= 12; fails.append(f"the headline is not said in the first 6 s: \"{open_txt[:60]}\"")
    if len(sents[0]["text"].split()) > 18 and first.endswith("?"):
        o -= 5; notes.setdefault("open", []).append("opens on a long question")
    if fm.count(fm.FILLER, open_txt.lower()) >= 2:
        o -= 4; notes.setdefault("open", []).append("fillers in the first 4 s")
    notes.setdefault("open", []).insert(0, f"first 4 s: \"{open_txt[:70]}\"")
    areas["open"] = max(0, o)

    # clarity
    c = 15
    toks = [w["text"].strip('",.?!()\'').lower() for w in ws]
    restarts = sum(1 for i in range(len(toks) - 1) if len(toks[i]) > 2 and toks[i] not in SMALL
                   and (toks[i] == toks[i + 1] or (i + 2 < len(toks) and toks[i] == toks[i + 2])))
    fill = fm.count(fm.FILLER, low) if prof["filler"] else 0
    frag = sum(1 for s in sents if s["n"] <= 2 and not _sent_text(s).endswith("?"))
    mean_len = n / max(len(sents), 1)
    wps = n / max(dur, 1)
    c -= min(6, 2 * restarts)
    c -= min(5, round(100 * fill / max(n, 1)))
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
    if talk and not be and not (re.search(INTEREST, last_txt, re.I) or (keys and said(keys, norm(last_txt)) >= 0.25)):
        p -= 6; notes.setdefault("payoff", []).append("the last line carries no stake and does not land the title")
        fails.append(f"the last line is not the payoff: \"{last_txt[:60]}\"")
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
    three = any(a + 1 == b and b + 1 == c for a, b, c in zip(dead, dead[1:], dead[2:]))
    if two:
        r -= 4
    if talk and (three or share > 0.4):
        fails.append(f"flat stretch: {len(dead)} of {wins} windows with nothing to hold on to" + (" (three in a row)" if three else ""))
    areas["retention"] = max(0, r)

    # story: the 5 Ws and a progression (RULES 41). WHO/WHAT: the title's words are said inside the first 10 s, so
    # the viewer never depends on the title band. WHY/HOW: a reason or a contrast after the hook. Progression: new
    # numbers, names or stakes keep arriving; at most two questions (one idea); the guest holds the floor.
    st = 20
    head10_txt = " ".join(w["text"] for w in ws if w["t"] < 10.0)
    head10 = norm(head10_txt)
    cover = said(keys, head10) if keys else 1.0
    # a subject named out loud: a capitalised word that is not a sentence starter (Higgsfield, Google, Yuri)
    subject = [w for w in re.findall(r"(?<![.?!\"]\s)(?<!^)\b([A-Z][a-z]{2,})\b", " " + head10_txt) if w.lower() not in fm.STARTERS and w != "I"]
    if cover < 0.3 and not subject:
        st -= 8; notes.setdefault("story", []).append(f"who/what: only {cover:.0%} of the title's words and no name in the first 10 s")
        if talk and keys:
            fails.append(f"the viewer depends on the title: {cover:.0%} of its words and no name said in the first 10 s")
    elif cover < 0.3:
        st -= 3; notes.setdefault("story", []).append(f"who/what: {', '.join(subject[:2])} named; {cover:.0%} of the title's words said in 10 s")
    else:
        notes.setdefault("story", []).append(f"who/what said in the first 10 s ({cover:.0%} of the title's words)")
    body_after = " ".join(w["text"] for w in ws if w["t"] >= 4.0).lower()
    if not (re.search(REASON, body_after) or re.search(fm.CONTRAST, body_after)):
        st -= 4; notes.setdefault("story", []).append("no why/how: no reason or contrast after the hook")
    tokens, seen_at = [], {}
    for w in ws:
        tok = w["text"].strip(",.?!\"'").lower()
        if re.fullmatch(INTEREST, tok, re.I) or re.fullmatch(r"\$?\d[\d,.]*%?", tok):
            seen_at.setdefault(tok, w["t"])
    late = [t for t, at in seen_at.items() if at >= 5.0]
    if len(seen_at) < 3 or not late:
        st -= 5; notes.setdefault("story", []).append(f"little progression: {len(seen_at)} distinct stakes, {len(late)} after the hook")
        if talk and len(seen_at) < 2:
            fails.append("no progression: nothing new after the hook line")
    qn = sum(1 for x in sents if _sent_text(x).endswith("?"))
    if qn > 2:
        st -= min(6, 3 * (qn - 2)); notes.setdefault("story", []).append(f"{qn} questions: more than one idea")
    spk = {}
    for w in ws:
        spk[w.get("speaker", "s0")] = spk.get(w.get("speaker", "s0"), 0) + 1
    top = max(spk.values()) / n
    if talk and len(spk) > 1 and top < 0.55:
        st -= 3; notes.setdefault("story", []).append(f"nobody holds the floor (top speaker {top:.0%})")
    areas["story"] = max(0, st)

    # the fix: where the clip should start and end instead (used by the re-edit and by plan.refine)
    for i, s in enumerate(sents[:6]):
        t = _sent_text(s)
        hs = bool(re.search(r"\$|\b\d{2,}\b|\b(million|billion|thousand|percent|hundred)\b|\d\s*%", t, re.I)) or any(k in norm(t) for k in names) or said(keys, norm(t)) >= 0.4
        sq = t.endswith("?") and len(t.split()) <= 12 and said(keys, norm(t)) >= 0.25
        if not bad_open(t) and (hs or sq or not keys) and (re.search(INTEREST, t, re.I) or t.endswith("?") or re.search(r"\b(I|we|my)\b", t)):
            if i:
                fix["start"] = s["start"]
            break
    for j in range(len(sents) - 1, max(len(sents) - 6, 0) - 1, -1):
        tj = _sent_text(sents[j])
        if not bad_end(tj, sents[j]["n"]) and (re.search(INTEREST, tj, re.I) or (keys and said(keys, norm(tj)) >= 0.25)):
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
    res = read(words, det["cuts"], det.get("spec", {}).get("style"), det.get("spec", {}).get("hook", ""))
    (folder / "engage_report.md").write_text(report(res))
    return res


if __name__ == "__main__":
    if len(sys.argv) >= 4:
        w = json.load(open(sys.argv[1]))
        r = read(w, [[float(sys.argv[2]), float(sys.argv[3])]], title=sys.argv[4] if len(sys.argv) > 4 else "")
        print(report(r)); print("fix", r["fix"])
    else:
        r = read_folder(sys.argv[1])
        print(f"audience {r['total']}/100 " + " ".join(f"{k} {v}" for k, v in r["areas"].items()) + (" | " + "; ".join(r["fails"]) if r["fails"] else ""))
