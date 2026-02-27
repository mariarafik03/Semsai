import json
from state import AgentState
from main_helpers import ask_ollama

# ---------------------------------------------------------------------------
# Known valid values for normalization
# ---------------------------------------------------------------------------

VALID_PURPOSES = {"rent", "invest", "live"}
VALID_PAYMENT_TYPES = {"cash", "installments"}
VALID_PROPERTY_TYPES = {"Apartment", "Villa", "Chalet"}

PROPERTY_ALIASES = {
    "villa": "Villa",
    "vila": "Villa",
    "apartment": "Apartment",
    "flat": "Apartment",
    "chalet": "Chalet",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_purpose(raw: str) -> str | None:
    raw = raw.strip().lower()
    if raw in VALID_PURPOSES:
        return raw
    return None


def _normalize_payment_type(raw: str) -> str | None:
    raw = raw.strip().lower()
    if raw in VALID_PAYMENT_TYPES:
        return raw
    return None


def _normalize_property_type(raw: str) -> str | None:
    raw = raw.strip().lower()
    for alias, canonical in PROPERTY_ALIASES.items():
        if alias in raw:
            return canonical
    return None


def _parse_numeric(raw) -> int | None:
    if raw is None:
        return None
    raw_str = str(raw).strip().replace(",", "").replace("_", "")
    digits = "".join(filter(str.isdigit, raw_str))
    if digits:
        return int(digits)
    return None


# ---------------------------------------------------------------------------
# Extraction Agent (Non-blocking)
# ---------------------------------------------------------------------------

def extraction_agent(state: AgentState) -> AgentState:
    """
    Entry-point agent. Two-phase:
    Phase 1 (no user_input): Generate greeting, set pending_question, return.
    Phase 2 (with user_input): Extract fields from user message.
    """

    # Phase 1: Generate greeting and ask for input
    if not state.get("user_input"):
        greeting = ask_ollama(
            "You are a friendly, premium real estate assistant in Egypt. "
            "Start a warm short conversation and invite the user to tell you everything "
            "they have in mind about the property they are looking for — purpose, "
            "budget, preferred area, type of property, payment method, etc. "
            "Encourage them to share as much as they want in a single message. "
            "Do not answer for them, just ask."
        )
        state["pending_question"] = greeting
        return state

    # Phase 2: Extract fields from user input
    user_input = state["user_input"]

    extraction_prompt = f"""
You are a real estate data extraction engine.

From the following user message, extract as many of these fields as you can.
Only include a field if the user **clearly** mentioned it; do NOT guess.

Fields to extract:
- purpose        : one of "rent", "invest", "live"  (if the user says "buy" with no further detail, leave null)
- budget         : total budget in EGP as an integer (convert shorthand like "3M" to 3000000, "500k" to 500000)
- location       : area/city in Egypt  (capitalize each word, e.g. "New Cairo")
- typeofproperty : one of "Apartment", "Villa", "Chalet"
- payment_type   : one of "cash", "installments" only if user explicitly mentions it
- Downpayment    : down-payment amount in EGP as an integer (only if user mentioned installments)
- monthlyinstall : monthly installment in EGP as an integer (only if user mentioned installments)

User message: \"{user_input}\"

Respond ONLY with valid JSON. Use null for any field you cannot extract.
Example:
{{
  "purpose": "invest",
  "budget": 3000000,
  "location": "New Cairo",
  "typeofproperty": "Apartment",
  "payment_type": "cash",
  "Downpayment": null,
  "monthlyinstall": null
}}
"""

    raw = ask_ollama(extraction_prompt)
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        extracted = json.loads(raw)
    except json.JSONDecodeError:
        state["_extraction_done"] = True  # don't loop even if parse fails
        return state

    # Apply extracted values
    purpose = _normalize_purpose(extracted.get("purpose") or "")
    if purpose:
        state["purpose"] = purpose

    budget = _parse_numeric(extracted.get("budget"))
    if budget and budget > 0:
        state["budget"] = budget

    location = (extracted.get("location") or "").strip()
    if location:
        state["location"] = location.title()

    prop_type = _normalize_property_type(extracted.get("typeofproperty") or "")
    if prop_type:
        state["typeofproperty"] = prop_type

    pay_type = _normalize_payment_type(extracted.get("payment_type") or "")
    if pay_type:
        state["payment_type"] = pay_type

    dp = _parse_numeric(extracted.get("Downpayment"))
    if dp and dp > 0:
        state["Downpayment"] = dp

    mi = _parse_numeric(extracted.get("monthlyinstall"))
    if mi and mi > 0:
        state["monthlyinstall"] = mi

    # Mark extraction as done so the router moves forward
    state["_extraction_done"] = True
    state["user_input"] = None  # consumed

    return state
