from state import AgentState
from graph import SimpleStateGraph, END
from agents.purpose_agent import purpose_agent
from agents.questioning_agent import questioning_agent
from agents.budget_agent import budget_agent
from agents.education_agent import education_agent
from agents.location_agent import location_agent

state = {
    "user_input": None,
    "purpose": None,
    "pending_confirmation": None,
    "budget": None,
    "location": None,
    "next_step": None,
    "payment_type":None,
    "Downpayment": None,
    "monthlyinstall": None
}

graph = SimpleStateGraph()
graph.add_node("purpose_agent", purpose_agent)
graph.add_node("questioning_agent", questioning_agent)
graph.add_node("budget_agent", budget_agent)
graph.add_node("education_agent", education_agent)
graph.add_node("location_agent", location_agent)
graph.set_entry_point("purpose_agent")

# Stepwise execution
next_node = None

# Start conversation
state, next_node = graph.step(state)
state["user_input"] = input("You: ")
state["next_step"] = "purpose_agent"
state, next_node = graph.step(state)

# Handle pending confirmation
while state.get("pending_confirmation"):
    state["user_input"] = input("You (confirm yes/no): ")
    state, next_node = graph.step(state)

# Continue rest of the graph
while next_node != END:
    fn = graph.nodes[next_node]
    state = fn(state)
    next_node = state.get("next_step", END)

print("\n--- Final Plan ---")
print("Purpose:", state["purpose"])
print("Budget:", state["budget"])
print("Location:", state["location"])
