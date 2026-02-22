from state import AgentState
from main_helpers import ask_ollama

# ---- Normalization Maps ----
PROPERTY_MAP = {
    "villa": "Villa",
    "vila": "Villa",
    "apartment": "Apartment",
    "flat": "Apartment",
    "chalet": "Chalet"
}

def extract_property_type(llm_output: str):
    """
    Extract and normalize property type from LLM output
    """
    llm_output = llm_output.lower()
    for key, value in PROPERTY_MAP.items():
        if key in llm_output:
            return value
    return None


def location_agent(state: AgentState):
    print("\n--- Location Agent (Ollama) ---")

    # =============================
    # 1️⃣ Ask for location
    # =============================
    question = ask_ollama(
        "You are a friendly real estate assistant. "
        "Ask the user where they would like to buy a property in Egypt in a natural way. "
        "Do not answer yourself, just ask the question."
    )
    print("Agent:", question)

    while True:
        user_location_input = input("You: ").strip()

        if not user_location_input:
            print("Agent: Please enter a valid location in Egypt.")
            continue

        extracted_location = ask_ollama(
            "Extract ONLY the location from the user input. "
            "It must be inside Greater Cairo or the North Coast. "
            "Capitalize the first letter of each word like (New Cairo, New Capital). "
            f"User input: '{user_location_input}'"
        ).strip()

        if extracted_location:
            state["location"] = extracted_location.title()
            break
        else:
            print("Agent: I couldn’vt recognize that location. Could you try again?")

    # =============================
    # 2️⃣ Ask for property type
    # =============================
    question2 = ask_ollama(
        "Ask the user what type of property they are interested in "
        "(apartment, villa, chalet). Keep it short and friendly."
    )
    print("Agent:", question2)

    while True:
        type_input = input("You: ").strip()

        if not type_input:
            print("Agent: Please choose Apartment, Villa, or Chalet.")
            continue

        llm_type_output = ask_ollama(
            "Extract ONLY the type of property from the user input. "
            "Return only one word if possible (Apartment, Villa, or Chalet). "
            f"User input: '{type_input}'"
        )

        normalized_type = extract_property_type(llm_type_output)

        if normalized_type:
            state["typeofproperty"] = normalized_type
            break
        else:
            print("Agent: Sorry, I only support Apartment, Villa, or Chalet. Could you repeat that?")

    return state
