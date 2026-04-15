"""
graph_definition.py
───────────────────
Builds and exports the compiled StateGraph singleton.

Updated Flow (with budget validation loop):
    extraction_agent
    → budget_agent
    → location_agent
    → compounds_agent
    → 🔥 budget validation (loop if needed)
    → developers_agent
    → compound_features_agent
    → embedding_agent
    → user_preferences_agent
    → compound_ranking_agent
    → final_output_agent
    → END
"""

from graph import StateGraph, END

# ── Agent imports ─────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────
# 🔥 STATE ROUTER (UPDATED)
# ─────────────────────────────────────────────────────────────

def state_router(state: dict) -> str:

    # ── 0. Hard stop ─────────────────────────────────────────
    if state.get("abort"):
        return END

    # ── 1. Location + property type ─────────────────────────
    if not state.get("location") or not state.get("typeofproperty"):
        print("DEBUG → location_agent", flush=True)
        return "location_agent"

    # ── 2. Payment type ─────────────────────────────────────
    if not state.get("payment_type"):
        print("DEBUG → budget_agent (payment type)", flush=True)
        return "budget_agent"

    # ── 3. Budget completeness ──────────────────────────────
    budget_ok = bool(state.get("budget"))
    installments_ok = bool(
        state.get("Downpayment") and state.get("monthlyinstall")
    )

    if not budget_ok and not installments_ok:
        print("DEBUG → budget_agent (budget missing)", flush=True)
        return "budget_agent"

    # ── 4. Fetch compounds ──────────────────────────────────
    if state.get("candidate_compounds") is None:
        print("DEBUG → compounds_agent", flush=True)
        return "compounds_agent"

    # ── 5. 🔥 Budget validation loop ─────────────────────────
    if state.get("budget_valid") is False:
        print("DEBUG → budget too low → back to budget_agent", flush=True)

        # trigger retry mode
        state["budget_retry"] = True

        return "budget_agent"

    # ── 6. Developers filtering ─────────────────────────────
    if state.get("final_compounds") is None:
        print("DEBUG → developers_agent", flush=True)
        return "developers_agent"

    # ── 7. Feature extraction ───────────────────────────────
    if state.get("compound_features_stats") is None:
        print("DEBUG → compound_features_agent", flush=True)
        return "compound_features_agent"

    # ── 8. Embeddings ───────────────────────────────────────
    if state.get("embeddings") is None:
        print("DEBUG → embedding_agent", flush=True)
        return "embedding_agent"

    # ── 9. User preferences ─────────────────────────────────
    if state.get("user_preferences") is None:
        print("DEBUG → user_preferences_agent", flush=True)
        return "user_preferences_agent"

    # ── 10. Ranking ─────────────────────────────────────────
    if state.get("ranked_compounds") is None:
        print("DEBUG → compound_ranking_agent", flush=True)
        return "compound_ranking_agent"

    # ── 11. Final output ────────────────────────────────────
    if state.get("final_best_compound") is None:
        print("DEBUG → final_output_agent", flush=True)
        return "final_output_agent"

    return END


# ─────────────────────────────────────────────────────────────
# Build Graph
# ─────────────────────────────────────────────────────────────

graph = StateGraph()

# ── Nodes ────────────────────────────────────────────────────
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

# ── Entry Point ──────────────────────────────────────────────
graph.set_entry_point("extraction_agent")

# ── Edges (ALL go through router) ────────────────────────────
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