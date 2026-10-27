"""Scan Content Rewards for campaigns worth joining and write the "CAMPAIGNS TO JOIN" doc in Drive.

Best effort: the discover page is a web app and may block scripts. When it does, the doc says so and
the bot scores whatever links rico pasted into the "CAMPAIGN LINKS" doc instead. Scoring is the
financial scorecard (campaign_score.py); the pick favours the lane with the fewest live campaigns,
not the highest rate (rico, 2026-10-27).
"""
import html
import json
import re
from datetime import datetime, timezone
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
import campaign_score as cs  # noqa: E402
import drive  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"}
DISCOVER = "https://contentrewards.com/discover"


def fetch(url):
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    return r.text


BANNED = r"\b(casino|gambling|betting|sportsbook|crypto pump|adult|onlyfans|fansly|sinparty|nsfw|18\+|porn|xxx|escort|sugar daddy|vape|nicotine|kratom)\b"


def _money(tok):
    """'$359.3K' -> 359300.0, '$2,000' -> 2000.0"""
    tok = tok.replace(",", "").replace("$", "").replace(" ", "").strip().lower()
    mult = 1000 if tok.endswith("k") else 1_000_000 if tok.endswith("m") else 1
    return float(tok.rstrip("km")) * mult


def cards_from_html(html):
    """Campaign cards from the Discover page.
    The page is server-rendered: each card is an <a href="/c/campaigns/<uuid>"> with the org, title,
    '$spent/$budget' and '$X/1K' as text. Falls back to embedded JSON when present."""
    out, seen = [], set()
    for m in re.finditer(r'<a\b[^>]*href="(/c/campaigns/([0-9a-f-]{36})[^"]*)"[^>]*>(.*?)</a>', html, flags=re.S | re.I):
        href, uid, inner = m.group(1), m.group(2), m.group(3)
        if uid in seen:
            continue
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", inner)).strip()
        parts = [t.strip() for t in text.split("|") if t.strip()]
        flat = re.sub(r"\s+", " ", text.replace("|", " "))        # rate and budget may be split over several tags
        c = {"host": "Content Rewards", "link": "https://contentrewards.com" + href.split("?")[0], "raw": flat[:160]}
        rate = re.search(r"\$\s?(\d+(?:\.\d+)?)(?:\s*[-\u2013]\s*\$?\s?\d+(?:\.\d+)?)?\s*/\s*1\s*[kK]", flat)
        if not rate:
            rate = re.search(r"\$\s?(\d+(?:\.\d+)?)\s*(?:per|/)\s*(?:1,?000|1\s*k)", flat, re.I)
        if rate:
            c["rate"] = float(rate.group(1))
        bud = re.search(r"(\$\s?[\d.,]+\s?[kKmM]?)\s*/\s*(\$\s?[\d.,]+\s?[kKmM]?)(?!\s*/)", flat)
        if bud and not re.search(r"/\s*1\s*[kK]", bud.group(0)):
            spent, total = _money(bud.group(1)), _money(bud.group(2))
            c["budget_total"] = total
            c["budget_left"] = max(total - spent, 0.0)
        else:
            one = re.search(r"\$\s?([\d.,]+\s?[kKmM]?)\b(?!\s*/)", flat)
            if one:
                c["budget_left"] = _money(one.group(1))
        vw = re.search(r"(\d[\d.,]*)\s*([kKmM])?\s*views?", flat, re.I)
        if vw:
            c["views"] = _money(vw.group(1) + (vw.group(2) or ""))
        cl = re.search(r"\$\s?[\d.,]+\s?[kKmM]?\s*/\s*\$\s?[\d.,]+\s?[kKmM]?\s+(\d[\d,]*)\s+\$", flat)
        if cl:
            c["clippers"] = int(cl.group(1).replace(",", ""))
        parts = [html.unescape(p) for p in parts]
        words = [p for p in parts if not re.search(r"\$|^\d+[hdw]\b|^\d+\s*(mo|w|d|h)$|^\d[\d,]*$|views?$|ago$", p, re.I)]
        cats = [p for p in words if p.lower() in CATEGORIES]
        if cats:
            c["category"] = cats[0]
            words = [p for p in words if p not in cats]
        words.sort(key=len, reverse=True)
        c["name"] = words[0] if words else uid
        if len(words) > 1:
            c["org"] = words[1]
        low = text.lower()
        c["platforms"] = [p for p in ("youtube", "tiktok", "instagram", "facebook") if p in low]
        c["banned_content"] = bool(re.search(BANNED, low))
        if "rate" in c or "budget_left" in c:
            out.append(c)
            seen.add(uid)
    best = {}
    for c in out:
        k = folder_name(c.get("name", ""))
        if k not in best or c.get("budget_left", 0) > best[k].get("budget_left", 0):
            best[k] = c
    out = list(best.values())
    if out:
        return out
    for blob in re.findall(r"<script[^>]*>(\{.*?\})</script>", html, flags=re.S):
        try:
            data = json.loads(blob)
        except Exception:
            continue
        stack = [data]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                if {"title", "rate"} <= set(k.lower() for k in x) or {"name", "cpm"} <= set(k.lower() for k in x):
                    out.append(x)
                stack += list(x.values())
            elif isinstance(x, list):
                stack += x
    return out


def card_from_page(url):
    html = fetch(url)
    low = re.sub(r"<[^>]+>", " ", html)
    c = {"name": re.sub(r"\s+", " ", (re.search(r"<title>([^<]*)", html) or [None, url])[1]).strip(), "host": "Content Rewards", "link": url}
    m = re.search(r"\$\s?(\d+(?:\.\d+)?)\s*(?:/|per)\s*(?:1,?000|1k)", low, re.I)
    if m: c["rate"] = float(m.group(1))
    m = re.search(r"\$\s?([\d,]+(?:\.\d+)?)\s*(?:of\s*\$[\d,]+\s*)?(?:left|remaining)", low, re.I)
    if m: c["budget_left"] = float(m.group(1).replace(",", ""))
    m = re.search(r"(\d+)\s*days?\s*(?:left|remaining)", low, re.I)
    if m: c["days_left"] = int(m.group(1))
    m = re.search(r"(\d[\d,]*)\s*(?:clippers|participants|members)", low, re.I)
    if m: c["clippers"] = int(m.group(1).replace(",", ""))
    c["platforms"] = [p for p in ("youtube", "tiktok", "instagram", "facebook") if p in low.lower()]
    c["pay_to_join"] = bool(re.search(r"pay to join|entry fee", low, re.I))
    c["banned_content"] = bool(re.search(BANNED, low, re.I))
    c["text"] = re.sub(r"\s+", " ", low)[:3000]
    return c


def lane_for(platforms):
    for p, lane in (("youtube", "A"), ("instagram", "B"), ("tiktok", "C")):
        if p in platforms:
            return lane
    return "?"


SEEN = Path(__file__).resolve().parent.parent / "data" / "scan_seen.json"
MAX_NEW = 3


CATEGORIES = {"finance", "business", "entertainment", "technology", "apps", "lifestyle", "gaming", "music", "sports", "education",
              "beauty", "fashion", "comedy", "podcast", "health", "fitness", "crypto", "news", "reality", "food", "travel", "art", "other"}
TOPIC = {  # rico's lanes: lane = what the content is about
    "A": r"\b(finance|financial|business|money|invest|investing|stocks?|trading|entrepreneur|startup|marketing|sales|real estate|wealth|millionaire|economy|bank|sofi|credit|crypto|bitcoin|side hustle|ecom|dropship|saas|career)\b",
    "C": r"\b(gaming|game|games|gamer|roblox|minecraft|fortnite|call of duty|warfare|warzone|gta|valorant|xbox|playstation|nintendo|speedrun|esports|streamer|streaming|twitch|kick|music|concert|rap|hip hop|artist|album|sports?|football|soccer|nba|nfl|ufc|mma|boxing|wwe|f1|racing|cars?|tech|technology|gadget|anime|comedy|comedian|funny|prank|highlights|metaverse|gym|bodybuilding|podcast|show|episode)\b",
    "B": r"\b(beauty|makeup|skincare|fashion|outfit|celebrity|celebrities|drama|gossip|reality|dating|relationship|love|girls?|women|influencer|kardashian|pop|lifestyle|wellness|self care|glow|aesthetic|bridgerton|tea)\b",
}
BORING = r"\b(ugc|split[- ]screen|app|apps|software|download|sign[- ]?up|referral|use my link|promo code|promo|discount|extension|wallet|casino|betting)\b"
FUN = r"\b(podcast|interview|episode|show|story|stories|clips?|stream|streamer|concert|live|reaction|comedy|funny|drama|celebrity|reality)\b"
LANE_PLATFORM = {"A": "youtube", "B": "instagram", "C": "tiktok"}
CAT_LANE = {"finance": "A", "business": "A", "crypto": "A", "education": "A", "technology": "C", "gaming": "C", "entertainment": "C", "sports": "C",
            "music": "C", "comedy": "C", "podcast": "C", "lifestyle": "B", "beauty": "B", "fashion": "B", "reality": "B", "health": "B", "fitness": "C"}


def content_fit(c):
    """(lane, topic_pts 0-10, fun_pts 0-15). Lane by topic first (rico: YouTube = business and money,
    TikTok = entertainment and cool stuff, Instagram = girly stuff and drama), platform second."""
    blob = " ".join(str(c.get(k, "")) for k in ("name", "org", "category", "text")).lower()
    plats = [p.lower() for p in c.get("platforms", [])]
    hits = {l: len(re.findall(rx, blob)) for l, rx in TOPIC.items()}
    lane, topic = None, 0
    for l, _n in sorted(hits.items(), key=lambda kv: -kv[1]):
        if hits[l] and LANE_PLATFORM[l] in plats:
            lane, topic = l, 10 if hits[l] >= 2 else 7
            break
    if lane is None:
        cat = CAT_LANE.get(c.get("category", "").lower())
        if cat and LANE_PLATFORM[cat] in plats:
            lane, topic = cat, 5   # lane from the card's category
        elif not c.get("platforms_guessed"):
            for l in ("C", "B", "A"):
                if LANE_PLATFORM[l] in plats:
                    lane, topic = l, 2   # platform fits, topic unclear
                    break
    fun = 0
    fun += min(8, 4 * len(re.findall(FUN, blob)))
    fun += 4 if (c.get("category", "").lower() in ("entertainment", "comedy", "sports", "gaming", "music", "podcast", "reality")) else 0
    fun += 3 if c.get("views", 0) >= 250e3 else 0
    fun -= min(15, 6 * len(re.findall(BORING, blob)))
    return lane or "?", topic, max(0, min(15, fun))


def auto_score(c):
    """Score a Discover card. The full scorecard needs a research dossier (creator reach, clip library);
    a card only shows pay, budget, spend and views, so A + E come from campaign_score and the rest
    from traction proxies. Returns (total out of 100, verdict, stops)."""
    for k in [k for k, v in c.items() if v is None]:
        del c[k]
    raw, _verdict, pts, stops = cs.score(c)
    name = c.get("name", "")
    if re.search(r"[\u0600-\u06FF\u0400-\u04FF\u0E00-\u0E7F\u3040-\u30FF\u4E00-\u9FFF\uAC00-\uD7AF]", name) or \
       re.search(r"\b(en fran[cç]ais|espa[ñn]ol|hablando|portugu[eê]s|deutsch|italiano|international|arabic|hindi|\(fr\)|\(es\)|\(de\)|\(pt\))\b", name, re.I):
        stops.append("not an English campaign (our accounts post in English)")
    a, e = pts["A pay and budget"], pts["E rules load"]
    tot_b = c.get("budget_total") or 0
    spent = (tot_b - c.get("budget_left", 0)) / tot_b if tot_b else 0
    tr = 12 if spent >= 0.5 else 9 if spent >= 0.2 else 5 if spent >= 0.05 else 0
    v = c.get("views", 0)
    tr += 13 if v >= 1e6 else 10 if v >= 250e3 else 6 if v >= 50e3 else 3 if v >= 10e3 else 0
    cl = c.get("clippers")
    comp = 5 if not cl else 10 if cl < 100 else 6 if cl < 400 else 3 if cl < 1500 else 0
    dl = c.get("days_left")
    fresh = 5 if dl is None or dl >= 14 else 3 if dl >= 7 else 0
    lane, topic, fun = content_fit(c)
    c["lane"] = lane
    guess = 3 if c.get("platforms_guessed") else 0
    c["pts"] = {"pay+budget": a, "rules": e, "traction": tr, "competition": comp, "time": fresh, "lane fit": topic, "entertainment": fun, "platform guessed": -guess}
    total = a + e + tr + comp + fresh + topic + fun - guess   # max 100
    verdict = "STOP" if stops else "JOIN" if total >= 60 else "MAYBE" if total >= 50 else "SKIP"
    return total, verdict, stops


def folder_name(title):
    t = re.sub(r"[\\/:*?\"<>|]+", " ", title)
    t = re.sub(r"\s+", " ", t).strip(" .")
    return t[:60].strip() or "campaign"


def main():
    rt = drive.root()
    live = [n for n, _ in drive.campaigns()]
    seen = json.loads(SEEN.read_text()) if SEEN.exists() else {}
    notes, cards = [], []
    try:
        cards = cards_from_html(fetch(DISCOVER))
        notes.append(f"Discover page read: {len(cards)} campaigns found." if cards else "Discover page loaded but its format could not be read.")
    except Exception as e:
        notes.append(f"Discover page blocked from GitHub ({type(e).__name__}).")
    # Discover cards carry no platforms/days: open the campaign page for the best-looking ones
    # (pre-filter on the two hard stops we can see: rate >= 0.75 and budget left >= 1000).
    enrich = [c for c in cards if not c.get("platforms") and c.get("rate", 0) >= 0.75 and c.get("budget_left", 0) >= 1000
              and folder_name(c.get("name", "")) not in seen and folder_name(c.get("name", "")) not in live]
    enrich.sort(key=lambda c: (-c.get("rate", 0), -c.get("budget_left", 0)))
    for c in enrich[:15]:
        try:
            page = card_from_page(c["link"])
        except Exception:
            continue
        for k in ("platforms", "days_left", "clippers", "pay_to_join"):
            if page.get(k):
                c[k] = page[k]
        c["banned_content"] = c.get("banned_content") or page.get("banned_content", False)
        c["text"] = page.get("text", "")[:3000]
        if not c.get("platforms"):
            c["platforms"], c["platforms_guessed"] = ["youtube", "tiktok", "instagram"], True
    rows, dump = [], []
    for c in cards:
        c["folder"] = folder_name(c.get("name", ""))
        if c["folder"] in seen or c["folder"] in live:
            continue  # already offered once (rico deleted it or joined it): never offer again
        try:
            total, verdict, stops = auto_score(c)
        except Exception as e:
            dump.append({"name": c.get("name"), "error": f"{type(e).__name__}: {e}"})
            continue
        dump.append({k: c.get(k) for k in ("name", "org", "category", "lane", "rate", "budget_left", "budget_total", "views", "clippers", "days_left", "platforms", "pts", "link", "raw")}
                    | {"total": total, "verdict": verdict, "stops": stops})
        if stops or c["lane"] == "?" or total < 55:
            continue
        rows.append((c, total, verdict if verdict == "JOIN" else "MAYBE, best in its lane"))
    dump.sort(key=lambda d: -d.get("total", 0))
    (SEEN.parent / "scan_cards.json").write_text(json.dumps(dump, indent=1))
    # diversify: lanes with no live campaign first, then score; one new campaign per lane per run
    live_lanes = {lane_for([p for p in ("youtube", "instagram", "tiktok") if p in n.lower()]) for n in live}
    rows.sort(key=lambda r: (r[0].get("lane") in live_lanes, -r[1]))
    made, lanes_done = [], set()
    for c, tot, verdict in rows:
        if len(made) >= MAX_NEW or c["lane"] in lanes_done:
            continue
        folder = f"{rt}/0_START/{c['folder']}"
        drive.be().mkdir(folder)
        text = "\n".join([
            f"{c['name']}",
            "",
            f"Link: {c['link']}",
            f"Pay: ${c.get('rate', '?')} per 1k views   Budget left: ${c.get('budget_left', '?'):,.0f}" if isinstance(c.get("budget_left"), float) else f"Pay: ${c.get('rate', '?')} per 1k views",
            f"Lane: {c['lane']} ({ {'A': 'YouTube business/money', 'B': 'Instagram girly/drama', 'C': 'TikTok entertainment'}[c['lane']] })   Score: {tot}/100 ({verdict})",
            "Points: " + ", ".join(f"{k} {v}" for k, v in c.get("pts", {}).items() if v),
            "",
            "1. Open the link and join the campaign.",
            "2. Download the requirements and drop them in this folder.",
            "3. The bot reads them on its next run (every 5 hours) and puts 3 clips in 1_CHECK.",
            "",
            "Not interested? Delete this folder. The bot will not bring it back.",
        ])
        drive.write_doc("JOIN", text, folder)
        seen[c["folder"]] = {"link": c["link"], "score": tot, "lane": c["lane"], "offered": datetime.now(timezone.utc).isoformat(timespec="minutes")}
        made.append(c["folder"])
        lanes_done.add(c["lane"])
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps(seen, indent=1))
    print("\n".join(notes + [f"scored {len(rows)} JOIN candidates; new folders in 0_START: {made or 'none'}", "live: " + (", ".join(live) or "none")]))


if __name__ == "__main__":
    main()
