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
    # ── 1. Interruption Check (CRITICAL) ────────────────────────────────
    # If an agent is waiting for user input, we must stop the graph execution.
    if state.get("waiting_for"):
        return END

    # ── 2. Hard stop ───────────────────────────────────────────────────
    if state.get("abort"):
        return END

    # ── 3. Location + property type ──────────────────────────────────────
    if not state.get("location") or not state.get("typeofproperty"):
        return "location_agent"

    # ── 4. Budget & Payment (Using the new validation logic) ─────────────
    # Move to budget_agent if payment type is missing OR budget isn't validated yet
    if not state.get("payment_type") or not state.get("budget_valid"):
        return "budget_agent"

    # ── 5. Compound discovery ────────────────────────────────────────────
    if state.get("candidate_compounds") is None:
        return "compounds_agent"

    # ── 6. Developer filtering ───────────────────────────────────────────
    if state.get("final_compounds") is None:
        return "developers_agent"

    # ── 7. Feature extraction ────────────────────────────────────────────
    if state.get("compound_features_stats") is None:    
        return "compound_features_agent"

    # ── 8. Embedding generation ──────────────────────────────────────────
    if state.get("embeddings") is None:
        return "embedding_agent"

    # ── 9. User preferences interview ────────────────────────────────────
    if state.get("user_preferences") is None:
        return "user_preferences_agent"

    # ── 10. Vector ranking ───────────────────────────────────────────────
    if state.get("ranked_compounds") is None:
        return "compound_ranking_agent"

    # ── 11. Final output ─────────────────────────────────────────────────
    if state.get("final_best_compound") is None:
        return "final_output_agent"

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