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


def parse(text):
    low = text.lower()
    b = {"text": text, "platforms": [], "tags": [], "links": [], "min_s": 20, "max_s": 60,
         "rate_per_1k": None, "min_payout": None, "max_per_clip": None, "face_first_s": None,
         "captions_required": False, "no_ads": False, "assigned_video": False, "rules": []}
    for p in ("youtube", "tiktok", "instagram", "facebook", "x.com", "snapchat"):
        if p in low:
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
    m = re.search(r"disclosure[^\"\u201c\n]{0,60}[\"\u201c]([^\"\u201d\n]{8,160})[\"\u201d]", text, re.I)
    b["disclosure"] = m.group(1).strip() if m else ""
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
