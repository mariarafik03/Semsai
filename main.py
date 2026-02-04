
from graph import StateGraph, END
from agents.purpose_agent import purpose_agent
from agents.questioning_agent import questioning_agent
from agents.budget_agent import budget_agent
from agents.location_agent import location_agent
from agents.compounds_agent import compounds_agent
from agents.developers_agent import developers_agent    

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
    "typeofproperty": None
   
}
graph = StateGraph()
graph.add_node("purpose_agent", purpose_agent)
graph.add_node("questioning_agent", questioning_agent)
graph.add_node("budget_agent", budget_agent)
graph.add_node("location_agent", location_agent)
graph.add_node("developers_agent", developers_agent)

graph.add_node("compounds_agent", compounds_agent)


graph.add_edge("purpose_agent", lambda s: "budget_agent" if s.get("purpose") else "questioning_agent")
graph.add_edge("questioning_agent", lambda s: "budget_agent")
graph.add_edge("budget_agent", lambda s: "location_agent" )
graph.add_edge("location_agent", lambda s: "compounds_agent")

graph.add_edge("compounds_agent", lambda s: "developers_agent")
graph.add_edge("developers_agent", END)

graph.set_entry_point("purpose_agent")

next_node = None
while next_node != END:
    state, next_node = graph.step(state)

print("\n--- Final Plan ---")
print("Purpose:", state["purpose"])
print("Type of Property:", state["typeofproperty"])
print("Budget:", state["budget"])
print("Downpayment", state["Downpayment"])
print("monthlyinstall:", state["monthlyinstall"])
print("Location:", state["location"])
print("payment type:", state["payment_type"])

