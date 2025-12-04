from state import AgentState
from main_helpers import ask_ollama


def purpose_agent(state: AgentState):
    print("\n--- Purpose Agent (Ollama) ---")

   
    if not state.get("user_input") and not state.get("pending_confirmation"):
        prompt = (
            "You are an extra friendly real estate assistant. "
            "Greet the user naturally and ask why they are interested in real estate. "
            "Do NOT process anything yet; just ask the question."
        )
        response_text = ask_ollama(prompt)
        print("Agent:", response_text)
        state["next_step"] = None  
        return state

    
    if not state.get("pending_confirmation"):
        
        prompt = (
            f"You are a helpful real estate assistant. "
            f"Extract the purpose of buying real estate from the user's input. "
            f"User said: '{state['user_input']}' "
            "Return ONLY one of: rent, invest, live. "
            "Do NOT add extra text."
        )
        response_text = ask_ollama(prompt)
        print("Debug (extracted purpose):", response_text)

       
        purpose = None
        for w in ["rent", "invest", "live" ]:
            if w in response_text.lower():
                purpose = w
                break

        if purpose:
            
            confirmation_prompt = (
                f"So, you are interested in buying a property to {purpose}? "
                "Please reply yes or no."
            )
            print("Agent:", confirmation_prompt)
            state["pending_confirmation"] = purpose
            state["next_step"] = None  
        else:
            
            state["next_step"] = "questioning_agent"
        return state

    
    if state.get("pending_confirmation"):
        user_reply = state["user_input"].lower()
        if "yes" in user_reply:
            state["purpose"] = state["pending_confirmation"]
            state["next_step"] = "budget_agent"
        else:
            
            state["next_step"] = "questioning_agent"

        
        state["pending_confirmation"] = None

    return state
