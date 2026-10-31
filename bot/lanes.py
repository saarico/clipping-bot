"""Which ONE platform a clip goes to (rico, 2026-10-27 and 2026-10-29: "separate clips on Insta, TikTok and
YouTube based on the category of the clip"; a clip is never posted to all three).

    YouTube  (@fedsaa)   = business / money
    Instagram (@fesavoo) = celebrity / pop culture / drama / gossip
    TikTok               = entertainment: comedy, streamers, gaming, music, action, sports

The lane is set by what the story is about: the clip's own spoken words and hook are scored on the 12
genres (bot/genres.py). A movie, stream or concert starts from TikTok and a podcast from YouTube; another
lane has to beat that baseline clearly (1.3x) to take the clip. The reviewer can pin a clip with
`"lane": "youtube"` in plan.json. config/accounts.json holds the handles."""
import json
import re
from pathlib import Path

import genres

LANE_GENRES = {
    "youtube": ("business", "selfhelp", "truecrime"),
    "instagram": ("gossip", "romance", "drama"),
    "tiktok": ("comedy", "action", "horror", "sports", "gaming", "music"),
}
BASELINE = {"podcast": "youtube", "": "youtube", "cinematic": "tiktok", "stream": "tiktok", "performance": "tiktok"}
MONEY = r"\$\s?\d|\b\d+ ?(k|m|million|billion|trillion|percent|%)\b|\b(dollar|dollars|salary|revenue|profit|invest\w*|market|markets|stock|stocks|crypto|bitcoin|business|company|startup|ceo|founder|money|rich|billionaire|millionaire)\b"
CELEB = r"\b(kardashian|jenner|drake|taylor swift|kanye|beyonc|rihanna|bieber|tom cruise|cruise|celebrit\w*|famous|dating|boyfriend|girlfriend|ex\b|breakup|cheat\w*|divorce|wedding|pregnan\w*|drama|gossip|exposed|scandal)\b"


def _sents(text):
    out = []
    for s in re.split(r"(?<=[.!?])\s+", (text or "").strip()):
        if s:
            out.append({"text": s, "n": len(s.split())})
    return out


def scores(hook, text, style=""):
    """{platform: points} for one clip from its own words."""
    full = f"{hook or ''}. {text or ''}"
    low = full.lower()
    gs = genres.genre_scores(_sents(full), low)
    lane = {p: float(sum(gs.get(g, 0) for g in gl)) for p, gl in LANE_GENRES.items()}
    lane["youtube"] += 3.0 * genres.count(MONEY, low)
    lane["instagram"] += 3.0 * genres.count(CELEB, low)
    return lane


def pick(hook, text, style="", override=None):
    """(platform, reason). `text` = the clip's spoken words (captions), `style` = grading profile."""
    if override in LANE_GENRES:
        return override, "pinned by the reviewer"
    lane = scores(hook, text, style)
    base = BASELINE.get(style or "", "youtube")
    best = max(lane, key=lane.get)
    if best != base and lane[best] < 1.3 * max(lane[base], 1.0):
        best = base
    why = ", ".join(f"{p} {v:.0f}" for p, v in sorted(lane.items(), key=lambda kv: -kv[1]))
    return best, f"{why}; baseline {base} ({style or 'podcast'})"


def assign(clips, allowed=None):
    """Lanes for a campaign's kept clips: [(platform, reason)] in order. Each clip is picked on its own;
    then, when every clip landed in the same lane, the clip whose second lane is at least half as strong
    moves there, so one campaign feeds more than one channel (rico: lane diversity counts).
    clips = [{"hook", "text", "style", "lane"(optional pin)}]"""
    out = [list(pick(c.get("hook", ""), c.get("text", ""), c.get("style", ""), c.get("lane"))) for c in clips]
    # the campaign's own platform list wins (2026-10-31: a Higgsfield clip was sent to TikTok on a YouTube + Instagram
    # brief): a lane outside it moves to the strongest allowed one
    allowed = [a for a in (allowed or []) if a in LANE_GENRES]
    for i, c in enumerate(clips):
        if allowed and out[i][0] not in allowed:
            sc = scores(c.get("hook", ""), c.get("text", ""), c.get("style", ""))
            best = max(allowed, key=lambda p: sc.get(p, 0))
            out[i] = [best, out[i][1] + f"; {out[i][0]} is not in this campaign's platforms, moved to {best}"]
    lanes = {o[0] for o in out}
    if len(clips) >= 2 and len(lanes) == 1:
        best_i, best_ratio, best_alt = None, 0.5, None
        for i, c in enumerate(clips):
            if c.get("lane") in LANE_GENRES:
                continue
            sc = scores(c.get("hook", ""), c.get("text", ""), c.get("style", ""))
            cur = out[i][0]
            alts = [p for p in sc if p != cur and (not allowed or p in allowed)]
            if not alts:
                continue
            alt = max(alts, key=sc.get)
            ratio = sc[alt] / max(sc[cur], 1.0)
            if ratio >= best_ratio:
                best_i, best_ratio, best_alt = i, ratio, alt
        if best_i is not None:
            out[best_i] = [best_alt, out[best_i][1] + f"; moved from {out[best_i][0]} for lane diversity (second lane {best_ratio:.0%} as strong)"]
    return [tuple(o) for o in out]


def handle(platform):
    acc = json.loads((Path(__file__).parent.parent / "config" / "accounts.json").read_text())
    return acc.get(platform, "?")


if __name__ == "__main__":
    import sys
    print(pick(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "", sys.argv[3] if len(sys.argv) > 3 else ""))
