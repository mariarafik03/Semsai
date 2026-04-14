"""
agents/budget_agent.py  (Fixed with proper flow control)
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
"location"               → asked for preferred location
"""

from state import AgentState
from main_helpers import ask_ollama
from typing import List, Dict, Any

def _ask(prompt: str) -> str:
    """Wrapper for LLM calls with error handling"""
    try:
        return (ask_ollama(prompt) or "").strip()
    except Exception as e:
        print(f"[ERROR] budget_agent LLM call failed: {e}")
        return ""


def _digits(text: str) -> str:
    """Extract only digits from text"""
    return "".join(filter(str.isdigit, str(text or "")))


def _search_units(state: AgentState) -> List[Dict[str, Any]]:
    """Search for units matching budget and location from MongoDB data"""
    try:
        budget = state.get("budget", 0)
        location = state.get("location", "").lower()
        payment_type = state.get("payment_type", "cash")
        
        # Get candidate_units from state (loaded from MongoDB)
        all_units = state.get("candidate_units", [])
        
        if not all_units:
            print("[WARNING] No candidate_units in state for search")
            return []
        
        matching_units = []
        
        for unit in all_units:
            # Extract unit details
            unit_location = (unit.get("location") or "").lower()
            unit_price = unit.get("price", 0)
            
            # Check location match (flexible - contains or is contained)
            location_match = location in unit_location or unit_location in location
            
            # Check budget match based on payment type
            if payment_type == "cash":
                # For cash: check unit_price against budget (with 15% tolerance)
                price_match = unit_price <= budget * 1.15
            else:
                # For installments: check payment plans
                price_match = _check_installment_match(unit, state)
            
            if location_match and price_match:
                matching_units.append(unit)
        
        # Sort by price (ascending)
        matching_units.sort(key=lambda u: u.get("price", 0))
        
        print(f"[DEBUG] Found {len(matching_units)} matching units for location={location}, budget={budget}")
        return matching_units
    
    except Exception as e:
        print(f"[ERROR] Unit search failed: {e}")
        return []


def _check_installment_match(unit: Dict[str, Any], state: AgentState) -> bool:
    """Check if unit's payment plans match user's installment budget"""
    try:
        user_dp = state.get("Downpayment", 0)
        user_monthly = state.get("monthlyinstall", 0)
        user_years = state.get("years", 5)
        
        payment_plans = unit.get("payment_plans", [])
        
        for plan in payment_plans:
            if plan.get("is_cash"):
                continue
            
            plan_dp = plan.get("down_payment", 0)
            plan_years = plan.get("years", 0)
            plan_frequency = plan.get("frequency", "monthly")
            plan_installment = plan.get("single_installment_amount", 0)
            
            # Convert to monthly if quarterly
            if plan_frequency == "quarterly":
                monthly_installment = plan_installment / 3
            else:
                monthly_installment = plan_installment
            
            # Check if this plan fits within user's budget (with 10% tolerance)
            dp_match = plan_dp <= user_dp * 1.1
            monthly_match = monthly_installment <= user_monthly * 1.1
            years_match = plan_years <= user_years + 2  # Allow 2 years flexibility
            
            if dp_match and monthly_match and years_match:
                return True
        
        return False
    
    except Exception as e:
        print(f"[ERROR] Installment matching failed: {e}")
        return False


def _format_unit_display(units: List[Dict[str, Any]], payment_type: str, limit: int = 5) -> str:
    """Format units for display to user"""
    if not units:
        return ""
    
    result = []
    for i, unit in enumerate(units[:limit], 1):
        name = unit.get("name", "Unknown Property")
        location = unit.get("location", "N/A")
        price = unit.get("price", 0)
        compound = unit.get("compound_name", "")
        bedrooms = unit.get("bedrooms", 0)
        area = unit.get("area", 0)
        
        # Format price
        price_str = f"{price:,.0f} EGP"
        
        # Build display string
        display = f"{i}. **{compound}** - {location}\n"
        display += f"   • {bedrooms} bedrooms, {area}m²\n"
        display += f"   • Price: {price_str}"
        
        result.append(display)
    
    return "\n\n".join(result)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

def budget_agent(state: AgentState) -> AgentState:
    """
    Budget collection agent - handles payment type, budget, and location.
    
    CRITICAL: This agent sets state["waiting_for"] when it needs user input.
    The orchestrator MUST check this and pause before proceeding to next agent.
    
    Returns:
        state with either:
        - waiting_for = some value → STOP and return to user
        - budget_agent_complete = True → proceed to next agent
    """
    print("\n" + "="*60)
    print("🏦 BUDGET AGENT")
    print("="*60)

    user_input = (state.get("user_input") or "").strip()
    waiting    = state.get("waiting_for") or ""

    print(f"  User input: {user_input[:50]}..." if len(user_input) > 50 else f"  User input: {user_input}")
    print(f"  Waiting for: {waiting}")
    print(f"  Payment type: {state.get('payment_type')}")
    print(f"  Budget: {state.get('budget')}")
    print(f"  Location: {state.get('location')}")

    # ════════════════════════════════════════════════════════════════════
    # STEP 1 — Confirm / collect payment type
    # ════════════════════════════════════════════════════════════════════

    if not state.get("payment_type"):
        print("  → Need payment type")

        if waiting == "payment_type":
            # User replied — extract payment type
            extracted = _ask(
                f"Extract ONLY the payment type from this input. "
                f"Return exactly one word: cash or installments, or unknown if unclear.\n"
                f"User said: '{user_input}'"
            ).lower()

            print(f"  → Extracted payment type: {extracted}")

            if extracted in ("cash", "installments"):
                state["payment_type"]           = extracted
                state["payment_type_confirmed"] = True
                state["waiting_for"]            = None
                print(f"  ✅ Payment type set: {extracted}")
                # Fall through to budget collection below
            else:
                state["agent_message"] = "I didn't catch that. Would you prefer to pay in **cash** or by **installments**?"
                state["waiting_for"]   = "payment_type"
                print("  ⏸️  Waiting for payment type (retry)")
                return state

        else:
            # First time — ask directly
            state["agent_message"] = "Would you like to pay in **cash** or by **installments**?"
            state["waiting_for"]   = "payment_type"
            print("  ⏸️  Asking for payment type (first time)")
            return state

    state["payment_type_confirmed"] = True

    # ════════════════════════════════════════════════════════════════════
    # STEP 2a — CASH PAYMENT
    # ════════════════════════════════════════════════════════════════════

    if state["payment_type"] == "cash" and not state.get("budget"):
        print("  → Need cash budget")

        if waiting == "cash_budget":
            # Try to extract budget from user input
            d = _digits(user_input)
            print(f"  → Extracted digits: {d}")
            
            if d and len(d) >= 4:  # at least 4 digits for a valid budget
                state["budget"]      = int(d)
                state["waiting_for"] = None
                print(f"  ✅ Budget set: {state['budget']:,} EGP")
                # Continue to location
            else:
                # Check if user says they don't know
                lower_input = user_input.lower()
                if any(phrase in lower_input for phrase in ["don't know", "not sure", "no idea", "unsure"]):
                    state["agent_message"] = (
                        "No problem! To help you, could you share a **range**? "
                        "For example: 1-3 million EGP, or 500K-1M EGP?"
                    )
                    state["waiting_for"] = "cash_budget"
                    print("  ⏸️  User unsure - asking for range")
                    return state
                
                # If still no number, ask again more directly
                state["agent_message"] = (
                    "I need a number to proceed. What's your budget? "
                    "(You can give me a range like 1-2 million EGP)"
                )
                state["waiting_for"] = "cash_budget"
                print("  ⏸️  No valid number - asking again")
                return state

        else:
            # First time asking
            state["agent_message"] = "What's your total budget for the property?"
            state["waiting_for"]   = "cash_budget"
            print("  ⏸️  Asking for cash budget (first time)")
            return state

    # ════════════════════════════════════════════════════════════════════
    # STEP 2b — INSTALLMENTS
    # ════════════════════════════════════════════════════════════════════

    if state["payment_type"] == "installments" and not state.get("budget"):
        print("  → Need installment details")

        # ── Handle downpayment ───────────────────────────────────────────
        if not state.get("Downpayment"):
            print("    → Need down payment")
            
            if waiting in ("install_dp", "install_both"):
                # Try to extract downpayment
                d = _digits(user_input)
                print(f"    → Extracted digits: {d}")
                
                if d and len(d) >= 4:
                    state["Downpayment"] = int(d)
                    state["waiting_for"] = None
                    print(f"    ✅ Down payment set: {state['Downpayment']:,} EGP")
                    # Continue to monthly installment
                else:
                    # Check if unsure
                    lower_input = user_input.lower()
                    if any(phrase in lower_input for phrase in ["don't know", "not sure", "no idea"]):
                        state["agent_message"] = (
                            "That's okay! A typical down payment is 10-30% of the property value. "
                            "Could you share an approximate amount?"
                        )
                        state["waiting_for"] = "install_dp"
                        print("    ⏸️  User unsure about DP - providing guidance")
                        return state
                    
                    state["agent_message"] = "Please provide your down payment amount (in EGP):"
                    state["waiting_for"] = "install_dp"
                    print("    ⏸️  No valid DP - asking again")
                    return state
            
            else:
                # First time asking
                state["agent_message"] = "How much can you pay as a **down payment**?"
                state["waiting_for"]   = "install_dp"
                print("    ⏸️  Asking for down payment (first time)")
                return state

        # ── Handle monthly installment ───────────────────────────────────
        if not state.get("monthlyinstall"):
            print("    → Need monthly installment")
            
            if waiting in ("install_mi", "install_both"):
                # Try to extract monthly installment
                d = _digits(user_input)
                print(f"    → Extracted digits: {d}")
                
                if d and len(d) >= 3:
                    state["monthlyinstall"] = int(d)
                    state["waiting_for"] = None
                    print(f"    ✅ Monthly installment set: {state['monthlyinstall']:,} EGP")
                    # Calculate total budget
                    _finalise_installments(state)
                    print(f"    ✅ Total budget calculated: {state['budget']:,} EGP")
                else:
                    # Check if unsure
                    lower_input = user_input.lower()
                    if any(phrase in lower_input for phrase in ["don't know", "not sure", "no idea"]):
                        state["agent_message"] = (
                            "No worries! Could you share what you're comfortable paying monthly? "
                            "For example: 10,000 EGP, 20,000 EGP, etc."
                        )
                        state["waiting_for"] = "install_mi"
                        print("    ⏸️  User unsure about monthly - providing guidance")
                        return state
                    
                    state["agent_message"] = "Please provide your monthly installment amount:"
                    state["waiting_for"] = "install_mi"
                    print("    ⏸️  No valid monthly - asking again")
                    return state
            
            else:
                # First time asking
                state["agent_message"] = "What **monthly installment** amount are you comfortable with?"
                state["waiting_for"]   = "install_mi"
                print("    ⏸️  Asking for monthly installment (first time)")
                return state

    # ════════════════════════════════════════════════════════════════════
    # STEP 3 — SEARCH & NEGOTIATE
    # ════════════════════════════════════════════════════════════════════

    if state.get("budget") and state.get("location"):
        print("  → Performing search and check...")
        
        # Search for matching units
        matching_units = _search_units(state)
        
        if matching_units:
            # Store in state
            state["candidate_units"] = matching_units
            
            # Format units for display
            unit_display = _format_unit_display(
                matching_units, 
                state.get("payment_type", "cash"),
                limit=5
            )
            
            state["agent_message"] = (
                f"Great news! I found **{len(matching_units)}** unit(s) in {state['location']} "
                f"that match your criteria:\n\n"
                f"{unit_display}\n\n"
                f"Would you like to explore these further or refine your preferences?"
            )
            state["budget_agent_complete"] = True
            print(f"  ✅ Found {len(matching_units)} matching units. Agent COMPLETE.")
        else:
            # ─────────────────────────────────────────────────────────────
            # NEGOTIATION LOGIC
            # ─────────────────────────────────────────────────────────────
            print("  ⚠️ No matching units found - Starting negotiation")
            
            # If we're already in a negotiation choice, handle the response
            if waiting == "negotiate_no_results":
                print(f"  → Processing negotiation choice: {user_input}")
                choice = _ask(
                    "The user was told no properties match their budget/location/type. "
                    "They were asked to choose: change location, change property type, or adjust budget. "
                    f"Based on their response: '{user_input}', which one do they want to change? "
                    "Return ONLY one word: location, type, or budget. If unclear, return unknown."
                ).lower()
                
                print(f"  → Choice detected: {choice}")
                
                if "location" in choice:
                    state["location"] = None
                    state["waiting_for"] = None
                    return state
                elif "type" in choice:
                    state["typeofproperty"] = None
                    state["waiting_for"] = None
                    return state
                elif "budget" in choice:
                    state["budget"] = None
                    state["Downpayment"] = None
                    state["monthlyinstall"] = None
                    state["waiting_for"] = None
                    return state
                else:
                    # User might have just given a new location/budget directly
                    # Let's clear waiting and see if the router/extraction can pick it up
                    # or just ask more clearly.
                    state["agent_message"] = "I'm sorry, I didn't quite catch that. Would you like to change your **location**, **property type**, or **budget**?"
                    state["waiting_for"] = "negotiate_no_results"
                    return state

            # Construct the negotiation message
            location = state.get('location')
            budget = state.get('budget')
            prop_type = state.get('typeofproperty', 'property')
            
            state["agent_message"] = (
                f"I've searched our current listings, but I couldn't find any **{prop_type}s** in **{location}** "
                f"within your budget of **{budget:,.0f} EGP**.\n\n"
                f"To help you find the right home, would you like to:\n"
                f"1. **Change Location**: Look in a different area where prices might fit better?\n"
                f"2. **Change Property Type**: For example, would you consider an Apartment if you were looking for a Villa?\n"
                f"3. **Adjust Budget**: Increase your budget slightly to see more options?\n\n"
                f"What would you like to do?"
            )
            state["waiting_for"] = "negotiate_no_results"
            
            # We DON'T mark budget_agent_complete = True because we want to stay here
            # until there's a match or the user decides to proceed anyway.
            print("  ⏸️ Waiting for negotiation choice")
            return state

    return state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _finalise_installments(state: dict) -> None:
    """Calculate total budget from installment details"""
    years = state.get("years") or 5  # default to 5 years if not specified
    state["budget"] = (
        state["Downpayment"] + state["monthlyinstall"] * 12 * years
    )