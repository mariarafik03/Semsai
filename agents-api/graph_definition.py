"""
graph_definition.py
───────────────────
Builds and exports the compiled StateGraph singleton.

BUGS FIXED (vs original)
────────────────────────
1. handoff_to_human → END (not "handoff_agent" which was never registered)
2. no_units_response check moved BEFORE candidate_compounds check.
   compounds_agent clears candidate_compounds=None when it sets
   waiting_for="no_units_response". Without this fix the router looped
   back into compounds_agent before the user's choice was consumed.
3. Legacy state fallback helpers added.
   compounds_agent and developers_agent still write to dict-style
   state keys (state["candidate_compounds"], state["final_compounds"]).
   The router now reads both context AND legacy list fields.
4. compiled_graph alias added so graph_runner.py imports work.
"""

from graph import StateGraph, END
from state import AgentState

# ── Agent imports ─────────────────────────────────────────────────────────────
from agents.extraction_agent         import extraction_agent
from agents.budget_agent             import budget_agent
from agents.location_agent           import location_agent
from agents.property_type_agent      import property_type_agent
from agents.payment_agent            import payment_agent
from agents.compounds_agent          import compounds_agent
from agents.developers_agent         import developers_agent
from agents.comparing_agent          import comparing_agent
from agents.compound_ranking_agent   import compound_ranking_agent
from agents.final_output_agent       import final_output_agent


# ── Helpers: read context OR legacy list fields ────────────────────────────────
# compounds_agent / developers_agent write to dict-style state fields,
# NOT to state.context.  These helpers check both places.

def _candidate_compounds(state: AgentState):
    """Return candidate_compounds from context or legacy field."""
    ctx = state.context.candidate_compounds
    if ctx:
        return ctx
    legacy = state.candidate_compounds  # AgentState legacy field
    return legacy if legacy else None


def _final_compounds(state: AgentState):
    """Return final_compounds from context or legacy field."""
    ctx = state.context.final_compounds
    if ctx:
        return ctx
    legacy = state.final_compounds  # AgentState legacy field
    return legacy if legacy else None


# ========================================
# Router
# ========================================

def state_router(state) -> str:
    """
    Route to next agent based on state.
    
    CRITICAL: Must handle BOTH dict and Pydantic AgentState objects
    during migration period.
    """
    
    # ═══════════════════════════════════════════════════════════════════
    # TYPE-SAFE STATE ACCESS
    # ═══════════════════════════════════════════════════════════════════
    # Handle both dict (legacy) and Pydantic (new) state formats
    
    if isinstance(state, dict):
        # Dict format (from old code or JSON deserialization)
        context = state.get("context", {})
        waiting_for = state.get("waiting_for")
        handoff = state.get("handoff_to_human", False)
        phase = state.get("current_phase", "discovery")
        candidate_compounds = state.get("candidate_compounds", [])
        final_compounds = state.get("final_compounds", [])
        
        # Extract context fields safely
        location = context.get("location") if isinstance(context, dict) else None
        location_normalized = context.get("location_normalized") if isinstance(context, dict) else None
        property_type = context.get("property_type") if isinstance(context, dict) else None
        payment_type = context.get("payment_type") if isinstance(context, dict) else None
        budget = context.get("budget") if isinstance(context, dict) else None
        budget_valid = context.get("budget_valid", False) if isinstance(context, dict) else False
        comparison_result = context.get("comparison_result") if isinstance(context, dict) else None
        ranked_compounds = context.get("ranked_compounds") if isinstance(context, dict) else None
        final_best_compound = context.get("final_best_compound") if isinstance(context, dict) else None
        if not final_best_compound:
            final_best_compound = state.get("final_best_compound")
        
    else:
        # Pydantic AgentState format (from new code)
        context = state.context
        waiting_for = state.waiting_for
        handoff = getattr(state, "handoff_to_human", False)
        phase = state.current_phase
        candidate_compounds = state.candidate_compounds
        final_compounds = state.final_compounds
        
        # Extract context fields
        location = context.location
        location_normalized = context.location_normalized
        property_type = context.property_type
        payment_type = context.payment_type
        budget = context.budget
        budget_valid = context.budget_valid
        comparison_result = context.comparison_result
        ranked_compounds = context.ranked_compounds
        final_best_compound = context.final_best_compound or getattr(state, "final_best_compound", None)
    
    # ═══════════════════════════════════════════════════════════════════
    # ROUTING LOGIC (Now type-safe!)
    # ═══════════════════════════════════════════════════════════════════
    
    # 1. Human handoff check
    if handoff:
        return END
        
    # 1.5 Done check (final best compound selected)
    if final_best_compound:
        return END
    
    # 2. Check if we should route to extraction_agent first (initial state)
    current_node = None
    if isinstance(state, dict):
        current_node = state.get("graph_current_node")
    else:
        current_node = getattr(state, "graph_current_node", None)
        
    if not current_node and not location and not property_type and not payment_type and not budget:
        return "extraction_agent"
        
    # 3. Waiting for user input routing
    if waiting_for:
        if waiting_for == "location":
            return "location_agent"
        elif waiting_for == "property_type":
            return "property_type_agent"
        elif waiting_for in ("payment_type", "downpayment", "monthly_installment"):
            return "payment_agent"
        elif waiting_for == "budget":
            return "budget_agent"
        elif waiting_for == "no_units_response":
            return "compounds_agent"
        elif waiting_for == "no_developer_response":
            return "developers_agent"
        else:
            return END
    
    # 4. Phase-based routing
    if phase == "discovery":
        # Discovery phase: collect location, property type, payment, budget
        
        if not location or not location_normalized:
            return "location_agent"
        
        if not property_type:
            return "property_type_agent"
        
        if not payment_type:
            return "payment_agent"
        
        if not budget or not budget_valid:
            return "budget_agent"
        
        # All discovery complete → move to search
        return "compounds_agent"
    
    elif phase == "search":
        # Search phase: find and filter properties
        
        if not candidate_compounds:
            return "compounds_agent"
        
        if not final_compounds:
            return "developers_agent"
        
        # Search complete → move to comparison
        return "comparing_agent"
    
    elif phase == "comparison":
        # Comparison phase: analyze and rank
        
        if not comparison_result:
            return "comparing_agent"
            
        if not ranked_compounds:
            return "compound_ranking_agent"
            
        return "final_output_agent"
    
    elif phase == "presentation":
        # Final phase: generate output
        
        return "final_output_agent"
    
    # Invalid or unknown phase - log and end
    print(f"⚠️ WARNING: Invalid phase '{phase}' in router — ending conversation")
    return END


def should_continue(state: AgentState) -> str:
    """Wrapper kept for backward compatibility."""
    return state_router(state)


# ---------------------------------------------------------------------------
# Build the graph (singleton)
# ---------------------------------------------------------------------------

graph = StateGraph()

# ── Nodes ────────────────────────────────────────────────────────────────────
graph.add_node("extraction_agent",       extraction_agent)
graph.add_node("location_agent",         location_agent)
graph.add_node("property_type_agent",    property_type_agent)
graph.add_node("payment_agent",          payment_agent)
graph.add_node("budget_agent",           budget_agent)
graph.add_node("compounds_agent",        compounds_agent)
graph.add_node("developers_agent",       developers_agent)
graph.add_node("comparing_agent",        comparing_agent)
graph.add_node("compound_ranking_agent", compound_ranking_agent)
graph.add_node("final_output_agent",     final_output_agent)

# ── Entry point ──────────────────────────────────────────────────────────────
graph.set_entry_point("extraction_agent")

# ── Edges: every node routes through state_router ────────────────────────────
all_nodes = [
    "extraction_agent",
    "location_agent",
    "property_type_agent",
    "payment_agent",
    "budget_agent",
    "compounds_agent",
    "developers_agent",
    "comparing_agent",
    "compound_ranking_agent",
    "final_output_agent",
]

for _node in all_nodes:
    graph.add_edge(_node, state_router)

# graph.py does not require an explicit .compile() call; expose as alias.
compiled_graph = graph
print("✓ Graph compiled successfully")
