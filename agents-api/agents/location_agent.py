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
    get_retry_message,
    format_give_up_message,
    get_remaining_retries
)
from database import get_db  # Assume this exists


def location_agent(state: AgentState) -> AgentState:
    """
    Validate and normalize user's location preference.
    
    Parameters
    ----------
    state : AgentState
        Current conversation state
    
    Returns
    -------
    AgentState
        Updated state
    """
    
    print("\n--- Location Agent ---")
    
    db = get_db()
    
    # ══════════════════════════════════════════════════════════════════
    # STEP 1: Check if we're waiting for this field
    # ══════════════════════════════════════════════════════════════════
    if state.waiting_for == "location":
        
        # Extract from user input
        extracted, confidence, _ = extract_location(state.user_input)
        
        if not extracted:
            # Couldn't extract → ask again or give up
            if should_retry(state, "location"):
                remaining = get_remaining_retries(state, "location")
                state.agent_message = get_retry_message(
                    "location",
                    "I didn't catch that. Which city or area would you like?",
                    remaining
                )
                state.add_error("location", state.user_input, "Could not extract")
            else:
                # Give up after max retries
                state.agent_message = format_give_up_message("location")
                state.waiting_for = None
                state.handoff_to_human = True
            
            state.sync_to_legacy()
            return state
        
        # Validate extracted value
        is_valid, normalized, error = validate_location(extracted, db)
        
        if is_valid:
            # ✅ Success! Save to context
            state.context.location = extracted
            state.context.location_normalized = normalized
            state.waiting_for = None
            state.agent_message = f"Great! I'll search for properties in {normalized}."
            print(f"✓ Location set: {extracted} → {normalized}")
            
        else:
            # ❌ Validation failed
            if should_retry(state, "location"):
                remaining = get_remaining_retries(state, "location")
                state.agent_message = get_retry_message("location", error, remaining)
                state.add_error("location", extracted, error)
            else:
                # Give up
                state.agent_message = format_give_up_message("location")
                state.waiting_for = None
                state.handoff_to_human = True
        
        state.sync_to_legacy()
        return state
    
    # ══════════════════════════════════════════════════════════════════
    # STEP 2: Check if field is missing
    # ══════════════════════════════════════════════════════════════════
    if not state.context.location:
        state.agent_message = "Which city or area are you interested in? (e.g., Cairo, New Cairo, North Coast)"
        state.waiting_for = "location"
        state.sync_to_legacy()
        return state
    
    # ══════════════════════════════════════════════════════════════════
    # STEP 3: location is set but may lack location_normalized
    # (happens when extraction_agent pre-fills location without going
    # through validation — the router will loop back here indefinitely
    # if location_normalized stays None).
    # ══════════════════════════════════════════════════════════════════
    if not state.context.location_normalized:
        is_valid, normalized, error = validate_location(state.context.location, db)
        if is_valid:
            state.context.location_normalized = normalized
            print(f"✓ Location normalized (pre-filled): {state.context.location} → {normalized}")
        else:
            # Pre-filled value is invalid — clear it and ask the user
            print(f"⚠️  Pre-filled location '{state.context.location}' failed validation: {error}")
            state.context.location = None
            state.agent_message = "Which city or area are you interested in? (e.g., Cairo, New Cairo, North Coast)"
            state.waiting_for = "location"
            state.sync_to_legacy()
            return state

    state.sync_to_legacy()
    return state