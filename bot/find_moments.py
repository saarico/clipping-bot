"""Read a whole episode's transcript and rank the best 20-60 s moments to clip (PLAYBOOK 28).

Usage:
  python3 find_moments.py <words.json> [--graphics graphics.json] [--top 20] [--out candidates]

words.json = [{"text", "start", "end", "speaker"}] in episode seconds (the OpusClip transcript).
Writes <out>.json and <out>.md: for each candidate the window, the score with its reasons, the first
line a stranger would hear, a suggested title, and the full text to read.

What scores (a normal scroller's view, not a marketer's):
  stakes     money, a famous name, a failure, a surprise, a secret, strong emotion, a number
  shape      a question then its answer; a story ("so one day", "he told me", "when I was"); a contrast
             ("but", "actually", "turns out"); a reaction from the other person ("wow", "really?")
  clarity    the first sentence names who/what (a name, a number, "I"/"we" + a verb) and is not a
             pointer back ("as I said", "that", "this is why")
  pace       2.2-3.3 words per second; long pauses and filler words cost points
  visuals    the show has a card, photo or strip on screen inside the window (graphics_map.py)
The result is a shortlist to READ, not a verdict: Claude reads the top candidates in full and the
judge (scorecards/judgment.md) grades the finished cut.
"""
import json
import re
import sys
from collections import Counter

MONEY = r"\$|\b(million|billion|thousand|dollars?|bucks|rich|broke|paid|pay|salary|revenue|profit|debt|price|cost)\b"
FAIL = r"\b(fail(ed|ure|ing)?|fired|lost|lose|losing|quit|bankrupt|mistakes?|worst|broke|wrong|rejected|collapsed|divorced?|addict(ed|ion|ive)?)\b"
SURPRISE = r"\b(actually|turns out|crazy|insane|nobody|no one|secret|truth|never|always|shocked|wild|unbelievable|literally|the only)\b"
EMOTION = r"\b(miserable|happy|happiness|afraid|fear|shame|anxious|anxiety|love|hate|cried|cry|angry|depressed|lonely|terrified|proud|jealous)\b"
NUMBER = r"\b(\d[\d,.]*|one|two|three|four|five|six|seven|eight|nine|ten|twenty|thirty|forty|fifty|hundred|first|second|half)\b"
STORY = r"\b(so one day|one day|when i was|when he was|he told me|she told me|told him|my (dad|mom|father|mother|wife|brother|friend)|i remember|years? ago|and then|the next day)\b"
CONTRAST = r"\b(but|actually|however|except|turns out|the problem is|here's the thing|the truth is|what nobody|in fact)\b"
REACTION = r"^(wow|really|no way|how|damn|holy|what|seriously|right|yeah)\b[.?!]?$"
FILLER = r"\b(um|uh|like|you know|sort of|kind of|i mean)\b"
BACKREF = r"^(and |so |but )?(as i (said|mentioned)|like i said|that's why|this is why|which is why|that is|this|that|it|which|these|those|he|she|they)\b"
PODCAST_TALK = r"(we('ve| have)? talked about|talk(ed)? about (this|that) (a lot )?in|in (a few|the|that|another|our) [a-z ]{0,20}episodes?|you said something|as i (said|mentioned)|like i said|earlier in|last episode|this episode|the (shame|change|failure) episode)"
FAMOUS = r"\b(elon|musk|bezos|jobs|steve jobs|gates|zuckerberg|trump|obama|kanye|taylor swift|agassi|jordan|kobe|lebron|tiger|federer|serena|oprah|rogan|google|apple|amazon|netflix|tesla|openai|chatgpt|facebook|instagram|tiktok|youtube|buddha|jesus|einstein|michael jackson|beyonce|drake|mrbeast|nfl|nba|olympics?)\b"


def sentences(words):
    """Group words into sentences: end punctuation, a speaker change, or a pause over 1 s."""
    out, cur = [], []
    for w, nxt in zip(words, words[1:] + [None]):
        cur.append(w)
        end = w["text"].rstrip('"\')').endswith((".", "?", "!"))
        if nxt is None or end or nxt["speaker"] != w["speaker"] or nxt["start"] - w["end"] > 1.0:
            out.append({"start": cur[0]["start"], "end": cur[-1]["end"], "speaker": cur[0]["speaker"],
                        "text": " ".join(x["text"] for x in cur), "n": len(cur)})
            cur = []
    return out


def count(rx, text):
    return len(re.findall(rx, text, flags=re.I))


def score_window(sents, graphics):
    text = " ".join(s["text"] for s in sents)
    low = text.lower()
    dur = sents[-1]["end"] - sents[0]["start"]
    nwords = sum(s["n"] for s in sents)
    wps = nwords / max(dur, 1)
    first = sents[0]["text"]
    reasons = {}
    reasons["stakes"] = min(25, 4 * count(MONEY, low) + 4 * count(FAIL, low) + 3 * count(SURPRISE, low)
                            + 3 * count(EMOTION, low) + 2 * count(NUMBER, low) + 6 * count(FAMOUS, low))
    # proper names (capitalised words not at a sentence start) read as "someone famous / a real story"
    names = [m for m in re.findall(r"(?<![.?!]\s)(?<!^)\b([A-Z][a-z]{2,})\b", text) if m.lower() not in ("i", "the", "and", "but", "so")]
    reasons["names"] = min(8, 2 * len(set(names)))
    shape = 0
    if "?" in " ".join(s["text"] for s in sents[:2]):
        shape += 6
    shape += min(8, 3 * count(STORY, low))
    shape += min(6, 2 * count(CONTRAST, low))
    reactions = sum(1 for s in sents if re.match(REACTION, s["text"].strip().lower()))
    shape += min(6, 3 * reactions)
    reasons["shape"] = min(20, shape)
    clarity = 10
    if re.match(BACKREF, first.strip(), flags=re.I):
        clarity -= 7
    head = " ".join(x["text"] for x in sents[:2]).lower()
    if re.search(PODCAST_TALK, head):
        clarity -= 8          # "we talked about this in the shame episode": a stranger is lost
    inside = count(PODCAST_TALK, low)
    if sents[0]["n"] < 6:
        clarity -= 3
    if not (re.search(NUMBER, first, re.I) or re.search(r"\b[A-Z][a-z]{2,}\b", first[1:]) or re.search(r"\b(I|we|my)\b", first)):
        clarity -= 3
    reasons["clarity"] = max(0, clarity)
    pace = 10
    if wps < 1.8:
        pace -= 6
    elif wps < 2.2:
        pace -= 3
    elif wps > 3.6:
        pace -= 2
    fill = count(FILLER, low) / max(nwords, 1)
    if fill > 0.06:
        pace -= 4
    elif fill > 0.035:
        pace -= 2
    gaps = sum(1 for a, b in zip(sents, sents[1:]) if b["start"] - a["end"] > 1.0)
    pace -= min(4, gaps)
    reasons["pace"] = max(0, pace)
    gfx = [g for g in graphics if g["from"] < sents[-1]["end"] and g["to"] > sents[0]["start"]]
    reasons["visuals"] = min(12, 6 * len({g["type"] for g in gfx}) + 2 * len(gfx))
    # payoff: the last sentence should be a point, not a trail-off
    last = sents[-1]["text"].strip()
    reasons["payoff"] = 10 if (last.endswith((".", "!")) and sents[-1]["n"] >= 5) else 4
    # length: 35-55 s is the sweet spot for Shorts with a story
    reasons["length"] = 5 if 30 <= dur <= 55 else 3 if 22 <= dur <= 60 else 0
    reasons["self_contained"] = -4 * min(inside, 3)   # every podcast back-reference costs 4
    total = sum(reasons.values())
    return total, reasons, text, gfx


def hook_from(sents):
    """Suggested title: the sentence with the most stakes words, trimmed to 12 words."""
    best = max(sents, key=lambda s: count(MONEY + "|" + FAIL + "|" + SURPRISE + "|" + EMOTION + "|" + FAMOUS, s["text"].lower()) * 10 - abs(s["n"] - 9))
    toks = best["text"].split()
    return " ".join(toks[:12]) + ("..." if len(toks) > 12 else "")


def main(words_path, graphics_path=None, top=20, out="candidates"):
    words = json.load(open(words_path))
    graphics = json.load(open(graphics_path)) if graphics_path else []
    sents = sentences(words)
    cands = []
    for i in range(len(sents)):
        for j in range(i + 1, min(i + 40, len(sents))):
            dur = sents[j]["end"] - sents[i]["start"]
            if dur < 20:
                continue
            if dur > 62:
                break
            total, reasons, text, gfx = score_window(sents[i:j + 1], graphics)
            cands.append({"start": round(sents[i]["start"], 2), "end": round(sents[j]["end"], 2), "dur": round(dur, 1),
                          "score": total, "reasons": reasons, "first_line": sents[i]["text"],
                          "hook": hook_from(sents[i:j + 1]), "graphics": gfx, "text": text})
    cands.sort(key=lambda c: -c["score"])
    picked = []
    for c in cands:
        if all(min(c["end"], p["end"]) - max(c["start"], p["start"]) < 0.4 * min(c["dur"], p["dur"]) for p in picked):
            picked.append(c)
        if len(picked) >= top:
            break
    json.dump(picked, open(out + ".json", "w"), indent=1)
    lines = [f"# Candidate moments ({words_path})", "", "Scores are a shortlist to read, not a verdict (PLAYBOOK 28).", ""]
    for k, c in enumerate(picked, 1):
        m0, s0 = divmod(int(c["start"]), 60)
        r = ", ".join(f"{a} {b}" for a, b in c["reasons"].items())
        g = ", ".join(f"{x['type']} {x['from']:.0f}-{x['to']:.0f}s" for x in c["graphics"]) or "none"
        lines += [f"## {k}. {m0}:{s0:02d}  ({c['dur']} s)  score {c['score']}", f"- reasons: {r}", f"- show graphics inside: {g}",
                  f"- first line: {c['first_line']}", f"- title idea: {c['hook']}", "", f"> {c['text']}", ""]
    open(out + ".md", "w").write("\n".join(lines))
    print(f"{len(picked)} candidates -> {out}.md / .json")
    for k, c in enumerate(picked[:10], 1):
        m0, s0 = divmod(int(c["start"]), 60)
        print(f"{k:2d}. {m0}:{s0:02d} {c['dur']:5.1f}s score {c['score']:3d}  {c['first_line'][:80]}")


if __name__ == "__main__":
    a = sys.argv[1:]
    g = a[a.index("--graphics") + 1] if "--graphics" in a else None
    t = int(a[a.index("--top") + 1]) if "--top" in a else 20
    o = a[a.index("--out") + 1] if "--out" in a else "candidates"
    main(a[0], g, t, o)
