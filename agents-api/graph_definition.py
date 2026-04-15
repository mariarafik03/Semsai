"""
graph_definition.py
───────────────────
Builds and exports the compiled StateGraph singleton.

Full pipeline (HTTP-safe):
    extraction_agent          (greet + extract fields from opening message)
    → location_agent          (location + typeofproperty — if not already extracted)
    → budget_agent            (payment_type + budget/installments — validated against DB)
    → compounds_agent         (candidate_compounds — with no-units fallback loop)
    → developers_agent        (final_compounds)
    → compound_features_agent (compound_features_stats)
    → embedding_agent         (embeddings)
    → user_preferences_agent  (user_preferences)
    → compound_ranking_agent  (ranked_compounds)
    → final_output_agent      (final_best_compound)
    → END

If no units are found matching location + type + budget, the user is offered:
    1. Increase budget  →  loops back to budget_agent
    2. Change location  →  loops back to location_agent
    3. Change type      →  loops back to location_agent (property-type section)
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
    Routes the graph to the next agent based on what state is currently missing.

    Order:
      1. waiting_for set  → END  (agent is paused waiting for user)
      2. abort flag set   → END
      3. location / typeofproperty missing → location_agent
      4. payment_type / budget_valid missing → budget_agent
      5. candidate_compounds is None → compounds_agent   (includes no-units fallback)
      6–11. rest of pipeline
    """
    # ── 1. Interruption Check ────────────────────────────────────────────
    if state.get("waiting_for"):
        print(f"🛑 Router: Waiting for '{state.get('waiting_for')}' → END")
        return END

    # ── 2. Hard stop ─────────────────────────────────────────────────────
    if state.get("abort"):
        print(f"🛑 Router: Abort flag set → END")
        return END

    # ── 3. Location + property type ──────────────────────────────────────
    if not state.get("location") or not state.get("typeofproperty"):
        print(f"→ Router: Missing location/property → location_agent")
        return "location_agent"

    # ── 4. Budget & Payment type ─────────────────────────────────────────
    if not state.get("payment_type") or not state.get("budget_valid"):
        print(f"→ Router: Missing payment/budget → budget_agent")
        return "budget_agent"

    # ── 5. Compound discovery (None = not yet found OR user reset it) ────
    if state.get("candidate_compounds") is None:
        print(f"→ Router: Finding compounds → compounds_agent")
        return "compounds_agent"

    # ── 6. Developer filtering ───────────────────────────────────────────
    if state.get("final_compounds") is None:
        print(f"→ Router: Filtering developers → developers_agent")
        return "developers_agent"

    # ── 7. Feature extraction ────────────────────────────────────────────
    if state.get("compound_features_stats") is None:
        print(f"→ Router: Extracting features → compound_features_agent")
        return "compound_features_agent"

    # ── 8. Embedding generation ──────────────────────────────────────────
    if state.get("embeddings") is None:
        print(f"→ Router: Generating embeddings → embedding_agent")
        return "embedding_agent"

    # ── 9. User preferences interview ────────────────────────────────────
    if state.get("user_preferences") is None:
        print(f"→ Router: Collecting preferences → user_preferences_agent")
        return "user_preferences_agent"

    # ── 10. Vector ranking ───────────────────────────────────────────────
    if state.get("ranked_compounds") is None:
        print(f"→ Router: Ranking compounds → compound_ranking_agent")
        return "compound_ranking_agent"

    # ── 11. Final output ─────────────────────────────────────────────────
    if state.get("final_best_compound") is None:
        print(f"→ Router: Generating final output → final_output_agent")
        return "final_output_agent"

    print(f"✓ Router: All complete → END")
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

print("✓ Graph compiled successfully")