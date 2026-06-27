"""
SEMSAI — Nawy.com Scraper Module  (v4.2 feature-complete)
==========================================================
Extracted from semsai_agent_v4.2.py and wrapped as a reusable module.

Every feature from v4.2 is preserved exactly:
  ✅ NEXT_DATA targeted paths
  ✅ Unit-object detection (dict with price + area keys)
  ✅ Full JSON tree fallback
  ✅ JSON-LD schema.org extraction
  ✅ Comma-formatted large numbers
  ✅ EGP-labelled numbers
  ✅ Million shorthand (X million EGP)
  ✅ Danger keyword filter
  ✅ Installment recovery
  ✅ Dedup shared prices >50%
  ✅ Compound ID allowed-set (slug-filtered)
  ✅ URL slug type conflict pre-filter
  ✅ Bedroom strict match
  ✅ Area tolerance ±20%
  ✅ Property type keyword check (positive + negative rivals)
  ✅ Noise section strip
  ✅ Compound text variants (Arabic)
  ✅ Z-score outlier removal (2.5 normal / 1.8 fallback)
  ✅ IQR secondary filter (fallback mode)
  ✅ n<=2 LOW_CONFIDENCE
  ✅ CV > 0.5 LOW_CONFIDENCE
  ✅ PPM sanity cap >180k
  ✅ Cluster split (resale vs developer sale bimodal)
  ✅ Compound-inclusive fallback query
  ✅ Sale type validation (JSON + text)
  ✅ Median (not mean)
"""

import re
import json
import time
import statistics
import requests
import pandas as pd
from collections import Counter
from dataclasses import dataclass, field
from bs4 import BeautifulSoup
from urllib.parse import urlparse, unquote
from tavily_client import tavily_search as _tavily_search, tavily_fetch

# ──────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────

# API key is set in tavily_client.py — change it there once for all scrapers
PPM_CEILING_STANDARD  = 220_000
PPM_CEILING_LARGE     = 250_000
PPM_SANITY_FLAG       = 180_000
AREA_LARGE_THRESHOLD  = 400
AREA_TOLERANCE_RATIO  = 0.20
STRICT_BEDROOM_MATCH  = True
CLUSTER_GAP_THRESHOLD = 40.0

PRICE_KEYS = {
    "price", "totalprice", "unitprice", "startingprice", "minprice", "maxprice",
    "listprice", "saleprice", "offerprice", "askingprice", "priceegp", "priceinegp",
    "amount", "value", "min_price", "max_price", "starting_price", "total_price",
    "unit_price", "sellingprice", "selling_price",
}

DANGER_KEYWORDS = ["مقدم", "قسط", "installment", "downpayment", "monthly", "per month"]

SLUG_TYPE_CONFLICTS = {
    "apartment": [
        "penthouse", "townhouse", "twinhouse", "twin-house",
        "serviced-apartment", "studio-for-sale",
    ],
    "villa": [
        "apartment-for-sale", "penthouse-for-sale",
        "studio-for-sale", "duplex-for-sale",
    ],
    "chalet": [
        "apartment-for-sale", "studio-for-sale",
    ],
}

NAWY_UNIT_PRICE_PATHS = [
    ["props", "pageProps", "propertyDetails", "price"],
    ["props", "pageProps", "propertyDetails", "totalPrice"],
    ["props", "pageProps", "propertyDetails", "unitPrice"],
    ["props", "pageProps", "unit", "price"],
    ["props", "pageProps", "unit", "totalPrice"],
    ["props", "pageProps", "property", "price"],
    ["props", "pageProps", "property", "totalPrice"],
    ["props", "pageProps", "listing", "price"],
    ["props", "pageProps", "listing", "totalPrice"],
    ["props", "pageProps", "data", "price"],
    ["props", "pageProps", "data", "totalPrice"],
    ["props", "pageProps", "data", "unit", "price"],
]

_SLUG_NOISE_TOKENS = {
    "the", "el", "al", "il", "new", "park", "view",
    "east", "west", "north", "south", "city", "gardens",
}

_DEVELOPER_SALE_KEYWORDS = [
    "payment plan", "down payment", "installment", "off-plan",
    "under construction", "delivery date", "handover", "new launch",
    "book now", "reserve now", "limited units", "developer sale",
    "1st installment", "first installment", "launch price",
    "خطة سداد", "مقدم", "قسط", "تسليم", "حجز", "بيع مطور",
    "وحدات محدودة", "إطلاق جديد", "حجز الآن",
]
_RESALE_KEYWORDS = [
    "resale", "re-sale", "re sale", "owner resale",
    "ready to move", "immediate delivery", "immediate possession",
    "اعادة بيع", "إعادة بيع", "مالك مباشر", "تسليم فوري",
    "جاهز للتسليم", "ريسيل",
]

FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ──────────────────────────────────────────────────────────────
# RESULT TYPE
# ──────────────────────────────────────────────────────────────

@dataclass
class ScraperResult:
    source:   str
    prices:   list = field(default_factory=list)
    median:   float = 0.0
    ppm:      float = 0.0
    n:        int   = 0
    low_conf: bool  = False
    fallback: bool  = False
    urls:     list  = field(default_factory=list)
    error:    str   = None

    def __bool__(self):
        return len(self.prices) > 0


# ──────────────────────────────────────────────────────────────
# SALE TYPE DETECTION
# ──────────────────────────────────────────────────────────────

def detect_sale_type_from_json(raw_html):
    nd_match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', raw_html, re.DOTALL
    )
    if not nd_match:
        return None
    raw = nd_match.group(1).lower()
    m = re.search(r'"isresale"\s*:\s*(true|false)', raw)
    if m:
        return "resale" if m.group(1) == "true" else "developer"
    for key in ["saletype", "listingtype", "unitstatus"]:
        m = re.search(rf'"{key}"\s*:\s*"([^"]+)"', raw)
        if m:
            val = m.group(1).lower()
            if any(x in val for x in ["resale", "secondary", "used"]):
                return "resale"
            if any(x in val for x in ["primary", "new", "developer", "off-plan"]):
                return "developer"
    return None


def detect_sale_type_from_text(text_lower):
    dev_count = sum(1 for kw in _DEVELOPER_SALE_KEYWORDS if kw in text_lower)
    res_count = sum(1 for kw in _RESALE_KEYWORDS if kw in text_lower)
    if res_count > 0 and dev_count == 0:
        return "resale"
    if dev_count >= 2 and res_count == 0:
        return "developer"
    if res_count > dev_count:
        return "resale"
    if dev_count > res_count:
        return "developer"
    return None


def validate_sale_type(raw_html, text_lower, target_sale_type, debug=False):
    target   = "resale" if "resale" in target_sale_type.lower() else "developer"
    detected = detect_sale_type_from_json(raw_html)
    if detected is None:
        detected = detect_sale_type_from_text(text_lower)
    if detected is None:
        return True
    if detected != target:
        if debug:
            print(f"      [REJECT] sale type: listing={detected}, target={target}")
        return False
    return True


# ──────────────────────────────────────────────────────────────
# URL HELPERS
# ──────────────────────────────────────────────────────────────

def nawy_url_type(url):
    path = unquote(urlparse(url).path.lower())
    if any(p in path for p in ["/blog/", "/news/", "/articles/", "/insights/", "/guide/"]):
        return "blog"
    if "/search/" in path:
        return "search"
    if "/compound/undefined/" in path:
        return "rejected"
    if "/compound/" in path and "/property/" in path:
        return "property"
    return "rejected"


def get_price_bounds(area):
    ceiling = PPM_CEILING_LARGE if area >= AREA_LARGE_THRESHOLD else PPM_CEILING_STANDARD
    return area * 18_000, area * ceiling


def extract_bedrooms_from_text(text_lower):
    m = re.search(r'with\s*(\d{1,2})\s*bedrooms?', text_lower)
    return int(m.group(1)) if m else None


def extract_area_from_text(text_lower):
    m = re.search(r'(\d{2,4})\s*(?:m2|m2|sqm)', text_lower)
    return float(m.group(1)) if m else None


def extract_compound_id(url):
    path = unquote(urlparse(url).path.lower())
    if "/compound/" in path:
        seg   = path.split("/compound/", 1)[1].split("/")[0]
        parts = seg.split("-", 1)
        if parts[0].isdigit():
            return int(parts[0])
    return None


def url_has_type_conflict(url, target_type):
    path = unquote(urlparse(url).path.lower())
    for slug in SLUG_TYPE_CONFLICTS.get(target_type.lower(), []):
        if slug in path:
            return True, slug
    return False, ""


# ──────────────────────────────────────────────────────────────
# COMPOUND ID RESOLUTION
# ──────────────────────────────────────────────────────────────

def resolve_compound_ids(compound_name):
    """
    Collect all Nawy compound IDs that belong to the target brand.
    Searches with max_results=10 (was 5 — too few for brands with many sub-compounds).
    Also runs a second search specifically for the main compound URL to catch
    cases where sub-brands appear before the main one in results.
    """
    query = f'site:nawy.com/compound "{compound_name}" property'
    data  = _run_search(query, max_results=10)

    # Also search for the compound page directly (catches main compound ID)
    data2 = _run_search(f'site:nawy.com/compound "{compound_name}"', max_results=5)
    all_items = data.get("organic", []) + data2.get("organic", [])

    name_tokens = set(re.split(r'[\s\-_]+', compound_name.lower()))
    meaningful  = name_tokens - _SLUG_NOISE_TOKENS
    if not meaningful:
        meaningful = name_tokens

    allowed_ids = set()
    for item in all_items:
        url = item.get("link", "")
        cid = extract_compound_id(url)
        if cid is None:
            continue
        path = unquote(urlparse(url).path.lower())
        if "/compound/" in path:
            slug = path.split("/compound/", 1)[1].split("/")[0]
            if any(token in slug for token in meaningful):
                allowed_ids.add(cid)

    if allowed_ids:
        print(f"   [IDs] '{compound_name}' → {sorted(allowed_ids)}")
    else:
        print(f"   [IDs] '{compound_name}' → none, text fallback")
    return allowed_ids


# ──────────────────────────────────────────────────────────────
# COMPOUND VARIANTS (Arabic)
# ──────────────────────────────────────────────────────────────

def compound_variants(name):
    n = name.lower().strip()
    variants = {n, n.replace(" ", ""), n.replace(" ", "-"), n.replace(" ", "_")}
    arabic_map = {
        "il ": "ايل ", "al ": "ال", "el ": "ال", "new ": "نيو ",
        "capital": "كابيتال", "mondo": "موندو", "palm": "بالم",
        "lake": "ليك", "garden": "جاردن", "park": "بارك", "view": "فيو",
    }
    ar = n
    for en, ar_val in arabic_map.items():
        ar = ar.replace(en, ar_val)
    if ar != n:
        variants.add(ar)
    return list(variants)


# ──────────────────────────────────────────────────────────────
# VALIDATOR
# ──────────────────────────────────────────────────────────────

def validate_nawy_listing(clean_text, url, target_features, raw_html="", debug=False):
    def reject(reason):
        if debug:
            print(f"      [REJECT] {reason}")
        return False

    if nawy_url_type(url) != "property":
        return reject(f"url type = {nawy_url_type(url)}")

    path = unquote(urlparse(url).path.lower())

    target_type = target_features.get("property_type", "apartment")
    conflict, slug = url_has_type_conflict(url, target_type)
    if conflict:
        return reject(f"slug conflict: '{slug}'")

    allowed_ids = target_features.get("compound_ids")
    if allowed_ids:
        url_id = extract_compound_id(url)
        if url_id is not None and url_id not in allowed_ids:
            return reject(f"ID {url_id} not in {sorted(allowed_ids)}")

    for section in ["Top Searches", "Popular locations", "Related Compounds", "Explore similar"]:
        clean_text = clean_text.split(section)[0]
    text_lower = clean_text.lower()

    target_sale_type = target_features.get("sale_type", "")
    if target_sale_type and raw_html:
        if not validate_sale_type(raw_html, text_lower, target_sale_type, debug=debug):
            return False

    target_beds = target_features.get("bedrooms")
    if STRICT_BEDROOM_MATCH and target_beds is not None:
        listing_beds = extract_bedrooms_from_text(text_lower)
        if listing_beds is not None and listing_beds != target_beds:
            return reject(f"bedrooms mismatch: listing={listing_beds}, target={target_beds}")

    target_area = target_features.get("area")
    if target_area:
        listing_area = extract_area_from_text(text_lower)
        if listing_area is not None:
            lo = target_area * (1 - AREA_TOLERANCE_RATIO)
            hi = target_area * (1 + AREA_TOLERANCE_RATIO)
            if not (lo <= listing_area <= hi):
                return reject(f"area mismatch: {listing_area:.0f} not in [{lo:.0f}-{hi:.0f}]")

    target_compound = target_features.get("compound", "").lower().strip()
    if target_compound and not allowed_ids:
        cvariants = compound_variants(target_compound)
        compound_slug = ""
        if "/compound/" in path:
            after = path.split("/compound/", 1)[1].split("/")[0]
            if after == "undefined":
                return reject("compound/undefined")
            parts = after.split("-", 1)
            compound_slug = parts[1] if len(parts) > 1 and parts[0].isdigit() else after
        slug_tokens   = set(re.split(r'[-_\s]+', compound_slug))
        target_tokens = set(re.split(r'[-_\s]+', target_compound))
        slug_match    = target_tokens.issubset(slug_tokens)
        text_match    = any(
            v.replace(" ", "-") in text_lower.replace(" ", "-") or v in text_lower
            for v in cvariants if len(v) >= 6
        )
        if not slug_match and not text_match:
            return reject(f"compound '{target_compound}' not matched")

    TYPE_KEYWORDS = {
        "apartment": {
            "positive": ["apartment", "flat", "studio", "duplex", "penthouse", "\u0634\u0642\u0629", "\u0634\u0642\u0647"],
            "negative": ["villa", "\u0641\u064a\u0644\u0627", "chalet", "\u0634\u0627\u0644\u064a\u0647"],
        },
        "villa": {
            "positive": ["villa", "standalone", "twin house", "townhouse", "ivilla", "\u0641\u064a\u0644\u0627"],
            "negative": ["apartment", "\u0634\u0642\u0629"],
        },
        "chalet": {
            "positive": ["chalet", "cabin", "beach unit", "sahel unit", "\u0634\u0627\u0644\u064a\u0647", "\u0643\u0627\u0628\u064a\u0646\u0629"],
            "negative": ["apartment", "\u0634\u0642\u0629"],
        },
    }
    entry   = TYPE_KEYWORDS.get(target_type.lower(), {"positive": [target_type], "negative": []})
    text_ns = re.sub(r'\s+', '', text_lower)
    if not any((w in text_lower or w.replace(" ", "") in text_ns) for w in entry["positive"]):
        return reject(f"no '{target_type}' keyword")
    body_lower = text_lower[1000:-1000] if len(text_lower) > 3000 else text_lower
    for neg in entry["negative"]:
        count     = body_lower.count(neg)
        threshold = 8 if neg in {"apartment", "\u0634\u0642\u0629"} else 2
        if count > threshold:
            return reject(f"rival '{neg}' x{count} (threshold {threshold})")

    if debug:
        print(f"      [PASS]")
    return True


# ──────────────────────────────────────────────────────────────
# PRICE EXTRACTION
# ──────────────────────────────────────────────────────────────

def _get_nested(obj, path):
    cur = obj
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _extract_prices_from_json(obj, price_keys, depth=0):
    hits = []
    if depth > 20:
        return hits
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in price_keys and isinstance(v, (int, float)) and v > 0:
                hits.append(int(v))
            else:
                hits.extend(_extract_prices_from_json(v, price_keys, depth + 1))
    elif isinstance(obj, list):
        for item in obj:
            hits.extend(_extract_prices_from_json(item, price_keys, depth + 1))
    return hits


def _extract_next_data_price(nd_json, logical_floor, logical_ceiling):
    for path in NAWY_UNIT_PRICE_PATHS:
        val = _get_nested(nd_json, path)
        if isinstance(val, (int, float)) and logical_floor <= val <= logical_ceiling:
            print(f"      [ND:targeted] {'.'.join(path[-2:])} = {int(val):,.0f}")
            return [int(val)]

    def find_unit_objects(obj, depth=0):
        results = []
        if depth > 8:
            return results
        if isinstance(obj, dict):
            kl = {k.lower() for k in obj.keys()}
            if any(p in kl for p in ["price", "totalprice", "unitprice"]) and \
               any(a in kl for a in ["area", "space", "size", "sqm"]):
                for k, v in obj.items():
                    if k.lower() in {"price", "totalprice", "unitprice"} and \
                       isinstance(v, (int, float)) and v > 0:
                        results.append(int(v))
            for v in obj.values():
                results.extend(find_unit_objects(v, depth + 1))
        elif isinstance(obj, list):
            for item in obj:
                results.extend(find_unit_objects(item, depth + 1))
        return results

    unit_prices = [p for p in find_unit_objects(nd_json) if logical_floor <= p <= logical_ceiling]
    if unit_prices:
        print(f"      [ND:unit_obj] {unit_prices[:3]}")
        return unit_prices

    all_keyed = _extract_prices_from_json(nd_json, PRICE_KEYS)
    in_range  = [p for p in all_keyed if logical_floor <= p <= logical_ceiling]
    if in_range:
        print(f"      [ND:full_scan] {in_range[:5]}")
    return in_range


def deduplicate_shared_prices(prices):
    if len(prices) < 3:
        return prices
    counts   = Counter(prices)
    n        = len(prices)
    filtered = [p for p in prices if counts[p] / n <= 0.50]
    if not filtered:
        return prices
    removed = list({p for p in prices if counts[p] / n > 0.50})
    if removed:
        print(f"      [DEDUP] removed shared: {[f'{p:,.0f}' for p in removed[:3]]}")
    return filtered


def recover_price_from_installments(clean_text, logical_floor, logical_ceiling):
    text = clean_text.lower().replace(",", "")
    dp_pats = [
        r'(?:down[\s_-]?payment|downpayment|\u0645\u0642\u062f\u0645)[^\d]{0,25}(\d{5,10})',
        r'(\d{5,10})[^\d]{0,15}(?:down[\s_-]?payment|downpayment|\u0645\u0642\u062f\u0645)',
    ]
    downpayments = [int(m) for pat in dp_pats for m in re.findall(pat, text) if m]
    mo_pats = [
        r'(?:monthly|per[\s_]month|\u0634\u0647\u0631\u064a)[^\d]{0,25}(\d{4,9})',
        r'(\d{4,9})[^\d]{0,15}(?:monthly|per[\s_]month|/month|\u0634\u0647\u0631\u064a\u0627)',
    ]
    monthlies     = [int(m) for pat in mo_pats for m in re.findall(pat, text) if m]
    period_months = None
    yr = re.search(r'(\d{1,2})[\s_-]*(?:year|years|\u0633\u0646\u0629|\u0633\u0646\u0648\u0627\u062a)', text)
    mo = re.search(r'(\d{2,3})[\s_-]*(?:month|months|\u0634\u0647\u0631)', text)
    if yr:   period_months = int(yr.group(1)) * 12
    elif mo: period_months = int(mo.group(1))
    if not (downpayments and monthlies and period_months):
        return None
    dp      = max(downpayments)
    monthly = sorted(monthlies)[len(monthlies) // 2]
    total   = dp + monthly * period_months
    return total if logical_floor <= total <= logical_ceiling else None


def extract_nawy_price(raw_html, clean_text, target_area, logical_floor, logical_ceiling, url=""):
    found = []

    nd_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', raw_html, re.DOTALL)
    if nd_match:
        try:
            nd_json = json.loads(nd_match.group(1))
            found  += _extract_next_data_price(nd_json, logical_floor, logical_ceiling)
        except Exception as e:
            print(f"      [ND parse error] {e}")

    for script in BeautifulSoup(raw_html, "html.parser").find_all("script", type="application/ld+json"):
        try:
            ld = json.loads(script.string or "")
            found += [p for p in _extract_prices_from_json(ld, PRICE_KEYS)
                      if logical_floor <= p <= logical_ceiling]
        except Exception:
            pass

    for m in re.findall(r'(\d{1,3}(?:,\d{3}){2,})|(\d{7,10})', clean_text):
        try:
            found.append(int((m[0] or m[1]).replace(",", "")))
        except ValueError:
            pass

    for m in re.findall(r'(?:egp|جنيه)\s*(\d[\d,]+)', clean_text.lower()):
        try:
            found.append(int(m.replace(",", "")))
        except ValueError:
            pass

    for m in re.findall(r'(\d+\.?\d*)\s*(?:million|m)\s*(?:egp|le|pounds?)?', clean_text.lower()):
        try:
            found.append(int(float(m) * 1_000_000))
        except ValueError:
            pass

    in_range = sorted(set(p for p in found if logical_floor <= p <= logical_ceiling), reverse=True)
    text_nc  = clean_text.replace(",", "")
    safe     = []
    for price in in_range:
        pos     = text_nc.find(str(price))
        context = text_nc[max(0, pos - 60): pos + 60].lower()
        danger  = next((w for w in DANGER_KEYWORDS if w in context), None)
        if danger:
            print(f"      [SKIP danger '{danger}'] {price:,.0f}")
            continue
        safe.append(price)

    if not safe:
        recovered = recover_price_from_installments(clean_text, logical_floor, logical_ceiling)
        if recovered:
            safe = [recovered]
            print(f"      [INSTALLMENT] recovered {recovered:,.0f}")

    if not safe:
        print(f"      [NO_PRICE] floor={logical_floor:,.0f} / ceil={logical_ceiling:,.0f}")
        return None

    safe = deduplicate_shared_prices(safe)
    best = sorted(safe)[len(safe) // 2]
    ppm  = best / target_area
    ceiling_ppm = PPM_CEILING_LARGE if target_area >= AREA_LARGE_THRESHOLD else PPM_CEILING_STANDARD
    if not (15_000 <= ppm <= ceiling_ppm):
        print(f"      [SKIP ppm={ppm:,.0f}] {best:,.0f}")
        return None

    return best


# ──────────────────────────────────────────────────────────────
# OUTLIER REMOVAL + CONFIDENCE
# ──────────────────────────────────────────────────────────────

def remove_outliers(prices, area, fallback_mode=False):
    if len(prices) < 3:
        return prices, len(prices) <= 2

    threshold = 1.8 if fallback_mode else 2.5
    s   = pd.Series(prices)
    med = s.median()
    mad = (s - med).abs().median()
    clean = s[((0.6745 * (s - med)) / mad).abs() <= threshold].tolist() if mad > 0 else prices

    if fallback_mode and len(clean) >= 4:
        q1  = statistics.quantiles(clean, n=4)[0]
        q3  = statistics.quantiles(clean, n=4)[2]
        iqr = q3 - q1
        iqr_clean = [p for p in clean if (q1 - 1.5 * iqr) <= p <= (q3 + 1.5 * iqr)]
        if iqr_clean:
            removed = set(clean) - set(iqr_clean)
            if removed:
                print(f"      [IQR] removed: {[f'{p:,.0f}' for p in removed]}")
            clean = iqr_clean

    clean = clean if clean else prices
    low_confidence = len(clean) <= 2 or len(set(prices)) == 1

    if len(clean) >= 3:
        cv = statistics.stdev(clean) / statistics.mean(clean)
        if cv > 0.5:
            print(f"      [HIGH VARIANCE] CV={cv:.2f} — LOW_CONFIDENCE")
            low_confidence = True

    if clean:
        avg_ppm = (sum(clean) / len(clean)) / area
        if avg_ppm > PPM_SANITY_FLAG:
            print(f"      [PPM SANITY] {avg_ppm:,.0f}/sqm > {PPM_SANITY_FLAG:,} — LOW_CONFIDENCE")
            low_confidence = True

    if low_confidence:
        print(f"      [LOW_CONFIDENCE] flagged")

    return clean, low_confidence


# ──────────────────────────────────────────────────────────────
# CLUSTER SPLIT
# ──────────────────────────────────────────────────────────────

def select_cluster_by_sale_type(prices, sale_type, gap_threshold=CLUSTER_GAP_THRESHOLD):
    if len(prices) < 4:
        return prices
    sorted_p  = sorted(prices)
    max_gap_pct, split_idx = 0.0, None
    for i in range(1, len(sorted_p)):
        g = (sorted_p[i] - sorted_p[i - 1]) / sorted_p[i - 1] * 100
        if g > max_gap_pct:
            max_gap_pct, split_idx = g, i
    if max_gap_pct < gap_threshold or split_idx is None:
        return prices
    lower, upper = sorted_p[:split_idx], sorted_p[split_idx:]
    if len(lower) < 2 or len(upper) < 2:
        return prices
    is_resale = "resale" in sale_type.lower()
    chosen    = upper if is_resale else lower
    print(
        f"      [CLUSTER SPLIT] gap={max_gap_pct:.0f}%\n"
        f"        lower={[f'{p/1e6:.1f}M' for p in lower]} "
        f"upper={[f'{p/1e6:.1f}M' for p in upper]}\n"
        f"        -> using {'upper (resale)' if is_resale else 'lower (developer sale)'}"
    )
    return chosen


# ──────────────────────────────────────────────────────────────
# SEARCH + FETCH
# ──────────────────────────────────────────────────────────────

def _run_search(query, max_results=10):
    """Search via Tavily — returns {"organic": [{"link": url}]}"""
    results = _tavily_search(query, max_results=max_results)
    return {"organic": [{"link": r["url"]} for r in results]}


def _fetch_page(url):
    """Fetch a page via Tavily /extract (headless browser — bypasses Cloudflare)."""
    from tavily_client import tavily_fetch_one
    html = tavily_fetch_one(url)
    if not html:
        print(f"      [FETCH FAILED] {url[-70:]}")
    return html


# ──────────────────────────────────────────────────────────────
# PUBLIC API
# ──────────────────────────────────────────────────────────────

def scrape(compound, area, bedrooms, ptype, sale_type, location=""):
    """
    Scrape nawy.com for comparable listings.
    Returns ScraperResult.
    """
    sale_hint = "resale" if "resale" in sale_type.lower() else "for sale"
    query     = f'site:nawy.com/compound "{compound}" {ptype} {sale_hint}'
    print(f"\n[NAWY] {query}")

    data          = _run_search(query, max_results=50)
    candidate_urls = []
    fallback_used  = False

    for item in data.get("organic", []):
        url = item.get("link", "")
        if nawy_url_type(url) != "property":
            continue
        conflict, slug = url_has_type_conflict(url, ptype)
        if conflict:
            print(f"   [SKIP:slug '{slug}'] {url[:70]}")
            continue
        candidate_urls.append(url)

    if not candidate_urls:
        fb_query = f'site:nawy.com "{compound}" {ptype} {sale_hint}'
        print(f"   Fallback: {fb_query}")
        data2 = _run_search(fb_query, max_results=50)
        for item in data2.get("organic", []):
            url = item.get("link", "")
            if nawy_url_type(url) != "property":
                continue
            conflict, _ = url_has_type_conflict(url, ptype)
            if conflict:
                continue
            candidate_urls.append(url)
        fallback_used = bool(candidate_urls)

    # Batch-fetch all candidate URLs via Tavily (faster than one-by-one)
    print(f"   [NAWY] Fetching {len(candidate_urls)} URLs via Tavily...")
    fetched_pages = tavily_fetch(candidate_urls[:15])  # cap at 15
    fetched = [{"url": r["url"], "html": r["raw_content"]}
               for r in fetched_pages if r.get("raw_content")]

    compound_ids = set()
    if not fallback_used:
        compound_ids = resolve_compound_ids(compound)

    val_features = {
        "compound":      "" if fallback_used else compound,
        "compound_ids":  compound_ids,
        "property_type": ptype,
        "area":          area,
        "bedrooms":      bedrooms,
        "sale_type":     sale_type,
    }

    logical_floor, logical_ceiling = get_price_bounds(area)
    raw_prices, urls, seen = [], [], set()

    for item in fetched:
        url = item["url"]
        if url in seen:
            continue
        seen.add(url)
        soup       = BeautifulSoup(item["html"], "html.parser")
        clean_text = soup.get_text(separator=" ")
        print(f"  -> {url[:70]}")
        if not validate_nawy_listing(
            clean_text, url, val_features,
            raw_html=item["html"], debug=True
        ):
            continue
        price = extract_nawy_price(
            item["html"], clean_text, area,
            logical_floor, logical_ceiling, url=url
        )
        if price:
            raw_prices.append(price)
            urls.append(url)
            print(f"      OK {price:,.0f} EGP  ({price/area:,.0f}/sqm)")
        else:
            print(f"      X  No usable price")

    clean_prices, low_confidence = remove_outliers(
        raw_prices, area=area, fallback_mode=fallback_used
    )

    if clean_prices and not fallback_used:
        clean_prices = select_cluster_by_sale_type(clean_prices, sale_type)

    print(f"\n   Raw    : {[f'{p:,.0f}' for p in raw_prices]}")
    print(f"   Clean  : {[f'{p:,.0f}' for p in clean_prices]}")

    if not clean_prices:
        return ScraperResult(source="nawy", error="no prices", fallback=fallback_used)

    med = statistics.median(clean_prices)
    print(f"   Median : {med:,.0f} EGP  ({med/area:,.0f}/sqm)")

    return ScraperResult(
        source   = "nawy",
        prices   = clean_prices,
        median   = med,
        ppm      = med / area,
        n        = len(clean_prices),
        low_conf = low_confidence,
        fallback = fallback_used,
        urls     = urls[:5],
    )
