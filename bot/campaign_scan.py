"""Scan Content Rewards for campaigns worth joining and write the "CAMPAIGNS TO JOIN" doc in Drive.

Best effort: the discover page is a web app and may block scripts. When it does, the doc says so and
the bot scores whatever links rico pasted into the "CAMPAIGN LINKS" doc instead. Scoring is the
financial scorecard (campaign_score.py); the pick favours the lane with the fewest live campaigns,
not the highest rate (rico, 2026-10-27).
"""
import html as htmlmod
import json
import os
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
    r = requests.get(url, headers=UA, timeout=20)
    r.raise_for_status()
    return r.text


NEVER = r"\b(mark manson|manson|solved)\b"   # rico, 2026-10-27 03:11: never again
BANNED = r"\b(flip\.gg|case opening|cases? battle|skins? gambling|sinparty|onlyfans|casino|gambling|betting|sportsbook|crypto pump|adult|onlyfans|fansly|sinparty|nsfw|18\+|porn|xxx|escort|sugar daddy|vape|nicotine|kratom)\b"


def _money(tok):
    """'$359.3K' -> 359300.0, '$2,000' -> 2000.0"""
    tok = tok.replace(",", "").replace("$", "").replace(" ", "").strip().lower()
    mult = 1000 if tok.endswith("k") else 1_000_000 if tok.endswith("m") else 1
    return float(tok.rstrip("km")) * mult


def cards_from_json(html):
    """The Discover page embeds every campaign as JSON inside a Next.js flight string
    ({\"campaign\":{...}} with escaped quotes): title, brand, category, platforms, payoutSortRaw (rate),
    availableBudgetRaw, budgetTotalRaw, creatorCountRaw (clippers), submissionCountRaw, description, id."""
    doc = html.replace('\\"', '"')
    dec = json.JSONDecoder()
    out, seen = [], set()
    for m in re.finditer(r'"campaign":\s*\{', doc):
        try:
            obj, _ = dec.raw_decode(doc, m.end() - 1)
        except Exception:
            continue
        uid = obj.get("id")
        if not uid or uid in seen or not obj.get("title"):
            continue
        seen.add(uid)
        c = {"host": "Content Rewards", "link": f"https://contentrewards.com/c/campaigns/{uid}",
             "name": htmlmod.unescape(obj["title"]), "org": obj.get("brand") or "", "category": obj.get("category") or "",
             "description": (obj.get("description") or "")[:600], "platforms": [p.lower() for p in obj.get("platforms") or []],
             "clippers": obj.get("creatorCountRaw"), "submissions": obj.get("submissionCountRaw"),
             "budget_total": obj.get("budgetTotalRaw"), "budget_left": obj.get("availableBudgetRaw"),
             "application_only": bool(obj.get("requiresApplication")), "verified": bool(obj.get("isVerified")),
             "pay_type": obj.get("type"), "funded_ago": obj.get("fundedAgo"), "launched_ms": obj.get("launchedAtMs"),
             "budget_spent": obj.get("budgetSpentRaw"), "raw": "json"}
        if obj.get("type") == "cpm" and obj.get("payoutSortRaw") is not None:
            c["rate"] = float(obj["payoutSortRaw"])
        low = f"{c['name']} {c['org']} {c['description']}".lower()
        c["banned_content"] = bool(re.search(BANNED, low))
        out.append(c)
    return out


def cards_from_html(html):
    """Campaign cards from the Discover page: the embedded JSON first (complete), the visible card
    text second ('Org · age Title $spent / $budget <clippers> $rate /1K', numbers split over tags)."""
    cards = cards_from_json(html)
    out, seen = [], {c["link"].rsplit("/", 1)[-1] for c in cards}
    out += cards
    for m in re.finditer(r'<a\b[^>]*href="(/c/campaigns/([0-9a-f-]{36})[^"]*)"[^>]*>(.*?)</a>', html, flags=re.S | re.I):
        href, uid, inner = m.group(1), m.group(2), m.group(3)
        if uid in seen:
            continue
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", inner)).strip()
        parts = [t.strip() for t in text.split("|") if t.strip()]
        flat = re.sub(r"\s+", " ", text.replace("|", " "))
        c = {"host": "Content Rewards", "link": "https://contentrewards.com" + href.split("?")[0], "raw": flat[:160]}
        rate = re.search(r"\$\s?(\d+(?:\.\d+)?)(?:\s*[-\u2013]\s*\$?\s?\d+(?:\.\d+)?)?\s*/\s*1\s*[kK]", flat)
        if rate:
            c["rate"] = float(rate.group(1))
        bud = re.search(r"(\$\s?[\d.,]+\s?[kKmM]?)\s*/\s*(\$\s?[\d.,]+\s?[kKmM]?)(?!\s*/)", flat)
        if bud and not re.search(r"/\s*1\s*[kK]", bud.group(0)):
            spent, total = _money(bud.group(1)), _money(bud.group(2))
            c["budget_total"], c["budget_left"] = total, max(total - spent, 0.0)
        cl = re.search(r"\$\s?[\d.,]+\s?[kKmM]?\s*/\s*\$\s?[\d.,]+\s?[kKmM]?\s+(\d[\d,]*)\s+\$", flat)
        if cl:
            c["clippers"] = int(cl.group(1).replace(",", ""))
        parts = [htmlmod.unescape(p) for p in parts]
        words = [p for p in parts if not re.search(r"\$|^\d+[hdw]\b|^\d+\s*(mo|w|d|h)$|^\d[\d,]*$|views?$|ago$", p, re.I)]
        cats = [p for p in words if p.lower() in CATEGORIES]
        if cats:
            c["category"] = cats[0]
            words = [p for p in words if p not in cats]
        words.sort(key=len, reverse=True)
        c["name"] = words[0] if words else uid
        if len(words) > 1:
            c["org"] = words[1]
        c["platforms"] = []
        c["banned_content"] = bool(re.search(BANNED, text.lower()))
        if "rate" in c or "budget_left" in c:
            out.append(c)
            seen.add(uid)
    return out


def lane_for(platforms):
    for p, lane in (("youtube", "A"), ("instagram", "B"), ("tiktok", "C")):
        if p in platforms:
            return lane
    return "?"


SEEN = Path(__file__).resolve().parent.parent / "data" / "scan_seen.json"
try:
    ACCOUNTS = json.loads((Path(__file__).resolve().parent.parent / "config" / "accounts.json").read_text())
except Exception:
    ACCOUNTS = {}
MAX_NEW = 3


CATEGORIES = {"finance", "business", "entertainment", "technology", "apps", "lifestyle", "gaming", "music", "sports", "education",
              "beauty", "fashion", "comedy", "podcast", "health", "fitness", "crypto", "news", "reality", "food", "travel", "art", "other"}
TOPIC = {  # rico's lanes: lane = what the content is about
    "A": r"\b(finance|financial|business|money|invest|investing|stocks?|trading|entrepreneur|startup|marketing|sales|real estate|wealth|millionaire|economy|bank|sofi|credit|crypto|bitcoin|side hustle|ecom|dropship|saas|career)\b",
    "C": r"\b(gaming|game|games|gamer|roblox|minecraft|fortnite|call of duty|warfare|warzone|gta|valorant|xbox|playstation|nintendo|speedrun|esports|streamer|streaming|twitch|kick|music|concert|rap|hip hop|artist|album|sports?|football|soccer|nba|nfl|ufc|mma|boxing|wwe|f1|racing|cars?|tech|technology|gadget|anime|comedy|comedian|funny|prank|highlights|metaverse|gym|bodybuilding|podcast|show|episode)\b",
    "B": r"\b(beauty|makeup|skincare|fashion|outfit|celebrity|celebrities|drama|gossip|reality|dating|relationship|love|girls?|women|influencer|kardashian|pop|lifestyle|wellness|self care|glow|aesthetic|bridgerton|tea)\b",
}
BORING = r"\b(ugc|split[- ]screen|app|apps|software|download|sign[- ]?up|referral|use my link|promo code|promo|discount|extension|wallet|casino|betting)\b"
FUN = r"\b(podcast|interview|episode|show|story|stories|stream|streamer|concert|live|reaction|comedy|comedian|funny|drama|celebrity|reality|highlights|moments)\b"
# rico (2026-10-27 05:20 UTC): never again a brand ad. Clips must grow the channels, so a campaign has to
# be about a SHOW or a PERSON (podcast, streamer, performer, game footage), not a product.
SHOW = r"\b(podcasts?|interviews?|episodes?|show|shows|streamer|streamers|streams?|streaming|live|concert|performance|tour|comedy|comedian|reaction|reacts|highlights|moments|vlogs?|talks?|debate|panel|rant|kick|twitch|youtuber|creator|influencer|clip the show|clipping army|fight|fighter|match|game|games|gaming|roblox|minecraft|fortnite|warfare|warzone|esports|speedrun|music|rapper|singer|band|dj)\b"
AD = r"\b(ugc|split[- ]screen|app|apps|software|saas|download|install|sign[- ]?up|referral|use my link|promo code|promo|discount|extension|wallet|product|products|brand awareness|launch|early access|pre-?orders?|crowdfund|invest in|token|nft|metaverse|airdrop|web3|crypto|blockchain|virtual world|decentraland|teasers?|content bank|trading cards?|collectibles?|merch|ai tool|ai video|generator|fintech|bitcoin rewards|debit card|credit card|subscription|supplement|skincare brand)\b"
AD_CATS = {"apps", "finance", "technology", "health & wellness", "crypto", "software", "ecommerce", "e-commerce", "product", "brand", "business", "saas"}


def is_ad(c):
    """True when the campaign promotes a product or company instead of clipping a show or a person."""
    blob = " ".join(str(c.get(k, "")) for k in ("name", "org", "category")).lower()
    desc = str(c.get("description", "")).lower()[:1500]
    show = len(re.findall(SHOW, blob)) * 2 + len(re.findall(SHOW, desc))
    if not re.search(PERSON, blob + " " + desc):      # game words are "show" content only with a person in it (game_promo)
        show -= len(re.findall(GAME, blob)) * 2 + len(re.findall(GAME, desc))
    ad = len(re.findall(AD, blob)) * 2 + len(re.findall(AD, desc))
    cat = str(c.get("category", "")).lower()
    if cat in AD_CATS and show < 2:
        return True
    return ad >= 2 and ad > show


PERSON = r"\b(streamer|streamers|twitch|kick|youtuber|youtubers|creator|creators|podcast|podcasts|show|host|reacts?|reaction|vlog|vlogs|clipping army|his|her|their|he|she|comedian|caster|commentary|facecam|irl)\b"
GAME = r"\b(gaming|video ?game|roblox|minecraft|fortnite|call of duty|cod|modern warfare|warzone|gta|valorant|esports|multiplayer|dlc|gameplay|campaign moments)\b"


def game_promo(c):
    """Video-game footage with nobody in it: a publisher's ad, not a person's content (rico 2026-10-29). The same
    words count as "show" content in is_ad only when a person is named, so the two gates agree."""
    blob = " ".join(str(c.get(k, "")) for k in ("name", "org", "category", "description")).lower()
    return (bool(re.search(GAME, blob)) or str(c.get("category", "")).lower() in ("gaming", "roblox")) and not re.search(PERSON, blob)


LANE_PLATFORM = {"A": "youtube", "B": "instagram", "C": "tiktok"}
CAT_LANE = {"finance": "A", "business": "A", "crypto": "A", "education": "A", "technology": "C", "gaming": "C", "entertainment": "C", "sports": "C",
            "music": "C", "comedy": "C", "podcast": "C", "lifestyle": "B", "beauty": "B", "fashion": "B", "reality": "B", "health": "B", "fitness": "C"}


# shows whose lane the title alone does not tell (rico's lanes): a money podcast is YouTube even when its name says "coffee"
KNOWN_SHOWS = {"A": r"iced coffee hour|graham stephan|20vc|diary of a ceo|my first million|all-in podcast|bigger pockets|lex fridman",
               "B": r"bilf|mara dorne|call her daddy|kardashian|love island|bachelor",
               "C": r"kai cenat|ishowspeed|adin ross|xqc|theo von|joe rogan|flagrant|kill tony|impaulsive"}
# Reach-style campaigns want the posting account's niche to match or a dedicated account (TJR, 2026-10-29): rico's channels
# are general, so they are offered no more
DEDICATED = r"\bdedicated (?:account|page|pages)\b|\bfan page\b(?! needed)|reach"


def content_fit(c):
    """(lane, topic_pts 0-10, fun_pts 0-15). Lane by topic first (rico: YouTube = business and money,
    TikTok = entertainment and cool stuff, Instagram = girly stuff and drama), platform second."""
    blob = " ".join(str(c.get(k, "")) for k in ("name", "org", "category")).lower()
    desc = str(c.get("description", "")).lower()
    plats = [p.lower() for p in c.get("platforms", [])]
    hits = {l: len(re.findall(rx, blob)) for l, rx in TOPIC.items()}
    if not any(hits.values()):
        hits = {l: len(re.findall(rx, desc)) for l, rx in TOPIC.items()}
    for l, rx in KNOWN_SHOWS.items():
        if re.search(rx, blob + " " + desc):
            hits = {k: (3 if k == l else 0) for k in TOPIC}   # a known show settles the lane
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
    fun += min(8, 4 * len(re.findall(FUN, blob + " " + desc)))
    fun += 4 if (c.get("category", "").lower() in ("entertainment", "comedy", "sports", "gaming", "music", "podcast", "reality")) else 0
    fun += 3 if (c.get("views") or 0) >= 250e3 else 0   # a card with views: null crashed the score and the card vanished
    fun -= min(15, 6 * len(re.findall(BORING, blob + " " + desc)))
    return lane or "?", topic, max(0, min(15, fun))


def auto_score(c):
    """Score a Discover card. The full scorecard needs a research dossier (creator reach, clip library);
    a card only shows pay, budget, spend and views, so A + E come from campaign_score and the rest
    from traction proxies. Returns (total out of 100, verdict, stops)."""
    for k in [k for k, v in c.items() if v is None]:
        del c[k]
    raw, _verdict, pts, stops = cs.score(c)
    name = c.get("name", "")
    if re.search(NEVER, name, re.I):
        stops.append("rico said never")
    if is_ad(c):
        stops.append("brand ad, not a show (rico: clips must grow the channels)")
    if game_promo(c):
        stops.append("game footage with no person in it = a game-launch ad (rico 2026-10-29: the page would look like it just posts ads)")
    if re.search(DEDICATED, f"{name} {c.get('org', '')} {c.get('description', '')}", re.I) and not re.search(r"no fan page needed", str(c.get("description", "")), re.I):
        stops.append("wants a dedicated / niche-matching account (Reach style; rico dropped TJR for this 2026-10-30)")
    if re.search(r"[\u0600-\u06FF\u0400-\u04FF\u0E00-\u0E7F\u3040-\u30FF\u4E00-\u9FFF\uAC00-\uD7AF]", name) or \
       re.search(r"\b(en fran[cç]ais|espa[ñn]ol|hablando|portugu[eê]s|deutsch|italiano|international|arabic|hindi|\(fr\)|\(es\)|\(de\)|\(pt\)|con|para|sobre|pour|avec|und|vistas|clips en)\b|€", name, re.I):
        stops.append("not an English campaign (our accounts post in English)")
    a = pts["A pay and budget"]                      # 0-25: rate, budget left, budget per clipper
    tot_b = c.get("budget_total") or 0
    spent = (tot_b - c.get("budget_left", 0)) / tot_b if tot_b else 0
    tr = 12 if 0.5 <= spent < 0.9 else 9 if spent >= 0.2 else 5 if spent >= 0.05 else 0   # 0-12: money already paid out = clips get paid
    sub = c.get("submissions") or 0
    tr += 8 if sub >= 300 else 5 if sub >= 80 else 2 if sub >= 15 else 0                   # 0-8: clips already submitted = clippers trust it
    cl = c.get("clippers")
    comp = 5 if not cl else 10 if cl < 100 else 6 if cl < 400 else 3 if cl < 1500 else 0  # 0-10: fewer clippers = more budget each
    dl = c.get("days_left")
    if dl is not None and dl < 7:
        stops.append("under 7 days left")
    # Content Rewards campaigns have no end date: they close when the budget is spent (pages read 2026-10-29). So
    # "close to ending" = budget left at the pace it has been paid out since launch; under 10 days is a stop.
    if c.get("launched_ms") and tot_b:
        age = (datetime.now(timezone.utc).timestamp() - c["launched_ms"] / 1000) / 86400
        paid = c.get("budget_spent") if c.get("budget_spent") is not None else tot_b - (c.get("budget_left") or 0)
        if age >= 1 and paid > 0:
            c["days_est"] = round((c.get("budget_left") or 0) / (paid / age))
            if c["days_est"] < 10 and not re.search(r"\b(weekly|monthly|week \d+)\b", name, re.I):   # a weekly pot refills; a one-off does not
                stops.append(f"budget runs out in about {c['days_est']} day(s) at its current pace")
    lane, topic, fun = content_fit(c)               # 0-10 lane fit, 0-15 entertainment
    c["lane"] = lane
    if lane == "?" or topic < 5:                    # rico 2026-10-29: every campaign must fit ONE account's identity (config/accounts.json)
        stops.append("fits none of the three accounts (no clear topic for YouTube money, Instagram drama or TikTok entertainment)")
    guess = 3 if c.get("platforms_guessed") else 0
    c["pts"] = {"pay+budget": a, "paid out": tr, "competition": comp, "lane fit": topic, "entertainment": fun, "platform guessed": -guess}
    total = round(max(0, a + tr + comp + topic + fun - guess) / 72 * 100)   # 72 = every point a card can earn
    total = min(total, 100)
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
        page = fetch(DISCOVER)
        if os.environ.get("SAVE_PAGE"):
            (SEEN.parent / "discover_sample.html").write_text(page)   # on demand: test the reader offline on the real page
        cards = cards_from_html(page)
        notes.append(f"Discover page read: {len(cards)} campaigns found." if cards else "Discover page loaded but its format could not be read.")
    except Exception as e:
        notes.append(f"Discover page blocked from GitHub ({type(e).__name__}: {str(e)[:120]}).")
    # Discover cards carry no platforms: campaign pages are client-rendered (nothing readable from GitHub), so every
    # card is scored as "all three platforms" and the lane comes from its words. The JOIN doc tells rico to check.
    for c in cards:
        if not c.get("platforms"):
            c["platforms"], c["platforms_guessed"] = ["youtube", "tiktok", "instagram"], True
    rows, dump = [], []
    seen_ids = {v.get("link", "").rsplit("/", 1)[-1] for v in seen.values()}
    for c in cards:
        c["folder"] = folder_name(c.get("name", ""))
        if c["folder"] in seen or c["folder"] in live or c["link"].rsplit("/", 1)[-1] in seen_ids:
            continue  # already offered once (rico deleted it or joined it): never offer again, under any title
        try:
            total, verdict, stops = auto_score(c)
        except Exception as e:
            dump.append({"name": c.get("name"), "error": f"{type(e).__name__}: {e}"})
            continue
        dump.append({k: c.get(k) for k in ("name", "org", "category", "lane", "rate", "budget_left", "budget_total", "views", "clippers", "days_left", "days_est", "funded_ago", "platforms", "submissions", "application_only", "pts", "link", "raw")}
                    | {"total": total, "verdict": verdict, "stops": stops})
        if stops or total < 55:
            continue
        rows.append((c, total, verdict if verdict == "JOIN" else "MAYBE, best in its lane"))
    dump.sort(key=lambda d: -d.get("total", 0))
    (SEEN.parent / "scan_cards.json").write_text(json.dumps(dump, indent=1))
    # diversify: lanes with no live campaign first, then score; one new campaign per lane per run
    lanes_done = {seen[n]["lane"] for n in live if n in seen and seen[n].get("lane")}   # one open offer per lane at a time
    rows.sort(key=lambda r: (r[0].get("lane") in lanes_done, -r[1]))
    made = []
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
            f"Account: {ACCOUNTS.get(LANE_PLATFORM[c['lane']], '?')}   posts: {ACCOUNTS.get('identity', {}).get(LANE_PLATFORM[c['lane']], {}).get('posts', '')}",
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
