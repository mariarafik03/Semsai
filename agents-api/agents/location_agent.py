"""
Location Agent — determines preferred location + property type.
"""
from typing import Any
from llm_helper import ask_llm


PROPERTY_MAP = {
    "villa": "Villa",
    "vila": "Villa",
    "apartment": "Apartment",
    "flat": "Apartment",
    "شقة": "Apartment",
    "شقه": "Apartment",
    "فيلا": "Villa",
    "chalet": "Chalet",
    "شاليه": "Chalet",
}


def _extract_property_type(text: str) -> str | None:
    text_lower = text.lower()
    for key, value in PROPERTY_MAP.items():
        if key in text_lower:
            return value
    return None


def location_agent(state: dict[str, Any], user_input: str | None) -> dict[str, Any]:
    """
    Sub-phases:
      ask_location → extract_location → ask_type → extract_type
    """
    sub = state.get("sub_phase")

    # ---- Ask location ----
    if sub is None or sub == "ask_location":
        question = ask_llm(
            "You are a friendly real estate assistant. "
            "Ask the user where they would like to buy a property in Egypt. "
            "Keep it short (1-2 sentences). Do not answer yourself."
        )
        state["sub_phase"] = "extract_location"
        state["agent_message"] = question
        state["awaiting_input"] = True
        return state

    if sub == "extract_location" and user_input:
        extracted = ask_llm(
            "Extract ONLY the location from the user input. "
            "It must be inside Greater Cairo or the North Coast. "
            "Capitalize the first letter of each word like (New Cairo, New Capital). "
            f"User input: '{user_input}'"
        ).strip()

        if extracted and len(extracted) < 60:
            state["location"] = extracted.title()
            state["sub_phase"] = "ask_type"
            state["awaiting_input"] = False
            state["agent_message"] = None
        else:
            state["agent_message"] = "I couldn't recognize that location. Could you try again?"
            state["sub_phase"] = "extract_location"
            state["awaiting_input"] = True
        return state

    # ---- Ask property type ----
    if sub == "ask_type":
        question = ask_llm(
            "Ask the user what type of property they are interested in "
            "(apartment, villa, chalet). Keep it short and friendly."
        )
        state["sub_phase"] = "extract_type"
        state["agent_message"] = question
        state["awaiting_input"] = True
        return state

    if sub == "extract_type" and user_input:
        llm_output = ask_llm(
            "Extract ONLY the type of property from the user input. "
            "Return only one word (Apartment, Villa, or Chalet). "
            f"User input: '{user_input}'"
        )
        normalized = _extract_property_type(llm_output) or _extract_property_type(user_input)

        if normalized:
            state["typeofproperty"] = normalized
            state["phase"] = "processing"
            state["sub_phase"] = None
            state["awaiting_input"] = False
            state["agent_message"] = f"Got it! Looking for {normalized}s in {state.get('location', 'your area')}..."
        else:
            state["agent_message"] = "Sorry, I only support Apartment, Villa, or Chalet. Could you repeat that?"
            state["sub_phase"] = "extract_type"
            state["awaiting_input"] = True
        return state

    return state
