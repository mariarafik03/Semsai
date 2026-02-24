from state import AgentState
from main_helpers import ask_ollama

def questioning_agent(state: AgentState):
    print("\n--- Clarification Agent (Ollama) ---")
    asked_questions = []
    state["breakingquest"] = False
    while state["breakingquest"] is False:
        previous_qs_text = "\n".join(asked_questions)
        
        prompt = """
You are an extremely intelligent, empathetic real estate assistant.
The user has not clearly stated their purpose for buying real estate.
Your goal is to discover the user's true intent: one of ["rent", "invest", "live", "buy"].

Instructions:
1. Ask ONE subtle, natural, human-like question at a time to guide the user toward revealing their purpose.
2. Never directly ask "What is your purpose?" or list options.
3. Make sure the next question is COMPLETELY different from all previous questions asked in this conversation:
{previous_qs_text}
4. Make the questions friendly, contextual, and not obvious.
5. Stop after asking the question and wait for user input.
6. Only output the question.

Return ONLY the question.
"""
        question = ask_ollama(prompt)
        asked_questions.append(question)
        print("Agent:", question)

        
        state["user_input"] = input("You: ")

        
        purpose = ask_ollama(
            f"Extract ONLY one purpose from user input (rent, invest, live, buy) if you can: '{state['user_input']}'"
        ).strip().lower()
        

        
        
        if purpose in ["rent", "invest", "live"]:
            state["purpose"] = purpose
            state["retry"] = False       # clear so router doesn't bounce here again
            state["breakingquest"] = True

    return state
