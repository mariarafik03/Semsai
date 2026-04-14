"""
graph_definition.py
───────────────────
Builds and exports the compiled StateGraph singleton.

Full pipeline (HTTP-safe):
    extraction_agent
    → budget_agent            (payment_type + budget)
    → location_agent          (location + typeofproperty)
    → compounds_agent         (candidate_compounds)
    → developers_agent        (final_compounds)
    → compound_features_agent (compound_features_stats)
    → embedding_agent         (embeddings)
    → user_preferences_agent  (user_preferences)
    → compound_ranking_agent  (ranked_compounds)
    → final_output_agent      (final_best_compound)
    → END
"""

from graph import StateGraph, END

# ── Agent imports ─────────────────────────────────────────────────────────────
from agents.extraction_agent         import extraction_agent
from agents.budget_agent             import budget_agent
from agents.location_agent           import location_agent
from agents.compounds_agent          import compounds_agent
from agents.developers_agent         import developers_agent
from agents.compound_features_agent  import compound_features_agent
from agents.embedding_agent          import embedding_agent
from agents.user_preferences_agent   import user_preferences_agent
from agents.compound_ranking_agent   import compound_ranking_agent
from agents.final_output_agent       import final_output_agent


# ---------------------------------------------------------------------------
# State Router — single source of truth for all routing
# ---------------------------------------------------------------------------

def state_router(state: dict) -> str:
    """
    Routes to the next agent based on state.
    
    CRITICAL: If any agent sets state["waiting_for"], 
    we MUST return END to pause the graph and wait for user input.
    """

    # ══════════════════════════════════════════════════════════════════════
    # PRIORITY 1: Check if waiting for user input
    # ══════════════════════════════════════════════════════════════════════
    
    if state.get("waiting_for"):
        print(f"⏸️  PAUSING GRAPH - waiting for: {state['waiting_for']}", flush=True)
        print(f"📤 Message to user: {state.get('agent_message', 'N/A')[:100]}...", flush=True)
        return END  # STOP HERE - wait for user response

    # ══════════════════════════════════════════════════════════════════════
    # PRIORITY 2: Hard abort
    # ══════════════════════════════════════════════════════════════════════
    
    if state.get("abort"):
        print("🛑 ABORT flag set - ending graph", flush=True)
        return END

    # ══════════════════════════════════════════════════════════════════════
    # STEP 1: Extraction (already complete if we're here)
    # ══════════════════════════════════════════════════════════════════════
    
    # Extraction runs first and doesn't wait for user input
    
    # ══════════════════════════════════════════════════════════════════════
    # STEP 2: Budget Agent (payment type + budget collection)
    # ══════════════════════════════════════════════════════════════════════
    
    # Check if budget agent is complete
    if not state.get("budget_agent_complete"):
        # Need to run or continue budget agent
        has_payment_type = bool(state.get("payment_type"))
        has_budget = bool(state.get("budget"))
        has_installments = bool(state.get("Downpayment") and state.get("monthlyinstall"))
        
        # If missing any of these, go to budget agent
        if not has_payment_type or (not has_budget and not has_installments):
            print("DEBUG: going budget agent", flush=True)
            return "budget_agent"

    # ══════════════════════════════════════════════════════════════════════
    # STEP 3: Location Agent (location + property type)
    # ══════════════════════════════════════════════════════════════════════
    
    if not state.get("location") or not state.get("typeofproperty"):
        print("DEBUG: going location agent", flush=True)
        return "location_agent"

    # ══════════════════════════════════════════════════════════════════════
    # STEP 4: Compounds Agent (find candidate compounds)
    # ══════════════════════════════════════════════════════════════════════
    
    if state.get("candidate_compounds") is None:
        print("DEBUG: going compounds agent", flush=True)
        return "compounds_agent"

    # ══════════════════════════════════════════════════════════════════════
    # STEP 5: Developers Agent (filter by developer quality)
    # ══════════════════════════════════════════════════════════════════════
    
    if state.get("final_compounds") is None:
        print("going developers agent", flush=True)
        return "developers_agent"

    # ══════════════════════════════════════════════════════════════════════
    # STEP 6: Features Agent (extract compound features)
    # ══════════════════════════════════════════════════════════════════════
    
    if state.get("compound_features_stats") is None:    
        print("going compound features agent", flush=True)
        return "compound_features_agent"

    # ══════════════════════════════════════════════════════════════════════
    # STEP 7: Embedding Agent (generate embeddings)
    # ══════════════════════════════════════════════════════════════════════
    
    if state.get("embeddings") is None:
        print("going embedding agent", flush=True)
        return "embedding_agent"

    # ══════════════════════════════════════════════════════════════════════
    # STEP 8: User Preferences Agent (interactive interview)
    # ══════════════════════════════════════════════════════════════════════
    
    if state.get("user_preferences") is None:
        print("going user preferences agent", flush=True)
        return "user_preferences_agent"

    # ══════════════════════════════════════════════════════════════════════
    # STEP 9: Ranking Agent (rank compounds by preferences)
    # ══════════════════════════════════════════════════════════════════════
    
    if state.get("ranked_compounds") is None:
        print("going ranking agent", flush=True)
        return "compound_ranking_agent"

    # ══════════════════════════════════════════════════════════════════════
    # STEP 10: Final Output Agent (generate report)
    # ══════════════════════════════════════════════════════════════════════
    
    if state.get("final_best_compound") is None:
        print("going final output agent", flush=True)
        return "final_output_agent"

    # ══════════════════════════════════════════════════════════════════════
    # All done!
    # ══════════════════════════════════════════════════════════════════════
    
    print("✅ All agents complete - ending graph", flush=True)
    return END


# ---------------------------------------------------------------------------
# Build the graph (singleton)
# ---------------------------------------------------------------------------

graph = StateGraph()

# ── Nodes ────────────────────────────────────────────────────────────────────
graph.add_node("extraction_agent",        extraction_agent)
graph.add_node("budget_agent",            budget_agent)
graph.add_node("location_agent",          location_agent)
graph.add_node("compounds_agent",         compounds_agent)
graph.add_node("developers_agent",        developers_agent)
graph.add_node("compound_features_agent", compound_features_agent)
graph.add_node("embedding_agent",         embedding_agent)
graph.add_node("user_preferences_agent",  user_preferences_agent)
graph.add_node("compound_ranking_agent",  compound_ranking_agent)
graph.add_node("final_output_agent",      final_output_agent)

# ── Entry point ──────────────────────────────────────────────────────────────
graph.set_entry_point("extraction_agent")

# ── Edges (all route through state_router) ───────────────────────────────────
for _node in [
    "extraction_agent",
    "budget_agent",
    "location_agent",
    "compounds_agent",
    "developers_agent",
    "compound_features_agent",
    "embedding_agent",
    "user_preferences_agent",
    "compound_ranking_agent",
    "final_output_agent",
]:
    graph.add_edge(_node, state_router)