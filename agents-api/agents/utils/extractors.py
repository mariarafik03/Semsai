"""
agents/utils/extractors.py
──────────────────────────
LLM-powered field extraction using ask_llm_with_history from main_helpers.
Same public API as before — every agent calls extract_*(text) and gets back
(value | None, confidence_str, error | None) — no agent code needs to change.

Regex fallback is kept so a flaky API call never breaks the conversation.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple


def _ask(prompt: str) -> str:
    """One focused LLM extraction call. Returns '' on any failure."""
    try:
        from main_helpers import ask_llm_with_history
        return ask_llm_with_history(
            system_prompt=(
                "You are a precise data-extraction engine for Egyptian real estate. "
                "Return ONLY the requested value — no explanation, no punctuation, "
                "no markdown, no extra words. If you cannot extract it, return: none"
            ),
            history=[],
            user_prompt=prompt,
            max_tokens=32,
            temperature=0.0,
        ).strip()
    except Exception as exc:
        print(f"   ⚠️ extractor LLM call failed: {exc}")
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Location
# ─────────────────────────────────────────────────────────────────────────────

def extract_location(text: str) -> Tuple[Optional[str], str, Optional[str]]:
    reply = _ask(
        f"Extract the Egyptian city or area name from this text.\n"
        f"Text: \"{text}\"\n"
        f"Examples: 'New Cairo', 'El Sheikh Zayed', 'North Coast', 'Alexandria'.\n"
        f"Return ONLY the place name, or 'none' if no location is mentioned."
    )
    if reply and reply.lower() not in ("none", ""):
        return reply.strip().title(), "high", None

    # Regex fallback
    try:
        from agents.Normalization import LOCATION_ALIASES
    except ImportError:
        try:
            from Normalization import LOCATION_ALIASES
        except ImportError:
            LOCATION_ALIASES = {}
    cleaned = re.sub(r"[،,.\-_]+", " ", text.strip().lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    for alias, normalized in LOCATION_ALIASES.items():
        if alias in cleaned:
            return normalized, "high", None

    return None, "low", "Could not extract a location."


# ─────────────────────────────────────────────────────────────────────────────
# Property type
# ─────────────────────────────────────────────────────────────────────────────

_VALID_PROPERTY_TYPES = {"apartment", "villa", "chalet"}

def extract_property_type(text: str) -> Tuple[Optional[str], str, Optional[str]]:
    reply = _ask(
        f"What property type is the user asking for?\n"
        f"Text: \"{text}\"\n"
        f"Return ONLY one word: apartment, villa, or chalet.\n"
        f"Synonyms: flat/studio/duplex/penthouse → apartment; house/townhouse → villa.\n"
        f"Return 'none' if no property type is mentioned."
    ).lower()
    if reply in _VALID_PROPERTY_TYPES:
        return reply, "high", None

    # Regex fallback
    t = text.lower()
    for ptype, aliases in {
        "apartment": ["apartment", "flat", "شقة", "شقه", "studio", "duplex", "penthouse"],
        "villa":     ["villa", "house", "فيلا", "فيلة", "townhouse"],
        "chalet":    ["chalet", "شاليه", "شالية"],
    }.items():
        if any(a in t for a in aliases):
            return ptype, "high", None

    return None, "low", "Could not extract a property type."


# ─────────────────────────────────────────────────────────────────────────────
# Payment type
# ─────────────────────────────────────────────────────────────────────────────

_VALID_PAYMENT_TYPES = {"cash", "installment"}

def extract_payment_type(text: str) -> Tuple[Optional[str], str, Optional[str]]:
    reply = _ask(
        f"Does the user want to pay cash or by installments?\n"
        f"Text: \"{text}\"\n"
        f"Return ONLY one word: cash or installment.\n"
        f"Synonyms: 'installments/monthly/تقسيط/قسط' → installment; 'كاش/نقدي/full price' → cash.\n"
        f"Return 'none' if unclear."
    ).lower()
    if reply in _VALID_PAYMENT_TYPES:
        return reply, "high", None

    # Regex fallback
    t = text.lower()
    if any(w in t for w in ["cash", "كاش", "نقدي"]):
        return "cash", "high", None
    if any(w in t for w in ["installment", "installments", "monthly", "تقسيط", "قسط"]):
        return "installment", "high", None

    return None, "low", "Could not extract a payment type."


# ─────────────────────────────────────────────────────────────────────────────
# Numeric amounts (budget, downpayment, monthly installment)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_numeric(text: str) -> Optional[float]:
    """Convert '5m', '5 million', '500k', '5000000' → float. None if not found."""
    t = text.lower().replace(",", "").strip()
    match = re.search(r"(\d+(?:\.\d+)?)\s*(millions?|billions?|thousands?|m|b|k)\b", t)
    if match:
        val, unit = float(match.group(1)), match.group(2)
        if unit.startswith("b"):   val *= 1_000_000_000
        elif unit.startswith("m"): val *= 1_000_000
        elif unit.startswith("k"): val *= 1_000
        return val
    nums = re.findall(r"\d+(?:\.\d+)?", t.replace(" ", ""))
    return float(nums[0]) if nums else None


def extract_budget(text: str) -> Tuple[Optional[float], str, Optional[str]]:
    reply = _ask(
        f"Extract the total budget amount in EGP from this text.\n"
        f"Text: \"{text}\"\n"
        f"Convert shorthand: 5M → 5000000, 500k → 500000, 1.5 million → 1500000.\n"
        f"Return ONLY digits (e.g. 5000000), or 'none'."
    )
    if reply and reply.lower() != "none":
        val = _parse_numeric(reply) or _parse_numeric(text)
        if val and val >= 100_000:
            return val, "high", None

    val = _parse_numeric(text)
    if val and val >= 100_000:
        return val, "high", None

    return None, "low", "Could not extract a budget amount."


def extract_downpayment(text: str) -> Tuple[Optional[float], str, Optional[str]]:
    reply = _ask(
        f"Extract the down payment amount in EGP from this text.\n"
        f"Text: \"{text}\"\n"
        f"Convert shorthand: 5M → 5000000, 500k → 500000.\n"
        f"Return ONLY digits, or 'none'."
    )
    if reply and reply.lower() != "none":
        val = _parse_numeric(reply) or _parse_numeric(text)
        if val and val > 0:
            return val, "high", None

    val = _parse_numeric(text)
    if val and val > 0:
        return val, "high", None

    return None, "low", "Could not extract a down-payment amount."


def extract_monthly_installment(text: str) -> Tuple[Optional[float], str, Optional[str]]:
    reply = _ask(
        f"Extract the monthly installment amount in EGP from this text.\n"
        f"Text: \"{text}\"\n"
        f"Convert shorthand: 5M → 5000000, 500k → 500000.\n"
        f"Return ONLY digits, or 'none'."
    )
    if reply and reply.lower() != "none":
        val = _parse_numeric(reply) or _parse_numeric(text)
        if val and val > 0:
            return val, "high", None

    val = _parse_numeric(text)
    if val and val > 0:
        return val, "high", None

    return None, "low", "Could not extract a monthly installment amount."


# ─────────────────────────────────────────────────────────────────────────────
# Multi-field (fallback for extraction_agent)
# ─────────────────────────────────────────────────────────────────────────────

def extract_all_fields(text: str) -> Dict[str, Tuple[Any, str]]:
    """Extract all recognisable fields from one message. Used as fallback in extraction_agent."""
    results: Dict[str, Tuple[Any, str]] = {}
    for fn, key in (
        (extract_location,      "location"),
        (extract_property_type, "property_type"),
        (extract_payment_type,  "payment_type"),
        (extract_budget,        "budget"),
    ):
        val, conf, _ = fn(text)
        if val and conf == "high":
            results[key] = (val, conf)
    return results