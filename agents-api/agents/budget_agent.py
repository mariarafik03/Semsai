"""
budget_agent.py — Validate budget against location and property type constraints

RESPONSIBILITY
──────────────
Extract budget, validate it against the database relying on property type
and location previously set.

WORKFLOW
────────
1. PREREQUISITE CHECK: Need location + property_type first
2. Check if waiting for this field
3. If waiting:
   - Extract from user input
   - Validate
   - Handle errors/retries
4. If field missing or not validated → ask for it
5. If field valid → clear waiting_for
"""

from state import AgentState
from agents.utils.extractors import extract_budget
from agents.utils.validators import validate_budget
from agents.utils.error_helpers import (
    should_retry,
    get_retry_message,
    format_give_up_message,
    get_remaining_retries
)



def budget_agent(state: AgentState) -> AgentState:
    """
    Validate budget against location and property type constraints.
    
    Parameters
    ----------
    state : AgentState
        Current conversation state
    
    Returns
    -------
    AgentState
        Updated state
    """
    
    print("\n--- Budget Agent ---")
    
    # ═══════════════════════════════════════════════════════════════
    # PREREQUISITE CHECK: Need location + property_type first
    # ═══════════════════════════════════════════════════════════════
    if not state.context.location_normalized or not state.context.property_type:
        print("⚠️ Budget validation requires location + property_type first")
        state.sync_to_legacy()
        return state
    
    # ═══════════════════════════════════════════════════════════════
    # STEP 1: If waiting for budget
    # ═══════════════════════════════════════════════════════════════
    if state.waiting_for == "budget":
        
        extracted, confidence, _ = extract_budget(state.user_input)
        
        if not extracted:
            if should_retry(state, "budget"):
                remaining = get_remaining_retries(state, "budget")
                state.agent_message = get_retry_message(
                    "budget",
                    "I didn't catch that. What's your budget? (e.g., 5 million, 500k)",
                    remaining
                )
                state.add_error("budget", state.user_input, "Could not extract")
            else:
                state.agent_message = format_give_up_message("budget")
                state.waiting_for = None
                state.handoff_to_human = True
            
            state.sync_to_legacy()
            return state
        
        # Validate against DB constraints
        is_valid, min_budget, error = validate_budget(
            extracted,
            state.context.location_normalized,
            state.context.property_type,
            db=None,  # reserved for future DB-backed min-price validation
        )
        
        if is_valid:
            state.context.budget = extracted
            state.context.budget_valid = True
            state.waiting_for = None
            state.agent_message = (
                f"Got it! Budget of {extracted:,.0f} EGP for "
                f"{state.context.property_type} in {state.context.location}."
            )
            print(f"✓ Budget validated: {extracted:,.0f} EGP")
            
        else:
            if should_retry(state, "budget"):
                remaining = get_remaining_retries(state, "budget")
                state.agent_message = get_retry_message("budget", error, remaining)
                state.add_error("budget", str(extracted), error)
            else:
                state.agent_message = format_give_up_message("budget")
                state.waiting_for = None
                state.handoff_to_human = True
        
        state.sync_to_legacy()
        return state
    
    # ═══════════════════════════════════════════════════════════════
    # STEP 2: If budget missing or not validated
    # ═══════════════════════════════════════════════════════════════
    if not state.context.budget or not state.context.budget_valid:
        state.agent_message = (
            f"What's your budget for a {state.context.property_type} "
            f"in {state.context.location}? (e.g., 5 million, 500k)"
        )
        state.waiting_for = "budget"
        state.sync_to_legacy()
        return state
    
    # ═══════════════════════════════════════════════════════════════
    # STEP 3: Budget valid
    # ═══════════════════════════════════════════════════════════════
    state.sync_to_legacy()
    return state