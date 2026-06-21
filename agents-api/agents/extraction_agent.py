"""
extraction_agent.py — Extract ALL fields from the user's first message

RESPONSIBILITY
──────────────
Extract all possible fields from user's initial message.
Only saves high-confidence extractions to avoid false positives.
Validation happens in specialized agents.

WORKFLOW
────────
1. Extract all fields at once from state.user_input
2. Save HIGH-confidence extractions only to state.context
3. Log extraction results
"""

from state import AgentState
from agents.utils.extractors import extract_all_fields

# ── Field-owner map ──────────────────────────────────────────────────────────
# Mirrors the waiting_for routing block in graph_definition.state_router.
# Imported lazily inside the function (not at module load time) to avoid any
# risk of circular imports while keeping a single source of truth for which
# agent owns which field.
def _field_agent_for(waiting_for: str):
    from agents.location_agent      import location_agent
    from agents.property_type_agent import property_type_agent
    from agents.payment_agent       import payment_agent
    from agents.budget_agent        import budget_agent
    from agents.compounds_agent     import compounds_agent
    from agents.developers_agent    import developers_agent

    return {
        "location":             location_agent,
        "property_type":        property_type_agent,
        "payment_type":         payment_agent,
        "downpayment":          payment_agent,
        "monthly_installment":  payment_agent,
        "budget":               budget_agent,
        "no_units_response":    compounds_agent,
        "no_developer_response": developers_agent,
    }.get(waiting_for)


def extraction_agent(state: AgentState) -> AgentState:
    """
    Extract all possible fields from user's initial message.
    
    Only saves high-confidence extractions to avoid false positives.
    Validation happens in specialized agents.
    
    Parameters
    ----------
    state : AgentState
        Current conversation state
    
    Returns
    -------
    AgentState
        Updated state with extracted fields in context
    """
    
    print("\n--- Extraction Agent ---")

    # ── FIX: If we're already waiting for a field, this agent is being
    # resumed because graph_current_node was saved as "extraction_agent"
    # when the graph paused (extraction_agent set waiting_for on turn 1,
    # and graph.step() always re-pins the cursor on whichever node was just
    # run while waiting_for stays set — it never re-pins to the agent that
    # actually owns the field).
    #
    # Just returning here (the old behavior) does NOT "let the router
    # fire" — graph.step() only consults the router once waiting_for is
    # empty. Returning untouched keeps waiting_for set, so the cursor stays
    # pinned on extraction_agent forever and the conversation never
    # progresses past the opening question.
    #
    # The real fix: actively delegate to the agent that owns the current
    # waiting_for field, so it can process this turn's answer and clear
    # waiting_for itself. Once it does, graph.step() will consult the
    # router normally and the graph advances.
    if state.waiting_for:
        field_agent = _field_agent_for(state.waiting_for)
        if field_agent:
            print(f"↩️  Resuming with waiting_for='{state.waiting_for}' — delegating to {field_agent.__name__}")
            return field_agent(state)

        # Unknown waiting_for value — clear it rather than looping forever,
        # and let the router decide what to do next.
        print(f"⚠️ Unknown waiting_for='{state.waiting_for}' — clearing and handing off to router")
        state.waiting_for = None
        state.sync_to_legacy()
        return state

    # Handle empty input — this happens if the graph is ever invoked with no
    # user message (e.g. an unexpected /chat/respond with empty body).
    # Rather than returning silently (which causes the router to loop until the
    # MAX_STEPS guard fires and shows the user an error), we pause the graph
    # here by setting waiting_for so the runner surfaces the welcome question.
    if not state.user_input or not state.user_input.strip():
        print("⚠️ No user input to extract from — asking opening question")
        if not state.waiting_for:
            state.agent_message = (
                "Hello! I'm your real estate assistant. "
                "Which city or area are you looking in? "
                "(e.g., New Cairo, Sheikh Zayed, North Coast)"
            )
            state.waiting_for = "location"
        state.sync_to_legacy()
        return state
    
    # Extract all fields at once
    extracted = extract_all_fields(state.user_input)
    
    # Track successful extractions
    extracted_count = 0
    
    # Save HIGH-confidence extractions only
    for field_name, (value, confidence) in extracted.items():
        if value and confidence == "high":
            # Map field names to context attributes
            if field_name == "location":
                state.context.location = value
            elif field_name == "property_type":
                state.context.property_type = value
            elif field_name == "payment_type":
                state.context.payment_type = value
            elif field_name == "budget":
                state.context.budget = value
            elif field_name == "downpayment":
                state.context.downpayment = value
            elif field_name == "monthly_installment":
                state.context.monthly_installment = value
            
            print(f"  ✓ {field_name}: {value}")
            extracted_count += 1
    
    # Summary
    if extracted_count > 0:
        print(f"📊 Extracted {extracted_count}/6 fields with high confidence")
    else:
        print("ℹ️ No high-confidence extractions found (other agents will ask)")
    
    state.sync_to_legacy()
    return state