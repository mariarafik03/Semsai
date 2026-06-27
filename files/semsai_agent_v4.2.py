"""
SEMSAI AGENTIC LUXURY APPRAISER — v4.2
=======================================
v4.2 fixes the sale type mismatch bug properly.

Root cause of the mixing problem:
  Nawy pages do NOT reliably carry isResale/saleType JSON fields,
  and text detection can't distinguish the types either.
  So content-based detection returns None → listings pass → mixed prices.

  The real signal is PRICE LEVEL, not page content:
    Developer Sale prices are LOWER (primary market, pre-delivery)
    Resale prices are HIGHER (secondary market, delivered + premium)
  When both types appear together, the prices form TWO DISTINCT CLUSTERS
  with a large gap (>40%) between them.

Fix: select_cluster_by_sale_type()
  Finds the largest % gap between consecutive sorted prices.
  If gap > 40% → two clusters detected.
  Developer Sale → use lower cluster.
  Resale         → use upper cluster.
  - Resale queries no longer return Developer Sale listings
  - Developer Sale queries no longer return Resale listings

Two-layer detection:
  Layer 1: NEXT_DATA JSON (isResale / saleType / listingType fields)
  Layer 2: Page text keywords (Arabic + English)

If detected sale type conflicts with target → listing is rejected.
If sale type cannot be determined → listing passes (safe default).
"""

import pandas as pd
import re
import json
import time
import statistics
import numpy as np
import requests
from collections import Counter
from catboost import CatBoostRegressor, Pool
from langgraph.graph import StateGraph
from typing import TypedDict
from bs4 import BeautifulSoup
from urllib.parse import urlparse, unquote

# ──────────────────────────────────────────────────────────────
# 1. CONFIGURATION
# ──────────────────────────────────────────────────────────────

TAVILY_API_KEY = "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"

PPM_CEILING_STANDARD  = 220_000
PPM_CEILING_LARGE     = 250_000
PPM_SANITY_FLAG       = 180_000
AREA_LARGE_THRESHOLD  = 400

AREA_TOLERANCE_RATIO = 0.20
STRICT_BEDROOM_MATCH = True

# ──────────────────────────────────────────────────────────────
# 2. LOAD MODEL
# ──────────────────────────────────────────────────────────────

print("Loading Agentic Luxury Appraiser Model...")
try:
    model = CatBoostRegressor()
    model.load_model("catboost_true_model.cbm")
    print(" ✅ Model loaded successfully!\n")
except Exception as e:
    print(f" ❌ Error: Could not find 'catboost_true_model.cbm'. {e}")
    exit()

cat_features = [
    "property_type", "finishing", "sale_type",
    "compound_name", "location_TRIMMED", "developer_name"
]

# ──────────────────────────────────────────────────────────────
# 3. USER INPUT
# ──────────────────────────────────────────────────────────────

def get_numeric_input(prompt, type_func=float):
    while True:
        try:
            return type_func(input(prompt))
        except ValueError:
            print("  -> Invalid input. Please enter a number.")


def get_categorical_input(prompt, valid_options):
    options_str = " / ".join(valid_options)
    while True:
        choice = input(f"{prompt} ({options_str}):\n> ").strip().lower()
        for option in valid_options:
            if choice == option.lower():
                return option
        print("  -> Invalid choice. Please choose from the list.")


def get_user_input():
    print("=" * 50 + "\nENTER PROPERTY DETAILS\n" + "=" * 50)
    return {
        "area":          get_numeric_input("1. Area (sqm)?\n> ", float),
        "bedrooms":      get_numeric_input("2. Bedrooms?\n> ", int),
        "bathrooms":     get_numeric_input("3. Bathrooms?\n> ", int),
        "delivery_year": get_numeric_input("4. Delivery Year?\n> ", int),
        "property_type": get_categorical_input("5. Property Type?",
                             ["Apartment", "Villa", "Chalet"]),
        "finishing":     get_categorical_input("6. Finishing?",
                             ["Finished", "semi-finished", "not finished", "Furnished"]),
        "sale_type":     get_categorical_input("7. Sale Type?",
                             ["Resale", "Developer Sale"]),
        "compound":      input("8. Compound Name:\n> ").strip(),
        "location":      input("9. Location:\n> ").strip(),
        "developer":     input("10. Developer Name:\n> ").strip(),
    }

# ──────────────────────────────────────────────────────────────
# 4. CONSTANTS
# ──────────────────────────────────────────────────────────────

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

# ── Sale type detection keywords ─────────────────────────────
# Strong signals that a listing is a DEVELOPER SALE
_DEVELOPER_SALE_KEYWORDS = [
    "payment plan", "down payment", "installment", "off-plan",
    "under construction", "delivery date", "handover", "new launch",
    "book now", "reserve now", "limited units", "developer sale",
    "1st installment", "first installment", "launch price",
    "خطة سداد", "مقدم", "قسط", "تسليم", "حجز", "بيع مطور",
    "وحدات محدودة", "إطلاق جديد", "حجز الآن",
]

# Strong signals that a listing is a RESALE
_RESALE_KEYWORDS = [
    "resale", "re-sale", "re sale", "owner resale",
    "ready to move", "immediate delivery", "immediate possession",
    "second hand", "previously owned",
    "اعادة بيع", "إعادة بيع", "مالك مباشر", "تسليم فوري",
    "جاهز للتسليم", "ريسيل",
]

# ──────────────────────────────────────────────────────────────
# 5. SALE TYPE DETECTION  (the new fix)
# ──────────────────────────────────────────────────────────────

def detect_sale_type_from_json(raw_html: str) -> str | None:
    """
    Layer 1: Check __NEXT_DATA__ JSON for explicit sale type fields.
    Returns 'resale', 'developer', or None (undetermined).

    Nawy stores the sale type in fields like:
      isResale: true/false
      saleType: "resale" / "primary"
      listingType: "secondary" / "primary"
      unitStatus: "resale" / "primary"
    """
    nd_match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', raw_html, re.DOTALL
    )
    if not nd_match:
        return None

    raw = nd_match.group(1).lower()

    # isResale field — most reliable
    m = re.search(r'"isresale"\s*:\s*(true|false)', raw)
    if m:
        return "resale" if m.group(1) == "true" else "developer"

    # saleType / listingType / unitStatus fields
    for key in ["saletype", "listingtype", "unitstatus", "type"]:
        m = re.search(rf'"{key}"\s*:\s*"([^"]+)"', raw)
        if m:
            val = m.group(1).lower()
            if any(x in val for x in ["resale", "secondary", "used"]):
                return "resale"
            if any(x in val for x in ["primary", "new", "developer", "off-plan"]):
                return "developer"

    return None


def detect_sale_type_from_text(text_lower: str) -> str | None:
    """
    Layer 2: Count sale-type keywords in page text.
    Returns 'resale', 'developer', or None (ambiguous).

    Logic: needs at least 1 unambiguous signal to decide.
    If both types have signals → returns whichever has more.
    """
    dev_hits = [kw for kw in _DEVELOPER_SALE_KEYWORDS if kw in text_lower]
    res_hits = [kw for kw in _RESALE_KEYWORDS if kw in text_lower]

    dev_count = len(dev_hits)
    res_count = len(res_hits)

    if res_count > 0 and dev_count == 0:
        return "resale"
    if dev_count >= 2 and res_count == 0:
        return "developer"
    if res_count > dev_count:
        return "resale"
    if dev_count > res_count:
        return "developer"

    return None  # truly ambiguous — don't reject


def validate_sale_type(raw_html: str, text_lower: str,
                        target_sale_type: str, debug: bool = False) -> bool:
    """
    NEW FIX: Validates that a listing's sale type matches the target.

    Priority:
      1. JSON detection (most reliable — from Nawy's own data)
      2. Text keyword detection (fallback)
      3. If undetermined → PASS (don't reject on uncertainty)

    target_sale_type: "Resale" or "Developer Sale"
    """
    target = "resale" if "resale" in target_sale_type.lower() else "developer"

    # Layer 1: JSON
    detected = detect_sale_type_from_json(raw_html)

    # Layer 2: text fallback if JSON inconclusive
    if detected is None:
        detected = detect_sale_type_from_text(text_lower)

    # If still undetermined → pass (safe default, don't reject uncertain listings)
    if detected is None:
        return True

    # Check for mismatch
    if detected != target:
        if debug:
            print(f"      [REJECT] sale type mismatch: listing={detected}, target={target}")
        return False

    return True

# ──────────────────────────────────────────────────────────────
# 6. HELPERS
# ──────────────────────────────────────────────────────────────

def nawy_url_type(url: str) -> str:
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


def get_price_bounds(area: float) -> tuple[float, float]:
    ceiling_ppm = PPM_CEILING_LARGE if area >= AREA_LARGE_THRESHOLD else PPM_CEILING_STANDARD
    return area * 18_000, area * ceiling_ppm


def extract_bedrooms_from_text(text_lower: str) -> int | None:
    m = re.search(r'with\s*(\d{1,2})\s*bedrooms?', text_lower)
    if m:
        return int(m.group(1))
    return None


def extract_area_from_text(text_lower: str) -> float | None:
    m = re.search(r'(\d{2,4})\s*(?:m2|m²|sqm)', text_lower)
    if m:
        return float(m.group(1))
    return None

# ──────────────────────────────────────────────────────────────
# 7. COMPOUND ID RESOLUTION
# ──────────────────────────────────────────────────────────────

def extract_compound_id(url: str) -> int | None:
    path = unquote(urlparse(url).path.lower())
    if "/compound/" in path:
        segment = path.split("/compound/", 1)[1].split("/")[0]
        parts   = segment.split("-", 1)
        if parts[0].isdigit():
            return int(parts[0])
    return None


def resolve_compound_ids(compound_name: str) -> set[int]:
    query = f'site:nawy.com/compound "{compound_name}" property'
    data  = _run_search(query, max_results=5)

    name_tokens = set(re.split(r'[\s\-_]+', compound_name.lower()))
    meaningful  = name_tokens - _SLUG_NOISE_TOKENS
    if not meaningful:
        meaningful = name_tokens

    allowed_ids: set[int] = set()
    for item in data.get("organic", []):
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
        print(f"   [IDs] '{compound_name}' → none, using text fallback")
    return allowed_ids

# ──────────────────────────────────────────────────────────────
# 8. URL SLUG TYPE PRE-FILTER
# ──────────────────────────────────────────────────────────────

def url_has_type_conflict(url: str, target_type: str) -> tuple[bool, str]:
    path = unquote(urlparse(url).path.lower())
    for slug in SLUG_TYPE_CONFLICTS.get(target_type.lower(), []):
        if slug in path:
            return True, slug
    return False, ""

# ──────────────────────────────────────────────────────────────
# 9. VALIDATOR  (sale type check integrated)
# ──────────────────────────────────────────────────────────────

def compound_variants(name: str) -> list[str]:
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


def validate_nawy_listing(
    clean_text: str,
    url: str,
    target_features: dict,
    raw_html: str = "",
    debug: bool = False,
) -> bool:
    def reject(reason):
        if debug:
            print(f"      [REJECT] {reason}")
        return False

    if nawy_url_type(url) != "property":
        return reject(f"url type = {nawy_url_type(url)}")

    path = unquote(urlparse(url).path.lower())

    # FIX 3: URL slug type pre-filter
    target_type = target_features.get("property_type", "apartment")
    conflict, slug = url_has_type_conflict(url, target_type)
    if conflict:
        return reject(f"slug conflict: '{slug}'")

    # FIX 2: Compound ID check
    allowed_ids = target_features.get("compound_ids")
    if allowed_ids:
        url_id = extract_compound_id(url)
        if url_id is not None and url_id not in allowed_ids:
            return reject(f"ID {url_id} not in {sorted(allowed_ids)}")

    # Noise strip
    for section in ["Top Searches", "Popular locations", "Related Compounds", "Explore similar"]:
        clean_text = clean_text.split(section)[0]
    text_lower = clean_text.lower()

    # NEW FIX — Sale type validation
    target_sale_type = target_features.get("sale_type", "")
    if target_sale_type and raw_html:
        if not validate_sale_type(raw_html, text_lower, target_sale_type, debug=debug):
            return False  # reject message already printed inside validate_sale_type

    # Bedroom strict match
    target_beds = target_features.get("bedrooms")
    if STRICT_BEDROOM_MATCH and target_beds is not None:
        listing_beds = extract_bedrooms_from_text(text_lower)
        if listing_beds is not None and listing_beds != target_beds:
            return reject(f"bedrooms mismatch: listing={listing_beds}, target={target_beds}")

    # Area tolerance filter
    target_area = target_features.get("area")
    if target_area:
        listing_area = extract_area_from_text(text_lower)
        if listing_area is not None:
            low  = target_area * (1 - AREA_TOLERANCE_RATIO)
            high = target_area * (1 + AREA_TOLERANCE_RATIO)
            if not (low <= listing_area <= high):
                return reject(f"area mismatch: {listing_area:.0f} not in [{low:.0f}–{high:.0f}]")

    # Text-based compound check (when no ID set resolved)
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

    # Property-type keyword check
    TYPE_KEYWORDS = {
        "apartment": {
            "positive": ["apartment", "flat", "studio", "duplex", "penthouse", "شقة", "شقه"],
            "negative": ["villa", "فيلا", "chalet", "شاليه"],
        },
        "villa": {
            "positive": ["villa", "standalone", "twin house", "townhouse", "ivilla", "فيلا"],
            "negative": ["apartment", "شقة"],
        },
        "chalet": {
            "positive": ["chalet", "cabin", "beach unit", "sahel unit", "شاليه", "كابينة"],
            "negative": ["apartment", "شقة"],
        },
    }
    entry   = TYPE_KEYWORDS.get(target_type.lower(), {"positive": [target_type], "negative": []})
    text_ns = re.sub(r'\s+', '', text_lower)

    if not any((w in text_lower or w.replace(" ", "") in text_ns) for w in entry["positive"]):
        return reject(f"no '{target_type}' keyword")

    body_lower = text_lower[1000:-1000] if len(text_lower) > 3000 else text_lower
    for neg in entry["negative"]:
        count     = body_lower.count(neg)
        threshold = 8 if neg in {"apartment", "شقة"} else 2
        if count > threshold:
            return reject(f"rival '{neg}' ×{count} (threshold {threshold})")

    if debug:
        print(f"      [PASS]")
    return True

# ──────────────────────────────────────────────────────────────
# 10. PRICE EXTRACTOR
# ──────────────────────────────────────────────────────────────

def _get_nested(obj: dict, path: list):
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


def _extract_next_data_price(nd_json: dict, logical_floor: float,
                              logical_ceiling: float) -> list[int]:
    # Step 1: targeted unit-price paths
    for path in NAWY_UNIT_PRICE_PATHS:
        val = _get_nested(nd_json, path)
        if isinstance(val, (int, float)) and logical_floor <= val <= logical_ceiling:
            print(f"      [ND:targeted] {'.'.join(path[-2:])} = {int(val):,.0f}")
            return [int(val)]

    # Step 2: unit-object detection
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

    # Step 3: full-tree fallback
    all_keyed = _extract_prices_from_json(nd_json, PRICE_KEYS)
    in_range  = [p for p in all_keyed if logical_floor <= p <= logical_ceiling]
    if in_range:
        print(f"      [ND:full_scan] {in_range[:5]}")
    return in_range


def deduplicate_shared_prices(prices: list[int]) -> list[int]:
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
        r'(?:down[\s_-]?payment|downpayment|مقدم)[^\d]{0,25}(\d{5,10})',
        r'(\d{5,10})[^\d]{0,15}(?:down[\s_-]?payment|downpayment|مقدم)',
    ]
    downpayments = [int(m) for pat in dp_pats for m in re.findall(pat, text) if m]
    mo_pats = [
        r'(?:monthly|per[\s_]month|شهري)[^\d]{0,25}(\d{4,9})',
        r'(\d{4,9})[^\d]{0,15}(?:monthly|per[\s_]month|/month|شهريا)',
    ]
    monthlies     = [int(m) for pat in mo_pats for m in re.findall(pat, text) if m]
    period_months = None
    yr = re.search(r'(\d{1,2})[\s_-]*(?:year|years|سنة|سنوات)', text)
    mo = re.search(r'(\d{2,3})[\s_-]*(?:month|months|شهر)', text)
    if yr:   period_months = int(yr.group(1)) * 12
    elif mo: period_months = int(mo.group(1))
    if not (downpayments and monthlies and period_months):
        return None
    dp      = max(downpayments)
    monthly = sorted(monthlies)[len(monthlies) // 2]
    total   = dp + monthly * period_months
    return total if logical_floor <= total <= logical_ceiling else None


def extract_nawy_price(raw_html: str, clean_text: str, target_area: float,
                       logical_floor: float, logical_ceiling: float,
                       url: str = "") -> int | None:
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
# 11. OUTLIER REMOVAL + CONFIDENCE FLAG
# ──────────────────────────────────────────────────────────────

def remove_outliers(prices: list[int], area: float,
                    fallback_mode: bool = False) -> tuple[list[int], bool]:
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
            clean = iqr_clean

    clean = clean if clean else prices
    low_confidence = len(clean) <= 2 or len(set(prices)) == 1

    # CV check — high variance = unreliable even with many listings
    if len(clean) >= 3:
        cv = statistics.stdev(clean) / statistics.mean(clean)
        if cv > 0.5:
            print(f"      [HIGH VARIANCE] CV={cv:.2f} > 0.5 — LOW_CONFIDENCE")
            low_confidence = True

    # ppm sanity cap
    if clean:
        avg_ppm = (sum(clean) / len(clean)) / area
        if avg_ppm > PPM_SANITY_FLAG:
            print(f"      [PPM SANITY] {avg_ppm:,.0f}/sqm > {PPM_SANITY_FLAG:,} — LOW_CONFIDENCE")
            low_confidence = True

    if low_confidence:
        print(f"      [LOW_CONFIDENCE] flagged")

    return clean, low_confidence

# ──────────────────────────────────────────────────────────────
# 11b. CLUSTER-BASED SALE TYPE SEPARATION  (the real fix)
# ──────────────────────────────────────────────────────────────

def select_cluster_by_sale_type(
    prices: list[int],
    sale_type: str,
    gap_threshold: float = 40.0,
) -> list[int]:
    """
    Fixes the resale/developer sale mixing problem.

    Root cause: Nawy indexes both sale types together in search results.
    Content-based detection (isResale field / keywords) is unreliable
    because Nawy pages don't consistently label their sale type.

    The reliable signal is PRICE LEVEL:
      Developer Sale = lower prices (primary market, off-plan/pre-delivery)
      Resale         = higher prices (secondary market, delivered + premium)

    When both types are mixed, the price list is BIMODAL — two clusters
    with a large gap between them. This function finds that gap and
    selects the correct cluster based on the target sale type.

    Args:
        prices:        cleaned price list (after outlier removal)
        sale_type:     "Resale" or "Developer Sale"
        gap_threshold: min % gap to consider a cluster split (default 40%)

    Returns:
        The correct cluster, or the original list if no clear split found.
    """
    if len(prices) < 4:
        return prices  # too few to detect clusters reliably

    sorted_p = sorted(prices)

    # Find the largest percentage gap between consecutive sorted prices
    max_gap_pct = 0.0
    split_idx   = None
    for i in range(1, len(sorted_p)):
        gap_pct = (sorted_p[i] - sorted_p[i-1]) / sorted_p[i-1] * 100
        if gap_pct > max_gap_pct:
            max_gap_pct = gap_pct
            split_idx   = i

    # Only split if the gap is significant
    if max_gap_pct < gap_threshold or split_idx is None:
        return prices  # single cluster — no split needed

    lower = sorted_p[:split_idx]
    upper = sorted_p[split_idx:]

    # Require at least 2 prices in each cluster to be meaningful
    if len(lower) < 2 or len(upper) < 2:
        return prices

    is_resale = "resale" in sale_type.lower()
    chosen    = upper if is_resale else lower

    print(
        f"      [CLUSTER SPLIT] gap={max_gap_pct:.0f}% detected\n"
        f"        lower={[f'{p/1e6:.1f}M' for p in lower]}  "
        f"upper={[f'{p/1e6:.1f}M' for p in upper]}\n"
        f"        → using {'upper (resale)' if is_resale else 'lower (developer sale)'}"
    )
    return chosen


# ──────────────────────────────────────────────────────────────
# 12. FETCH + TAVILY SEARCH
# ──────────────────────────────────────────────────────────────

def _fetch_page(url: str) -> str | None:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    for attempt in range(2):
        try:
            r = requests.get(url, headers=headers, timeout=20)
            if r.status_code == 200:
                return r.text
            if r.status_code == 500 and attempt == 0:
                time.sleep(5)
                continue
            print(f"      [HTTP {r.status_code}] {url[-60:]}")
            return None
        except Exception as e:
            if attempt == 0:
                time.sleep(3)
                continue
            print(f"      [FETCH ERROR] {type(e).__name__}")
            return None
    return None


def _run_search(query: str, max_results: int = 10) -> dict:
    """Tavily Search API — returns {"organic": [{"link": url}]}"""
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            headers={"Content-Type": "application/json"},
            json={
                "api_key":            TAVILY_API_KEY,
                "query":              query,
                "search_depth":       "advanced",
                "max_results":        max_results,
                "include_answer":     False,
                "include_raw_content": False,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"   [TAVILY {resp.status_code}] {resp.text[:150]}")
            return {}
        data    = resp.json()
        organic = [
            {"link": r.get("url", "")}
            for r in data.get("results", [])
            if r.get("url")
        ]
        return {"organic": organic}
    except Exception as e:
        print(f"   [TAVILY ERROR] {type(e).__name__}: {e}")
        return {}

# ──────────────────────────────────────────────────────────────
# 13. LANGGRAPH STATE & NODES
# ──────────────────────────────────────────────────────────────

class GraphState(TypedDict):
    input_features:  dict
    search_query:    str
    fallback_used:   bool
    listings:        list
    sources:         list
    avg_price:       float
    model_price:     float
    final_price:     float
    low_confidence:  bool


def build_query(state: GraphState):
    f         = state["input_features"]
    sale_hint = "resale" if "resale" in f["sale_type"].lower() else "for sale"
    query     = f'site:nawy.com/compound "{f["compound"]}" {f["property_type"]} {sale_hint}'
    print(f"🔍 Primary query: {query}")
    return {"search_query": query, "fallback_used": False}


def web_search(state: GraphState):
    print("🌐 [Node] Searching Nawy listings…")
    f    = state["input_features"]
    data = _run_search(state["search_query"], max_results=50)

    results = []
    for item in data.get("organic", []):
        url = item.get("link", "")
        if nawy_url_type(url) != "property":
            print(f"   [SKIP:{nawy_url_type(url)}] {url[:75]}")
            continue
        conflict, slug = url_has_type_conflict(url, f["property_type"])
        if conflict:
            print(f"   [SKIP:slug '{slug}'] {url[:75]}")
            continue
        print(f"   [FETCH] {url[:75]}")
        html = _fetch_page(url)
        if html:
            results.append({"url": url, "html": html})

    fallback_used = False
    if not results:
        sale_hint     = "resale" if "resale" in f["sale_type"].lower() else "for sale"
        fallback_query = f'site:nawy.com "{f["compound"]}" {f["property_type"]} {sale_hint}'
        print(f"⚠️  No results — fallback: {fallback_query}")
        data2 = _run_search(fallback_query, max_results=50)
        for item in data2.get("organic", []):
            url = item.get("link", "")
            if nawy_url_type(url) != "property":
                continue
            conflict, slug = url_has_type_conflict(url, f["property_type"])
            if conflict:
                continue
            html = _fetch_page(url)
            if html:
                results.append({"url": url, "html": html})
        fallback_used = bool(results)

    return {
        "listings":      results,
        "sources":       [r["url"] for r in results],
        "fallback_used": fallback_used,
    }


def extract_prices(state: GraphState):
    print("🕸️  [Node] Extracting prices from Nawy listings…")
    listings      = state.get("listings", [])
    fallback_used = state.get("fallback_used", False)
    f             = state["input_features"]

    compound_ids: set[int] = set()
    if not fallback_used:
        compound_ids = resolve_compound_ids(f["compound"])

    val_features = {
        "compound":      "" if fallback_used else f["compound"],
        "compound_ids":  compound_ids,
        "property_type": f["property_type"],
        "area":          f["area"],
        "bedrooms":      f["bedrooms"],
        "sale_type":     f["sale_type"],   # ← passed to sale type validator
    }
    if fallback_used:
        print("   ℹ️  Fallback mode: compound filter disabled.")

    logical_floor, logical_ceiling = get_price_bounds(f["area"])
    raw_prices = []
    seen_urls  = set()

    for item in listings:
        url = item["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)

        soup       = BeautifulSoup(item["html"], "html.parser")
        clean_text = soup.get_text(separator=" ")

        print(f"  → {url[:75]}")
        # raw_html passed so sale type check can read NEXT_DATA JSON
        if not validate_nawy_listing(
            clean_text, url, val_features,
            raw_html=item["html"], debug=True
        ):
            continue

        price = extract_nawy_price(
            item["html"], clean_text, f["area"],
            logical_floor, logical_ceiling, url=url
        )
        if price:
            raw_prices.append(price)
            print(f"      ✅ {price:,.0f} EGP  ({price / f['area']:,.0f} EGP/sqm)")
        else:
            print(f"      ❌ No usable price")

    clean_prices, low_confidence = remove_outliers(
        raw_prices, area=f["area"], fallback_mode=fallback_used
    )

    # Cluster-based sale type separation — picks the correct price cluster
    # when Developer Sale and Resale listings are mixed together
    if clean_prices and not fallback_used:
        clean_prices = select_cluster_by_sale_type(clean_prices, f["sale_type"])

    avg = statistics.median(clean_prices) if clean_prices else 0
    print(f"\n   📊 Raw      : {[f'{p:,.0f}' for p in raw_prices]}")
    print(f"   📊 Clean    : {[f'{p:,.0f}' for p in clean_prices]}")
    print(f"   📊 Web median: {avg:,.0f} EGP\n")

    return {"avg_price": avg, "low_confidence": low_confidence}


def model_predict(state: GraphState):
    print("🧠 [Node] Predicting via CatBoost…")
    f = state["input_features"].copy()
    f.update({
        "years_to_delivery": f["delivery_year"] - 2026,
        "total_rooms":       f["bedrooms"] + f["bathrooms"],
        "area_per_bedroom":  f["area"] / f["bedrooms"] if f["bedrooms"] > 0 else f["area"],
        "bath_to_bed_ratio": f["bathrooms"] / f["bedrooms"] if f["bedrooms"] > 0 else 0,
        "area_squared":      f["area"] ** 2,
        "is_ultra_luxury":   1 if f["area"] >= 500 else 0,
        "compound_name":     f["compound"],
        "location_TRIMMED":  f["location"],
        "developer_name":    f["developer"],
    })
    df       = pd.DataFrame([f])[model.feature_names_]
    pred_ppm = model.predict(Pool(df, cat_features=cat_features))[0]
    return {"model_price": float(pred_ppm * f["area"])}


def combine_prices(state: GraphState):
    m, w = state["model_price"], state["avg_price"]
    if w > 0:
        if state.get("low_confidence"):
            web_weight = 0.40
        elif state.get("fallback_used"):
            web_weight = 0.60
        else:
            web_weight = 0.70
        final = (1 - web_weight) * m + web_weight * w
    else:
        final = m
    return {"final_price": final}

# ──────────────────────────────────────────────────────────────
# 14. GRAPH ASSEMBLY
# ──────────────────────────────────────────────────────────────

builder = StateGraph(GraphState)

for name, fn in [
    ("build_query",    build_query),
    ("web_search",     web_search),
    ("extract_prices", extract_prices),
    ("model_predict",  model_predict),
    ("combine",        combine_prices),
]:
    builder.add_node(name, fn)

builder.set_entry_point("build_query")
builder.add_edge("build_query",    "web_search")
builder.add_edge("web_search",     "extract_prices")
builder.add_edge("extract_prices", "model_predict")
builder.add_edge("model_predict",  "combine")
builder.set_finish_point("combine")

appraiser_agent = builder.compile()

# ──────────────────────────────────────────────────────────────
# 15. MAIN LOOP
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    while True:
        u_in = get_user_input()
        print("\n" + "=" * 60 + "\n   SEMSAI AGENT: RUNNING WORKFLOW\n" + "=" * 60)
        res = appraiser_agent.invoke({"input_features": u_in})

        print("\n" + "⭐" * 30 + "\n   FINAL APPRAISAL REPORT\n" + "⭐" * 30)
        print(f"🏠 UNIT     : {u_in['compound']} | {u_in['area']} sqm | {u_in['location']}")
        print(f"🏗️  DEVELOPER: {u_in['developer']}")
        print(f"📐 DETAILS  : {u_in['bedrooms']}BR / {u_in['bathrooms']}BA | "
              f"{u_in['finishing']} | {u_in['sale_type']}")
        print("-" * 60)

        ml_price  = res["model_price"]
        web_price = res["avg_price"]
        final     = res["final_price"]

        print(f"📊 ML Prediction : {ml_price:>15,.0f} EGP  ({ml_price / u_in['area']:,.0f} EGP/sqm)")

        if web_price > 0:
            if res.get("low_confidence"):
                blend = "40% web / 60% ML  [LOW CONFIDENCE]"
            elif res.get("fallback_used"):
                blend = "60% web / 40% ML"
            else:
                blend = "70% web / 30% ML"

            print(f"🌐 Nawy Median   : {web_price:>15,.0f} EGP  ({web_price / u_in['area']:,.0f} EGP/sqm)")
            print(f"🎯 FINAL VALUE   : {final:>15,.0f} EGP  ({final / u_in['area']:,.0f} EGP/sqm)  [{blend}]")

            if res.get("low_confidence"):
                print("   ⚠️  LOW CONFIDENCE — price unreliable. ML weight increased to 60%.")
            if res.get("fallback_used"):
                print("   ⚠️  Location-level comps only — treat with caution.")
        else:
            print(f"🌐 Nawy Median   :     No comparable listings found")
            print(f"🎯 FINAL VALUE   : {final:>15,.0f} EGP  ({final / u_in['area']:,.0f} EGP/sqm)  [ML only]")

        if res.get("sources"):
            seen, unique = set(), []
            for src in res["sources"]:
                if src not in seen:
                    seen.add(src)
                    unique.append(src)
            print(f"\n🔗 NAWY SOURCES ({len(unique)} pages):")
            for i, src in enumerate(unique[:5], 1):
                print(f"   {i}. {src}")

        if input("\nAppraise another? (y/n): ").lower() != "y":
            break
