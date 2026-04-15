import os
import re
from pymongo import MongoClient
from dotenv import load_dotenv
from state import AgentState
from main_helpers import ask_ollama
from .Normalization import normalize_location

# Load environment variables for MongoDB
load_dotenv()

# ---------------------------------------------------------------------------
# Helpers & Parsing (The "Brains")
# ---------------------------------------------------------------------------

def parse_numeric_amount(text: str) -> int | None:
    if not str(text).strip():
        return None

    text = str(text).strip().replace(",", "").lower()
    text = re.sub(r"[.\s]+$", "", text)

    # Match patterns like: "20m", "20 million", "1.5b", "500k"
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(millions?|billions?|thousands?|m|b|k)\b",
        text
    )
    if match:
        val = float(match.group(1))
        unit = match.group(2)
        if unit.startswith("m"): val *= 1_000_000
        elif unit.startswith("k"): val *= 1_000
        elif unit.startswith("b"): val *= 1_000_000_000
        return int(val)

    # Match plain numbers
    plain = text.replace(" ", "")
    matches = re.findall(r"\d+(?:\.\d+)?", plain)
    if matches:
        return int(float(matches[0]))

    return None

def get_db_min_prices(location: str, property_type: str, payment_type: str):
    uri = os.getenv("MONGO_URI")
    if not uri: return None
    
    client = MongoClient(uri)
    db = client["semsai"]
    collection = db["units"]

    base_query = {
        "location": {"$regex": location, "$options": "i"},
        "property_type": {"$regex": f"^{property_type}$", "$options": "i"},
    }

    if payment_type == "cash":
        pipeline = [
            {"$match": {**base_query, "payment_plans.is_cash": True}},
            {"$unwind": "$payment_plans"},
            {"$match": {"payment_plans.is_cash": True}},
            {"$group": {"_id": None, "min_price": {"$min": "$payment_plans.unit_price"}}},
        ]
    else:
        pipeline = [
            {"$match": {**base_query, "payment_plans.is_cash": False}},
            {"$unwind": "$payment_plans"},
            {"$match": {"payment_plans.is_cash": False}},
            {"$group": {
                "_id": None,
                "min_down_payment": {"$min": "$payment_plans.down_payment"},
                "min_monthly": {"$min": "$payment_plans.single_installment_amount"},
            }},
        ]

    result = list(collection.aggregate(pipeline))
    client.close()
    return result[0] if result else None

# ---------------------------------------------------------------------------
# Budget Agent (The "Skeleton") — FIXED VERSION
# ---------------------------------------------------------------------------

def budget_agent(state: AgentState) -> AgentState:
    print("--- Budget Agent Active ---")
    
    user_input = (state.get("user_input") or "").strip()
    waiting = state.get("waiting_for")

    # ═══════════════════════════════════════════════════════════════════════
    # 0. HANDLE "BUDGET EXCEEDED" CHOICE RESPONSE
    # ═══════════════════════════════════════════════════════════════════════
    if waiting == "budget_exceeded_choice":
        choice_text = user_input.lower()

        if "1" in choice_text or "increase" in choice_text or "budget" in choice_text:
            # User wants to increase budget — reset budget fields
            state["budget_valid"] = None
            if state.get("payment_type") == "cash":
                state["budget"] = None
                state["waiting_for"] = None
                # Router will send back to budget_agent which will re-ask cash_budget
            else:
                state["Downpayment"] = None
                state["monthlyinstall"] = None
                state["waiting_for"] = None
            print("→ Budget exceeded choice: increase budget")
            return state

        elif "2" in choice_text or "location" in choice_text:
            # Try to extract the new location directly from the user's message
            # e.g. "change the location to new cairo" → extract "New Cairo"
            new_location = normalize_location(user_input)
            if new_location:
                state["location"]     = new_location
                state["budget_valid"] = None
                state["waiting_for"]  = None
                state["agent_message"] = (
                    f"\u2705 Location changed to **{new_location}**. "
                    f"Let me check availability there..."
                )
                print(f"\u2713 Location changed to: {new_location}")
            else:
                # No inline location found — reset and let location_agent ask fresh
                state["location"]       = None
                state["typeofproperty"] = None
                state["budget_valid"]   = None
                state["waiting_for"]    = None
                print("\u2192 Budget exceeded: change location (will ask fresh)")
            return state

        elif "3" in choice_text or "type" in choice_text or "property" in choice_text:
            # Try to extract the new property type directly from the user's message
            # e.g. "change to apartment" or "I'd prefer a chalet"
            _PROP_MAP = {
                "villa": "Villa",      "vila": "Villa",
                "apartment": "Apartment", "flat": "Apartment",
                "chalet": "Chalet",    "studio": "Apartment",
                "penthouse": "Apartment", "duplex": "Apartment",
                "townhouse": "Villa",
            }
            new_type = next((v for k, v in _PROP_MAP.items() if k in choice_text), None)
            if new_type:
                state["typeofproperty"] = new_type
                state["budget_valid"]   = None
                state["waiting_for"]    = None
                state["agent_message"] = (
                    f"\u2705 Property type changed to **{new_type}**. "
                    f"Let me check what's available..."
                )
                print(f"\u2713 Property type changed to: {new_type}")
            else:
                # No inline type found — reset and let location_agent ask fresh
                state["typeofproperty"] = None
                state["budget_valid"]   = None
                state["waiting_for"]    = None
                print("\u2192 Budget exceeded: change type (will ask fresh)")
            return state

        else:
            # Couldn't understand — re-ask
            state["agent_message"] = (
                "I didn't quite catch that. Please choose one of:\n\n"
                "1\ufe0f\u20e3 Increase my budget\n"
                "2\ufe0f\u20e3 Change location\n"
                "3\ufe0f\u20e3 Change property type"
            )
            state["waiting_for"] = "budget_exceeded_choice"
            return state

    # ═══════════════════════════════════════════════════════════════════════
    # 1. HANDLE PAYMENT TYPE
    # ═══════════════════════════════════════════════════════════════════════
    if not state.get("payment_type"):
        if waiting == "payment_type":
            # User is responding to payment type question
            extracted = ask_ollama(f"Extract payment type: cash or installments? User said: '{user_input}'").lower()
            
            if "cash" in extracted:
                state["payment_type"] = "cash"
                state["waiting_for"] = None  # ✅ FIX: Clear waiting flag
                print(f"✓ Payment type set to: cash")
            elif "installment" in extracted:
                state["payment_type"] = "installments"
                state["waiting_for"] = None  # ✅ FIX: Clear waiting flag
                print(f"✓ Payment type set to: installments")
            else:
                # Couldn't understand, ask again
                state["agent_message"] = "I'm sorry, I didn't understand. Would you prefer to pay in **cash** or **installments**?"
                state["waiting_for"] = "payment_type"
                return state
        else:
            # First time asking for payment type
            state["agent_message"] = "How would you like to pay? We offer cash and installment plans."
            state["waiting_for"] = "payment_type"
            return state

    # ═══════════════════════════════════════════════════════════════════════
    # 2. HANDLE CASH FLOW
    # ═══════════════════════════════════════════════════════════════════════
    if state["payment_type"] == "cash":
        if not state.get("budget"):
            if waiting == "cash_budget":
                # User is responding to budget question
                amount = parse_numeric_amount(user_input)
                if amount and amount >= 100_000:
                    state["budget"] = amount
                    state["waiting_for"] = None  # ✅ FIX: Clear waiting flag
                    print(f"✓ Cash budget set to: {amount:,} EGP")
                else:
                    state["agent_message"] = "Could you please specify your total cash budget? (e.g., 5 million EGP). Minimum is 100,000 EGP."
                    state["waiting_for"] = "cash_budget"
                    return state
            else:
                # First time asking for cash budget
                state["agent_message"] = "What is your total **cash budget** in EGP?"
                state["waiting_for"] = "cash_budget"
                return state

    # ═══════════════════════════════════════════════════════════════════════
    # 3. HANDLE INSTALLMENT FLOW
    # ═══════════════════════════════════════════════════════════════════════
    else:  # payment_type == "installments"
        # 3a. Check Downpayment
        if not state.get("Downpayment"):
            if waiting == "downpayment":
                # User is responding to downpayment question
                amount = parse_numeric_amount(user_input)
                if amount:
                    state["Downpayment"] = amount
                    state["waiting_for"] = None  # ✅ FIX: Clear waiting flag
                    print(f"✓ Downpayment set to: {amount:,} EGP")
                else:
                    state["agent_message"] = "What is the down payment amount you are comfortable with? (e.g., 500,000 EGP)"
                    state["waiting_for"] = "downpayment"
                    return state
            else:
                # First time asking for downpayment
                state["agent_message"] = "To find the best plan, what is your preferred down payment?"
                state["waiting_for"] = "downpayment"
                return state
        
        # 3b. Check Monthly Installment
        if not state.get("monthlyinstall"):
            if waiting == "monthly":
                # User is responding to monthly installment question
                amount = parse_numeric_amount(user_input)
                if amount:
                    state["monthlyinstall"] = amount
                    state["waiting_for"] = None  # ✅ FIX: Clear waiting flag
                    print(f"✓ Monthly installment set to: {amount:,} EGP")
                else:
                    state["agent_message"] = "What is the maximum monthly installment you can pay? (e.g., 20,000 EGP)"
                    state["waiting_for"] = "monthly"
                    return state
            else:
                # First time asking for monthly installment
                state["agent_message"] = "And what is your maximum monthly installment?"
                state["waiting_for"] = "monthly"
                return state

    # ═══════════════════════════════════════════════════════════════════════
    # 4. VALIDATION AGAINST DB — ONLY AFTER ALL BUDGET INFO IS COLLECTED
    # ═══════════════════════════════════════════════════════════════════════
    loc = state.get("location")
    ptype = state.get("typeofproperty")
    
    # ✅ FIX: Only validate if we have location, property type, AND all budget info
    if loc and ptype:
        # For cash: we need budget
        # For installments: we need both Downpayment and monthlyinstall
        should_validate = False
        
        if state["payment_type"] == "cash" and state.get("budget"):
            should_validate = True
        elif state["payment_type"] == "installments" and state.get("Downpayment") and state.get("monthlyinstall"):
            should_validate = True
        
        if should_validate:
            db_data = get_db_min_prices(loc, ptype, state["payment_type"])
            
            if db_data:
                if state["payment_type"] == "cash":
                    min_p = db_data.get('min_price', 0)
                    user_budget = state.get("budget", 0)
                    
                    if user_budget < min_p:
                        state["agent_message"] = (
                            f"\u26a0\ufe0f In {loc}, the cheapest {ptype} starts at {min_p:,} EGP. "
                            f"Your budget is {user_budget:,} EGP.\n\n"
                            f"What would you like to do?\n\n"
                            f"1\ufe0f\u20e3 Increase my budget\n"
                            f"2\ufe0f\u20e3 Change location\n"
                            f"3\ufe0f\u20e3 Change property type"
                        )
                        state["waiting_for"] = "budget_exceeded_choice"
                        return state
                
                else:  # installments
                    min_dp = db_data.get('min_down_payment', 0)
                    min_mi = db_data.get('min_monthly', 0)
                    user_dp = state.get("Downpayment", 0)
                    user_mi = state.get("monthlyinstall", 0)
                    
                    if user_dp < min_dp or user_mi < min_mi:
                        issues = []
                        if user_dp < min_dp:
                            issues.append(f"• Minimum down payment required: {min_dp:,} EGP (yours: {user_dp:,})") 
                        if user_mi < min_mi:
                            issues.append(f"• Minimum monthly installment required: {min_mi:,} EGP (yours: {user_mi:,})")
                        state["agent_message"] = (
                            f"\u26a0\ufe0f Market prices in {loc} for {ptype} via installments are higher than your current figures:\n\n"
                            + "\n".join(issues)
                            + "\n\nWhat would you like to do?\n\n"
                            "1\ufe0f\u20e3 Increase my budget / installments\n"
                            "2\ufe0f\u20e3 Change location\n"
                            "3\ufe0f\u20e3 Change property type"
                        )
                        state["waiting_for"] = "budget_exceeded_choice"
                        return state

    # ═══════════════════════════════════════════════════════════════════════
    # 5. SUCCESS — ALL BUDGET INFO COLLECTED AND VALIDATED
    # ═══════════════════════════════════════════════════════════════════════
    state["waiting_for"] = None
    state["budget_valid"] = True
    state["agent_message"] = "✓ Budget information confirmed! Moving to the next step..."
    
    print(f"✓ Budget agent complete:")
    print(f"  - Payment type: {state.get('payment_type')}")
    if state["payment_type"] == "cash":
        print(f"  - Cash budget: {state.get('budget', 0):,} EGP")
    else:
        print(f"  - Down payment: {state.get('Downpayment', 0):,} EGP")
        print(f"  - Monthly: {state.get('monthlyinstall', 0):,} EGP")
    
    return state