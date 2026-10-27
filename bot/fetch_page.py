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
        r = subprocess.run(["node", "-e", js, "--", url], capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        pass
    try:  # python playwright
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            p = b.new_page(viewport={"width": 1280, "height": 2000})
            p.goto(url, wait_until="networkidle", timeout=60000)
            p.wait_for_timeout(5000)
            for _ in range(6):
                p.mouse.wheel(0, 2000)
                p.wait_for_timeout(500)
            text = p.evaluate("() => document.body.innerText")
            b.close()
            return text.strip()
    except Exception as e:
        return f"(could not render {url}: {type(e).__name__}: {str(e)[:120]})"


def fetch_text(url):
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
        if len(rendered) > len(text):
            text = rendered
    return text


if __name__ == "__main__":
    print(fetch_text(sys.argv[1]))
