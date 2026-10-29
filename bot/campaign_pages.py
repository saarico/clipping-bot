"""Read Content Rewards campaign PAGES (end date, requirements, platforms) with a real browser.

The Discover feed (campaign_scan.py) carries no end date and no rules, and the campaign pages are client-rendered,
so requests sees nothing. This runs on the GitHub runner (the sandbox cannot reach contentrewards.com) with
Playwright chromium and saves what a person would see:
    data/campaign_pages/<id>.txt      the page's visible text
    data/campaign_pages/summary.json  per campaign: title, end/time-left lines, rate, budget, platforms, text length

    python3 bot/campaign_pages.py <id-or-link> [...]          (no args: every unstopped card in data/scan_cards.json)
"""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "campaign_pages"
BASE = "https://contentrewards.com/c/campaigns/"
TIME_LEFT = re.compile(r"[^\n]{0,80}\b(ends?(?: in| on)?|ending|deadline|days? (?:left|remaining)|hours? (?:left|remaining)|time left|remaining|"
                       r"until|expires?|closes?|end date|duration)\b[^\n]{0,80}", re.I)


def ids_from(args):
    ids = []
    for a in args:
        m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", a)
        if m:
            ids.append(m.group(1))
    return ids


def default_ids():
    cards = json.loads((ROOT / "data" / "scan_cards.json").read_text()) if (ROOT / "data" / "scan_cards.json").exists() else []
    cards = [c for c in cards if "error" not in c and not c.get("stops")]
    cards.sort(key=lambda c: -c.get("total", 0))
    return ids_from(c.get("link", "") for c in cards[:8])


def read(page, cid):
    url = BASE + cid
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        pass
    time.sleep(5)
    for _ in range(8):
        page.mouse.wheel(0, 1500)
        time.sleep(0.4)
    # tabs that hide the rules ("Requirements", "Details", "Rules", "Overview"): click each once and append its text
    texts = [page.evaluate("document.body.innerText")]
    for label in ("Requirements", "Rules", "Details", "Overview", "Content", "Assets"):
        try:
            el = page.get_by_text(label, exact=True).first
            if el.count():
                el.click(timeout=3000)
                time.sleep(2)
                texts.append(f"\n\n=== tab {label} ===\n" + page.evaluate("document.body.innerText"))
        except Exception:
            pass
    html = page.content()
    html = re.sub(r"<script[^>]+src=[^>]*></script>|<svg.*?</svg>|<style.*?</style>", "", html, flags=re.S)   # keep the inline data scripts
    return url, "\n".join(texts), html


def summarise(cid, url, text):
    low = text.lower()
    title = next((l.strip() for l in text.splitlines() if l.strip() and len(l.strip()) > 3), "")[:120]
    left = sorted({m.group(0).strip()[:160] for m in TIME_LEFT.finditer(text)})[:12]
    rate = re.search(r"\$\s?(\d+(?:\.\d+)?)\s*(?:/|per)\s*(?:1,?000|1k)", text, re.I)
    budget = re.search(r"\$\s?([\d,]+(?:\.\d+)?)\s*(?:of\s*\$[\d,]+\s*)?(?:left|remaining)", text, re.I)
    return {"id": cid, "link": url, "title": title, "chars": len(text),
            "time_left": left, "rate": float(rate.group(1)) if rate else None,
            "budget_left": float(budget.group(1).replace(",", "")) if budget else None,
            "platforms": [p for p in ("youtube", "tiktok", "instagram", "facebook", "x") if re.search(rf"\b{p}\b", low)],
            "application": bool(re.search(r"apply to join|application|requires approval", low)),
            "no_result": len(text) < 400}


def main(args):
    from playwright.sync_api import sync_playwright
    ids = ids_from(args) or default_ids()
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page(viewport={"width": 1280, "height": 2200},
                          user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36")
        for cid in ids:
            try:
                url, text, html = read(page, cid)
            except Exception as e:
                url, text, html = BASE + cid, f"ERROR {type(e).__name__}: {str(e)[:200]}", ""
            (OUT / f"{cid}.txt").write_text(text)
            (OUT / f"{cid}.html").write_text(html)      # the page's own data (Next.js flight JSON) for fields the text hides
            s = summarise(cid, url, text)
            summary[cid] = s
            print(f"{cid[:8]}  {s['chars']:6d} chars  {s['title'][:60]}  | time: {'; '.join(s['time_left'][:3]) or '?'}")
        b.close()
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
