from state import AgentState
from main_helpers import ask_ollama

def education_agent(state: AgentState):
    print("\n--- Ask Budget Again (Ollama) ---")
    new_budget = input("Agent: Please enter your budget (e.g., 50000): ")
    state["user_input"] = new_budget
    state["next_step"] = "budget_agent"
    return state
print('hello')