"""
property_type_agent.py — Validate and normalize property type preference

RESPONSIBILITY
──────────────
Extract property type, validate it, handle errors and normalize it.

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
from agents.utils.extractors import extract_property_type
from agents.utils.validators import validate_property_type
from agents.utils.error_helpers import (
    should_retry,
    get_retry_message,
    format_give_up_message,
    get_remaining_retries
)


def property_type_agent(state: AgentState) -> AgentState:
    """
    Validate and normalize property type preference.
    
    Parameters
    ----------
    state : AgentState
        Current conversation state
    
    Returns
    -------
    AgentState
        Updated state
    """
    
    print("\n--- Property Type Agent ---")
    
    # ══════════════════════════════════════════════════════════════════
    # STEP 1: Check if we're waiting for this field
    # ══════════════════════════════════════════════════════════════════
    if state.waiting_for == "property_type":
        
        # Extract from user input
        extracted, confidence, _ = extract_property_type(state.user_input)
        
        if not extracted:
            # Couldn't extract → ask again or give up
            if should_retry(state, "property_type"):
                remaining = get_remaining_retries(state, "property_type")
                state.agent_message = get_retry_message(
                    "property_type",
                    "I didn't catch that. What type of property are you looking for? (apartment, villa, or chalet)",
                    remaining
                )
                state.add_error("property_type", state.user_input, "Could not extract")
            else:
                # Give up after max retries
                state.agent_message = format_give_up_message("property_type")
                state.waiting_for = None
                state.handoff_to_human = True
            
            state.sync_to_legacy()
            return state
        
        # Validate extracted value
        is_valid, normalized, error = validate_property_type(extracted)
        
        if is_valid:
            # ✅ Success! Save to context
            state.context.property_type = normalized
            state.waiting_for = None
            state.agent_message = f"Perfect! Looking for a {normalized}."
            print(f"✓ Property type set: {extracted} → {normalized}")
            
        else:
            # ❌ Validation failed
            if should_retry(state, "property_type"):
                remaining = get_remaining_retries(state, "property_type")
                state.agent_message = get_retry_message("property_type", error, remaining)
                state.add_error("property_type", extracted, error)
            else:
                # Give up
                state.agent_message = format_give_up_message("property_type")
                state.waiting_for = None
                state.handoff_to_human = True
        
        state.sync_to_legacy()
        return state
    
    # ══════════════════════════════════════════════════════════════════
    # STEP 2: Check if field is missing
    # ══════════════════════════════════════════════════════════════════
    if not state.context.property_type:
        state.agent_message = "What type of property are you looking for? (apartment, villa, or chalet)"
        state.waiting_for = "property_type"
        state.sync_to_legacy()
        return state
    
    # ══════════════════════════════════════════════════════════════════
    # STEP 3: Field is valid, nothing to do
    # ══════════════════════════════════════════════════════════════════
    state.sync_to_legacy()
    return state