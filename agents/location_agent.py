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
    state["location"] = user_location_input

    question2 = ask_ollama(
        "Ask the user what type of property they are interested in ( apartment, villa, chalet). Keep it short and friendly."
    )

    print("Agent:", question2)
    typeinput = input("You: ")
    state["typeofproperty"] = typeinput



    return state    

