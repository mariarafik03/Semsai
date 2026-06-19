"""
extractors.py — Rule-based field extraction from user input.
"""
import re
from typing import Tuple, Optional, Dict, Any

def extract_location(text: str) -> Tuple[Optional[str], str, Optional[str]]:
    """Extract location from text."""
    # This is a stub for a real NLP extractor.
    # For now, we clean the text and return it if it looks like a name.
    cleaned = text.strip()
    if len(cleaned) > 2 and len(cleaned) < 50:
        return cleaned, "high", None
    return None, "low", None

def extract_property_type(text: str) -> Tuple[Optional[str], str, Optional[str]]:
    """Extract property type from text."""
    text = text.lower()
    mapping = {
        "apartment": ["apartment", "flat", "شقة", "شقه"],
        "villa": ["villa", "house", "فيلا", "فيلة"],
        "chalet": ["chalet", "شاليه", "شالية"]
    }
    for ptype, aliases in mapping.items():
        if any(alias in text for alias in aliases):
            return ptype, "high", None
    return None, "low", None

def extract_payment_type(text: str) -> Tuple[Optional[str], str, Optional[str]]:
    """Extract payment type from text."""
    text = text.lower()
    if any(word in text for word in ["cash", "كاش", "نقدي"]):
        return "cash", "high", None
    if any(word in text for word in ["installment", "تقسيط", "قسط"]):
        return "installment", "high", None
    return None, "low", None

def extract_budget(text: str) -> Tuple[Optional[float], str, Optional[str]]:
    """Extract budget amount from text."""
    # Match numbers like 5,000,000 or 5M
    text = text.lower().replace(',', '')
    
    # Handle "million" or "m"
    multiplier = 1.0
    if "million" in text or "مليون" in text or " m" in text or text.endswith("m"):
        multiplier = 1_000_000.0
    elif "thousand" in text or "ألف" in text or " k" in text or text.endswith("k"):
        multiplier = 1_000.0
        
    numbers = re.findall(r'\d+(?:\.\d+)?', text)
    if numbers:
        val = float(numbers[0]) * multiplier
        return val, "high", None
    return None, "low", None

def extract_downpayment(text: str) -> Tuple[Optional[float], str, Optional[str]]:
    """Extract downpayment amount from text."""
    return extract_budget(text) # Reuse budget extraction logic for now

def extract_monthly_installment(text: str) -> Tuple[Optional[float], str, Optional[str]]:
    """Extract monthly installment amount from text."""
    return extract_budget(text) # Reuse budget extraction logic for now

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
