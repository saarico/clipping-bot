"""Scan Content Rewards for campaigns worth joining and write the "CAMPAIGNS TO JOIN" doc in Drive.

Best effort: the discover page is a web app and may block scripts. When it does, the doc says so and
the bot scores whatever links rico pasted into the "CAMPAIGN LINKS" doc instead. Scoring is the
financial scorecard (campaign_score.py); the pick favours the lane with the fewest live campaigns,
not the highest rate (rico, 2026-10-27).
"""
import json
import re
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


def _money(tok):
    """'$359.3K' -> 359300.0, '$2,000' -> 2000.0"""
    tok = tok.replace(",", "").replace("$", "").strip().lower()
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
        c = {"host": "Content Rewards", "link": "https://contentrewards.com" + href.split("?")[0]}
        rate = re.search(r"\$\s?(\d+(?:\.\d+)?)(?:\s*[-\u2013]\s*\$?\d+(?:\.\d+)?)?\s*/\s*1\s*k", text, re.I)
        if rate:
            c["rate"] = float(rate.group(1))
        bud = re.search(r"(\$[\d.,]+[kKmM]?)\s*/\s*(\$[\d.,]+[kKmM]?)", text)
        if bud:
            spent, total = _money(bud.group(1)), _money(bud.group(2))
            c["budget_total"] = total
            c["budget_left"] = max(total - spent, 0.0)
        else:
            one = re.search(r"\$([\d.,]+[kKmM]?)\b(?!\s*/)", text)
            if one:
                c["budget_left"] = _money(one.group(1))
        words = [p for p in parts if not re.search(r"\$|^\d+[hdw]\b|views?$|ago$", p, re.I)]
        words.sort(key=len, reverse=True)
        c["name"] = words[0] if words else uid
        if len(words) > 1:
            c["org"] = words[1]
        low = text.lower()
        c["platforms"] = [p for p in ("youtube", "tiktok", "instagram", "facebook") if p in low]
        c["banned_content"] = bool(re.search(r"\b(casino|gambling|betting|crypto pump|adult|onlyfans)\b", low))
        if "rate" in c or "budget_left" in c:
            out.append(c)
            seen.add(uid)
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
    c["banned_content"] = bool(re.search(r"\b(casino|gambling|betting|crypto pump|adult|onlyfans)\b", low, re.I))
    return c


def lane_for(platforms):
    for p, lane in (("youtube", "A"), ("instagram", "B"), ("tiktok", "C")):
        if p in platforms:
            return lane
    return "?"


def main():
    rt = drive.root()
    live = [n for n, _ in drive.campaigns()]
    notes, cards = [], []
    try:
        cards = cards_from_html(fetch(DISCOVER))
        notes.append(f"Discover page read: {len(cards)} campaigns found." if cards else "Discover page loaded but its format could not be read.")
    except Exception as e:
        notes.append(f"Discover page blocked from GitHub ({type(e).__name__}).")
    links_doc = [f for f in drive.files(rt) if f["Name"].rsplit(".", 1)[0] == "CAMPAIGN LINKS"]
    if links_doc:
        txt = drive.text_of(links_doc[0]["Path"], links_doc[0]["Name"])
        for url in re.findall(r"https?://\S*contentrewards\.com/\S+", txt):
            try:
                cards.append(card_from_page(url.rstrip(").,")))
            except Exception as e:
                notes.append(f"Could not read {url}: {type(e).__name__}")
    else:
        drive.write_doc("CAMPAIGN LINKS", "Paste Content Rewards campaign links here, one per line. The bot scores them on its next run.", rt)
        notes.append("Created the CAMPAIGN LINKS doc for pasted links.")
    # Discover cards carry no platforms/days: open the campaign page for the best-looking ones
    # (pre-filter on the two hard stops we can see: rate >= 0.75 and budget left >= 1000).
    enrich = [c for c in cards if not c.get("platforms") and c.get("rate", 0) >= 0.75 and c.get("budget_left", 0) >= 1000]
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
    rows = []
    for c in cards:
        c.setdefault("lane", lane_for(c.get("platforms", [])))
        try:
            total, verdict, _pts, stops = cs.score(c)
        except Exception:
            continue
        rows.append((c, total, ("STOP: " + "; ".join(stops)) if stops else verdict))
    # diversify: lanes with no live campaign first, then score
    live_lanes = {lane_for([p for p in ("youtube", "instagram", "tiktok") if p in n.lower()]) for n in live}
    rows.sort(key=lambda r: (r[0].get("lane") in live_lanes, -r[1]))
    lines = ["CAMPAIGNS TO JOIN  (bot, financial scorecard; lane balance first, pay second)", ""]
    for c, tot, verdict in rows[:10]:
        lines.append(f"[{c.get('lane','?')}] {tot} {verdict}  {c.get('name','?')}  ${c.get('rate','?')}/1k  ${c.get('budget_left','?')} left  {c.get('link','')}")
    if not rows:
        lines.append("Nothing scored this run.")
    lines += ["", "Live campaigns: " + (", ".join(live) or "none"), ""] + notes
    lines += ["", "To join: click the link, join on the site, download the requirements, and make a folder named after the campaign inside CLIPPING/0_START/ and drop them there."]
    drive.write_doc("CAMPAIGNS TO JOIN", "\n".join(lines), rt)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
