"""Turn the campaign's requirements file (pdf / docx / Google Doc / txt) into brief.json.

Regexes catch the hard facts (length, platforms, tags, rate, links, face/captions rules); the full
text is kept in brief.json["text"] so the reviewer (Claude, or rico) reads the real wording. Anything
the regexes miss stays a rule in the text, it is never dropped.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import profiles  # noqa: E402

YT = r"(https?://(?:www\.)?(?:youtube\.com/(?:watch\?v=|playlist\?list=|shorts/|live/)|youtu\.be/)[\w\-&=?%]+)"


TS = r"(\d{1,2}:\d{2}(?::\d{2})?)"


def _secs(t):
    p = [int(x) for x in t.split(":")]
    return p[0] * 3600 + p[1] * 60 + p[2] if len(p) == 3 else p[0] * 60 + p[1]


RANGE = re.compile(TS + r"\s*[\u2013\u2014-]\s*" + TS)
QUOTES = ("\"", "\u201c", "\u201d")


def _last_quote(text, before):
    return max(text.rfind(c, 0, before) for c in QUOTES)


def clip_ideas(text):
    """The brief's own clip ideas: a quoted hook with a mm:ss-mm:ss range and a note, in any of the layouts a PDF
    table comes out as (2026-10-30, Higgsfield): hook and time on one line; the hook opened on the line above the
    time and closed on the line below it (the table wrapped the hook column); the hook closed right before the time.
    -> [{"hook", "start", "end", "note"}] in the brief's order. Times are in the brief's reference video; plan.py
    checks the words really sit there. Two-part ideas ("... 32:58-33:04 +") and ranges under 15 s are skipped."""
    out = []
    for m in RANGE.finditer(text):
        a, b = _secs(m.group(1)), _secs(m.group(2))
        if not (15 <= b - a <= 240):
            continue
        line_end = text.find("\n", m.end())
        line_end = len(text) if line_end < 0 else line_end
        note = text[m.end():line_end].strip(" -\u2014\t")
        if note.endswith("+"):
            continue
        q = _last_quote(text, m.start())
        if q < 0:
            continue
        between = text[q + 1:m.start()].strip()
        if not between:
            # the quote right before the time closes the hook: it runs from the quote before that
            p = _last_quote(text, q)
            if p < 0:
                continue
            hook = text[p + 1:q]
        else:
            # the hook opened before the time and was not closed yet: the rest sits on the next line(s)
            hook = between
            tail = text[line_end + 1:line_end + 400]
            close = re.search(r"[\"\u201d]", tail)
            if close and tail[:close.start()].count("\n") <= 1 and not RANGE.search(tail[:close.start()]):
                hook = hook + " " + tail[:close.start()]
        hook = re.sub(r"\s+", " ", hook).strip(" \n\u2026")
        seam = re.search(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", hook)   # "Business These": the note column leaked into the quote
        if seam and seam.start() > 0 and not hook[:seam.start()].rstrip().endswith((",", ":")) and re.search(r"[.?!]", hook[:seam.start()]):
            cut = max(hook.rfind(x, 0, seam.start()) for x in ".?!")
            hook = hook[:cut + 1]
        if len(hook.split()) > 14:   # the table's note column leaked into the quote: keep the first sentence(s) that fit
            keep, parts = "", re.split(r"(?<=[.?!])\s+", hook)
            for part in parts:
                if len((keep + " " + part).split()) > 14:
                    break
                keep = (keep + " " + part).strip()
            hook = keep or " ".join(hook.split()[:12])
        if not (8 <= len(hook) <= 180):
            continue
        out.append({"hook": hook, "start": a, "end": b, "note": note[:160]})
    return out


IDEA_HEAD = re.compile(r"^\s*(content ideas|clip ideas|ideas|angles|moments|what to clip|suggested text|text[- ]on[- ]screen|hooks?)\b", re.I)
STOP_HEAD = re.compile(r"^\s*(campaign rules|rules|requirements|assets|links|payout|payment|do not|don'?ts?|disclosure|hashtags?|tags)\b", re.I)
TOPIC_NOISE = {"malcolm", "todd", "clips", "clip", "moments", "moment", "interview", "interviews", "anything", "especially", "perform",
               "pages", "present", "typically", "different", "quotes", "standout", "about", "where", "which", "these", "those", "their",
               "other", "shows", "fans", "reason", "deeper", "campaign", "video", "videos", "podcast", "appearance", "official", "across",
               "discussing", "talks", "himself", "herself", "really", "every", "everyone", "right", "making", "proves", "speaks", "facts",
               "expect", "trying", "biggest", "career", "words", "being", "having", "there", "well", "like", "this", "that", "with", "from",
               "most", "real", "just", "even", "than", "them", "when", "what", "into", "your", "yet", "his", "her", "him", "its", "the",
               "show", "side", "year", "give", "goes", "went", "come", "came", "take", "took", "make", "made", "same", "some", "such",
               "each", "both", "been", "were", "have", "will", "would", "could", "should", "does", "done", "want", "need", "keep",
               "back", "down", "here", "while", "they", "then", "also", "over", "only", "time", "more", "much", "many", "very",
               "look", "looks", "feel", "feels", "gets", "says", "said", "tell", "tells", "told", "goal", "build", "hype", "give",
               "across", "around", "before", "after", "during", "through", "without", "within", "between", "again", "first", "last",
               "whole", "entire", "please", "ensure", "always", "never", "still", "already", "something", "anything", "everything",
               "nothing", "someone", "anyone", "everyone", "people", "person", "thing", "things", "stuff", "line", "lines", "text",
               "screen", "caption", "captions", "title", "titles", "hook", "hooks", "suggested", "ideas", "idea", "content",
               "visual", "visuals", "angle", "angles", "trimming", "trim", "circulate", "highlighting", "huge", "right"}


def topics(text):
    """The brief's subjects, for the scorecard (2026-10-31, Malcolm Todd: the brief listed "Chest Pain", "Earrings",
    Do That Again, the sold-out tour, going viral; the scorecard picked "literally literally" instead).
    Reads the idea sections (CONTENT IDEAS, ANGLES, SUGGESTED TEXT-ON-SCREEN ...) up to the next rules/assets heading:
    quoted phrases and Title Case names count double, every other content word once.
    -> [[phrase, weight], ...] lower case, at most 40."""
    lines, on = [], False
    for ln in text.splitlines():
        if IDEA_HEAD.match(ln):
            on = True
            continue
        if STOP_HEAD.match(ln):
            on = False
        if on and ln.strip():
            lines.append(ln.strip())
    if not lines:
        return []
    body = "\n".join(lines)
    out, quoted_words = {}, set()
    for q in re.findall(r"[\"\u201c]([^\"\u201d\n]{3,60})[\"\u201d]", body) + re.findall(r"(?<![a-z])'([^'\n]{3,40})'(?![a-z])", body):
        # a quoted title or line: "Chest Pain", 'Earrings'; a whole suggested caption is split into its content words below
        ph = re.sub(r"\s+", " ", q).strip(" ,.;:!?").lower()
        words = ph.split()
        if 1 <= len(words) <= 4 and "malcolm todd" not in ph:
            out[ph] = 2
            quoted_words.update(words)   # the title's own words are not topics on their own ("chest", "pain")
    for m in re.finditer(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+){1,3})\b", body):
        ph = m.group(1).lower()
        if "malcolm todd" not in ph and not all(w in TOPIC_NOISE for w in ph.split()):
            out.setdefault(ph, 2)
    for w in re.findall(r"[a-z][a-z-]{3,}", re.sub(r"[a-z]+'[a-z]+", " ", body.lower())):   # "wasn't", "you'd" are not words
        w = w.strip("-")
        if len(w) >= 4 and w not in TOPIC_NOISE and w not in quoted_words and not w.endswith("ly") and len(set(w)) > 2:
            out.setdefault(w, 1)
    ranked = sorted(out.items(), key=lambda kv: (-kv[1], kv[0]))
    return [[k, v] for k, v in ranked[:40]]


def parse(text):
    low = text.lower()
    # platforms are named in the rules, never read off the asset links: "youtube.com/watch?v=..." in a brief that
    # allows only TikTok + Instagram Reels (Malcolm Todd, 2026-10-31) must not make YouTube a lane
    low_np = re.sub(r"(https?://\S+|\b[\w.-]+\.(?:com|be|tv|net|org)\S*)", " ", low)
    b = {"text": text, "platforms": [], "tags": [], "links": [], "min_s": 20, "max_s": 60,
         "rate_per_1k": None, "min_payout": None, "max_per_clip": None, "face_first_s": None,
         "captions_required": False, "no_ads": False, "assigned_video": False, "rules": []}
    for p in ("youtube", "tiktok", "instagram", "facebook", "x.com", "snapchat"):
        if p in (low if p == "x.com" else low_np):
            b["platforms"].append("x" if p == "x.com" else p)
    b["tags"] = sorted({t.rstrip(".") for t in re.findall(r"(?<![\w.])@[A-Za-z0-9_.]{2,30}", text)} | set(re.findall(r"(?<![\w&])#[A-Za-z][A-Za-z0-9_]{2,30}", text)))
    # source links: YouTube first, then Drive / Dropbox / direct video files (the bot downloads those itself)
    src = re.findall(r"https?://(?:drive\.google\.com/(?:file/d/|drive/folders/|open\?id=)[^\s<>\"')\]]+|[^\s<>\"')\]]*dropbox\.com/[^\s<>\"')\]]+|[^\s<>\"')\]]+\.(?:mp4|mov|mkv|webm)(?:\?[^\s<>\"')\]]*)?)", text)
    b["links"] = list(dict.fromkeys(re.findall(YT, text) + src))
    m = re.search(r"(\d{1,3})\s*(?:s|sec|secs|seconds)?\s*(?:-|–|to)\s*(\d{1,3})\s*(?:s|sec|secs|seconds)\b", low)
    if m:
        a, c = int(m.group(1)), int(m.group(2))
        if 5 <= a < c <= 180:
            b["min_s"], b["max_s"] = a, c
    m = re.search(r"\$\s?(\d+(?:\.\d+)?)\s*(?:per|/|for every)\s*(?:1,?000|1k)", low)
    if m:
        b["rate_per_1k"] = float(m.group(1))
    # "min payout $3.75" and Reach's "$3.75 Min / $750 Max" (amount first; the old pattern read "$3.75 min $750" as min 750)
    m = re.search(r"\$\s?(\d+(?:\.\d+)?)\s*(?:min|minimum)\b", low) or \
        re.search(r"min(?:imum)?\s*(?:payout|earning|payment)?[^$\n]{0,25}\$\s?(\d+(?:\.\d+)?)(?!\s*max)", low)
    if m:
        b["min_payout"] = float(m.group(1))
    m = re.search(r"\$\s?(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:max|maximum)\b", low) or \
        re.search(r"max(?:imum)?\s*(?:payout|earning|payment)?[^$\n]{0,25}\$\s?(\d+(?:,\d{3})*(?:\.\d+)?)", low)
    if m:
        b["max_per_clip"] = float(m.group(1).replace(",", ""))
    m = re.search(r"face[^.\n]{0,60}?(\d{1,2})\s*(?:s|sec|seconds)", low) or re.search(r"(?:first|within)\s*(\d{1,2})\s*(?:s|sec|seconds)[^.\n]{0,60}face", low)
    if m:
        b["face_first_s"] = int(m.group(1))
    b["captions_required"] = bool(re.search(r"\b(subtitles?|captions?)\b", low))
    # a brand/show watermark the clip must carry (Higgsfield 20VC, 2026-10-30): the PNG comes with the brief in 0_START
    b["watermark"] = bool(re.search(r"\bwatermark", low))
    # "YouTube: @HiggsfieldAI + @20VC / Instagram: @higgsfield.ai @20vchq": each platform gets its own handles in the post kit
    byp = {}
    for line in text.splitlines():
        m = re.match(r"\s*(?:tagging|tags?|handles?)?\s*(youtube|instagram|tiktok|facebook)(?:\s*(?:shorts|reels))?\s*[:\-]?\s*((?:@[A-Za-z0-9_.]{2,30}[\s,+&]*(?:and\s+)?){1,4})\s*$", line.strip(), re.I)
        if m:
            byp.setdefault(m.group(1).lower(), [])
            byp[m.group(1).lower()] += [t.rstrip(".") for t in re.findall(r"@[A-Za-z0-9_.]{2,30}", m.group(2))]
    b["tags_by_platform"] = {k: list(dict.fromkeys(v)) for k, v in byp.items()}
    m = re.search(r"disclosure[^\"\u201c\n]{0,60}[\"\u201c]([^\"\u201d\n]{8,160})[\"\u201d]", text, re.I)
    b["disclosure"] = m.group(1).strip() if m else ""
    b["moments"] = clip_ideas(text)   # the brief's own "CLIP IDEAS" with times: the bot cuts those first (Higgsfield, 2026-10-30)
    b["style"] = profiles.detect_from_text(text)   # podcast / cinematic / stream / performance ('' = decide from the footage)
    m = re.search(r"(Rewards are unsecured[^\n]{10,220}?lose value\.)", text)   # the rewards rider some brands require near any rewards claim
    b["rider"] = m.group(1).strip() if m else ""
    b["no_ads"] = bool(re.search(r"\b(no|without|exclude|skip)\b[^.\n]{0,30}\b(ad reads?|ads|sponsor)", low))
    b["assigned_video"] = bool(b["links"]) and not re.search(r"\b(any|all) (of (his|her|their) )?(videos?|episodes?|content)\b", low)
    # every line that reads like a rule is kept as one
    for line in text.splitlines():
        s = line.strip(" -•*\t")
        if 12 < len(s) < 220 and re.search(r"\b(must|do not|don't|never|always|only|required|not allowed|at least|no more than|minimum|maximum)\b", s.lower()):
            b["rules"].append(s)
    return b


if __name__ == "__main__":
    import sys
    print(json.dumps(parse(open(sys.argv[1]).read()), indent=1)[:4000])


def speaker_tag(text):
    """The who-line shown under the hook for the first seconds (rico 2026-10-31: "who is this guy, what is the
    topic"): from brief wording like "Alex built Higgsfield, an AI video company" + "Alex Mashrabov talks with ...",
    -> "Alex Mashrabov · built Higgsfield (AI video)". Empty when the brief does not say; the campaign's state
    may carry a hand-written "speaker_tag" instead."""
    text = text or ""
    stop = {"Content", "Clip", "Find", "Hook", "Add", "Keep", "Shows", "The", "Use", "Make", "Post", "Watch"}
    names = [n for n in re.findall(r"\b([A-Z][a-z]+ [A-Z][a-z]+(?:[a-z]+)?)\b", text) if n.split()[0] not in stop]
    m = re.search(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)?) (built|founded|co-founded|runs|created|is the founder of|is the CEO of|leads) "
                  r"([A-Z][\w.]+(?: [A-Z][\w.]+)?)(?:,\s*(?:an?|the)\s+([^,.;\n]{3,40}?))?(?=[,.;\n ]|$)", text)
    if not m:
        return ""
    who, verb, company, desc = m.groups()
    if " " not in who:
        who = next((n for n in names if n.split()[0] == who), who)
    verb = {"is the founder of": "founder of", "is the CEO of": "CEO of", "leads": "runs"}.get(verb, verb)
    tag = f"{who} · {verb} {company}"
    if desc:
        desc = re.sub(r"\s+(company|startup|business|platform|app)$", "", desc.strip())
        tag += f" ({desc})"
    return tag
