import re
from state import AgentState
from main_helpers import ask_ollama
from .Normalization import normalize_location
from http_helpers import get_user_input

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
    "studio": "Apartment",       # map studio → Apartment
    "penthouse": "Apartment",    # map penthouse → Apartment
    "duplex": "Apartment",       # map duplex → Apartment
    "townhouse": "Villa",        # map townhouse → Villa
}

SUPPORTED_TYPES_MSG = "Apartment, Villa, or Chalet"


# ---- Helpers ----

def safe_ask_ollama(prompt: str) -> str | None:
    """
    Wrapper around ask_ollama that catches all exceptions.
    Returns None on failure instead of crashing.
    """
    try:
        result = ask_ollama(prompt)
        if result is None:
            return None
        return result.strip()
    except Exception as e:
        print(f"[ERROR] LLM call failed: {e}")
        return None


def extract_property_type(llm_output: str) -> str | None:
    """
    Extract and normalize property type from LLM output.
    Returns None if no match found.
    """
    if not llm_output:
        return None
    llm_output = llm_output.lower()
    for key, value in PROPERTY_MAP.items():
        if key in llm_output:
            return value
    return None


def is_valid_location(extracted: str) -> bool:
    """
    Validates that the extracted location is within Greater Cairo or North Coast.
    Uses a known-locations list as a guardrail against LLM hallucinations.
    """
    if not extracted:
        return False
    lowered = extracted.lower().strip()
    # Check against known valid areas
    for loc in VALID_LOCATIONS:
        if loc in lowered or lowered in loc:
            return True
    return False


def handle_llm_failure(context: str) -> None:
    """Prints a consistent error message when the LLM fails."""
    print(f"[ERROR] The assistant encountered an issue with {context}. Please try again later.")


# ---- Main Agent ----

def location_agent(state: AgentState) -> AgentState:
    print("\n--- Location Agent ---")

    # =============================
    # 1️⃣ Location
    # =============================
    if state.get("location"):
        print(f"   Location already set: {state['location']}  — skipping.")
    else:
        question = safe_ask_ollama(
            "You are a friendly real estate assistant. "
            "Ask the user where they would like to buy a property in Egypt in a natural way. "
            "Do not answer yourself, just ask the question."
        )

        if question:
            print("Agent:", question)
        else:
            print("Agent: Where would you like to buy a property? (e.g., New Cairo, North Coast)")

        retries = 0
        while retries < MAX_RETRIES:
            if "_input_queue" in state:
                q = question or "Where would you like to buy a property?"
                user_location_input = get_user_input(state, q)
            else:
                user_location_input = input("You: ").strip()

            # Empty input
            if not user_location_input:
                print("Agent: Please enter a valid location in Egypt.")
                retries += 1
                continue

            # Input too long (likely a paragraph, not a location)
            if len(user_location_input) > 100:
                print("Agent: That seems too long. Please enter just the area name, e.g. 'New Cairo'.")
                retries += 1
                continue

            extracted_location = safe_ask_ollama(
                "Extract ONLY the location name from the user input. "
                "It must be a real area inside Greater Cairo or the North Coast of Egypt. "
                "Capitalize the first letter of each word (e.g., New Cairo, New Capital, North Coast). "
                "Return ONLY the location name, nothing else. "
                f"User input: '{user_location_input}'"
            )

            # LLM failed to respond
            if extracted_location is None:
                handle_llm_failure("location extraction")
                retries += 1
                continue

            # Try normalization first (handles slang like tagmo3, october, etc.)
            normalized = normalize_location(user_location_input) or normalize_location(extracted_location)

            if normalized:
                state["location"] = normalized
                print(f"   ✓ Location set to: {state['location']}")
                break

            # Validate the extracted location is actually in our supported areas
            if not is_valid_location(extracted_location):
                print(
                    f"Agent: I couldn't recognize '{extracted_location}' as a supported area. "
                    "We currently cover Greater Cairo (New Cairo, New Capital, Maadi, etc.) "
                    "and the North Coast. Could you try again?"
                )
                retries += 1
                continue

            state["location"] = extracted_location.title()
            print(f"   ✓ Location set to: {state['location']}")
            break

        else:
            print(
                f"Agent: I'm sorry, I couldn't capture a valid location after {MAX_RETRIES} attempts. "
                "Please restart and try again."
            )
            # Optionally raise or return early depending on your pipeline
            return state

    state["next_step"] = "property_type_agent"
    return state