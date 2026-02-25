import os
import re

from dotenv import load_dotenv
from pymongo import MongoClient

from state import AgentState
from main_helpers import ask_ollama


def parse_numeric_amount(text: str) -> int | None:
    if not str(text).strip():
        return None

    text = str(text).replace(",", "").replace(" ", "").lower()

    match = re.search(r"(\d+(?:\.\d+)?)\s*(m|k|b|million|billion|thousand)", text)
    if match:
        val = float(match.group(1))
        unit = match.group(2)
        if unit in ("m", "million"):
            val *= 1_000_000
        elif unit in ("k", "thousand"):
            val *= 1_000
        elif unit in ("b", "billion"):
            val *= 1_000_000_000
        return int(val)

    matches = re.findall(r"\d+", text)
    if matches:
        return int(matches[0])

    return None


def get_min_price_for_location_and_type(location: str, property_type: str, payment_type: str) -> dict | None:
    load_dotenv()
    uri = os.getenv("MONGO_URI")
    if not uri:
        print("No MONGO_URI found in environment")
        return None

    client = MongoClient(uri)
    db = client["semsai"]
    collection = db["units"]

    base_query = {
        "location": {"$regex": location, "$options": "i"},
        "property_type": {"$regex": f"^{property_type}$", "$options": "i"},
    }

    if payment_type == "cash":
        pipeline = [
            {"$match": {
                **base_query,
                "payment_plans": {
                    "$elemMatch": {
                        "is_cash": True,
                        "unit_price": {"$ne": None, "$gt": 0},
                    }
                },
            }},
            {"$unwind": "$payment_plans"},
            {"$match": {
                "payment_plans.is_cash": True,
                "payment_plans.unit_price": {"$ne": None, "$gt": 0},
            }},
            {"$group": {"_id": None, "min_price": {"$min": "$payment_plans.unit_price"}}},
        ]
    else:
        pipeline = [
            {"$match": {
                **base_query,
                "payment_plans": {
                    "$elemMatch": {
                        "is_cash": False,
                        "down_payment": {"$ne": None, "$gt": 0},
                        "single_installment_amount": {"$ne": None, "$gt": 0},
                    }
                },
            }},
            {"$unwind": "$payment_plans"},
            {"$match": {
                "payment_plans.is_cash": False,
                "payment_plans.down_payment": {"$ne": None, "$gt": 0},
                "payment_plans.single_installment_amount": {"$ne": None, "$gt": 0},
            }},
            {"$group": {
                "_id": None,
                "min_down_payment": {"$min": "$payment_plans.down_payment"},
                "min_monthly": {"$min": "$payment_plans.single_installment_amount"},
            }},
        ]

    result = list(collection.aggregate(pipeline))
    client.close()

    if not result:
        return None

    return result[0]


def validate_budget_against_db(state: AgentState) -> None:
    location = state.get("location")
    property_type = state.get("typeofproperty")
    payment_type = state.get("payment_type")

    if not location or not property_type or not payment_type:
        return

    result = get_min_price_for_location_and_type(location, property_type, payment_type)
    if result is None:
        return

    if payment_type == "cash":
        min_price = result.get("min_price", 0)
        user_budget = state.get("budget", 0)

        while user_budget < min_price:
            message = ask_ollama(
                f"The user's budget is {user_budget} EGP, but the cheapest available "
                f"{property_type} in {location} costs {min_price} EGP. "
                "Politely inform them and ask them to revise it. Only ask, don't answer."
            )
            print("Agent:", message)
            user_input = input("You: ")

            parsed = parse_numeric_amount(user_input)
            if parsed is not None:
                state["budget"] = parsed
                user_budget = parsed
                continue

            guess = ask_ollama(
                f"User said: '{user_input}'. Extract or infer a numeric budget in EGP. Return ONLY digits."
            ).strip()
            parsed_guess = parse_numeric_amount(guess)
            if parsed_guess is not None:
                state["budget"] = parsed_guess
                user_budget = parsed_guess

    else:
        min_down = result.get("min_down_payment", 0)
        min_monthly = result.get("min_monthly", 0)
        user_down = state.get("Downpayment", 0)
        user_monthly = state.get("monthlyinstall", 0)

        while user_down < min_down or user_monthly < min_monthly:
            issues = []
            if user_down < min_down:
                issues.append(f"down payment is {user_down} EGP but minimum is {min_down} EGP")
            if user_monthly < min_monthly:
                issues.append(f"monthly installment is {user_monthly} EGP but minimum is {min_monthly} EGP")

            message = ask_ollama(
                f"The user wants a {property_type} in {location} via installments. "
                f"Their {' and '.join(issues)}. "
                "Politely inform them and ask for revised figures. Only ask, don't answer."
            )
            print("Agent:", message)

            if user_down < min_down:
                parsed_down = parse_numeric_amount(input("Revised down payment: "))
                if parsed_down is not None:
                    state["Downpayment"] = parsed_down
                    user_down = parsed_down

            if user_monthly < min_monthly:
                parsed_monthly = parse_numeric_amount(input("Revised monthly installment: "))
                if parsed_monthly is not None:
                    state["monthlyinstall"] = parsed_monthly
                    user_monthly = parsed_monthly


def budget_agent(state: AgentState):
    print("\n--- Budget Agent (Ollama) ---")

    if not state.get("payment_type_confirmed"):
        if state.get("payment_type"):
            prompt = (
                f"The user seems to want to pay by {state['payment_type']}. "
                "Ask them to confirm this naturally in one sentence."
            )
            question = ask_ollama(prompt)
            print("Agent:", question)
            user_input = input("You: ").strip().lower()

            confirm_prompt = (
                f"The user was asked to confirm '{state['payment_type']}' as payment method. "
                f"They replied: '{user_input}'. Did they confirm it? Reply ONLY: yes or no."
            )
            confirmed = ask_ollama(confirm_prompt).strip().lower()
            if confirmed != "yes":
                state["payment_type"] = None

        if not state.get("payment_type"):
            while True:
                question = ask_ollama(
                    "Ask the user if they want to pay by cash or installments in a natural, friendly way. "
                    "Only ask, don't answer."
                )
                print("Agent:", question)
                user_input = input("You: ").strip()

                extract_prompt = (
                    "Extract ONLY the payment type from this input. "
                    "Return exactly one word: cash or installments, or unknown if unclear.\n"
                    f"User said: '{user_input}'"
                )
                payment_type = ask_ollama(extract_prompt).strip().lower()
                if payment_type in ("cash", "installments"):
                    state["payment_type"] = payment_type
                    break
                print("Agent: Sorry, could you clarify - cash or installments?")

        state["payment_type_confirmed"] = True

    has_cash_budget = state.get("payment_type") == "cash" and state.get("budget")
    has_installment_budget = (
        state.get("payment_type") == "installments"
        and state.get("Downpayment")
        and state.get("monthlyinstall")
    )

    if has_cash_budget or has_installment_budget:
        if state.get("location") and state.get("typeofproperty"):
            validate_budget_against_db(state)
            state["budget_valid"] = True
        else:
            print("   Budget info already complete - skipping.")
        return state

    if state["payment_type"] == "cash" and state.get("budget") is None:
        prompt_cash = "Ask the user about their budget naturally without being direct."
        question = ask_ollama(prompt_cash)
        print("Agent:", question)
        user_input_cash = input("You: ")

        parsed_cash = parse_numeric_amount(user_input_cash)
        if parsed_cash is not None:
            state["budget"] = parsed_cash
            state["next_step"] = "location_agent"
            if state.get("location") and state.get("typeofproperty"):
                validate_budget_against_db(state)
                state["budget_valid"] = True
            return state

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
2. Never directly ask \"What is your budget?\" or list options.
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

            extract_prompt = f"""
User said: '{user_input}'.
Based on this information, estimate a reasonable numeric budget for buying a property in Egypt.
Return ONLY digits, no extra text.
"""
            budget_guess = ask_ollama(extract_prompt).strip()
            parsed_budget = parse_numeric_amount(budget_guess)
            if parsed_budget is not None:
                state["budget"] = parsed_budget
                state["next_step"] = "location_agent"
                state["breakingbudget"] = True

    elif state["payment_type"] == "installments" and (
        state.get("Downpayment") is None or state.get("monthlyinstall") is None
    ):
        prompt_install = (
            "Ask the user about their downpayment and monthly installment and number of years naturally "
            "without being direct or listing options. Only ask, don't answer."
        )
        question_install = ask_ollama(prompt_install)
        print("Agent:", question_install)

        user_input_downpayment = input("Down payment: ")
        user_input_monthly = input("Monthly installment: ")
        user_input_years = input("Number of years: ")

        parsed_down = parse_numeric_amount(user_input_downpayment)
        parsed_monthly = parse_numeric_amount(user_input_monthly)
        parsed_years = parse_numeric_amount(user_input_years)

        if parsed_down is not None:
            state["Downpayment"] = parsed_down
        if parsed_monthly is not None:
            state["monthlyinstall"] = parsed_monthly
        if parsed_years is not None:
            state["years"] = parsed_years

        if state.get("Downpayment") and state.get("monthlyinstall"):
            state["budget"] = state["Downpayment"] + state["monthlyinstall"] * 12 * state.get("years", 1)
            state["next_step"] = "location_agent"
            if state.get("location") and state.get("typeofproperty"):
                validate_budget_against_db(state)
                state["budget_valid"] = True
            return state

        state["breakinginstallments"] = False
        asked_install_questions: list[str] = []

        while not state["breakinginstallments"]:
            previous_qs_text = "\n".join(asked_install_questions)

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

                parsed_down_guess = parse_numeric_amount(down_guess)
                if parsed_down_guess is not None:
                    state["Downpayment"] = parsed_down_guess

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

                parsed_monthly_guess = parse_numeric_amount(monthly_guess)
                if parsed_monthly_guess is not None:
                    state["monthlyinstall"] = parsed_monthly_guess

            if state.get("Downpayment") and state.get("monthlyinstall"):
                state["budget"] = state["Downpayment"] + state["monthlyinstall"] * 12 * state.get("years", 1)
                state["next_step"] = "location_agent"
                state["breakinginstallments"] = True

    if state.get("location") and state.get("typeofproperty") and (
        state.get("budget") or (state.get("Downpayment") and state.get("monthlyinstall"))
    ):
        validate_budget_against_db(state)
        state["budget_valid"] = True

    return state
