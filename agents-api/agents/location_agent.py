"""
agents/location_agent.py  (HTTP-safe refactor)
───────────────────────────────────────────────
Handles two sub-steps sequentially:
  1. Collect location
  2. Collect property type

Each sub-step is a separate waiting_for value so we never lose track of
where we are between HTTP requests.

waiting_for values used
───────────────────────
"location_input"      → asked for location, waiting for answer
"location_retry_{n}"  → location was invalid, asking again (n = attempt count)
"property_type_input" → asked for property type, waiting for answer
"property_retry_{n}"  → type was invalid, asking again
"""

from state import AgentState
from main_helpers import ask_ollama

from .Normalization import normalize_location

MAX_RETRIES = 3

# We keep VALID_LOCATIONS for basic validation but use normalize_location for extraction
VALID_LOCATIONS = {
    "new cairo", "new capital", "north coast", "6th of october",
    "maadi", "zamalek", "heliopolis", "nasr city", "sheikh zayed",
    "fifth settlement", "obour", "shorouk", "mostakbal city",
    "ain sokhna", "ras el hekma", "sahel", "marassi", "sidi abdel rahman",
}

PROPERTY_MAP = {
    "villa": "Villa", "vila": "Villa",
    "apartment": "Apartment", "flat": "Apartment",
    "chalet": "Chalet", "studio": "Apartment",
    "penthouse": "Apartment", "duplex": "Apartment",
    "townhouse": "Villa",
}

SUPPORTED_TYPES_MSG = "Apartment, Villa, or Chalet"


def _safe_ask(prompt: str) -> str:
    try:
        result = ask_ollama(prompt)
        return (result or "").strip()
    except Exception as e:
        print(f"[ERROR] LLM call failed: {e}")
        return ""


def _is_valid_location(text: str) -> bool:
    if not text:
        return False
    # If it's already normalized, it's valid
    return True


def _extract_property_type(llm_output: str) -> str | None:
    if not llm_output:
        return None
    for key, value in PROPERTY_MAP.items():
        if key in llm_output.lower():
            return value
    return None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

def location_agent(state: AgentState) -> AgentState:

    user_input = (state.get("user_input") or "").strip()
    waiting    = state.get("waiting_for") or ""

    # ════════════════════════════════════════════════════════════════════
    # SECTION 1 — LOCATION
    # ════════════════════════════════════════════════════════════════════

    if not state.get("location"):

        # ── Returning with an answer ─────────────────────────────────────
        if waiting.startswith("location"):
            # Determine attempt number from flag (e.g. "location_retry_2" → 2)
            attempt = int(waiting.split("_")[-1]) if waiting.startswith("location_retry") else 1

            if not user_input or len(user_input) > 200:
                # Bad input — retry if attempts remain
                if attempt >= MAX_RETRIES:
                    state["agent_message"] = (
                        "I'm sorry, I couldn't capture a valid location after "
                        f"{MAX_RETRIES} attempts. Please restart."
                    )
                    state["abort"] = True
                    return state

                state["agent_message"] = (
                    "Please enter just the area name, e.g. 'New Cairo'."
                    if len(user_input) > 200
                    else "Please enter a valid location in Egypt."
                )
                state["waiting_for"] = f"location_retry_{attempt + 1}"
                return state

            # Try to normalize directly from user input first
            normalized = normalize_location(user_input)
            
            if not normalized:
                # If direct normalization fails, use LLM to extract then normalize
                raw_extracted = _safe_ask(
                    "Extract ONLY the location name from the user input. "
                    "Return ONLY the location name, nothing else. "
                    f"User input: '{user_input}'"
                )
                normalized = normalize_location(raw_extracted)

            if normalized:
                state["location"] = normalized
                state["waiting_for"] = None
                # Fall through to property-type section below
            else:
                if attempt >= MAX_RETRIES:
                    state["agent_message"] = (
                        f"I couldn't recognise a supported area after {MAX_RETRIES} attempts. "
                        "Please restart."
                    )
                    state["abort"] = True
                    return state

                state["agent_message"] = (
                    f"I couldn't recognise '{user_input}' as a supported area. "
                    "We cover Greater Cairo and the North Coast. Could you try again?"
                )
                state["waiting_for"] = f"location_retry_{attempt + 1}"
                return state

        else:
            # ── First time asking for location ───────────────────────────
            question = _safe_ask(
                "You are a friendly real estate assistant. "
                "Ask the user where they would like to buy a property in Egypt "
                "in a natural, friendly way. Do not answer yourself, just ask."
            ) or "Where would you like to buy? (e.g., New Cairo, North Coast)"

            state["agent_message"] = question
            state["waiting_for"]   = "location_input"
            return state

    # ════════════════════════════════════════════════════════════════════
    # SECTION 2 — PROPERTY TYPE
    # ════════════════════════════════════════════════════════════════════

    if not state.get("typeofproperty"):

        # ── Returning with an answer ─────────────────────────────────────
        if waiting.startswith("property"):
            attempt = int(waiting.split("_")[-1]) if waiting.startswith("property_retry") else 1

            if not user_input or len(user_input) > 100:
                if attempt >= MAX_RETRIES:
                    state["agent_message"] = (
                        f"I couldn't capture a valid property type after {MAX_RETRIES} attempts. "
                        "Please restart."
                    )
                    state["abort"] = True
                    return state

                state["agent_message"] = f"Please choose one of: {SUPPORTED_TYPES_MSG}."
                state["waiting_for"]   = f"property_retry_{attempt + 1}"
                return state

            llm_out = _safe_ask(
                "Extract ONLY the type of property from the user input. "
                f"Return only one word: Apartment, Villa, or Chalet. "
                "If the user says studio/penthouse/duplex → Apartment. "
                "If townhouse → Villa. "
                f"User input: '{user_input}'"
            )

            normalized = _extract_property_type(llm_out)

            if normalized:
                state["typeofproperty"] = normalized
                state["waiting_for"]    = None
                return state
            else:
                if attempt >= MAX_RETRIES:
                    state["agent_message"] = (
                        f"I only support {SUPPORTED_TYPES_MSG} after {MAX_RETRIES} attempts. "
                        "Please restart."
                    )
                    state["abort"] = True
                    return state

                state["agent_message"] = (
                    f"I only support {SUPPORTED_TYPES_MSG}. "
                    f"Could you pick one of those? (You said: '{user_input}')"
                )
                state["waiting_for"] = f"property_retry_{attempt + 1}"
                return state

        else:
            # ── First time asking for property type ──────────────────────
            question = _safe_ask(
                f"Ask the user what type of property they are interested in "
                f"({SUPPORTED_TYPES_MSG}). Keep it short and friendly."
            ) or f"What type of property are you looking for? ({SUPPORTED_TYPES_MSG})"

            state["agent_message"] = question
            state["waiting_for"]   = "property_type_input"
            return state

    # Both fields already set — nothing to do
    return state