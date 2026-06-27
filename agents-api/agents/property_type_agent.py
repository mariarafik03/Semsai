from state import AgentState
from http_helpers import get_user_input
from .location_agent import extract_property_type

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


def property_type_agent(state: AgentState) -> AgentState:
    print("\n--- Property Type Agent ---")

    if state.get("typeofproperty"):
        return state

    question = "What type of property are you looking for? (Apartment, Villa, or Chalet)"

    if "_input_queue" in state:
        user_input = get_user_input(state, question)
    else:
        user_input = input("You: ").strip()

    normalized = extract_property_type(user_input)

    if normalized:
        state["typeofproperty"] = normalized
        print(f"✓ Property type set to: {normalized}")
    else:
        # Try matching directly against PROPERTY_MAP
        lowered = user_input.lower().strip()
        for key, value in PROPERTY_MAP.items():
            if key in lowered:
                state["typeofproperty"] = value
                print(f"✓ Property type set to: {value}")
                break
        else:
            print(f"Please choose one of: {SUPPORTED_TYPES_MSG}.")

    state["next_step"] = "budget_agent"
    return state