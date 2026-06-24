"""
extractors.py — Rule-based field extraction from user input.
"""
import re
from typing import Tuple, Optional, Dict, Any


# ── Location keywords that signal a location phrase follows ──────────────────
_LOCATION_SIGNALS = [
    "in ", "at ", "near ", "around ", "في ", "بـ", "ب ", "قرب ",
]

# Known area names / fragments (lowercase). Add more as needed.
_KNOWN_LOCATIONS = [
    "tagmo3", "tagamoa", "new cairo", "cairo", "giza", "6th october",
    "sheikh zayed", "maadi", "heliopolis", "nasr city", "zamalek",
    "october", "obour", "shorouk", "badr", "ain sokhna", "north coast",
    "alexandria", "alex", "القاهرة", "الجيزة", "الشيخ زايد", "المعادي",
    "مدينة نصر", "التجمع", "الشروق", "البدر", "العبور",
]


def extract_location(text: str) -> Tuple[Optional[str], str, Optional[str]]:
    """
    Extract location from text.
    Returns (value, confidence, error_msg).

    Strategy:
    1. Check for known location names first (high confidence).
    2. Look for signal phrases like "in X" and take X (medium → high if plausible).
    3. Never return the whole sentence as location.
    """
    lower = text.lower()

    # 1. Known locations — exact substring match
    for loc in _KNOWN_LOCATIONS:
        if loc in lower:
            # Return the matched known name (title-cased for display)
            return loc.title(), "high", None

    # 2. Signal-phrase extraction: "in <word(s)>"
    for signal in _LOCATION_SIGNALS:
        idx = lower.find(signal)
        if idx != -1:
            after = text[idx + len(signal):].strip()
            # Take up to 3 words
            words = after.split()[:3]
            candidate = " ".join(words).strip(".,!?")
            if candidate and len(candidate) > 1:
                return candidate, "high", None

    return None, "low", None


def extract_property_type(text: str) -> Tuple[Optional[str], str, Optional[str]]:
    """Extract property type from text."""
    text_lower = text.lower()
    mapping = {
        "apartment": ["apartment", "flat", "شقة", "شقه"],
        "villa":     ["villa", "house", "فيلا", "فيلة"],
        "chalet":    ["chalet", "شاليه", "شالية"],
    }
    for ptype, aliases in mapping.items():
        if any(alias in text_lower for alias in aliases):
            return ptype, "high", None
    return None, "low", None


def extract_payment_type(text: str) -> Tuple[Optional[str], str, Optional[str]]:
    """Extract payment type from text."""
    text_lower = text.lower()
    if any(w in text_lower for w in ["cash", "كاش", "نقدي"]):
        return "cash", "high", None
    if any(w in text_lower for w in ["installment", "تقسيط", "قسط"]):
        return "installment", "high", None
    return None, "low", None


# Budget keywords that must appear near a number for it to be a budget figure.
_BUDGET_KEYWORDS = [
    "budget", "price", "cost", "afford", "spend", "pay", "worth",
    "million", "مليون", "thousand", "ألف", "egp", "le", "pound",
    "بـ", "ب ", "بميزانية", "سعر", "تكلف",
]

# Multiplier suffixes
_MULTIPLIERS = {
    "million": 1_000_000,
    "مليون":   1_000_000,
    "m":       1_000_000,
    "thousand": 1_000,
    "ألف":      1_000,
    "k":        1_000,
}


def extract_budget(text: str) -> Tuple[Optional[float], str, Optional[str]]:
    """
    Extract budget amount from text.

    A number is only treated as a budget if a budget keyword appears nearby
    OR the number has a multiplier suffix directly attached (e.g. "5M", "500k").

    This prevents grabbing digits embedded in location names ("tagmo3", "6th").
    """
    text_lower = text.lower().replace(",", "")

    has_keyword = any(kw in text_lower for kw in _BUDGET_KEYWORDS)

    # 1. Try to match number+suffix combos first (e.g. "5m", "500k", "2million")
    #    Pattern: optional space between digit and suffix
    suffix_pattern = re.compile(
        r'(\d+(?:\.\d+)?)\s*(million|مليون|thousand|ألف|[mk])\b',
        re.IGNORECASE | re.UNICODE,
    )
    m = suffix_pattern.search(text_lower)
    if m:
        num = float(m.group(1))
        suffix = m.group(2).lower()
        mult = _MULTIPLIERS.get(suffix, 1.0)
        return num * mult, "high", None

    # 2. Plain number — only if a budget keyword is present
    if not has_keyword:
        return None, "low", None

    # Find standalone numbers (not embedded in words like "tagmo3" or "6th")
    numbers = re.findall(
        r'(?<![a-zA-Z\u0600-\u06FF0-9])\d+(?:\.\d+)?(?![a-zA-Z\u0600-\u06FF])',
        text_lower,
    )
    if numbers:
        return float(numbers[0]), "high", None

    return None, "low", None


def extract_downpayment(text: str) -> Tuple[Optional[float], str, Optional[str]]:
    """Extract downpayment amount from text."""
    return extract_budget(text)


def extract_monthly_installment(text: str) -> Tuple[Optional[float], str, Optional[str]]:
    """Extract monthly installment amount from text."""
    return extract_budget(text)


def extract_all_fields(text: str) -> Dict[str, Tuple[Any, str]]:
    """
    Extract all possible fields from a single block of text.
    Used by the initial extraction agent.
    """
    results = {}

    loc, conf_loc, _ = extract_location(text)
    if loc and conf_loc == "high":
        results["location"] = (loc, conf_loc)

    ptype, conf_pt, _ = extract_property_type(text)
    if ptype and conf_pt == "high":
        results["property_type"] = (ptype, conf_pt)

    pay, conf_pay, _ = extract_payment_type(text)
    if pay and conf_pay == "high":
        results["payment_type"] = (pay, conf_pay)

    bud, conf_bud, _ = extract_budget(text)
    if bud and conf_bud == "high":
        results["budget"] = (bud, conf_bud)

    return results
