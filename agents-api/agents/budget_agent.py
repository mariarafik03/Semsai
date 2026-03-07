import os
import re
from .Normalization import normalize_location
from http_helpers import get_user_input
from dotenv import load_dotenv
from pymongo import MongoClient

from state import AgentState
from main_helpers import ask_ollama


def parse_numeric_amount(text: str) -> int | None:
    if not str(text).strip():
        return None

    # Normalize: remove commas, extra dots at end, lowercase
    text = str(text).strip().replace(",", "").lower()

    # Remove trailing punctuation like "20 m." → "20 m"
    text = re.sub(r"[.\s]+$", "", text)

    # Match patterns like: "20m", "20 m", "20million", "20 million", "1.5b", "500k"
    # Allow optional space between number and unit
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(millions?|billions?|thousands?|m|b|k)\b",
        text
    )
    if match:
        val = float(match.group(1))
        unit = match.group(2)
        if unit.startswith("m"):       # m, million, millions
            val *= 1_000_000
        elif unit.startswith("k"):     # k, thousand, thousands
            val *= 1_000
        elif unit.startswith("b"):     # b, billion, billions
            val *= 1_000_000_000
        return int(val)

    # Match plain numbers like "20000000"
    # Remove all spaces first for this pass
    plain = text.replace(" ", "")
    matches = re.findall(r"\d+(?:\.\d+)?", plain)
    if matches:
        return int(float(matches[0]))

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


def _detect_intent(user_input: str) -> str:
    """
    Detect what the user wants to do when budget doesn't match.
    Returns: 'change_location', 'change_budget', 'change_property_type', or 'unclear'
    """
    intent = ask_ollama(
        f"The user said: '{user_input}'.\n"
        "They were told their budget doesn't match available properties.\n"
        "What is their PRIMARY intent? Rules:\n"
        "- If they mention a city, area, or place name (e.g. 'new cairo', 'zayed', 'alexandria') → change_location\n"
        "- If they mention a new number or say 'increase budget' or 'raise budget' → change_budget\n"
        "- If they mention a property type (apartment, chalet, etc.) → change_property_type\n"
        "- Otherwise → unclear\n"
        "IMPORTANT: A place name always wins over other keywords. "
        "'change the budget to new cairo' means change_location, not change_budget.\n"
        "Return ONLY one of these exact words: change_location, change_budget, change_property_type, unclear"
    ).strip().lower()

    # Sanitize — only accept exact known values
    for valid in ("change_location", "change_budget", "change_property_type"):
        if valid in intent:
            return valid
    return "unclear"


def _extract_new_location(user_input: str) -> str | None:
    """Try to extract a location name from user input."""
    result = ask_ollama(
        f"The user said: '{user_input}'.\n"
        "Extract the location/area name they mentioned in Egypt (e.g. 'El Sheikh Zayed', 'Alexandria', 'New Cairo').\n"
        "Return ONLY the location name, or 'none' if no location found."
    ).strip()
    if result.lower() == "none":
        return None
    return result


def _ask_for_cash_budget(state) -> int | None:
    """
    Directly ask the user for their cash budget in a clear, simple way.
    Tries up to 3 times before giving up. Returns parsed integer or None.
    """
    for _ in range(3):
        question = ask_ollama(
            "Ask the user for their total cash budget in EGP. "
            "Be clear and direct. One sentence only. Do not answer, only ask."
        )
        print("Agent:", question)
        if "_input_queue" in state:
            user_input = get_user_input(state, question)
        else:
            user_input = input("You: ").strip()

        # Try direct parse first
        parsed = parse_numeric_amount(user_input)
        if parsed and parsed >= 100_000:
            return parsed

        # Ask LLM to interpret
        guess = ask_ollama(
            f"The user said: '{user_input}'.\n"
            "Extract their cash budget in EGP as a number. Return ONLY digits, nothing else."
        ).strip()
        parsed_guess = parse_numeric_amount(guess)
        if parsed_guess and parsed_guess >= 100_000:
            return parsed_guess

        print("Agent: I didn't quite catch a valid budget amount, let me ask again.")

    return None


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
                "Politely inform them and offer two options: revise their budget upward, "
                "or consider a different location or property type. Only ask, don't answer."
            )
            print("Agent:", message)
            if "_input_queue" in state:
                user_input = get_user_input(state, message)
            else:
                user_input = input("You: ")

            intent = _detect_intent(user_input)

            if intent == "change_location":
                new_location = _extract_new_location(user_input)
                if not new_location:
                    clarify = ask_ollama(
                        "The user wants to change location but didn't specify clearly. "
                        "Ask them which area in Egypt they'd like to look at instead. Only ask, don't answer."
                    )
                    print("Agent:", clarify)
                    if "_input_queue" in state:
                        new_location_input = get_user_input(state, clarify)
                    else:
                        new_location_input = input("You: ")
                    new_location = _extract_new_location(new_location_input) or new_location_input.strip()

                print(f"   ✓ Location changed to: {new_location}")
                state["location"] = new_location
                location = new_location

                state["candidate_compounds"] = None
                state["final_compounds"] = None
                state["compound_features_stats"] = None
                state["embeddings"] = None
                state["ranked_compounds"] = None
                state["final_best_compound"] = None

                new_result = get_min_price_for_location_and_type(location, property_type, payment_type)
                if new_result is None:
                    no_data_msg = ask_ollama(
                        f"We don't have data for {property_type} in {location}. "
                        "Inform the user politely and ask if they want to try another location or adjust their search."
                        " Only ask, don't answer."
                    )
                    print("Agent:", no_data_msg)
                    if "_input_queue" in state:
                        user_input2 = get_user_input(state, no_data_msg)
                    else:
                        user_input2 = input("You: ")
                    new_loc2 = _extract_new_location(user_input2)
                    if new_loc2:
                        state["location"] = new_loc2
                        location = new_loc2
                        new_result = get_min_price_for_location_and_type(location, property_type, payment_type)
                    if new_result is None:
                        return

                min_price = new_result.get("min_price", 0)
                continue

            elif intent == "change_property_type":
                clarify = ask_ollama(
                    "The user wants a different property type. "
                    "Ask them what type they'd prefer — apartment, villa, chalet, etc. Only ask, don't answer."
                )
                print("Agent:", clarify)
                if "_input_queue" in state:
                    new_type_input = get_user_input(state, clarify)
                else:
                    new_type_input = input("You: ").strip()
                new_type = ask_ollama(
                    f"User said: '{new_type_input}'. Extract property type (apartment/villa/chalet/townhouse). "
                    "Return ONLY the type word."
                ).strip().capitalize()
                print(f"   ✓ Property type changed to: {new_type}")
                state["typeofproperty"] = new_type
                property_type = new_type

                state["candidate_compounds"] = None
                state["final_compounds"] = None
                state["compound_features_stats"] = None
                state["embeddings"] = None
                state["ranked_compounds"] = None
                state["final_best_compound"] = None

                new_result = get_min_price_for_location_and_type(location, property_type, payment_type)
                if new_result is None:
                    return
                min_price = new_result.get("min_price", 0)
                continue

            else:
                # change_budget or unclear — try to parse a new number from input
                # First check: does the input contain a location name? If so, treat as location change.
                location_check = ask_ollama(
                    f"Does this text mention a city or area name in Egypt? '{user_input}'\n"
                    "Reply ONLY: yes or no."
                ).strip().lower()

                if location_check == "yes":
                    new_location = _extract_new_location(user_input)
                    if new_location:
                        print(f"   ✓ Location changed to: {new_location}")
                        state["location"] = new_location
                        location = new_location
                        state["candidate_compounds"] = None
                        state["final_compounds"] = None
                        state["compound_features_stats"] = None
                        state["embeddings"] = None
                        state["ranked_compounds"] = None
                        state["final_best_compound"] = None
                        new_result = get_min_price_for_location_and_type(location, property_type, payment_type)
                        if new_result is None:
                            return
                        min_price = new_result.get("min_price", 0)
                        continue

                parsed = parse_numeric_amount(user_input)
                if parsed is not None and parsed >= 100_000:
                    state["budget"] = parsed
                    user_budget = parsed
                    continue

                guess = ask_ollama(
                    f"User said: '{user_input}'. "
                    "If they mentioned a new budget amount, extract it as digits in EGP. "
                    "If no budget amount is mentioned, return: none"
                ).strip()
                if guess.lower() != "none":
                    parsed_guess = parse_numeric_amount(guess)
                    if parsed_guess is not None and parsed_guess >= 100_000:
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
                "Politely inform them, and offer options: revise their figures, change location, or change property type. "
                "Only ask, don't answer."
            )
            print("Agent:", message)
            if "_input_queue" in state:
                user_input = get_user_input(state, message)
            else:
                user_input = input("You: ")

            intent = _detect_intent(user_input)

            if intent == "change_location":
                new_location = _extract_new_location(user_input)
                if not new_location:
                    ask_loc = ask_ollama(
                        "Ask the user which area they'd like to look at instead. Only ask, don't answer."
                    )
                    print("Agent:", ask_loc)
                    if "_input_queue" in state:
                        loc_input = get_user_input(state, ask_loc)
                    else:
                        loc_input = input("You: ").strip()
                    new_location = _extract_new_location(loc_input) or loc_input.strip()

                print(f"   ✓ Location changed to: {new_location}")
                state["location"] = new_location
                location = new_location
                state["candidate_compounds"] = None
                state["final_compounds"] = None
                state["compound_features_stats"] = None
                state["embeddings"] = None
                state["ranked_compounds"] = None
                state["final_best_compound"] = None

                new_result = get_min_price_for_location_and_type(location, property_type, payment_type)
                if new_result is None:
                    return
                min_down = new_result.get("min_down_payment", 0)
                min_monthly = new_result.get("min_monthly", 0)
                continue

            elif intent == "change_property_type":
                clarify = ask_ollama(
                    "Ask the user what property type they'd prefer instead. Only ask, don't answer."
                )
                print("Agent:", clarify)
                if "_input_queue" in state:
                    new_type_input = get_user_input(state, clarify)
                else:
                    new_type_input = input("You: ").strip()
                new_type = ask_ollama(
                    f"User said: '{new_type_input}'. Extract property type. Return ONLY the type word."
                ).strip().capitalize()
                print(f"   ✓ Property type changed to: {new_type}")
                state["typeofproperty"] = new_type
                property_type = new_type
                state["candidate_compounds"] = None
                state["final_compounds"] = None
                state["compound_features_stats"] = None
                state["embeddings"] = None
                state["ranked_compounds"] = None
                state["final_best_compound"] = None

                new_result = get_min_price_for_location_and_type(location, property_type, payment_type)
                if new_result is None:
                    return
                min_down = new_result.get("min_down_payment", 0)
                min_monthly = new_result.get("min_monthly", 0)
                continue

            else:
                if user_down < min_down:
                    parsed_down = parse_numeric_amount(user_input)
                    if parsed_down is None:
                        q_down = "Revised down payment:"
                        if "_input_queue" in state:
                            raw_down = get_user_input(state, q_down)
                        else:
                            raw_down = input("Revised down payment: ")
                        parsed_down = parse_numeric_amount(raw_down)
                    if parsed_down is not None:
                        state["Downpayment"] = parsed_down
                        user_down = parsed_down

                if user_monthly < min_monthly:
                    q_monthly = "Revised monthly installment:"
                    if "_input_queue" in state:
                        raw_monthly = get_user_input(state, q_monthly)
                    else:
                        raw_monthly = input("Revised monthly installment: ")
                    parsed_monthly = parse_numeric_amount(raw_monthly)
                    if parsed_monthly is not None:
                        state["monthlyinstall"] = parsed_monthly
                        user_monthly = parsed_monthly


def budget_agent(state: AgentState):
    print("\n--- Budget Agent (Ollama) ---")

    # ── STEP 1: Always confirm payment type first, no assumptions ──────────
    if not state.get("payment_type_confirmed"):

        # If extraction agent guessed a payment type, confirm it with user
        if state.get("payment_type"):
            prompt = (
                f"The user seems to want to pay by {state['payment_type']}. "
                "Ask them to confirm this naturally in one sentence."
            )
            question = ask_ollama(prompt)
            print("Agent:", question)
            if "_input_queue" in state:
                user_input = get_user_input(state, question)
            else:
                user_input = input("You: ").strip()

            confirm_prompt = (
                f"The user was asked to confirm '{state['payment_type']}' as payment method. "
                f"They replied: '{user_input}'. Did they confirm it? Reply ONLY: yes or no."
            )
            confirmed = ask_ollama(confirm_prompt).strip().lower()
            if confirmed != "yes":
                # Reset ALL budget fields — payment type changed, old numbers are meaningless
                state["payment_type"] = None
                state["budget"] = None
                state["Downpayment"] = None
                state["monthlyinstall"] = None

        # If extraction agent found a number but NO payment type, clear numbers and ask cleanly
        elif state.get("budget") or state.get("Downpayment"):
            print("   [Budget Agent] A number was extracted but payment type is unknown — will ask.")
            state["budget"] = None
            state["Downpayment"] = None
            state["monthlyinstall"] = None

        # Ask for payment type if still unknown
        if not state.get("payment_type"):
            while True:
                question = ask_ollama(
                    "Ask the user if they want to pay by cash or installments in a natural, friendly way. "
                    "Only ask, don't answer."
                )
                print("Agent:", question)
                if "_input_queue" in state:
                    user_input = get_user_input(state, question)
                else:
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
                print("Agent: Sorry, could you clarify — cash or installments?")

        state["payment_type_confirmed"] = True

    # ── STEP 2: If budget fields already populated, validate against DB ────
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
        return state

    # ── STEP 3: Budget fields missing — collect them ───────────────────────

    if state.get("payment_type") == "cash" and state.get("budget") is None:

        # ── 3a: Check if the user mentioned a bare number (e.g. "25") without scale ──
        raw_hint = state.get("raw_budget_hint") or state.get("user_input", "")
        bare_number = None

        if raw_hint:
            bare_guess = ask_ollama(
                f"The user said: '{raw_hint}'. "
                "Did they mention a number that looks like a budget amount (e.g. '10', '5', '30')? "
                "If yes, return ONLY the digits of that number (e.g. '10'). "
                "If no number found, return: none"
            ).strip().lower()
            if bare_guess != "none" and bare_guess.isdigit():
                bare_number = int(bare_guess)

        if bare_number is not None:
            # User said something like "25" — confirm the scale
            confirm_q = ask_ollama(
                f"The user mentioned the number {bare_number} but didn't specify the scale. "
                f"Ask them naturally whether they meant {bare_number} million EGP, "
                f"{bare_number} thousand EGP, or something else. Only ask, don't answer."
            )
            print("Agent:", confirm_q)
            if "_input_queue" in state:
                scale_input = get_user_input(state, confirm_q)
            else:
                scale_input = input("You: ").strip()

            # Try to parse the confirmed amount directly first
            confirmed_amount = parse_numeric_amount(scale_input)
            if confirmed_amount and confirmed_amount >= 100_000:
                state["budget"] = confirmed_amount
                if state.get("location") and state.get("typeofproperty"):
                    validate_budget_against_db(state)
                state["budget_valid"] = True
                return state

            # If user said just "million" or "M" without repeating the number, multiply
            scale_lower = scale_input.lower()
            if any(w in scale_lower for w in ("million", "mln", "m", "m egp")):
                state["budget"] = bare_number * 1_000_000
            elif any(w in scale_lower for w in ("thousand", "k")):
                state["budget"] = bare_number * 1_000
            else:
                interpreted = ask_ollama(
                    f"The user was asked whether '{bare_number}' means million or thousand EGP. "
                    f"They replied: '{scale_input}'. "
                    "What is the full amount in EGP? Return ONLY digits, no text."
                ).strip()
                parsed_interp = parse_numeric_amount(interpreted)
                if parsed_interp and parsed_interp >= 100_000:
                    state["budget"] = parsed_interp

            if state.get("budget"):
                if state.get("location") and state.get("typeofproperty"):
                    validate_budget_against_db(state)
                state["budget_valid"] = True
                return state

        # ── 3b: No bare number found — directly ask for budget ──
        # Keep asking until we get a valid number (max 3 attempts via helper)
        parsed_budget = _ask_for_cash_budget(state)
        if parsed_budget is not None:
            state["budget"] = parsed_budget
            if state.get("location") and state.get("typeofproperty"):
                validate_budget_against_db(state)
            state["budget_valid"] = True
            return state

        # If all 3 attempts failed, inform user and exit gracefully
        print("Agent: I'm having trouble understanding your budget. "
              "Please restart and enter your budget clearly, e.g. '5 million EGP' or '5000000'.")
        state["budget_valid"] = False
        return state

    elif state.get("payment_type") == "installments" and (
        state.get("Downpayment") is None or state.get("monthlyinstall") is None
    ):
        # ── 3c: Installments — ask directly for down payment, monthly, and years ──
        prompt_install = (
            "Ask the user for their down payment amount, monthly installment amount, "
            "and preferred number of years for the payment plan. "
            "Be clear and direct. Only ask, don't answer."
        )
        question_install = ask_ollama(prompt_install)
        print("Agent:", question_install)

        if "_input_queue" in state:
            user_input_downpayment = get_user_input(state, "Down payment:")
            user_input_monthly = get_user_input(state, "Monthly installment:")
            user_input_years = get_user_input(state, "Number of years:")
        else:
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
            if state.get("location") and state.get("typeofproperty"):
                validate_budget_against_db(state)
            state["budget_valid"] = True
            return state

        # ── 3d: Fallback — collect missing installment fields one by one ──
        for _ in range(3):
            if state.get("Downpayment") is None:
                q = ask_ollama(
                    "Ask the user for their down payment amount in EGP clearly. "
                    "One sentence only. Only ask, don't answer."
                )
                print("Agent:", q)
                if "_input_queue" in state:
                    raw = get_user_input(state, q)
                else:
                    raw = input("You: ").strip()
                parsed = parse_numeric_amount(raw)
                if parsed is None:
                    parsed = parse_numeric_amount(
                        ask_ollama(
                            f"User said: '{raw}'. Extract down payment in EGP. Return ONLY digits."
                        ).strip()
                    )
                if parsed:
                    state["Downpayment"] = parsed

            if state.get("monthlyinstall") is None:
                q = ask_ollama(
                    "Ask the user for their monthly installment amount in EGP clearly. "
                    "One sentence only. Only ask, don't answer."
                )
                print("Agent:", q)
                if "_input_queue" in state:
                    raw = get_user_input(state, q)
                else:
                    raw = input("You: ").strip()
                parsed = parse_numeric_amount(raw)
                if parsed is None:
                    parsed = parse_numeric_amount(
                        ask_ollama(
                            f"User said: '{raw}'. Extract monthly installment in EGP. Return ONLY digits."
                        ).strip()
                    )
                if parsed:
                    state["monthlyinstall"] = parsed

            if state.get("Downpayment") and state.get("monthlyinstall"):
                state["budget"] = (
                    state["Downpayment"] + state["monthlyinstall"] * 12 * state.get("years", 1)
                )
                break

        if not (state.get("Downpayment") and state.get("monthlyinstall")):
            print("Agent: I'm having trouble capturing your installment details. "
                  "Please restart and provide your down payment and monthly installment clearly.")
            state["budget_valid"] = False
            return state

    # ── Final validation ───────────────────────────────────────────────────
    if state.get("location") and state.get("typeofproperty") and (
        state.get("budget") or (state.get("Downpayment") and state.get("monthlyinstall"))
    ):
        validate_budget_against_db(state)

    state["budget_valid"] = True
    return state