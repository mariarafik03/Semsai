
from graph import StateGraph, END
from agents.purpose_agent import purpose_agent
from agents.questioning_agent import questioning_agent
from agents.budget_agent import budget_agent
from agents.location_agent import location_agent
from agents.compounds_agent import compounds_agent, format_price
from agents.developers_agent import developers_agent  
from agents.comparing_agent import comparing_agent  

state = {
    "user_input": None,
    "purpose": None,
    "pending_confirmation": None,
    "budget": None,
    "location": None,
    "next_step": None,
    "payment_type":None,
    "Downpayment": None,
    "monthlyinstall": None,
    "retry":None,
    "budget_valid":None,
    "breakingquest":None,
    "breakingbudget":None,
    "breakinginstallments":None,
    "candidate_compounds": None,
    "typeofproperty": None,
    "final_candidates": None
   
}
graph = StateGraph()
graph.add_node("purpose_agent", purpose_agent)
graph.add_node("questioning_agent", questioning_agent)
graph.add_node("budget_agent", budget_agent)
graph.add_node("location_agent", location_agent)
graph.add_node("developers_agent", developers_agent)

graph.add_node("compounds_agent", compounds_agent)
graph.add_node("comparing_agent", comparing_agent)  # placeholder for next step


graph.add_edge("purpose_agent", lambda s: "budget_agent" if s.get("purpose") else "questioning_agent")
graph.add_edge("questioning_agent", lambda s: "budget_agent")
graph.add_edge("budget_agent", lambda s: "location_agent" )
graph.add_edge("location_agent", lambda s: "compounds_agent")

graph.add_edge("compounds_agent", lambda s: "developers_agent")
graph.add_edge("developers_agent", lambda s: "comparing_agent")
graph.add_edge("comparing_agent", lambda s: END)

graph.set_entry_point("purpose_agent")

next_node = None
while next_node != END:
    state, next_node = graph.step(state)

print("\n--- Final Plan ---")
print(f"Purpose: {state.get('purpose')}")
print(f"Budget: {format_price(state.get('budget'))}")
print(f"Downpayment: {format_price(state.get('Downpayment'))}")
print(f"Monthly Installment: {format_price(state.get('monthlyinstall'))}")
print(f"Location: {state.get('location')}")
print(f"Payment Type: {state.get('payment_type')}")
print(f"Type of Property: {state.get('typeofproperty')}")
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