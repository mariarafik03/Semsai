"""
SEMSAI — HTTP Fetch Client (FREE — no API key needed)
======================================================
Uses direct requests.get() — works from any home/office IP.
Cloudflare only blocks datacenter server IPs, not residential ones.

Drop-in replacement for the Tavily API version.
All 3 scrapers import from here — change nothing else.
"""

import re
import time
import requests
from urllib.parse import unquote

# ── Browser headers ───────────────────────────────────────────
HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
}


# ── Search via DuckDuckGo (free, no key) ─────────────────────
def tavily_search(query: str, max_results: int = 10) -> list[dict]:
    """
    Search the web via DuckDuckGo HTML endpoint.
    Returns list of {"url": str, "content": str}.
    Free — no API key, no rate limits for normal use.
    """
    try:
        r = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query, "kl": "eg-ar"},
            headers={**HEADERS, "Referer": "https://duckduckgo.com/"},
            timeout=20,
        )
        if r.status_code != 200:
            print(f"   [SEARCH] DuckDuckGo returned {r.status_code}")
            return []

        urls = []
        for enc in re.findall(r'uddg=([^&"]+)', r.text):
            try:
                url = unquote(enc).strip()
                if url.startswith("http"):
                    urls.append(url)
            except Exception:
                pass

        for url in re.findall(r'<a class="result__url"[^>]*href="([^"]+)"', r.text):
            url = url.strip()
            if url.startswith("http") and url not in urls:
                urls.append(url)

        seen, out = set(), []
        for url in urls:
            if url not in seen:
                seen.add(url)
                out.append({"url": url, "content": ""})
            if len(out) >= max_results:
                break
        return out

    except Exception as e:
        print(f"   [SEARCH ERROR] {e}")
        return []


# ── Fetch a single URL ────────────────────────────────────────
def tavily_fetch_one(url: str, referer: str = "https://www.google.com/") -> str | None:
    """
    Fetch a single URL using browser-like headers.
    Returns full HTML string or None.
    Works on home/office IPs — not blocked by Cloudflare.
    """
    hdrs = {**HEADERS, "Referer": referer}

    for attempt in range(3):
        try:
            r = requests.get(url, headers=hdrs, timeout=25)

            if r.status_code == 200:
                return r.text
            if r.status_code == 202:
                wait = 3 * (attempt + 1)
                print(f"   [FETCH] 202 — waiting {wait}s")
                time.sleep(wait)
                continue
            if r.status_code in (429, 503):
                wait = 5 * (attempt + 1)
                print(f"   [FETCH] {r.status_code} — waiting {wait}s")
                time.sleep(wait)
                continue
            if r.status_code == 403:
                print(f"   [FETCH] 403 blocked — use home/office network")
                return None
            if r.status_code == 500 and attempt == 0:
                time.sleep(5)
                continue
            print(f"   [FETCH] HTTP {r.status_code}: {url[:70]}")
            return None

        except requests.exceptions.Timeout:
            if attempt < 2:
                time.sleep(3)
            else:
                print(f"   [FETCH] Timeout: {url[:70]}")
                return None
        except Exception as e:
            print(f"   [FETCH] {type(e).__name__}: {e}")
            return None

    return None


# ── Fetch multiple URLs ───────────────────────────────────────
def tavily_fetch(urls: list[str]) -> list[dict]:
    """
    Fetch a list of URLs one by one with 0.5s delay between each.
    Returns list of {"url": str, "raw_content": str}.
    """
    results = []
    for i, url in enumerate(urls):
        if i > 0:
            time.sleep(0.5)
        html = tavily_fetch_one(url)
        results.append({"url": url, "raw_content": html or ""})
    return results
