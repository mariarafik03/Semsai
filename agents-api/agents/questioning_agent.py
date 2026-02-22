"""
Questioning Agent — asks subtle follow-up questions to discover purpose.
"""
from typing import Any
from llm_helper import ask_llm


def questioning_agent(state: dict[str, Any], user_input: str | None) -> dict[str, Any]:
    """
    Keeps asking until it can extract a purpose.
    sub_phase: "ask" | "extract"
    """
    sub = state.get("sub_phase")
    asked = state.get("asked_questions", [])

    # ---- GENERATE A QUESTION ----
    if sub is None or sub == "ask":
        previous_qs_text = "\n".join(asked)
        prompt = f"""You are an extremely intelligent, empathetic real estate assistant.
The user has not clearly stated their purpose for buying real estate.
Your goal is to discover the user's true intent: one of ["rent", "invest", "live"].

Instructions:
1. Ask ONE subtle, natural, human-like question at a time.
2. Never directly ask "What is your purpose?" or list options.
3. Make sure the next question is COMPLETELY different from:
{previous_qs_text}
4. Keep it friendly and short (1-2 sentences).
5. Return ONLY the question."""

        question = ask_llm(prompt)
        asked.append(question)
        state["asked_questions"] = asked
        state["sub_phase"] = "extract"
        state["agent_message"] = question
        state["awaiting_input"] = True
        return state

    # ---- EXTRACT PURPOSE ----
    if sub == "extract" and user_input:
        state["user_input"] = user_input

        purpose = ask_llm(
            f"Extract ONLY one purpose from user input (rent, invest, live) if you can: '{user_input}'"
        ).strip().lower()

        for p in ["rent", "invest", "live"]:
            if p in purpose:
                purpose = p
                break

        if purpose in ["rent", "invest", "live"]:
            state["purpose"] = purpose
            state["phase"] = "budget"
            state["sub_phase"] = None
            state["awaiting_input"] = False
            state["agent_message"] = None
        else:
            # Ask again
            state["sub_phase"] = "ask"
            state["awaiting_input"] = False  # auto-advance to generate next question
            state["agent_message"] = None
        return state

    return state
