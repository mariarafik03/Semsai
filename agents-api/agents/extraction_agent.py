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
    # resumed as a passthrough (because graph_current_node was saved as
    # "extraction_agent" when the graph paused).  Don't re-extract —
    # just return so the router fires and dispatches to the correct
    # field agent (location_agent, property_type_agent, etc.).
    if state.waiting_for:
        print(f"↩️  Resuming with waiting_for='{state.waiting_for}' — passing through to field agent")
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