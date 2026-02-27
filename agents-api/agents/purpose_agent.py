from state import AgentState
from main_helpers import ask_ollama


def purpose_agent(state: AgentState):
    """
    Determines user's purpose (rent/invest/live).
    Non-blocking: uses pending_question + user_input pattern.
    """

    # Skip if already resolved
    if state.get("purpose"):
        state["next_step"] = "budget_agent"
        return state

    user_input = state.get("user_input")

    # Phase 1: No input yet — ask the user
    if not user_input:
        question = ask_ollama(
            "Start a friendly conversation with the user and ask why they are interested in real estate. "
            "Do not answer yourself."
        )
        state["pending_question"] = question
        return state

    # Phase 2: Extract purpose from user input
    purpose = ask_ollama(
        f"Extract ONLY one purpose from user input (rent, invest, live): '{user_input}'"
    ).strip().lower()

    if purpose in ["rent", "invest", "live"]:
        # Confirm with user
        if not state.get("_purpose_confirming"):
            state["_purpose_confirming"] = purpose
            state["pending_question"] = f"So, you want to buy a property to {purpose}? Please reply yes or no."
            state["user_input"] = None  # clear for next round
            return state
    elif state.get("_purpose_confirming"):
        # User is responding to confirmation
        confirming_purpose = state.pop("_purpose_confirming")
        if user_input.strip().lower() in ["yes", "نعم", "اه", "يس", "اى", "y"]:
            state["purpose"] = confirming_purpose
            state["next_step"] = "budget_agent"
        else:
            state["retry"] = True
            state["next_step"] = "questioning_agent"
        state["user_input"] = None
        return state
    else:
        state["retry"] = True
        state["next_step"] = "questioning_agent"

    return state
