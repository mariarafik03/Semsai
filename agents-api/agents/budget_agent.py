"""
agents/budget_agent.py  (Fixed with proper flow control and validation)
─────────────────────────────────────────────────────────────
This agent MUST be called multiple times in a conversation loop.
It will set state["waiting_for"] when it needs user input.
The orchestrator MUST check this and return to user before proceeding.

waiting_for values used
───────────────────────
"payment_type"           → asked cash vs installments
"cash_budget"            → asked for total budget (direct)
"install_dp"             → asked for down payment only
"install_mi"             → asked for monthly installment only
"install_years"          → asked for installment duration (years)
"budget_exceeded_choice" → asked user to choose what to do if budget is too low
"""

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

def _digits(text: str) -> str:
    return "".join(filter(str.isdigit, str(text or "")))

def parse_numeric_amount(text: str) -> int | None:
    if not text:
        return None
    text = str(text).strip().replace(",", "").replace("_", "").lower()
    text = re.sub(r"[.\s]+$", "", text)
    
    # Try patterns like '15 million', '15m', '3.5 مليون', '1.5b'
    # Millions
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:millions?|مليون|m\b)', text)
    if m:
        return int(float(m.group(1)) * 1_000_000)
        
    # Billions
    b = re.search(r'(\d+(?:\.\d+)?)\s*(?:billions?|b\b)', text)
    if b:
        return int(float(b.group(1)) * 1_000_000_000)
        
    # Thousands
    k = re.search(r'(\d+(?:\.\d+)?)\s*(?:thousands?|ألف|الف|k\b)', text)
    if k:
        return int(float(k.group(1)) * 1_000)
        
    # Fallback: plain digits
    digits = "".join(filter(str.isdigit, text))
    if digits:
        return int(digits)

    return None

def get_db_min_prices(location: str, property_type: str, payment_type: str):
    uri = os.getenv("MONGO_URI")
    if not uri: return None
    
    try:
        import certifi
        client = MongoClient(uri, tls=True, tlsCAFile=certifi.where())
    except ImportError:
        client = MongoClient(uri)
        
    db = client.get_default_database()  # Safe retrieval of default DB
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
            else:
                state["Downpayment"] = None
                state["monthlyinstall"] = None
                state["years"] = None
                state["budget"] = None
                state["waiting_for"] = None
            print("→ Budget exceeded choice: increase budget")
            return state

        elif "2" in choice_text or "location" in choice_text:
            new_location = normalize_location(user_input)
            if new_location:
                state["location"]     = new_location
                state["budget_valid"] = None
                state["waiting_for"]  = None
                state["agent_message"] = (
                    f"✅ Location changed to **{new_location}**. "
                    f"Let me check availability there..."
                )
                print(f"✓ Location changed to: {new_location}")
            else:
                state["location"]       = None
                state["typeofproperty"] = None
                state["budget_valid"]   = None
                state["waiting_for"]    = None
                print("→ Budget exceeded: change location (will ask fresh)")
            return state

        elif "3" in choice_text or "type" in choice_text or "property" in choice_text:
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
                    f"✅ Property type changed to **{new_type}**. "
                    f"Let me check what's available..."
                )
                print(f"✓ Property type changed to: {new_type}")
            else:
                state["typeofproperty"] = None
                state["budget_valid"]   = None
                state["waiting_for"]    = None
                print("→ Budget exceeded: change type (will ask fresh)")
            return state

        else:
            state["agent_message"] = (
                "I didn't quite catch that. Please choose one of:\n\n"
                "1️⃣ Increase my budget\n"
                "2️⃣ Change location\n"
                "3️⃣ Change property type"
            )
            state["waiting_for"] = "budget_exceeded_choice"
            return state

    # ═══════════════════════════════════════════════════════════════════════
    # 1. HANDLE PAYMENT TYPE
    # ═══════════════════════════════════════════════════════════════════════
    if not state.get("payment_type"):
        if waiting == "payment_type":
            # Simple keyword matching — no LLM needed for "cash" or "installments"
            if any(x in user_input.lower() for x in ["cash", "كاش", "نقد", "كاچ"]):
                state["payment_type"] = "cash"
                state["waiting_for"] = None
                print("✓ Payment type set to: cash")
            elif any(x in user_input.lower() for x in ["install", "تقسيط", "قسط", "اقساط"]):
                state["payment_type"] = "installments"
                state["waiting_for"] = None
                print("✓ Payment type set to: installments")
            else:
                # LLM Fallback if keyword matching fails
                extracted = ask_ollama(f"Extract payment type: cash or installments? User said: '{user_input}'").lower()
                if "cash" in extracted:
                    state["payment_type"] = "cash"
                    state["waiting_for"] = None
                    print("✓ Payment type set to: cash (via LLM)")
                elif "installment" in extracted:
                    state["payment_type"] = "installments"
                    state["waiting_for"] = None
                    print("✓ Payment type set to: installments (via LLM)")
                else:
                    state["agent_message"] = "I'm sorry, I didn't understand. Would you prefer to pay in **cash** or **installments**?"
                    state["waiting_for"] = "payment_type"
                    return state
        else:
            state["agent_message"] = "How would you like to pay? We offer cash and installment plans."
            state["waiting_for"] = "payment_type"
            return state

    # ═══════════════════════════════════════════════════════════════════════
    # 2. HANDLE CASH FLOW
    # ═══════════════════════════════════════════════════════════════════════
    if state["payment_type"] == "cash":
        if not state.get("budget"):
            if waiting == "cash_budget":
                amount = parse_numeric_amount(user_input)
                if amount and amount >= 100_000:
                    state["budget"] = amount
                    state["waiting_for"] = None
                    print(f"✓ Cash budget set to: {amount:,} EGP")
                else:
                    state["agent_message"] = "Please specify your total cash budget (e.g. 5 million, 500k, 3000000). Minimum is 100,000 EGP."
                    state["waiting_for"] = "cash_budget"
                    return state
            else:
                state["agent_message"] = "What is your total **cash budget** in EGP?"
                state["waiting_for"] = "cash_budget"
                return state

    # ═══════════════════════════════════════════════════════════════════════
    # 3. HANDLE INSTALLMENT FLOW
    # ═══════════════════════════════════════════════════════════════════════
    else:  # payment_type == "installments"
        # 3a. Down Payment
        if not state.get("Downpayment"):
            if waiting == "install_dp":
                dp = parse_numeric_amount(user_input)
                if dp and dp >= 1000:
                    state["Downpayment"] = dp
                    state["waiting_for"] = None
                    print(f"✓ Downpayment set to: {dp:,} EGP")
                else:
                    state["agent_message"] = "Please enter your down payment (e.g. 500k, 1 million)"
                    state["waiting_for"] = "install_dp"
                    return state
            else:
                state["agent_message"] = "How much down payment are you considering?"
                state["waiting_for"] = "install_dp"
                return state
        
        # 3b. Monthly Installment
        if not state.get("monthlyinstall"):
            if waiting == "install_mi":
                mi = parse_numeric_amount(user_input)
                if mi and mi >= 100:
                    state["monthlyinstall"] = mi
                    state["waiting_for"] = None
                    print(f"✓ Monthly installment set to: {mi:,} EGP")
                else:
                    state["agent_message"] = "Please enter your monthly installment (e.g. 20k, 50000)"
                    state["waiting_for"] = "install_mi"
                    return state
            else:
                state["agent_message"] = "What monthly installment works for you?"
                state["waiting_for"] = "install_mi"
                return state

        # 3c. Installment Duration (Years)
        if not state.get("years"):
            if waiting == "install_years":
                d = _digits(user_input)
                if d:
                    yrs = int(d)
                    if 1 <= yrs <= 15:
                        state["years"] = yrs
                        state["waiting_for"] = None
                        print(f"✓ Years set to: {yrs}")
                    else:
                        state["agent_message"] = "Please enter a valid number of years (1-15)"
                        state["waiting_for"] = "install_years"
                        return state
                else:
                    state["agent_message"] = "Please enter the number of years (1-15)"
                    state["waiting_for"] = "install_years"
                    return state
            else:
                state["agent_message"] = "How many years for the installment plan? (max 15 years)"
                state["waiting_for"] = "install_years"
                return state

        # 3d. Calculate total budget
        if not state.get("budget_valid") or state.get("budget") is None:
            state["budget"] = (
                state["Downpayment"] +
                state["monthlyinstall"] * 12 * state["years"]
            )
            print(f"💰 Calculated installment budget: {state['budget']:,} EGP")

    # ═══════════════════════════════════════════════════════════════════════
    # 4. VALIDATION AGAINST DB — ONLY AFTER ALL BUDGET INFO IS COLLECTED
    # ═══════════════════════════════════════════════════════════════════════
    loc = state.get("location")
    ptype = state.get("typeofproperty")
    
    # Only validate if we have location, property type, AND all budget info
    should_validate = False
    
    if loc and ptype:
        if state["payment_type"] == "cash" and state.get("budget"):
            should_validate = True
        elif state["payment_type"] == "installments" and state.get("Downpayment") and state.get("monthlyinstall") and state.get("years"):
            should_validate = True
        
    if should_validate:
        db_data = get_db_min_prices(loc, ptype, state["payment_type"])
        
        if db_data:
            if state["payment_type"] == "cash":
                min_p = db_data.get('min_price', 0)
                user_budget = state.get("budget", 0)
                
                if user_budget < min_p:
                    state["agent_message"] = (
                        f"In {loc}, the cheapest {ptype} starts at {min_p:,} EGP. "
                        f"Your budget is {user_budget:,} EGP.\n\n"
                        f"What would you like to do?\n\n"
                        f"1️⃣ Increase my budget\n"
                        f"2️⃣ Change location\n"
                        f"3️⃣ Change property type"
                    )
                    state["waiting_for"] = "budget_exceeded_choice"
                    state["budget_valid"] = None
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
                        f"Market prices in {loc} for {ptype} via installments are higher than your current figures:\n\n"
                        + "\n".join(issues)
                        + "\n\nWhat would you like to do?\n\n"
                        "1️⃣ Increase my budget / installments\n"
                        "2️⃣ Change location\n"
                        "3️⃣ Change property type"
                    )
                    state["waiting_for"] = "budget_exceeded_choice"
                    state["budget_valid"] = None
                    return state

    # ═══════════════════════════════════════════════════════════════════════
    # 5. SUCCESS — ALL BUDGET INFO COLLECTED AND VALIDATED
    # ═══════════════════════════════════════════════════════════════════════
    state["waiting_for"] = None
    state["budget_valid"] = True
    state["agent_message"] = "✓ Budget information confirmed! Moving to the next step..."
    
    print("✓ Budget agent complete:")
    print(f"  - Payment type: {state.get('payment_type')}")
    if state["payment_type"] == "cash":
        print(f"  - Cash budget: {state.get('budget', 0):,} EGP")
    else:
        print(f"  - Down payment: {state.get('Downpayment', 0):,} EGP")
        print(f"  - Monthly: {state.get('monthlyinstall', 0):,} EGP")
        print(f"  - Years: {state.get('years', 0)}")
        print(f"  - Total calculated budget: {state.get('budget', 0):,} EGP")
    
    return state