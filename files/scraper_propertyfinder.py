"""
SEMSAI — PropertyFinder Egypt Scraper Module
=============================================
Extracts comparable property prices from propertyfinder.eg.

HOW IT WORKS:
  1. Build a PropertyFinder search URL using known query parameters
  2. Fetch the search results page via Tavily /extract (real browser — bypasses Cloudflare)
  3. Extract listing array from __NEXT_DATA__ JSON
  4. Filter by bedrooms (exact) and area (±20%)
  5. Apply cluster split for resale vs developer sale
  6. Return median price

URL STRUCTURE:
  Search: /en/search?c=2&ob=nd&t={type}&l={location_id}&q={compound}
    c=2  → buy  |  ob=nd → newest  |  t=1 apartment  t=3 villa  t=16 chalet
"""

import re
import json
import time
import requests
import statistics
from dataclasses import dataclass, field
from urllib.parse import urlencode, urlparse, unquote
from tavily_client import tavily_search as _tavily_search, tavily_fetch, tavily_fetch_one

# ── Config ────────────────────────────────────────────────────
# API key is in tavily_client.py — change it there once
PPM_CEILING_STANDARD  = 220_000
PPM_CEILING_LARGE     = 250_000
PPM_SANITY_FLAG       = 180_000
AREA_LARGE_THRESHOLD  = 400
AREA_TOLERANCE        = 0.20
CLUSTER_GAP_THRESHOLD = 40.0

BASE_URL = "https://www.propertyfinder.eg"

PF_TYPE_CODES = {
    "apartment": 1,
    "villa":     3,
    "chalet":    16,
    "townhouse": 4,
    "duplex":    11,
}

LOCATION_IDS = {
    "new cairo":        6020,
    "new zayed":        6032,
    "sheikh zayed":     6032,
    "6th of october":   6028,
    "6th october":      6028,
    "north coast":      6027,
    "ain sokhna":       6029,
    "sokhna":           6029,
    "madinaty":         6020,
    "new capital":      6034,
    "heliopolis":       6006,
    "nasr city":        6007,
    "zamalek":          6003,
    "cairo":            6001,
}

# ── Result type (imported from scraper_nawy if available) ─────
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
    if clean:
        ppm_avg = (sum(clean) / len(clean)) / max(p for p in clean)
        avg_ppm_abs = sum(clean) / len(clean)
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
    print(f"   [PF CLUSTER] gap={max_gap:.0f}% → {'upper(resale)' if is_resale else 'lower(dev)'}")
    return chosen


def _get_location_id(location: str) -> int | None:
    loc = location.lower().strip()
    for key, val in LOCATION_IDS.items():
        if key in loc or loc in key:
            return val
    return None


def _build_search_url(compound: str, ptype: str, sale_type: str, location: str) -> str:
    """Build PropertyFinder search URL."""
    type_code  = PF_TYPE_CODES.get(ptype.lower(), 1)
    loc_id     = _get_location_id(location)
    is_resale  = "resale" in sale_type.lower()

    params = {
        "c":  2,           # buy
        "ob": "nd",        # newest first
        "t":  type_code,
        "q":  compound,
    }
    if loc_id:
        params["l"] = loc_id
    if is_resale:
        params["rp"] = "y"   # resale flag

    return f"{BASE_URL}/en/search?{urlencode(params)}"


def _fetch(url: str, session=None) -> str | None:
    """Fetch via Tavily /extract — real browser, bypasses Cloudflare."""
    return tavily_fetch_one(url)


# ── NEXT_DATA extraction ──────────────────────────────────────
def _extract_listings_from_page(html: str) -> list[dict]:
    """
    Extract listing array from PropertyFinder __NEXT_DATA__.

    PropertyFinder search results JSON structure:
      props.pageProps.searchResult.properties  → list of listing objects
      props.pageProps.listings                 → alternate path

    Each listing object:
      {
        "price":          25000000,
        "bedroom_count":  3,
        "area":           160,
        "property_type":  {"slug": "apartment"},
        "compound":       {"name": "Mivida", "slug": "mivida"},
        "listing_type":   "sale" | "resale",
        "location":       {"name": "New Cairo"},
      }
    """
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        # Fallback: try to find embedded JSON in script tags
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
        for sc in scripts:
            if '"properties"' in sc and '"price"' in sc:
                try:
                    data = json.loads(sc)
                    props = data.get("props", {}).get("pageProps", {})
                    for path in [["searchResult", "properties"], ["listings"]]:
                        listings = _get_nested(props, path)
                        if isinstance(listings, list) and listings:
                            return listings
                except Exception:
                    pass
        return []

    try:
        data  = json.loads(m.group(1))
        props = data.get("props", {}).get("pageProps", {})
    except Exception as e:
        print(f"   [PF] JSON parse error: {e}")
        return []

    # Try multiple possible paths for the listings array
    candidate_paths = [
        ["searchResult", "properties"],
        ["listings", "properties"],
        ["listings"],
        ["properties"],
        ["searchResults"],
        ["data", "listings"],
        ["data", "properties"],
    ]
    for path in candidate_paths:
        listings = _get_nested(props, path)
        if isinstance(listings, list) and len(listings) > 0:
            print(f"   [PF] Found {len(listings)} listings at pageProps.{'.'.join(path)}")
            return listings

    # Deep search for any list with price+bedroom keys
    def _find_listing_array(obj, depth=0):
        if depth > 6:
            return None
        if isinstance(obj, list) and len(obj) >= 2:
            if isinstance(obj[0], dict) and "price" in obj[0] and (
                "bedroom_count" in obj[0] or "bedrooms" in obj[0] or "area" in obj[0]
            ):
                return obj
        if isinstance(obj, dict):
            for v in obj.values():
                found = _find_listing_array(v, depth + 1)
                if found:
                    return found
        return None

    found = _find_listing_array(props)
    if found:
        print(f"   [PF] Found {len(found)} listings via deep search")
        return found

    print("   [PF] No listing array found in NEXT_DATA")
    return []


def _parse_listing(listing: dict) -> dict | None:
    """Normalise a PropertyFinder listing object into a standard dict."""
    # Price — may be int or string
    price = listing.get("price") or listing.get("price_value") or listing.get("asking_price")
    if isinstance(price, str):
        price = int(re.sub(r'[^\d]', '', price)) if re.search(r'\d', price) else None
    if not isinstance(price, (int, float)) or price <= 0:
        return None

    # Bedrooms
    beds = (
        listing.get("bedroom_count") or
        listing.get("bedrooms") or
        listing.get("beds") or
        listing.get("bedroom")
    )
    try:
        beds = int(beds) if beds is not None else None
    except (ValueError, TypeError):
        beds = None

    # Area
    area = (
        listing.get("area") or
        listing.get("size") or
        listing.get("property_size")
    )
    try:
        area = float(area) if area is not None else None
    except (ValueError, TypeError):
        area = None

    # Sale type
    lt = str(listing.get("listing_type", "") or listing.get("sale_type", "")).lower()
    is_resale = "resale" in lt or "secondary" in lt

    # URL
    slug = listing.get("slug") or listing.get("id") or listing.get("property_id") or ""
    url  = f"{BASE_URL}/en/property/{slug}" if slug else ""

    return {
        "price":     int(price),
        "bedrooms":  beds,
        "area":      area,
        "is_resale": is_resale,
        "url":       url,
    }


# ── Also try fetching individual property pages ───────────────
def _find_property_urls(html: str, compound: str, ptype: str) -> list[str]:
    """Extract direct property page URLs from a search results page."""
    compound_slug = compound.lower().replace(" ", "-").replace("_", "-")
    ptype_slug    = ptype.lower()
    urls = []
    # PF property URLs: /en/property/{id}/apartment-for-sale-in-{compound}.html
    pattern = rf'href="(/en/property/\d+/[^"]*{ptype_slug}[^"]*{compound_slug}[^"]*\.html)"'
    matches = re.findall(pattern, html, re.IGNORECASE)
    for m in matches:
        urls.append(f"{BASE_URL}{m}")
    # Also find any property hrefs
    all_props = re.findall(r'href="(/en/property/\d+/[^"]+\.html)"', html)
    for m in all_props:
        full = f"{BASE_URL}{m}"
        if full not in urls:
            urls.append(full)
    return list(dict.fromkeys(urls))[:15]  # deduplicate, max 15


def _extract_price_from_property_page(html: str, area: float, bedrooms: int) -> dict | None:
    """Extract price from a single PropertyFinder property detail page."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        return None
    try:
        data  = json.loads(m.group(1))
        props = data.get("props", {}).get("pageProps", {})
    except Exception:
        return None

    prop_paths = [
        ["property"],
        ["listing"],
        ["propertyDetails"],
        ["data", "property"],
    ]
    for path in prop_paths:
        prop = _get_nested(props, path)
        if not isinstance(prop, dict):
            continue

        price = prop.get("price") or prop.get("price_value")
        if isinstance(price, str):
            price = int(re.sub(r'[^\d]', '', price)) if re.search(r'\d', price) else None
        if not isinstance(price, (int, float)) or price <= 0:
            continue

        beds = prop.get("bedroom_count") or prop.get("bedrooms")
        prop_area = prop.get("area") or prop.get("size")
        lt = str(prop.get("listing_type", "") or prop.get("sale_type", "")).lower()
        is_resale = "resale" in lt or "secondary" in lt

        return {
            "price":     int(price),
            "bedrooms":  int(beds) if beds is not None else None,
            "area":      float(prop_area) if prop_area else None,
            "is_resale": is_resale,
        }
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
    Scrape PropertyFinder Egypt for comparable listings.

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
    from scraper_nawy import ScraperResult as SR   # reuse dataclass

    search_url = _build_search_url(compound, ptype, sale_type, location)
    print(f"\n[PF] Fetching via Tavily: {search_url}")

    html = _fetch(search_url)
    if not html:
        return SR(source="propertyfinder", error="fetch failed — check Tavily key")

    # ── Strategy 1: extract from search results NEXT_DATA ──────
    raw_listings = _extract_listings_from_page(html)
    is_resale_target = "resale" in sale_type.lower()
    floor = area * 18_000
    ceil  = area * (PPM_CEILING_LARGE if area >= AREA_LARGE_THRESHOLD else PPM_CEILING_STANDARD)

    prices, urls = [], []
    for listing in raw_listings:
        parsed = _parse_listing(listing)
        if not parsed:
            continue

        p = parsed["price"]
        if not (floor <= p <= ceil):
            continue

        # Bedroom filter (strict)
        if parsed["bedrooms"] is not None and parsed["bedrooms"] != bedrooms:
            continue

        # Area filter ±20%
        if parsed["area"] is not None:
            lo_a, hi_a = area * (1 - AREA_TOLERANCE), area * (1 + AREA_TOLERANCE)
            if not (lo_a <= parsed["area"] <= hi_a):
                continue

        # Sale type filter
        if is_resale_target and not parsed["is_resale"]:
            continue
        if not is_resale_target and parsed["is_resale"]:
            continue

        ppm = p / area
        if not (15_000 <= ppm <= (PPM_CEILING_LARGE if area >= AREA_LARGE_THRESHOLD else PPM_CEILING_STANDARD)):
            continue

        prices.append(p)
        if parsed["url"]:
            urls.append(parsed["url"])
        print(f"   [PF ✓] {p:,.0f} EGP ({ppm:,.0f}/sqm)")

    # ── Strategy 2: fetch individual property pages ─────────────
    if len(prices) < 3:
        prop_urls = _find_property_urls(html, compound, ptype)
        prop_urls = [u for u in prop_urls[:8] if u not in urls]
        print(f"   [PF] Strategy 2: batch-fetching {len(prop_urls)} pages via Tavily")
        batch_results = tavily_fetch(prop_urls)
        for fetched in batch_results:
            url       = fetched["url"]
            prop_html = fetched.get("raw_content", "")
            if not prop_html:
                continue
            parsed = _extract_price_from_property_page(prop_html, area, bedrooms)
            if not parsed:
                continue

            p = parsed["price"]
            if not (floor <= p <= ceil):
                continue
            if parsed["bedrooms"] is not None and parsed["bedrooms"] != bedrooms:
                continue
            if is_resale_target and not parsed["is_resale"]:
                continue
            if not is_resale_target and parsed["is_resale"]:
                continue

            ppm = p / area
            if not (15_000 <= ppm <= (PPM_CEILING_LARGE if area >= AREA_LARGE_THRESHOLD else PPM_CEILING_STANDARD)):
                continue

            prices.append(p)
            urls.append(url)
            print(f"   [PF ✓] {p:,.0f} EGP ({ppm:,.0f}/sqm) [detail page]")

    if not prices:
        return SR(source="propertyfinder", error="no matching listings", urls=[search_url])

    # ── Outlier removal + cluster split ────────────────────────
    import pandas as pd
    clean, lc = _remove_outliers(prices)
    if clean:
        ppm_avg = sum(clean) / len(clean) / area
        if ppm_avg > PPM_SANITY_FLAG:
            lc = True
    if clean:
        clean = _cluster_by_sale_type(clean, sale_type)

    if not clean:
        return SR(source="propertyfinder", error="all prices removed by filters")

    med = statistics.median(clean)
    return SR(
        source   = "propertyfinder",
        prices   = clean,
        median   = med,
        ppm      = med / area,
        n        = len(clean),
        low_conf = lc,
        urls     = urls[:5],
    )


if __name__ == "__main__":
    # Quick test
    result = scrape("Mivida", 160, 3, "Apartment", "Resale", "New Cairo")
    print(f"\nResult: {result.n} prices, median={result.median:,.0f}, ppm={result.ppm:,.0f}")
    print(f"Prices: {result.prices}")
