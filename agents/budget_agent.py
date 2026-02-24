from state import AgentState
from main_helpers import ask_ollama


def budget_agent(state: AgentState):
    print("\n--- Budget Agent (Ollama) ---")

    # ── Step 1: Always confirm payment type if not explicitly confirmed ──────
    if not state.get("payment_type_confirmed"):

        # If payment_type was extracted, confirm it — don't just trust it
        if state.get("payment_type"):
            prompt = (
                f"The user seems to want to pay by {state['payment_type']}. "
                f"Ask them to confirm this naturally in one sentence."
            )
            question = ask_ollama(prompt)
            print("Agent:", question)
            user_input = input("You: ").strip().lower()

            confirm_prompt = (
                f"The user was asked to confirm '{state['payment_type']}' as payment method. "
                f"They replied: '{user_input}'. "
                f"Did they confirm it? Reply ONLY: yes or no."
            )
            confirmed = ask_ollama(confirm_prompt).strip().lower()

            if confirmed != "yes":
                # Clear the wrongly inferred payment type
                state["payment_type"] = None

        # If still no payment type, ask fresh
        if not state.get("payment_type"):
            while True:
                question = ask_ollama(
                    "Ask the user if they want to pay by cash or installments "
                    "in a natural, friendly way. Only ask, don't answer."
                )
                print("Agent:", question)
                user_input = input("You: ").strip()

                extract_prompt = (
                    f"Extract ONLY the payment type from this input. "
                    f"Return exactly one word: cash or installments, or unknown if unclear.\n"
                    f"User said: '{user_input}'"
                )
                payment_type = ask_ollama(extract_prompt).strip().lower()

                if payment_type in ("cash", "installments"):
                    state["payment_type"] = payment_type
                    break
                print("Agent: Sorry, could you clarify — cash or installments?")

        state["payment_type_confirmed"] = True  # mark as confirmed so we never ask again

    # ── Step 2: Check if budget info is already complete ────────────────────
    has_cash_budget = state.get("payment_type") == "cash" and state.get("budget")
    has_installment_budget = (
        state.get("payment_type") == "installments"
        and state.get("Downpayment")
        and state.get("monthlyinstall")
    )
    if has_cash_budget or has_installment_budget:
        print("   Budget info already complete — skipping.")
        return state

    # ── Step 3: CASH — collect budget ───────────────────────────────────────
    if state["payment_type"] == "cash" and state.get("budget") is None:

        # First direct attempt (subtle)
        prompt_cash = "Ask the user about their budget naturally without being direct."
        question = ask_ollama(prompt_cash)
        print("Agent:", question)
        user_input_cash = input("You: ")

        digits_cash = "".join(filter(str.isdigit, user_input_cash))
        if digits_cash:
            state["budget"] = int(digits_cash)
            state["next_step"] = "location_agent"
            return state

        # If failed → enter intelligent question loop
        state["breakingbudget"] = False
        asked_questions = []

        while state["breakingbudget"] is False:
            previous_qs_text = "\n".join(asked_questions)

            prompt = f"""
You are an intelligent, empathetic real estate assistant.
The user has not clearly stated their budget for buying real estate.
Your goal is to discover the user's budget.

Instructions:
1. Ask ONE subtle, natural, human-like question at a time to guide the user toward revealing their budget.
2. Never directly ask "What is your budget?" or list options.
3. Make sure the next question is COMPLETELY different from all previous questions asked:
{previous_qs_text}
4. Make the questions friendly and contextual.
5. Stop after asking the question.
6. Output ONLY the question.
"""
            question = ask_ollama(prompt)
            asked_questions.append(question)
            print("Agent:", question)

            user_input = input("You: ")
            state["user_input"] = user_input

            # Let model guess budget using inference
            extract_prompt = f"""
User said: '{user_input}'.
Based on this information, estimate a reasonable numeric budget for buying a property in Egypt.
Return ONLY digits, no extra text.
"""
            budget_guess = ask_ollama(extract_prompt).strip()
            digits = "".join(filter(str.isdigit, budget_guess))

            if digits:
                state["budget"] = int(digits)
                state["next_step"] = "location_agent"
                state["breakingbudget"] = True

    # ── Step 4: INSTALLMENTS — collect down payment + monthly ───────────────
    elif state["payment_type"] == "installments" and (
        state.get("Downpayment") is None or state.get("monthlyinstall") is None
    ):

        prompt_install = (
            "Ask the user about their downpayment and monthly installment naturally "
            "without being direct or listing options. Only ask, don't answer."
        )
        question_install = ask_ollama(prompt_install)
        print("Agent:", question_install)

        user_input_downpayment = input("Down payment: ")
        user_input_monthly = input("Monthly installment: ")

        digits_downpayment = "".join(filter(str.isdigit, user_input_downpayment))
        digits_monthly = "".join(filter(str.isdigit, user_input_monthly))

        if digits_downpayment:
            state["Downpayment"] = int(digits_downpayment)
        if digits_monthly:
            state["monthlyinstall"] = int(digits_monthly)

        # Exit only if both are provided
        if state.get("Downpayment") and state.get("monthlyinstall"):
            state["next_step"] = "location_agent"
            return state

        # Start intelligent questioning loop
        state["breakinginstallments"] = False
        asked_install_questions: list[str] = []

        while not state["breakinginstallments"]:
            previous_qs_text = "\n".join(asked_install_questions)

            # Missing Downpayment
            if state.get("Downpayment") is None:
                prompt_downpayment_loop = f"""
You are an intelligent real estate assistant.
The user has chosen installments but has not provided the down payment.
Ask ONE natural question to guide the user into revealing a possible down payment.
Never ask directly.
Make the next question different from:
{previous_qs_text}
Return ONLY the question.
"""
                question = ask_ollama(prompt_downpayment_loop)
                asked_install_questions.append(question)
                print("Agent:", question)

                user_input_downpayment = input("You: ")
                down_guess = ask_ollama(
                    f"""
The user said: '{user_input_downpayment}'.

Based on this information, reason about the user's intentions, financial context, and preferences, 
and provide a reasonable numeric estimate for the down payment for buying a property in Egypt. 

Rules:
- Return ONLY digits (no text, no currency symbols, no explanations).
- Try to infer a sensible amount even if the user did not provide a number.
"""
                ).strip()

                down_digits = "".join(filter(str.isdigit, down_guess))
                if down_digits:
                    state["Downpayment"] = int(down_digits)

            # Missing Monthly installment
            if state.get("monthlyinstall") is None:
                prompt_monthly_loop = f"""
You are an intelligent real estate assistant.
The user has chosen installments but has not provided the monthly installment.
Ask ONE natural question to guide the user into revealing a monthly installment.
Never ask directly.
Make the next question different from:
{previous_qs_text}
Return ONLY the question.
"""
                question = ask_ollama(prompt_monthly_loop)
                asked_install_questions.append(question)
                print("Agent:", question)

                user_input_monthly = input("You: ")
                monthly_guess = ask_ollama(
                    f"""
The user said: '{user_input_monthly}'.

Based on this information, reason about the user's intentions, financial context, and preferences, 
and provide a reasonable numeric estimate for the monthly installment for buying a property in Egypt. 

Rules:
- Return ONLY digits (no text, no currency symbols, no explanations).
- Try to infer a sensible amount even if the user did not provide a number.
"""
                ).strip()

                monthly_digits = "".join(filter(str.isdigit, monthly_guess))
                if monthly_digits:
                    state["monthlyinstall"] = int(monthly_digits)

            if state.get("Downpayment") and state.get("monthlyinstall"):
                state["next_step"] = "location_agent"
                state["breakinginstallments"] = True

    return state