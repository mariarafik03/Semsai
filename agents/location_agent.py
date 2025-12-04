from state import AgentState
from main_helpers import ask_ollama

def location_agent(state: AgentState):
    print("\n--- Location Agent (Ollama) ---")

    
    prompt = (
        "You are a friendly real estate assistant. "
        "Ask the user where they would like to buy a property in Egypt in a natural way. "
        "Do not answer yourself, just ask the question."
    )
    question = ask_ollama(prompt)
    print("Agent:", question)

    user_location_input = input("You: ")
    state["user_input"] = user_location_input

    
    normalize_prompt = (
        "Normalize this Egyptian location input into a standard city or neighborhood name. "
        "Return a short, clean location name.\n"
        f"User said: '{user_location_input}'"
    )
    normalized_location = ask_ollama(normalize_prompt).strip()

    if normalized_location:
        state["location"] = normalized_location
        state["next_step"] = "END" # end of the graph
        print(f"Debug: standardized location: {normalized_location}")
    else:
        print("Agent: I couldn't understand that location. Let's try again.")
        return location_agent(state)  # retry

    return state
