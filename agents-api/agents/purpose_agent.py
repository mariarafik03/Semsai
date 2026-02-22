"""
Purpose Agent — determines if user wants to rent, invest, or live.
Refactored: no input(), returns state with agent_message + awaiting_input.
"""
from typing import Any
from llm_helper import ask_llm


def purpose_agent(state: dict[str, Any], user_input: str | None) -> dict[str, Any]:
    """
    Phases:
      - "ask"          → generate greeting question
      - "extract"      → extract purpose from user reply
      - "confirm"      → ask user to confirm purpose
      - "confirmed"    → user said yes/no to confirmation
    """
    sub = state.get("sub_phase")

    # ---- FIRST CALL: generate greeting ----
    if sub is None or sub == "ask":
        question = ask_llm(
            "You are a friendly real estate assistant helping users in Egypt. "
            "Start a warm conversation and ask why they are interested in real estate. "
            "Keep it short (1-2 sentences). Do not answer for the user."
        )
        state["sub_phase"] = "extract"
        state["agent_message"] = question
        state["awaiting_input"] = True
        return state

    # ---- USER REPLIED: extract purpose ----
    if sub == "extract" and user_input:
        state["user_input"] = user_input

        purpose = ask_llm(
            f"Extract ONLY one purpose from user input (rent, invest, live): '{user_input}'"
        ).strip().lower()

        # Clean up — sometimes LLM returns extra text
        for p in ["rent", "invest", "live"]:
            if p in purpose:
                purpose = p
                break

        if purpose in ["rent", "invest", "live"]:
            state["pending_confirmation"] = purpose
            state["sub_phase"] = "confirm"
            state["agent_message"] = f"So you want to buy a property to {purpose}? Please confirm (yes/no)."
            state["awaiting_input"] = True
        else:
            # Couldn't extract — go to questioning agent
            state["retry"] = True
            state["phase"] = "questioning"
            state["sub_phase"] = None
            state["awaiting_input"] = False  # no input needed, auto-advance
            state["agent_message"] = None
        return state

    # ---- CONFIRMATION ----
    if sub == "confirm" and user_input:
        answer = user_input.strip().lower()
        if answer in ["yes", "y", "yeah", "أيوه", "اه", "نعم", "اة", "يس"]:
            state["purpose"] = state["pending_confirmation"]
            state["phase"] = "budget"
            state["sub_phase"] = None
            state["awaiting_input"] = False
            state["agent_message"] = None
        else:
            state["retry"] = True
            state["phase"] = "questioning"
            state["sub_phase"] = None
            state["awaiting_input"] = False
            state["agent_message"] = None
        return state

    return state
