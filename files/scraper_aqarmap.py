"""
SEMSAI — Aqarmap Egypt Scraper Module
======================================
Extracts comparable property prices from aqarmap.com.eg.

HOW IT WORKS:
  Strategy 1 — API (preferred):
    Aqarmap exposes a REST API used by their React frontend.
    /api/v3/en/listing/ accepts compound slug, listing_type, property_type.
    Returns paginated JSON with full listing data including price, area, rooms.

  Strategy 2 — NEXT_DATA scraping (fallback):
    Compound search page: /en/listing/type/sale/{location-slug}/comp-{compound-slug}/
    Contains __NEXT_DATA__ with listing array.

  Strategy 3 — Individual listing pages:
    Each listing at /en/listing/{id}/ has full JSON in NEXT_DATA.

URL / API STRUCTURE:
  Search API:  GET /api/v3/en/listing/
    Params: compound_slug, listing_type (sale|rent), property_type (apartment|villa|chalet)
            page, limit, area_from, area_to, rooms

  Location slugs:
    New Cairo:    egypt-cairo-new-cairo
    6th October:  egypt-cairo-6th-october
    Sheikh Zayed: egypt-cairo-sheikh-zayed
    North Coast:  egypt-north-coast-sahel
    Ain Sokhna:   egypt-suez-ain-sokhna
    New Capital:  egypt-cairo-new-capital

  Listing type:
    Developer Sale → listing_type=sale, is_primary=1
    Resale         → listing_type=sale, is_resale=1

NOTE: Run on your own machine — Cloudflare blocks cloud IPs.
"""

import re
import json
import time
import requests
import statistics
from dataclasses import dataclass, field
from urllib.parse import urlencode, urlparse, unquote
from tavily_client import tavily_search as _tavily_search, tavily_fetch, tavily_fetch_one

# ── Config — API key is in tavily_client.py ───────────────────
PPM_CEILING_STANDARD  = 220_000
PPM_CEILING_LARGE     = 250_000
PPM_SANITY_FLAG       = 180_000
AREA_LARGE_THRESHOLD  = 400
AREA_TOLERANCE        = 0.20
CLUSTER_GAP_THRESHOLD = 40.0

BASE_URL = "https://aqarmap.com.eg"
API_BASE = f"{BASE_URL}/api/v3/en"

AQ_PTYPE = {
    "apartment": "apartment",
    "villa":     "villa",
    "chalet":    "chalet",
    "townhouse": "townhouse",
    "duplex":    "duplex",
}

LOCATION_SLUGS = {
    "new cairo":        "egypt-cairo-new-cairo",
    "5th settlement":   "egypt-cairo-new-cairo",
    "6th settlement":   "egypt-cairo-new-cairo",
    "golden square":    "egypt-cairo-new-cairo",
    "6th of october":   "egypt-cairo-6th-october",
    "6th october":      "egypt-cairo-6th-october",
    "sheikh zayed":     "egypt-cairo-sheikh-zayed",
    "new zayed":        "egypt-cairo-sheikh-zayed",
    "north coast":      "egypt-north-coast-sahel",
    "sahel":            "egypt-north-coast-sahel",
    "ain sokhna":       "egypt-suez-ain-sokhna",
    "sokhna":           "egypt-suez-ain-sokhna",
    "new capital":      "egypt-cairo-new-capital",
    "administrative":   "egypt-cairo-new-capital",
    "madinaty":         "egypt-cairo-new-cairo",
    "heliopolis":       "egypt-cairo-heliopolis",
    "nasr city":        "egypt-cairo-nasr-city",
    "cairo":            "egypt-cairo",
}


# ── Result type ───────────────────────────────────────────────
@dataclass
class ScraperResult:
    source:   str
    prices:   list[int]  = field(default_factory=list)
    median:   float      = 0.0
    ppm:      float      = 0.0
    n:        int        = 0
    low_conf: bool       = False
    fallback: bool       = False
    urls:     list[str]  = field(default_factory=list)
    error:    str | None = None

    def __bool__(self):
        return len(self.prices) > 0


# ── Helpers ───────────────────────────────────────────────────
def _get_nested(obj, path):
    cur = obj
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _remove_outliers(prices, fallback=False):
    import pandas as pd
    if len(prices) < 3:
        return prices, len(prices) <= 2
    thr = 1.8 if fallback else 2.5
    s   = pd.Series(prices)
    med = s.median()
    mad = (s - med).abs().median()
    clean = s[((0.6745 * (s - med)) / mad).abs() <= thr].tolist() if mad > 0 else prices
    clean = clean if clean else prices
    lc = len(clean) <= 2 or len(set(prices)) == 1
    if clean and len(clean) >= 3:
        cv = statistics.stdev(clean) / statistics.mean(clean)
        if cv > 0.5:
            lc = True
    return clean, lc


def _cluster_by_sale_type(prices, sale_type):
    if len(prices) < 4:
        return prices
    sp = sorted(prices)
    max_gap, split = 0.0, None
    for i in range(1, len(sp)):
        g = (sp[i] - sp[i - 1]) / sp[i - 1] * 100
        if g > max_gap:
            max_gap, split = g, i
    if max_gap < CLUSTER_GAP_THRESHOLD or split is None:
        return prices
    lower, upper = sp[:split], sp[split:]
    if len(lower) < 2 or len(upper) < 2:
        return prices
    is_resale = "resale" in sale_type.lower()
    chosen = upper if is_resale else lower
    print(f"   [AQ CLUSTER] gap={max_gap:.0f}% → {'upper(resale)' if is_resale else 'lower(dev)'}")
    return chosen


def _to_compound_slug(compound: str) -> str:
    return compound.lower().strip().replace(" ", "-").replace("_", "-")


def _get_location_slug(location: str) -> str:
    loc = location.lower().strip()
    for key, val in LOCATION_SLUGS.items():
        if key in loc or loc in key:
            return val
    return "egypt-cairo"


def _fetch(url: str, session=None, accept_json: bool = False) -> str | None:
    """Fetch via Tavily /extract — real browser, bypasses Cloudflare."""
    return tavily_fetch_one(url)


# ── Strategy 1: Aqarmap REST API ─────────────────────────────
def _api_search(
    compound_slug: str,
    ptype:         str,
    sale_type:     str,
    bedrooms:      int,
    area:          float,
    session=None,
) -> list[dict]:
    """
    Call Aqarmap's internal listing API via Tavily.
    Returns list of raw listing dicts.
    """
    is_resale = "resale" in sale_type.lower()
    ptype_slug = AQ_PTYPE.get(ptype.lower(), "apartment")

    params = {
        "compound_slug":  compound_slug,
        "listing_type":   "sale",
        "property_type":  ptype_slug,
        "limit":          20,
        "page":           1,
    }
    if bedrooms:
        params["rooms"] = bedrooms
    if is_resale:
        params["is_resale"] = 1
    else:
        params["is_primary"] = 1

    params["area_from"] = int(area * 0.70)
    params["area_to"]   = int(area * 1.30)

    api_url = f"{API_BASE}/listing/?{urlencode(params)}"
    print(f"   [AQ API] {api_url[:100]}")

    raw = tavily_fetch_one(api_url)
    if not raw:
        return []

    try:
        data = json.loads(raw)
    except Exception:
        return []

    if isinstance(data, dict):
        results = (
            data.get("results") or
            data.get("listings") or
            _get_nested(data, ["data", "listings"]) or
            _get_nested(data, ["data", "results"]) or
            []
        )
        if isinstance(results, list):
            print(f"   [AQ API] {len(results)} listings returned")
            return results

    return []


def _parse_aq_listing(listing: dict) -> dict | None:
    """Normalise an Aqarmap listing dict."""
    # Price
    price = (
        listing.get("price") or
        listing.get("asking_price") or
        listing.get("total_price") or
        listing.get("unit_price")
    )
    if isinstance(price, str):
        price = int(re.sub(r'[^\d]', '', price)) if re.search(r'\d', price) else None
    if not isinstance(price, (int, float)) or price <= 0:
        return None

    # Bedrooms
    beds = (
        listing.get("rooms") or
        listing.get("bedrooms") or
        listing.get("bedroom_count") or
        listing.get("beds")
    )
    try:
        beds = int(beds) if beds is not None else None
    except (ValueError, TypeError):
        beds = None

    # Area
    area = (
        listing.get("area") or
        listing.get("property_size") or
        listing.get("size")
    )
    try:
        area = float(area) if area is not None else None
    except (ValueError, TypeError):
        area = None

    # Sale type
    lt = str(listing.get("listing_type", "") or listing.get("sale_type", "")).lower()
    is_resale_listing = (
        listing.get("is_resale") or
        "resale" in lt or
        "secondary" in lt
    )

    # URL
    lid = listing.get("id") or listing.get("listing_id") or ""
    url = f"{BASE_URL}/en/listing/{lid}/" if lid else ""

    return {
        "price":     int(price),
        "bedrooms":  beds,
        "area":      area,
        "is_resale": bool(is_resale_listing),
        "url":       url,
    }


# ── Strategy 2: NEXT_DATA from search page ────────────────────
def _scrape_search_page(
    compound:  str,
    location:  str,
    ptype:     str,
    session=None,
) -> list[dict]:
    """Scrape compound search page __NEXT_DATA__ for listing array."""
    compound_slug = _to_compound_slug(compound)
    location_slug = _get_location_slug(location)
    url = f"{BASE_URL}/en/listing/type/sale/{location_slug}/comp-{compound_slug}/"
    print(f"   [AQ PAGE] {url}")

    html = tavily_fetch_one(url)
    if not html:
        return []

    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        return []

    try:
        data  = json.loads(m.group(1))
        props = data.get("props", {}).get("pageProps", {})
    except Exception:
        return []

    # Try known paths for Aqarmap listing arrays
    candidate_paths = [
        ["listings", "results"],
        ["listings"],
        ["data", "listings"],
        ["data", "results"],
        ["results"],
        ["searchResult", "results"],
        ["listingData", "listings"],
    ]
    for path in candidate_paths:
        listings = _get_nested(props, path)
        if isinstance(listings, list) and len(listings) > 0:
            print(f"   [AQ PAGE] Found {len(listings)} listings at pageProps.{'.'.join(path)}")
            return listings

    # Deep scan
    def _find_list(obj, depth=0):
        if depth > 6:
            return None
        if isinstance(obj, list) and len(obj) >= 2:
            if isinstance(obj[0], dict) and "price" in obj[0]:
                return obj
        if isinstance(obj, dict):
            for v in obj.values():
                r = _find_list(v, depth + 1)
                if r:
                    return r
        return None

    found = _find_list(props)
    if found:
        print(f"   [AQ PAGE] Found {len(found)} listings via deep search")
        return found

    print("   [AQ PAGE] No listings in NEXT_DATA")
    return []


# ── Strategy 3: Individual listing pages ─────────────────────
def _find_listing_urls(html: str, compound: str) -> list[str]:
    """Extract /en/listing/{id}/ URLs from a search page."""
    urls = re.findall(r'href="(/en/listing/\d+/[^"]*)"', html)
    full = [f"{BASE_URL}{u}" for u in urls]
    compound_slug = _to_compound_slug(compound)
    # Prefer URLs mentioning the compound
    preferred = [u for u in full if compound_slug in u.lower()]
    others    = [u for u in full if u not in preferred]
    return list(dict.fromkeys(preferred + others))[:12]


def _extract_price_from_listing_page(html: str) -> dict | None:
    """Extract price + metadata from a single Aqarmap listing page."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        return None
    try:
        data  = json.loads(m.group(1))
        props = data.get("props", {}).get("pageProps", {})
    except Exception:
        return None

    listing_paths = [
        ["listing"],
        ["data", "listing"],
        ["propertyData"],
        ["listingDetails"],
    ]
    for path in listing_paths:
        listing = _get_nested(props, path)
        if isinstance(listing, dict):
            return _parse_aq_listing(listing)

    return None


# ── Public API ────────────────────────────────────────────────
def scrape(
    compound:  str,
    area:      float,
    bedrooms:  int,
    ptype:     str,
    sale_type: str,
    location:  str = "cairo",
) -> "ScraperResult":
    """
    Scrape Aqarmap Egypt for comparable listings.

    Args:
        compound:  compound name (e.g. "Mivida")
        area:      target area sqm
        bedrooms:  number of bedrooms
        ptype:     "Apartment" | "Villa" | "Chalet"
        sale_type: "Resale" | "Developer Sale"
        location:  city/area string (e.g. "New Cairo")

    Returns:
        ScraperResult
    """
    try:
        from scraper_nawy import ScraperResult as SR
    except ImportError:
        SR = ScraperResult

    compound_slug = _to_compound_slug(compound)
    is_resale     = "resale" in sale_type.lower()
    floor  = area * 18_000
    ceil   = area * (PPM_CEILING_LARGE if area >= AREA_LARGE_THRESHOLD else PPM_CEILING_STANDARD)
    lo_a, hi_a = area * (1 - AREA_TOLERANCE), area * (1 + AREA_TOLERANCE)

    prices, urls = [], []

    def _accept(parsed):
        if not parsed:
            return False
        p = parsed["price"]
        if not (floor <= p <= ceil):
            return False
        if parsed["bedrooms"] is not None and parsed["bedrooms"] != bedrooms:
            return False
        if parsed["area"] is not None and not (lo_a <= parsed["area"] <= hi_a):
            return False
        if is_resale and not parsed["is_resale"]:
            return False
        if not is_resale and parsed["is_resale"]:
            return False
        ppm = p / area
        ceiling_ppm = PPM_CEILING_LARGE if area >= AREA_LARGE_THRESHOLD else PPM_CEILING_STANDARD
        return 15_000 <= ppm <= ceiling_ppm

    print(f"\n[AQ] Compound={compound_slug}, type={ptype}, sale={sale_type}")

    # ── Strategy 1: API ─────────────────────────────────────────
    api_listings = _api_search(compound_slug, ptype, sale_type, bedrooms, area)
    for raw in api_listings:
        parsed = _parse_aq_listing(raw)
        if _accept(parsed):
            prices.append(parsed["price"])
            if parsed["url"]:
                urls.append(parsed["url"])
            print(f"   [AQ ✓ API] {parsed['price']:,.0f} EGP ({parsed['price']/area:,.0f}/sqm)")

    # ── Strategy 2: Search page NEXT_DATA ───────────────────────
    if len(prices) < 3:
        page_listings = _scrape_search_page(compound, location, ptype)
        for raw in page_listings:
            parsed = _parse_aq_listing(raw)
            if _accept(parsed) and parsed["price"] not in prices:
                prices.append(parsed["price"])
                if parsed["url"]:
                    urls.append(parsed["url"])
                print(f"   [AQ ✓ PAGE] {parsed['price']:,.0f} EGP ({parsed['price']/area:,.0f}/sqm)")

    # ── Strategy 3: Individual listing pages (batch via Tavily) ──
    if len(prices) < 3:
        search_page_url = f"{BASE_URL}/en/listing/type/sale/{_get_location_slug(location)}/comp-{compound_slug}/"
        page_html = tavily_fetch_one(search_page_url)
        if page_html:
            listing_urls = [u for u in _find_listing_urls(page_html, compound)[:8] if u not in urls]
            print(f"   [AQ] Strategy 3: batch-fetching {len(listing_urls)} pages via Tavily")
            batch = tavily_fetch(listing_urls)
            for item in batch:
                lhtml = item.get("raw_content", "")
                if not lhtml:
                    continue
                parsed = _extract_price_from_listing_page(lhtml)
                if _accept(parsed) and parsed["price"] not in prices:
                    prices.append(parsed["price"])
                    urls.append(item["url"])
                    print(f"   [AQ ✓ DETAIL] {parsed['price']:,.0f} EGP ({parsed['price']/area:,.0f}/sqm)")

    if not prices:
        return SR(source="aqarmap", error="no matching listings")

    # ── Outlier removal + cluster split ────────────────────────
    clean, lc = _remove_outliers(prices)
    if clean:
        ppm_avg = sum(clean) / len(clean) / area
        if ppm_avg > PPM_SANITY_FLAG:
            lc = True
    if clean:
        clean = _cluster_by_sale_type(clean, sale_type)

    if not clean:
        return SR(source="aqarmap", error="all prices filtered")

    med = statistics.median(clean)
    return SR(
        source   = "aqarmap",
        prices   = clean,
        median   = med,
        ppm      = med / area,
        n        = len(clean),
        low_conf = lc,
        urls     = urls[:5],
    )


if __name__ == "__main__":
    result = scrape("Mivida", 160, 3, "Apartment", "Resale", "New Cairo")
    print(f"\nResult: {result.n} prices, median={result.median:,.0f}, ppm={result.ppm:,.0f}")
