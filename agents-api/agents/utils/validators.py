"""
validators.py — Domain-specific validation logic for real estate fields.
"""
from typing import Tuple, Optional, Any
from agents.Normalization import normalize_location

def validate_location(location_name: str, db: Any = None) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate and normalize a location name.
    
    Returns:
        (is_valid, normalized_name, error_message)
    """
    if not location_name:
        return False, None, "Location cannot be empty."
        
    normalized = normalize_location(location_name)
    if normalized:
        return True, normalized, None
        
    return False, None, f"I couldn't find a location matching '{location_name}' in our database. Could you try a more general area?"

def validate_property_type(ptype: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Validate property type preference."""
    valid_types = ["apartment", "villa", "chalet"]
    ptype_clean = ptype.lower().strip()
    if ptype_clean in valid_types:
        return True, ptype_clean, None
    return False, None, "Please choose from: apartment, villa, or chalet."

def validate_payment_type(ptype: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Validate payment type (cash or installment)."""
    valid_types = ["cash", "installment"]
    ptype_clean = ptype.lower().strip()
    if ptype_clean in valid_types:
        return True, ptype_clean, None
    return False, None, "Please specify if you'd like to pay by 'cash' or 'installment'."

def validate_budget(budget: Any, location: str = None, property_type: str = None, db: Any = None) -> Tuple[bool, Optional[float], Optional[str]]:
    """Validate budget amount."""
    try:
        val = float(budget)
        if val <= 0:
            return False, None, "Budget must be a positive number."
        
        # Simple heuristic: most properties start at 1M+
        if val < 100000:
            return False, None, "The amount seems too low for a property. Are you sure?"
            
        return True, val, None
    except (ValueError, TypeError):
        return False, None, "Please provide a valid numeric amount for your budget."

def validate_payment_details(
    ptype: str, 
    budget: Optional[float], 
    downpayment: Optional[float], 
    monthly: Optional[float]
) -> Tuple[bool, Optional[str]]:
    """
    Validate that installment details make sense together.
    """
    if ptype != "installment":
        return True, None
        
    if downpayment is not None and budget is not None:
        if downpayment > budget:
            return False, "Downpayment cannot be greater than the total budget."
            
    if downpayment is not None and downpayment < 0:
        return False, "Downpayment cannot be negative."
        
    if monthly is not None and monthly < 0:
        return False, "Monthly installment cannot be negative."
        
    return True, None
