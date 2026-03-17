"""
graph_definition.py
───────────────────
Builds and exports the compiled StateGraph singleton.

This replaces the "graph definition" section that used to live at the
bottom of main.py.  Import `graph` from here in any module that needs it.

NOTE: purpose_agent has been removed per your instruction.
"""

from graph import StateGraph, END

# ── Agent imports ────────────────────────────────────────────────────────────
from agents.extraction_agent        import extraction_agent
from agents.questioning_agent       import questioning_agent
from agents.budget_agent            import budget_agent
from agents.location_agent          import location_agent
from agents.compounds_agent         import compounds_agent
from agents.developers_agent        import developers_agent
from agents.compound_features_agent import compound_features_agent
from agents.user_prefrences_agent   import user_preferences_agent
from agents.compound_ranking_agent  import compound_ranking_agent
from agents.final_output_agent      import final_output_agent
from agents.unit_agent              import unit_agent, rent_agent, living_agent
from agents.unit_filter_node        import interactive_unit_filter
from agents.embedding_agent         import embedding_agent

# ---------------------------------------------------------------------------
# State Router — single source of truth for all routing
# ---------------------------------------------------------------------------

def state_router(state: dict) -> str:

    if state.get("abort"):
        return END

    # No purpose_agent anymore — if purpose missing, ask via questioning_agent
    if not state.get("purpose"):
        return "questioning_agent"

    if not state.get("location"):
        return "location_agent"

    if not state.get("typeofproperty"):
        return "location_agent"

    if not state.get("budget") and not (
        state.get("Downpayment") and state.get("monthlyinstall")
    ):
        return "budget_agent"

    # ── Compound discovery pipeline ──────────────────────────────────────
    if state.get("candidate_compounds") is None:
        return "compounds_agent"

    if state.get("final_compounds") is None:
        return "developers_agent"

    if state.get("compound_features_stats") is None:
        return "compound_features_agent"

    if state.get("embeddings") is None:
        return "embedding_agent"

    if state.get("user_preferences") is None:
        return "user_preferences_agent"

    if state.get("ranked_compounds") is None:
        return "compound_ranking_agent"

    if state.get("final_best_compound") is None:
        return "final_output_agent"

    # ── Unit routing ─────────────────────────────────────────────────────
    if state.get("route") is None:
        return "unit_agent"

    if state.get("route") == "rent":
        return "rent_agent"

    if state.get("route") in ("live", "living"):
        return "unit_filter_node"

    return END


# ---------------------------------------------------------------------------
# Build the graph (singleton)
# ---------------------------------------------------------------------------

graph = StateGraph()

# ── Nodes ────────────────────────────────────────────────────────────────────
graph.add_node("extraction_agent",        extraction_agent)
graph.add_node("questioning_agent",       questioning_agent)
graph.add_node("budget_agent",            budget_agent)
graph.add_node("location_agent",          location_agent)
graph.add_node("compounds_agent",         compounds_agent)
graph.add_node("developers_agent",        developers_agent)
graph.add_node("compound_features_agent", compound_features_agent)
graph.add_node("user_preferences_agent",  user_preferences_agent)
graph.add_node("compound_ranking_agent",  compound_ranking_agent)
graph.add_node("final_output_agent",      final_output_agent)
graph.add_node("unit_agent",              unit_agent)
graph.add_node("rent_agent",              rent_agent)
graph.add_node("living_agent",            living_agent)
graph.add_node("embedding_agent",         embedding_agent)
graph.add_node("unit_filter_node",        interactive_unit_filter)

# ── Entry point ──────────────────────────────────────────────────────────────
graph.set_entry_point("extraction_agent")

# ── Edges (all loop through state_router except terminals) ───────────────────
for _node in [
    "extraction_agent",
    "questioning_agent",
    "budget_agent",
    "location_agent",
    "compounds_agent",
    "developers_agent",
    "compound_features_agent",
    "user_preferences_agent",
    "compound_ranking_agent",
    "final_output_agent",
    "unit_agent",
    "embedding_agent",
]:
    graph.add_edge(_node, state_router)

graph.add_edge("rent_agent",       lambda s: END)
graph.add_edge("unit_filter_node", lambda s: END)
