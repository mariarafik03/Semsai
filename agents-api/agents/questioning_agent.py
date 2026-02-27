from state import AgentState
from main_helpers import ask_ollama


def questioning_agent(state: AgentState):
    """
    Clarification agent — asks one question per call to discover user's purpose.
    Non-blocking: sets pending_question and returns.
    """

    user_input = state.get("user_input")

    # Phase 1: Ask a question
    if not user_input:
        asked_questions = state.get("_asked_questions", [])
        previous_qs_text = "\n".join(asked_questions)

        prompt = f"""
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
        state["_asked_questions"] = asked_questions

        state["pending_question"] = question
        state["user_input"] = None
        return state

    # Phase 2: Extract purpose from user response
    purpose = ask_ollama(
        f"""From this user message: '{user_input}'
        Extract their real estate purpose. Reply with ONLY one word from this list: rent, invest, live, buy.
        If unclear, reply: unknown"""
    ).strip().lower()

    for p in ["rent", "invest", "live", "buy"]:
        if p in purpose:
            purpose = p
            break

    if purpose in ["rent", "invest", "live"]:
        state["purpose"] = purpose
        state["retry"] = False
        state["user_input"] = None
    else:
        # Not clear yet — will loop back (router sends here again)
        state["user_input"] = None

    return state
