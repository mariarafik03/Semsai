"""
location_agent.py — Validate and normalize user's location preference

RESPONSIBILITY
──────────────
Extract location, validate it against the database, handle errors and normalize it.

WORKFLOW
────────
1. Check if waiting for this field
2. If waiting:
   - Extract from user input
   - Validate
   - Handle errors/retries
3. If field missing → ask for it
4. If field valid → clear waiting_for
"""

from state import AgentState
from agents.utils.extractors import extract_location
from agents.utils.validators import validate_location
from agents.utils.error_helpers import (
    should_retry,
    get_remaining_retries,
)
from agents.llm_messages import (
    ask_for_location,
    location_confirmed,
    location_retry,
    location_give_up,
)
from database import get_db


def location_agent(state: AgentState) -> AgentState:
    print("\n--- Location Agent ---")

    db = get_db()

    # ══════════════════════════════════════════════════════════════════
    # STEP 1: Check if we're waiting for this field
    # ══════════════════════════════════════════════════════════════════
    if state.waiting_for == "location":

        extracted, confidence, _ = extract_location(state.user_input)

        if not extracted:
            if should_retry(state, "location"):
                remaining = get_remaining_retries(state, "location")
                state.agent_message = location_retry(
                    "I didn't catch that. Which city or area would you like?",
                    remaining,
                    state,
                )
                state.add_error("location", state.user_input, "Could not extract")
            else:
                state.agent_message = location_give_up(state)
                state.waiting_for = None
                state.handoff_to_human = True

            state.sync_to_legacy()
            return state

        is_valid, normalized, error = validate_location(extracted, db)

        if is_valid:
            state.context.location = extracted
            state.context.location_normalized = normalized
            state.waiting_for = None
            state.agent_message = location_confirmed(normalized, state)
            print(f"✓ Location set: {extracted} → {normalized}")
        else:
            if should_retry(state, "location"):
                remaining = get_remaining_retries(state, "location")
                state.agent_message = location_retry(error, remaining, state)
                state.add_error("location", extracted, error)
            else:
                state.agent_message = location_give_up(state)
                state.waiting_for = None
                state.handoff_to_human = True

        state.sync_to_legacy()
        return state

    # ══════════════════════════════════════════════════════════════════
    # STEP 2: Check if field is missing
    # ══════════════════════════════════════════════════════════════════
    if not state.context.location:
        state.agent_message = ask_for_location(state)
        state.waiting_for = "location"
        state.sync_to_legacy()
        return state

    # ══════════════════════════════════════════════════════════════════
    # STEP 3: location is set but may lack location_normalized
    # ══════════════════════════════════════════════════════════════════
    if not state.context.location_normalized:
        is_valid, normalized, error = validate_location(state.context.location, db)
        if is_valid:
            state.context.location_normalized = normalized
            print(f"✓ Location normalized (pre-filled): {state.context.location} → {normalized}")
        else:
            print(f"⚠️  Pre-filled location '{state.context.location}' failed validation: {error}")
            state.context.location = None
            state.agent_message = ask_for_location(state)
            state.waiting_for = "location"
            state.sync_to_legacy()
            return state

    state.sync_to_legacy()
    return state
