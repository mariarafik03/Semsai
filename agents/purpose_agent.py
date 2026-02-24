from state import AgentState
from main_helpers import ask_ollama

def purpose_agent(state: AgentState):
    print("\n--- Purpose Agent (Ollama) ---")

    # Skip if extraction agent already resolved the purpose
    if state.get("purpose"):
        print(f"   Purpose already set: {state['purpose']}  — skipping.")
        state["next_step"] = "budget_agent"
        return state

    if not state.get("user_input") or state.get("retry"):
        question = ask_ollama(
            "Start a friendly conversation with the user and ask why they are interested in real estate. "
            "Do not answer yourself."
        )
        print("Agent:", question)
        state["user_input"] = input("You: ")
        state["retry"] = False

    purpose = ask_ollama(
        f"Extract ONLY one purpose from user input (rent, invest, live): '{state['user_input']}'"
    ).strip().lower()
    

   
    if purpose in ["rent", "invest", "live"]:
        print(f"Agent: So, you want to buy a property to {purpose}? Please reply yes or no.")
        confirmation = input("You (yes/no): ").strip().lower()
        if confirmation == "yes":
            state["purpose"] = purpose
            state["next_step"] = "budget_agent"
        else:
            state["retry"] = True
            state["next_step"] = "questioning_agent"
    else:
        
        state["retry"] = True
        state["next_step"] = "questioning_agent"
    

    return state
