from state import AgentState
from main_helpers import ask_ollama


def budget_agent(state: AgentState):
    print("\n--- Budget Agent (Ollama) ---")

    asked_questions = []
    if state.get("payment_type") is None:

        prompt = (
            "You are a friendly real estate assistant. "
            "Ask the user if they want to pay by cash or installments in a natural way. "
            "Do not answer for them, just ask the question."
        )
        question = ask_ollama(prompt)
        print("Agent:", question)

        user_payment_input = input("You: ")
        state["user_input"] = user_payment_input

        extract_prompt = (
            f"Extract ONLY the payment type from this input. "
            "Return exactly one word: 'cash' or 'installments'. "
            f"User said: '{user_payment_input}'"
        )
        payment_type = ask_ollama(extract_prompt).strip().lower()

        if payment_type not in ["cash", "installments"]:
            print("Agent: I couldn't understand. Please type 'cash' or 'installments'.")
            return budget_agent(state)  # retry

        state["payment_type"] = payment_type

    if state["payment_type"] == "cash" and state.get("budget") is None:
        state["breakingbudget"] = False
        while state["breakingbudget"] is False:
            previous_qs_text = "\n".join(asked_questions)
            prompt = f"""
You are an extremely intelligent, empathetic real estate assistant.
The user has not clearly stated their budget for buying real estate.
Your goal is to discover the user's budget.

Instructions:
1. Ask ONE subtle, natural, human-like question at a time to guide the user toward revealing their budget.
2. Never directly ask "What is your budget?" or list options.
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

            digits_budget = ask_ollama(
    f"""
The user provided the following information about their preferences: '{state['user_input']}'.
Based on this information, estimate a reasonable numeric budget for buying a property in Egypt.
Return ONLY the digits, no extra text.
"""
).strip()


            digits = "".join(filter(str.isdigit, digits_budget))
            if digits:
                state["budget"] = int(digits)
                state["next_step"] = "location_agent"
                state["breakingbudget"] = True

    elif state["payment_type"] == "installments" and (state.get("Downpayment") is None or state.get("monthlyinstall") is None):state["breakinginstallments"] = False
    if "asked_questions" not in state:
        state["asked_questions"] = []
    asked_questions = state["asked_questions"]

    while state["breakinginstallments"] is False:
        previous_qs_text = "\n".join(asked_questions)
        prompt = f"""
You are an extremely intelligent, empathetic real estate assistant.
The user has chosen installments but has not provided complete payment details.
Your goal is to discover the down payment and monthly installment amounts.

Instructions:
1. Ask ONE subtle, natural, human-like question at a time to guide the user toward revealing either the down payment or the monthly installment.
2. Never directly ask "What is your down payment?" or "What is your monthly installment?".
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

        # Estimate numeric values from user input
        extract_down_prompt = f"""
The user provided the following info: '{state['user_input']}'.
Based on this, estimate a reasonable numeric down payment for buying a property in Egypt.
Return ONLY digits, no extra text.
"""
        extract_monthly_prompt = f"""
The user provided the following info: '{state['user_input']}'.
Based on this, estimate a reasonable numeric monthly installment for buying a property in Egypt.
Return ONLY digits, no extra text.
"""
        down_digits = "".join(filter(str.isdigit, ask_ollama(extract_down_prompt)))
        monthly_digits = "".join(filter(str.isdigit, ask_ollama(extract_monthly_prompt)))

        if down_digits:
            state["Downpayment"] = int(down_digits)
        if monthly_digits:
            state["monthlyinstall"] = int(monthly_digits)

        # Stop loop once both values are obtained
        if state.get("Downpayment") and state.get("monthlyinstall"):
            state["next_step"] = "location_agent"
            state["breakinginstallments"] = True

        # Always update asked questions
        state["asked_questions"] = asked_questions

    return state
