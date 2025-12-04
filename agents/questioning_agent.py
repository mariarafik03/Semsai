from state import AgentState
from main_helpers import ask_ollama

def questioning_agent(state: AgentState):
    print("\n--- Clarification Agent (Ollama) ---")
    new_input = input("Agent: I didn't understand your purpose. Can you clarify? You: ")
    state["user_input"] = new_input
    state["next_step"] = "purpose_agent"
    return state
