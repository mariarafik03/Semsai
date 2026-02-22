"""
Budget Agent — determines payment type and budget/installments.
Refactored: step-based, no input() calls.
"""
from typing import Any
from llm_helper import ask_llm


def budget_agent(state: dict[str, Any], user_input: str | None) -> dict[str, Any]:
    """
    Sub-phases:
      ask_payment_type → extract_payment_type
      ask_cash_budget  → extract_cash_budget  → ask_cash_loop → extract_cash_loop
      ask_installments → extract_installments → ask_dp_loop   → extract_dp_loop
                                               → ask_mi_loop   → extract_mi_loop
    """
    sub = state.get("sub_phase")

    # ==========================================
    # STEP 1: Ask payment type
    # ==========================================
    if sub is None or sub == "ask_payment_type":
        question = ask_llm(
            "Ask the user if they want to pay by cash or installments in a natural way. "
            "Do not answer for them, just ask the question. Keep it short."
        )
        state["sub_phase"] = "extract_payment_type"
        state["agent_message"] = question
        state["awaiting_input"] = True
        return state

    if sub == "extract_payment_type" and user_input:
        extract = ask_llm(
            f"Extract ONLY the payment type from this input. "
            f"Return exactly one word: cash or installments.\n"
            f"User said: '{user_input}'"
        ).strip().lower()

        for pt in ["cash", "installments"]:
            if pt in extract:
                extract = pt
                break

        if extract in ["cash", "installments"]:
            state["payment_type"] = extract
            state["agent_message"] = f"Got it! You chose {extract}."
            if extract == "cash":
                state["sub_phase"] = "ask_cash_budget"
                state["awaiting_input"] = False  # auto-advance
            else:
                state["sub_phase"] = "ask_installments"
                state["awaiting_input"] = False
        else:
            state["agent_message"] = "Sorry, I didn't understand. Please specify 'cash' or 'installments'."
            state["sub_phase"] = "ask_payment_type"
            state["awaiting_input"] = False  # re-ask
        return state

    # ==========================================
    # STEP 2a: Cash — ask budget
    # ==========================================
    if sub == "ask_cash_budget":
        question = ask_llm(
            "Ask the user about their budget for buying a property naturally. Keep it short."
        )
        state["sub_phase"] = "extract_cash_budget"
        state["agent_message"] = question
        state["awaiting_input"] = True
        return state

    if sub == "extract_cash_budget" and user_input:
        digits = "".join(filter(str.isdigit, user_input))
        if digits and int(digits) > 0:
            state["budget"] = int(digits)
            state["phase"] = "location"
            state["sub_phase"] = None
            state["awaiting_input"] = False
            state["agent_message"] = None
        else:
            # Try LLM extraction
            budget_guess = ask_llm(
                f"User said: '{user_input}'. "
                f"Estimate a numeric budget for buying property in Egypt. "
                f"Return ONLY digits, no text."
            ).strip()
            digits = "".join(filter(str.isdigit, budget_guess))
            if digits and int(digits) > 0:
                state["budget"] = int(digits)
                state["phase"] = "location"
                state["sub_phase"] = None
                state["awaiting_input"] = False
                state["agent_message"] = None
            else:
                state["sub_phase"] = "ask_cash_loop"
                state["awaiting_input"] = False
        return state

    if sub == "ask_cash_loop":
        asked = state.get("asked_questions", [])
        previous = "\n".join(asked)
        question = ask_llm(
            f"You are an intelligent real estate assistant. "
            f"The user hasn't clearly stated their budget. "
            f"Ask ONE subtle question to discover their budget. "
            f"Different from: {previous}\nReturn ONLY the question."
        )
        asked.append(question)
        state["asked_questions"] = asked
        state["sub_phase"] = "extract_cash_loop"
        state["agent_message"] = question
        state["awaiting_input"] = True
        return state

    if sub == "extract_cash_loop" and user_input:
        budget_guess = ask_llm(
            f"User said: '{user_input}'. "
            f"Estimate a reasonable numeric budget for buying property in Egypt. "
            f"Return ONLY digits."
        ).strip()
        digits = "".join(filter(str.isdigit, budget_guess))
        if digits and int(digits) > 0:
            state["budget"] = int(digits)
            state["phase"] = "location"
            state["sub_phase"] = None
            state["awaiting_input"] = False
            state["agent_message"] = None
        else:
            state["sub_phase"] = "ask_cash_loop"
            state["awaiting_input"] = False
        return state

    # ==========================================
    # STEP 2b: Installments — ask DP + monthly
    # ==========================================
    if sub == "ask_installments":
        question = ask_llm(
            "Ask the user about their downpayment and expected monthly installment naturally. "
            "Keep it short."
        )
        state["sub_phase"] = "extract_installments"
        state["agent_message"] = question
        state["awaiting_input"] = True
        return state

    if sub == "extract_installments" and user_input:
        # Try extracting both values via LLM
        extraction = ask_llm(
            f"From this text, extract the downpayment and monthly installment amounts. "
            f"Return ONLY two numbers separated by a comma (downpayment,monthly). "
            f"If only one is mentioned, put 0 for the missing one.\n"
            f"User said: '{user_input}'"
        ).strip()

        parts = extraction.replace(" ", "").split(",")
        dp_digits = "".join(filter(str.isdigit, parts[0] if len(parts) > 0 else ""))
        mi_digits = "".join(filter(str.isdigit, parts[1] if len(parts) > 1 else ""))

        if dp_digits and int(dp_digits) > 0:
            state["Downpayment"] = int(dp_digits)
        if mi_digits and int(mi_digits) > 0:
            state["monthlyinstall"] = int(mi_digits)

        if state.get("Downpayment") and state.get("monthlyinstall"):
            state["phase"] = "location"
            state["sub_phase"] = None
            state["awaiting_input"] = False
            state["agent_message"] = None
        else:
            # Need to ask for missing values
            if not state.get("Downpayment"):
                state["sub_phase"] = "ask_dp_loop"
            else:
                state["sub_phase"] = "ask_mi_loop"
            state["awaiting_input"] = False
        return state

    # Ask DP loop
    if sub == "ask_dp_loop":
        question = ask_llm(
            "The user chose installments but hasn't provided a downpayment amount. "
            "Ask ONE natural question to discover it. Keep it short."
        )
        state["sub_phase"] = "extract_dp_loop"
        state["agent_message"] = question
        state["awaiting_input"] = True
        return state

    if sub == "extract_dp_loop" and user_input:
        guess = ask_llm(
            f"User said: '{user_input}'. Estimate downpayment amount. Return ONLY digits."
        ).strip()
        digits = "".join(filter(str.isdigit, guess))
        if digits and int(digits) > 0:
            state["Downpayment"] = int(digits)
            if state.get("monthlyinstall"):
                state["phase"] = "location"
                state["sub_phase"] = None
                state["awaiting_input"] = False
                state["agent_message"] = None
            else:
                state["sub_phase"] = "ask_mi_loop"
                state["awaiting_input"] = False
        else:
            state["sub_phase"] = "ask_dp_loop"
            state["awaiting_input"] = False
        return state

    # Ask monthly installment loop
    if sub == "ask_mi_loop":
        question = ask_llm(
            "The user chose installments but hasn't provided a monthly installment amount. "
            "Ask ONE natural question to discover it. Keep it short."
        )
        state["sub_phase"] = "extract_mi_loop"
        state["agent_message"] = question
        state["awaiting_input"] = True
        return state

    if sub == "extract_mi_loop" and user_input:
        guess = ask_llm(
            f"User said: '{user_input}'. Estimate monthly installment. Return ONLY digits."
        ).strip()
        digits = "".join(filter(str.isdigit, guess))
        if digits and int(digits) > 0:
            state["monthlyinstall"] = int(digits)
            if state.get("Downpayment"):
                state["phase"] = "location"
                state["sub_phase"] = None
                state["awaiting_input"] = False
                state["agent_message"] = None
            else:
                state["sub_phase"] = "ask_dp_loop"
                state["awaiting_input"] = False
        else:
            state["sub_phase"] = "ask_mi_loop"
            state["awaiting_input"] = False
        return state

    return state
