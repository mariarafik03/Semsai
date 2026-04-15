import os
import re
from pymongo import MongoClient
from dotenv import load_dotenv
from state import AgentState
from main_helpers import ask_ollama

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
# Budget Agent (The "Skeleton")
# ---------------------------------------------------------------------------

def budget_agent(state: AgentState) -> AgentState:
    print("--- Budget Agent Active ---")
    
    user_input = (state.get("user_input") or "").strip()
    waiting = state.get("waiting_for")
    
    # 1. HANDLE PAYMENT TYPE
    if not state.get("payment_type"):
        if waiting == "payment_type":
            extracted = ask_ollama(f"Extract payment type: cash or installments? User said: '{user_input}'").lower()
            if "cash" in extracted:
                state["payment_type"] = "cash"
            elif "installment" in extracted:
                state["payment_type"] = "installments"
            else:
                state["agent_message"] = "I'm sorry, would you prefer to pay in **cash** or **installments**?"
                return state
        else:
            state["agent_message"] = "How would you like to pay? We offer **cash** and **installment** plans."
            state["waiting_for"] = "payment_type"
            return state

    # 2. HANDLE CASH FLOW
    if state["payment_type"] == "cash":
        if not state.get("budget"):
            if waiting == "cash_budget":
                amount = parse_numeric_amount(user_input)
                if amount and amount >= 100_000:
                    state["budget"] = amount
                else:
                    state["agent_message"] = "Could you please specify your total cash budget? (e.g., 5 million EGP)"
                    return state
            else:
                state["agent_message"] = "What is your total **cash budget** in EGP?"
                state["waiting_for"] = "cash_budget"
                return state

    # 3. HANDLE INSTALLMENT FLOW
    else:
        # Check Downpayment
        if not state.get("Downpayment"):
            if waiting == "downpayment":
                amount = parse_numeric_amount(user_input)
                if amount: state["Downpayment"] = amount
                else:
                    state["agent_message"] = "What is the **down payment** amount you are comfortable with?"
                    return state
            else:
                state["agent_message"] = "To find the best plan, what is your preferred **down payment**?"
                state["waiting_for"] = "downpayment"
                return state
        
        # Check Monthly
        if not state.get("monthlyinstall"):
            if waiting == "monthly":
                amount = parse_numeric_amount(user_input)
                if amount: state["monthlyinstall"] = amount
                else:
                    state["agent_message"] = "What is the maximum **monthly installment** you can pay?"
                    return state
            else:
                state["agent_message"] = "And what is your maximum **monthly installment**?"
                state["waiting_for"] = "monthly"
                return state

    # 4. VALIDATION AGAINST DB
    # If we have all info, check if it's realistic for the location
    loc = state.get("location")
    ptype = state.get("typeofproperty")
    
    if loc and ptype:
        db_data = get_db_min_prices(loc, ptype, state["payment_type"])
        if db_data:
            if state["payment_type"] == "cash":
                min_p = db_data['min_price']
                if state["budget"] < min_p:
                    state["agent_message"] = f"In {loc}, the cheapest {ptype} is roughly {min_p:,} EGP. Your budget is {state['budget']:,}. Would you like to **increase your budget** or **change location**?"
                    state["budget"] = None # Reset to re-ask
                    state["waiting_for"] = "cash_budget"
                    return state
            else:
                min_dp = db_data.get('min_down_payment', 0)
                min_mi = db_data.get('min_monthly', 0)
                if state["Downpayment"] < min_dp or state["monthlyinstall"] < min_mi:
                    state["agent_message"] = f"Market prices in {loc} require a min down payment of {min_dp:,} and {min_mi:,} monthly. Please provide updated figures."
                    state["Downpayment"], state["monthlyinstall"] = None, None
                    state["waiting_for"] = "downpayment"
                    return state

    # 5. SUCCESS
    state["waiting_for"] = None
    state["budget_valid"] = True
    return state