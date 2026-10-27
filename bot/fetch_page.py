"""Text of a web page the requirements link to (Notion, Google Docs, a brand's rules page).
requests first; when the page is an app shell ("JavaScript must be enabled"), render it with Playwright.
    python3 bot/fetch_page.py <url>   -> prints the visible text
"""
import re
import subprocess
import sys

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"}
SHELL = re.compile(r"javascript must be enabled|enable javascript|<div id=\"__next\"></div>", re.I)


def plain(html):
    html = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</(p|div|li|h\d|tr)>", "\n", html, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def render(url, timeout=90):
    """Playwright (chromium) render; returns innerText or ''."""
    js = """
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({viewport: {width: 1280, height: 2000}});
  try { await p.goto(process.argv[2], {waitUntil: 'networkidle', timeout: 60000}); await p.waitForTimeout(5000);
        for (let i = 0; i < 6; i++) { await p.mouse.wheel(0, 2000); await p.waitForTimeout(500); }
        console.log(await p.evaluate(() => document.body.innerText)); } catch (e) { console.error('ERR ' + e.message); }
  await b.close();
})();
"""
    try:
        r = subprocess.run(["node", "-e", js, url], capture_output=True, text=True, timeout=timeout)
        if r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    try:  # python playwright: Notion keeps sockets open, so never wait for "networkidle"
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            p = b.new_page(viewport={"width": 1280, "height": 2400}, user_agent=UA["User-Agent"])
            p.goto(url, wait_until="domcontentloaded", timeout=45000)
            best = ""
            for _ in range(12):                      # up to ~30 s: wait until the text stops growing
                p.wait_for_timeout(2500)
                try:
                    t = p.evaluate("() => document.body.innerText") or ""
                except Exception:
                    t = ""
                if len(t) > len(best):
                    best = t
                elif len(best) > 400:
                    break
            for _ in range(6):
                p.mouse.wheel(0, 2500)
                p.wait_for_timeout(600)
            t = p.evaluate("() => document.body.innerText") or ""
            if len(t) > len(best):
                best = t
            b.close()
            return best.strip()
    except Exception as e:
        return f"(could not render {url}: {type(e).__name__}: {str(e)[:120]})"


def notion_text(url):
    """Public Notion page via the loadPageChunk API (no browser needed). '' when not readable."""
    m = re.search(r"([0-9a-f]{32})", url.replace("-", ""))
    if not m:
        return ""
    h = m.group(1)
    pid = f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"
    body = {"pageId": pid, "limit": 200, "cursor": {"stack": []}, "chunkNumber": 0, "verticalColumns": False}
    lines = []
    try:
        for host in ("https://www.notion.so", "https://app.notion.com"):
            r = requests.post(f"{host}/api/v3/loadPageChunk", json=body, headers={**UA, "Content-Type": "application/json"}, timeout=30)
            if r.status_code != 200:
                continue
            blocks = r.json().get("recordMap", {}).get("block", {})
            for b in blocks.values():
                v = b.get("value", {})
                title = v.get("properties", {}).get("title")
                if title:
                    lines.append("".join(t[0] for t in title if isinstance(t, list) and t))
            if lines:
                break
    except Exception as e:
        return f"(notion api: {type(e).__name__}: {str(e)[:100]})"
    return "\n".join(lines)


def fetch_text(url):
    if "notion" in url:
        t = notion_text(url)
        if len(t) > 200:
            return t
        for u in (url, "https://www.notion.so/" + (re.search(r"([0-9a-f]{32})", url.replace("-", "")) or [None, ""])[1]):
            r = render(u)
            if len(r) > 300 and "JavaScript must be enabled" not in r:
                return r
        return r
    if "docs.google.com/document" in url:
        url = re.sub(r"/edit.*$", "/export?format=txt", url)
    try:
        r = requests.get(url, headers=UA, timeout=30)
        html = r.text
    except Exception as e:
        html = ""
    text = plain(html) if html else ""
    if not html or SHELL.search(html) or len(text) < 300:
        rendered = render(url)
        if len(rendered) > len(text) or not text:
            text = rendered
    return text


if __name__ == "__main__":
    print(fetch_text(sys.argv[1]))
