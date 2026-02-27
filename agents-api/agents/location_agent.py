from state import AgentState
from main_helpers import ask_ollama

# ---- Constants ----
MAX_RETRIES = 3

VALID_LOCATIONS = {
    "new cairo", "new capital", "north coast", "6th of october",
    "maadi", "zamalek", "heliopolis", "nasr city", "sheikh zayed",
    "fifth settlement", "obour", "shorouk", "mostakbal city",
    "ain sokhna", "ras el hekma", "sahel", "marassi", "sidi abdel rahman"
}

PROPERTY_MAP = {
    "villa": "Villa",
    "vila": "Villa",
    "apartment": "Apartment",
    "flat": "Apartment",
    "chalet": "Chalet",
    "studio": "Apartment",
    "penthouse": "Apartment",
    "duplex": "Apartment",
    "townhouse": "Villa",
}

SUPPORTED_TYPES_MSG = "Apartment, Villa, or Chalet"


# ---- Helpers ----

def safe_ask_ollama(prompt: str) -> str | None:
    try:
        result = ask_ollama(prompt)
        if result is None:
            return None
        return result.strip()
    except Exception as e:
        print(f"[ERROR] LLM call failed: {e}")
        return None


def extract_property_type(llm_output: str) -> str | None:
    if not llm_output:
        return None
    llm_output = llm_output.lower()
    for key, value in PROPERTY_MAP.items():
        if key in llm_output:
            return value
    return None


def is_valid_location(extracted: str) -> bool:
    if not extracted:
        return False
    lowered = extracted.lower().strip()
    for loc in VALID_LOCATIONS:
        if loc in lowered or lowered in loc:
            return True
    return False


# ---- Main Agent (Non-blocking) ----

def location_agent(state: AgentState) -> AgentState:
    """
    Collects location and property type.
    Non-blocking: uses pending_question + user_input pattern.

    Internal state tracking via _location_step:
      "location" → asking where
      "property_type" → asking what type
    """

    user_input = state.get("user_input")
    step = state.get("_location_step", "init")

    # ── Determine starting step ──
    if step == "init":
        if not state.get("location"):
            step = "location"
        elif not state.get("typeofproperty"):
            step = "property_type"
        else:
            return state
        state["_location_step"] = step

    # ── Step: Location ──
    if step == "location":
        if state.get("location"):
            state["_location_step"] = "property_type"
            # Fall through to property_type
        elif not user_input:
            question = safe_ask_ollama(
                "You are a friendly real estate assistant. "
                "Ask the user where they would like to buy a property in Egypt in a natural way. "
                "Do not answer yourself, just ask the question."
            )
            state["pending_question"] = question or "Where would you like to buy a property? (e.g., New Cairo, North Coast)"
            return state
        else:
            # Extract location from user input
            extracted_location = safe_ask_ollama(
                "Extract ONLY the location name from the user input. "
                "It must be a real area inside Greater Cairo or the North Coast of Egypt. "
                "Capitalize the first letter of each word (e.g., New Cairo, New Capital, North Coast). "
                "Return ONLY the location name, nothing else. "
                f"User input: '{user_input}'"
            )

            if extracted_location and is_valid_location(extracted_location):
                state["location"] = extracted_location.title()
                state["user_input"] = None
                state["_location_step"] = "property_type"
                # Fall through to property_type
            else:
                retries = state.get("_location_retries", 0) + 1
                state["_location_retries"] = retries

                if retries >= MAX_RETRIES:
                    state["pending_question"] = (
                        "I'm having trouble understanding the location. "
                        "Could you please type just the area name? For example: New Cairo, North Coast, Sheikh Zayed"
                    )
                else:
                    state["pending_question"] = (
                        f"I couldn't recognize that as a supported area. "
                        "We currently cover Greater Cairo (New Cairo, New Capital, Maadi, etc.) "
                        "and the North Coast. Could you try again?"
                    )
                state["user_input"] = None
                return state

        # Check if we still need property type
        step = state.get("_location_step", "property_type")

    # ── Step: Property Type ──
    if step == "property_type":
        if state.get("typeofproperty"):
            state.pop("_location_step", None)
            return state

        if not user_input:
            question = safe_ask_ollama(
                f"Ask the user what type of property they are interested in "
                f"({SUPPORTED_TYPES_MSG}). Keep it short and friendly."
            )
            state["pending_question"] = question or f"What type of property are you looking for? ({SUPPORTED_TYPES_MSG})"
            return state

        # Extract property type from user input
        llm_type_output = safe_ask_ollama(
            "Extract ONLY the type of property from the user input. "
            f"Return only one word: Apartment, Villa, or Chalet. "
            "If the user says studio, penthouse, or duplex, return Apartment. "
            "If the user says townhouse, return Villa. "
            f"User input: '{user_input}'"
        )

        normalized_type = extract_property_type(llm_type_output)

        if normalized_type:
            state["typeofproperty"] = normalized_type
            state["user_input"] = None
            state.pop("_location_step", None)
            return state
        else:
            state["pending_question"] = (
                f"I only support {SUPPORTED_TYPES_MSG}. "
                f"Could you pick one of those?"
            )
            state["user_input"] = None
            return state

    return state