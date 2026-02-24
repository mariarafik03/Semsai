from graph import StateGraph, END
from agents.purpose_agent import purpose_agent
from agents.questioning_agent import questioning_agent
from agents.budget_agent import budget_agent
from agents.location_agent import location_agent
from agents.compounds_agent import compounds_agent, format_price
from agents.developers_agent import developers_agent  
from agents.comparing_agent import comparing_agent  
from agents.compound_features_agent import compound_features_agent
from agents.user_prefrences_agent import user_preferences_agent
from agents.compound_ranking_agent import compound_ranking_agent
from agents.final_output_agent import final_output_agent 
from agents.unit_agent import unit_agent, rent_agent, living_agent
from main_helpers import ask_ollama # adjust import to wherever your ask_ollama lives
from agents.unit_filter_node import interactive_unit_filter
state = {
    "user_input": None,
    "purpose": None,
    "pending_confirmation": None,
    "budget": None,
    "location": None,
    "next_step": None,
    "payment_type": None,
    "Downpayment": None,
    "monthlyinstall": None,
    "retry": None,
    "budget_valid": None,
    "breakingquest": None,
    "breakingbudget": None,
    "breakinginstallments": None,
    "candidate_compounds": None,
    "typeofproperty": None,
    "final_candidates": None,
    "candidate_units": None,       # populated by compounds_agent / unit fetching
    "selected_compound": None,     # populated by comparing_agent / compound selection
    "top_investment_units": None,  # populated by rent_agent
    "route": None,
}

# ---------------------------------------------------------------------------
# Wrap interactive_unit_filter so it fits the graph's single-argument node API
# while still receiving ask_ollama via closure
# ---------------------------------------------------------------------------
def unit_filter_node(state):
    return interactive_unit_filter(state, ask_ollama=ask_ollama)

# ---------------------------------------------------------------------------
# Graph definition
# ---------------------------------------------------------------------------
graph = StateGraph()
graph.add_node("purpose_agent",           purpose_agent)
graph.add_node("questioning_agent",        questioning_agent)
graph.add_node("budget_agent",             budget_agent)
graph.add_node("location_agent",           location_agent)
graph.add_node("developers_agent",         developers_agent)
graph.add_node("compounds_agent",          compounds_agent)
graph.add_node("compound_features_agent",  compound_features_agent)
graph.add_node("user_preferences_agent",   user_preferences_agent)
graph.add_node("compound_ranking_agent",   compound_ranking_agent)
graph.add_node("final_output_agent",       final_output_agent)
graph.add_node("unit_agent",               unit_agent)
graph.add_node("unit_filter_node",         unit_filter_node)   # NEW
graph.add_node("rent_agent",               rent_agent)
graph.add_node("living_agent",             living_agent)

# ---------------------------------------------------------------------------
# Edges
# ---------------------------------------------------------------------------
graph.add_edge("purpose_agent",          lambda s: "budget_agent" if s.get("purpose") else "questioning_agent")
graph.add_edge("questioning_agent",      lambda s: "budget_agent")
graph.add_edge("budget_agent",           lambda s: "location_agent")
graph.add_edge("location_agent",         lambda s: "compounds_agent")
graph.add_edge("compounds_agent",        lambda s: "developers_agent")
graph.add_edge("developers_agent",       lambda s: "compound_features_agent")
graph.add_edge("compound_features_agent",lambda s: "user_preferences_agent")
graph.add_edge("user_preferences_agent", lambda s: "compound_ranking_agent")
graph.add_edge("compound_ranking_agent", lambda s: "final_output_agent")
graph.add_edge("final_output_agent",     lambda s: "unit_agent")

# unit_agent sets state["route"], then we always go to unit_filter_node
# unit_filter_node narrows candidates, then routes to the right scoring agent
graph.add_edge("unit_agent",             lambda s: "unit_filter_node")
graph.add_edge("unit_filter_node",       lambda s: "rent_agent" if s.get("route") == "rent" else "living_agent")

graph.add_edge("rent_agent",             lambda s: END)
graph.add_edge("living_agent",           lambda s: END)

graph.set_entry_point("purpose_agent")

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