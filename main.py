from graph import StateGraph, END
from agents.extraction_agent import extraction_agent
from agents.budget_agent import budget_agent
from agents.location_agent import location_agent
from agents.compounds_agent import compounds_agent, format_price
from agents.developers_agent import developers_agent  
from agents.comparing_agent import comparing_agent  
from agents.compound_features_agent import compound_features_agent
from agents.user_prefrences_agent import user_preferences_agent
from agents.compound_ranking_agent import compound_ranking_agent
from agents.final_output_agent import final_output_agent 
from main_helpers import ask_ollama 
from agents.embedding_agent import embedding_agent

state = {
    "user_input": None,
    "purpose": None,
    "pending_confirmation": None,
    "budget": None,
    "location": None,
    "next_step": None,
    "payment_type": None,
    "payment_type_confirmed": False,
    "Downpayment": None,
    "monthlyinstall": None,
    "budget_valid": None,
    "breakingbudget": None,
    "breakinginstallments": None,
    "candidate_compounds": None,
    "final_compounds": None,
    "top_compounds": None,
    "top_developers": None,
    "typeofproperty": None,
    "final_candidates": None,
    "compound_features_stats": None,
    "features_limit": 0,
    "features_force_refresh": False,
    "candidate_units": None,
    "selected_compound": None,
    "raw_budget_hint": None,
}

# ---------------------------------------------------------------------------
# State Router  — single source of truth for all routing
# ---------------------------------------------------------------------------
def state_router(state: dict) -> str:

    if state.get("abort"):
        return END

    if not state.get("location"):
        return "location_agent"

    if not state.get("typeofproperty"):
        return "location_agent"

    if not state.get("budget_valid"):
        return "budget_agent"

    # ── Compound discovery pipeline ──────────────────────────────────────────
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

    return END

# ---------------------------------------------------------------------------
# Graph definition
# ---------------------------------------------------------------------------
graph = StateGraph()

# ── All nodes ───────────────────────────────────────────────────────────────
graph.add_node("extraction_agent",        extraction_agent)
graph.add_node("budget_agent",            budget_agent)
graph.add_node("location_agent",          location_agent)
graph.add_node("compounds_agent",         compounds_agent)
graph.add_node("developers_agent",        developers_agent)
graph.add_node("compound_features_agent", compound_features_agent)
graph.add_node("user_preferences_agent",  user_preferences_agent)
graph.add_node("compound_ranking_agent",  compound_ranking_agent)
graph.add_node("final_output_agent",      final_output_agent)
graph.add_node("embedding_agent",         embedding_agent)

# ── Entry ───────────────────────────────────────────────────────────────────
graph.set_entry_point("extraction_agent")

# ── Every node loops back to state_router ───────────────────────────────────
for _node in [
    "extraction_agent", "budget_agent", "location_agent", "compounds_agent",
    "developers_agent", "compound_features_agent",
    "user_preferences_agent", "compound_ranking_agent",
    "final_output_agent", "embedding_agent",
]:
    graph.add_edge(_node, state_router)

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
next_node = None
while next_node != END:
    state, next_node = graph.step(state)

# ---------------------------------------------------------------------------
# Final summary
# ---------------------------------------------------------------------------
print("\n--- Final Plan ---")
print(f"Purpose:             {state.get('purpose')}")
print(f"Budget:              {format_price(state.get('budget'))}")
print(f"Downpayment:         {format_price(state.get('Downpayment'))}")
print(f"Monthly Installment: {format_price(state.get('monthlyinstall'))}")
print(f"Location:            {state.get('location')}")
print(f"Payment Type:        {state.get('payment_type')}")
print(f"Type of Property:    {state.get('typeofproperty')}")

final_candidates = state.get("final_candidates") or []
print("\n--- Final Candidates ---")
if not final_candidates:
    print("No final candidates.")
else:
    for i, d in enumerate(final_candidates, 1):
        print(f"\n{i}. Developer: {d.get('name', 'Unknown')}")
        print(f"   Class: {d.get('Developer_Class', 'N/A')}")
        print(f"   Class Score: {d.get('class_score', 0)}")
        print(f"   Matching Compounds: {d.get('compound_count', 0)}")
        matched = d.get("matched_compound_names") or []
        if matched:
            print("   Compounds:")
            for name in matched:
                print(f"      • {name}")
        if d.get("website"):
            print(f"   Website: {d.get('website')}")