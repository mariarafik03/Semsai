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
    """Try to pull an integer out of a value that might be a string, int, or None."""
    if raw is None:
        return None
    raw_str = str(raw).strip().replace(",", "").replace("_", "")
    digits = "".join(filter(str.isdigit, raw_str))
    if digits:
        return int(digits)
    return None


# ---------------------------------------------------------------------------
# Extraction Agent
# ---------------------------------------------------------------------------

def extraction_agent(state: AgentState) -> AgentState:
    """
    Entry-point agent.  Greets the user, collects their opening message,
    then uses the LLM to extract every recognisable field in one pass.

    Fields it tries to extract:
        purpose, budget, location, typeofproperty, payment_type,
        Downpayment, monthlyinstall
    """

    print("\n--- Extraction Agent ---")

    # Greet the user and collect their opening message
    greeting = ask_ollama(
        "You are a friendly, premium real estate assistant in Egypt. "
        "Start a warm shortconversation and invite the user to tell you everything "
        "they have in mind about the property they are looking for — purpose, "
        "budget, preferred area, type of property, payment method, etc. "
        "Encourage them to share as much as they want in a single message. "
        "Do not answer for them, just ask."
    )
    print(f"Agent: {greeting}")
    user_input = input("You: ").strip()

    if not user_input:
        # Nothing to extract — downstream agents will ask everything
        state["user_input"] = ""
        return state

    state["user_input"] = user_input

    # ---- LLM extraction ----
    extraction_prompt = f"""
You are a real estate data extraction engine.

From the following user message, extract as many of these fields as you can.
Only include a field if the user **clearly** mentioned it; do NOT guess.

Fields to extract:
- purpose        : one of "rent", "invest", "live"  (if the user says "buy" with no further detail, leave null)
- budget         : total budget in EGP as an integer (convert shorthand like "3M" to 3000000, "500k" to 500000)
- location       : area/city in Egypt  (capitalize each word, e.g. "New Cairo")
- typeofproperty : one of "Apartment", "Villa", "Chalet"
- payment_type   : one of "cash", "installments" ony if user explicitly mentions it
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

    # Strip markdown fences the LLM sometimes adds
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        extracted = json.loads(raw)
    except json.JSONDecodeError:
        print("   (Could not parse extraction — downstream agents will ask.)")
        return state

    # ---- Apply extracted values with validation ----

    # Purpose
    purpose = _normalize_purpose(extracted.get("purpose") or "")
    if purpose:
        state["purpose"] = purpose
        print(f"   ✓ Purpose: {purpose}")

    # Budget
    budget = _parse_numeric(extracted.get("budget"))
    if budget and budget > 0:
        state["budget"] = budget
        print(f"   ✓ Budget: {budget:,} EGP")

    # Location
    location = (extracted.get("location") or "").strip()
    if location:
        state["location"] = location.title()
        print(f"   ✓ Location: {state['location']}")

    # Property type
    prop_type = _normalize_property_type(extracted.get("typeofproperty") or "")
    if prop_type:
        state["typeofproperty"] = prop_type
        print(f"   ✓ Property type: {prop_type}")

    # Payment type
    pay_type = _normalize_payment_type(extracted.get("payment_type") or "")
    if pay_type:
        state["payment_type"] = pay_type
        print(f"   ✓ Payment type: {pay_type}")

    # Down-payment
    dp = _parse_numeric(extracted.get("Downpayment"))
    if dp and dp > 0:
        state["Downpayment"] = dp
        print(f"   ✓ Down-payment: {dp:,} EGP")

    # Monthly installment
    mi = _parse_numeric(extracted.get("monthlyinstall"))
    if mi and mi > 0:
        state["monthlyinstall"] = mi
        print(f"   ✓ Monthly installment: {mi:,} EGP")

    # Summarise what's still missing
    missing = []
    if not state.get("purpose"):
        missing.append("purpose")
    if not state.get("budget") and not (state.get("Downpayment") and state.get("monthlyinstall")):
        missing.append("budget / payment details")
    if not state.get("location"):
        missing.append("location")
    if not state.get("typeofproperty"):
        missing.append("property type")

    if missing:
        print(f"   ℹ Still needed: {', '.join(missing)}  — will be asked next.")
    else:
        print("   ✅ All key info extracted!")

    return state
