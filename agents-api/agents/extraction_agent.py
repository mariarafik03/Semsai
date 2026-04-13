"""
agents/extraction_agent.py  (HTTP-safe refactor)
─────────────────────────────────────────────────
Turn 1 (waiting_for is None, user_input is None):
    → greet the user, set waiting_for = "opening_message", return

Turn 2 (waiting_for == "opening_message", user_input has their text):
    → extract fields from user_input, update state, clear waiting_for, return
"""

import json
from state import AgentState
from main_helpers import ask_ollama
# Import the new normalization logic
from Normalization import normalize_location

VALID_PURPOSES      = {"rent", "invest", "live"}
VALID_PAYMENT_TYPES = {"cash", "installments"}
VALID_PROPERTY_TYPES = {"Apartment", "Villa", "Chalet"}

PROPERTY_ALIASES = {
    "villa":      "Villa",
    "vila":       "Villa",
    "apartment":  "Apartment",
    "flat":       "Apartment",
    "chalet":     "Chalet",
}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_purpose(raw: str) -> str | None:
    raw = raw.strip().lower()
    return raw if raw in VALID_PURPOSES else None


def _normalize_payment_type(raw: str) -> str | None:
    raw = raw.strip().lower()
    return raw if raw in VALID_PAYMENT_TYPES else None


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
    return int(digits) if digits else None


# ---------------------------------------------------------------------------
# Agent (re-entrant, no input())
# ---------------------------------------------------------------------------

def extraction_agent(state: AgentState) -> AgentState:
    """
    Re-entrant entry-point agent that uses Normalization.py for location mapping.
    """

    # ── Turn 2: we have the user's opening message ───────────────────────
    if state.get("waiting_for") == "opening_message":
        user_input = (state.get("user_input") or "").strip()
        state["waiting_for"] = None   # clear pause flag

        if not user_input:
            state["user_input"] = ""
            return state

        # ---- LLM extraction ----
        extraction_prompt = f"""
You are a real estate data extraction engine.
From the following user message, extract as many of these fields as you can.
Only include a field if the user **clearly** mentioned it; do NOT guess.

Fields to extract:
- purpose        : one of "rent", "invest", "live"
- budget         : total budget in EGP as an integer (convert "3M"→3000000, "500k"→500000)
- location       : area/city name (extract the raw text used by the user)
- typeofproperty : one of "Apartment", "Villa", "Chalet"
- payment_type   : one of "cash", "installments"
- Downpayment    : down-payment in EGP as integer
- monthlyinstall : monthly installment in EGP as integer

User message: \"{user_input}\"

Respond ONLY with valid JSON. Use null for missing fields.
"""
        raw = ask_ollama(extraction_prompt)
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        try:
            extracted = json.loads(raw)
            print(f"DEBUG [extraction_agent]: Extracted JSON data -> {extracted}")
        except json.JSONDecodeError:
            return state

        # Apply extracted values with enhanced location normalization
        if purpose := _normalize_purpose(extracted.get("purpose") or ""):
            state["purpose"] = purpose

        if (budget := _parse_numeric(extracted.get("budget"))) and budget > 0:
            state["budget"] = budget

        # --- UPDATED LOCATION LOGIC ---
        if raw_loc := extracted.get("location"):
            # Use the external dictionary-based normalizer
            normalized_loc = normalize_location(raw_loc)
            if normalized_loc:
                state["location"] = normalized_loc
            else:
                # Fallback to Title Case if not in the dictionary
                state["location"] = raw_loc.strip().title()
        # ------------------------------

        if prop_type := _normalize_property_type(extracted.get("typeofproperty") or ""):
            state["typeofproperty"] = prop_type

        if pay_type := _normalize_payment_type(extracted.get("payment_type") or ""):
            state["payment_type"] = pay_type

        if (dp := _parse_numeric(extracted.get("Downpayment"))) and dp > 0:
            state["Downpayment"] = dp

        if (mi := _parse_numeric(extracted.get("monthlyinstall"))) and mi > 0:
            state["monthlyinstall"] = mi

        return state

    # ── Turn 1: greet and ask for opening message ────────────────────────
    greeting = ask_ollama(
        "You are a friendly, premium real estate assistant in Egypt. "
        "Start a warm short conversation and invite the user to tell you everything "
        "they have in mind about the property they are looking for."
    )

    state["agent_message"] = greeting
    state["waiting_for"]   = "opening_message"
    return state