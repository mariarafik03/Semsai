"""
property_type_agent.py — Validate and normalize property type preference

RESPONSIBILITY
──────────────
Extract property type, validate it, handle errors and normalize it.
All messages written by the LLM via agents.llm_messages.
"""

from state import AgentState
from agents.utils.extractors import extract_property_type
from agents.utils.validators import validate_property_type
from agents.utils.error_helpers import should_retry, get_remaining_retries
from agents.llm_messages import (
    ask_for_property_type,
    property_type_confirmed,
    property_type_retry,
    property_type_give_up,
)


def property_type_agent(state: AgentState) -> AgentState:
    print("\n--- Property Type Agent ---")

    # ══════════════════════════════════════════════════════════════════
    # STEP 1: Check if we're waiting for this field
    # ══════════════════════════════════════════════════════════════════
    if state.waiting_for == "property_type":

        extracted, confidence, _ = extract_property_type(state.user_input)

        if not extracted:
            if should_retry(state, "property_type"):
                remaining = get_remaining_retries(state, "property_type")
                state.agent_message = property_type_retry(
                    "I didn't catch that. What type of property are you looking for? (apartment, villa, or chalet)",
                    remaining,
                    state,
                )
                state.add_error("property_type", state.user_input, "Could not extract")
            else:
                state.agent_message = property_type_give_up(state)
                state.waiting_for = None
                state.handoff_to_human = True

            state.sync_to_legacy()
            return state

        is_valid, normalized, error = validate_property_type(extracted)

        if is_valid:
            state.context.property_type = normalized
            state.waiting_for = None
            state.agent_message = property_type_confirmed(normalized, state)
            print(f"✓ Property type set: {extracted} → {normalized}")
        else:
            if should_retry(state, "property_type"):
                remaining = get_remaining_retries(state, "property_type")
                state.agent_message = property_type_retry(error, remaining, state)
                state.add_error("property_type", extracted, error)
            else:
                state.agent_message = property_type_give_up(state)
                state.waiting_for = None
                state.handoff_to_human = True

        state.sync_to_legacy()
        return state

    # ══════════════════════════════════════════════════════════════════
    # STEP 2: Check if field is missing
    # ══════════════════════════════════════════════════════════════════
    if not state.context.property_type:
        state.agent_message = ask_for_property_type(state)
        state.waiting_for = "property_type"
        state.sync_to_legacy()
        return state

    state.sync_to_legacy()
    return state
