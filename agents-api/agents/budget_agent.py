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
"install_years"          → asked for installment duration (years)
"location"               → asked for preferred location
"""

from state import AgentState
from main_helpers import ask_ollama

MAX_LOOP = 5


def _ask(prompt: str) -> str:
    try:
        return (ask_ollama(prompt) or "").strip()
    except:
        return ""


def _digits(text: str) -> str:
    return "".join(filter(str.isdigit, str(text or "")))


def _parse_budget(text: str) -> int | None:
    """Parse budget from text — understands '15 million', '15M', '3.5m', '500k', etc."""
    import re
    text = str(text or "").lower().strip().replace(",", "").replace("_", "")

    # Try patterns like '15 million', '15m', '3.5 مليون'
    m = re.search(r'(\d+\.?\d*)\s*(?:million|مليون|m\b)', text)
    if m:
        return int(float(m.group(1)) * 1_000_000)

    m = re.search(r'(\d+\.?\d*)\s*(?:thousand|ألف|الف|k\b)', text)
    if m:
        return int(float(m.group(1)) * 1_000)

    # Fallback: plain digits
    digits = "".join(filter(str.isdigit, text))
    if digits and len(digits) >= 4:
        return int(digits)

    return None


# ─────────────────────────────────────────────
# 🔥 SMART SUGGESTION GENERATOR
# ─────────────────────────────────────────────

def _build_smart_budget_message(state: dict) -> str:
    min_price = state.get("min_price_in_market") or 0
    budget = state.get("budget") or 0

    # Estimate installment suggestion
    estimated_dp = int(min_price * 0.15) if min_price else 300000
    estimated_mi = int((min_price - estimated_dp) / (8 * 12)) if min_price else 8000

    return (
        f"I couldn’t find options within your current budget of {budget:,} EGP.\n\n"
        f"💡 In this area, properties start from around {min_price:,} EGP.\n\n"
        f"Here are a few options you can consider:\n"
        f"1️⃣ Increase your budget closer to {min_price:,}\n"
        f"2️⃣ Switch to installments (e.g. ~{estimated_dp:,} down payment & ~{estimated_mi:,}/month)\n"
        f"3️⃣ Explore a different (more affordable) location\n"
        f"4️⃣ Consider a smaller unit type\n\n"
        f"What would you like to do?"
    )


# ─────────────────────────────────────────────
# Agent
# ─────────────────────────────────────────────

def budget_agent(state: AgentState) -> AgentState:
    print("\n--- budget_agent ---")

    user_input = (state.get("user_input") or "").lower().strip()
    waiting = state.get("waiting_for") or ""

    # ═══════════════════════════════════════════════
    # 🔥 STEP 0 — HANDLE BUDGET TOO LOW (SMART MODE)
    # ═══════════════════════════════════════════════

    if state.get("budget_retry"):

        if waiting != "budget_adjustment":
            state["agent_message"] = _build_smart_budget_message(state)
            state["waiting_for"] = "budget_adjustment"
            state["budget_retry"] = False
            return state

        # ── Handle user decision ─────────────────────

        # 1️⃣ User enters new budget
        d = _digits(user_input)
        if d and len(d) >= 4:
            state["budget"] = int(d)

            # 🔥 RESET PIPELINE
            state["candidate_compounds"] = None
            state["budget_valid"] = None

            state["waiting_for"] = None
            return state

        # 2️⃣ User chooses installments
        if any(x in user_input for x in ["installment", "installments", "تقسيط"]):
            state["payment_type"] = "installments"
            state["Downpayment"] = None
            state["monthlyinstall"] = None

            # reset flow
            state["candidate_compounds"] = None
            state["budget_valid"] = None

            state["waiting_for"] = None
            return state

        # 3️⃣ User wants cheaper location
        if any(x in user_input for x in ["cheaper", "another area", "different location", "ارخص"]):
            state["location"] = None

            state["candidate_compounds"] = None
            state["budget_valid"] = None

            state["waiting_for"] = None
            return state

        # 4️⃣ User wants smaller unit
        if any(x in user_input for x in ["smaller", "small", "studio", "1 bedroom"]):
            state["unit_preference"] = "small"

            state["candidate_compounds"] = None
            state["budget_valid"] = None

            state["waiting_for"] = None
            return state

        # fallback
        state["agent_message"] = "Could you tell me which option you prefer or give a new budget?"
        state["waiting_for"] = "budget_adjustment"
        return state

    # ═══════════════════════════════════════════════
    # STEP 1 — PAYMENT TYPE
    # ═══════════════════════════════════════════════

    if not state.get("payment_type"):

        if waiting == "payment_type":
            # Simple keyword matching — no LLM needed for "cash" or "installments"
            if any(x in user_input for x in ["cash", "كاش", "نقد", "كاچ"]):
                state["payment_type"] = "cash"
                state["waiting_for"] = None
            elif any(x in user_input for x in ["install", "تقسيط", "قسط", "اقساط"]):
                state["payment_type"] = "installments"
                state["waiting_for"] = None
            else:
                state["agent_message"] = "Cash or installments?"
                state["waiting_for"] = "payment_type"
                return state
        else:
            state["agent_message"] = "Would you like to pay cash or installments?"
            state["waiting_for"] = "payment_type"
            return state

    # ═══════════════════════════════════════════════
    # STEP 2 — CASH
    # ═══════════════════════════════════════════════

    if state["payment_type"] == "cash" and not state.get("budget"):

        if waiting == "cash_budget":
            budget = _parse_budget(user_input)
            if budget and budget >= 1000:
                state["budget"] = budget
                state["budget_valid"] = True
                state["waiting_for"] = None
                return state
            else:
                state["agent_message"] = "Please enter your budget (e.g. 5 million, 500k, 3000000)"
                state["waiting_for"] = "cash_budget"
                return state

        state["agent_message"] = "What budget range are you considering?"
        state["waiting_for"] = "cash_budget"
        return state

    # ═══════════════════════════════════════════════
    # STEP 3 — INSTALLMENTS (DP → Monthly → Years)
    # ═══════════════════════════════════════════════

    if state["payment_type"] == "installments":

        # 3a — Down Payment
        if not state.get("Downpayment"):
            if waiting == "install_dp":
                dp = _parse_budget(user_input)
                if dp and dp >= 1000:
                    state["Downpayment"] = dp
                    state["waiting_for"] = None
                    # Fall through to ask monthly
                else:
                    state["agent_message"] = "Please enter your down payment (e.g. 500k, 1 million)"
                    state["waiting_for"] = "install_dp"
                    return state
            else:
                state["agent_message"] = "How much down payment are you considering?"
                state["waiting_for"] = "install_dp"
                return state

        # 3b — Monthly Installment
        if not state.get("monthlyinstall"):
            if waiting == "install_mi":
                mi = _parse_budget(user_input)
                if mi and mi >= 100:
                    state["monthlyinstall"] = mi
                    state["waiting_for"] = None
                    # Fall through to ask years
                else:
                    state["agent_message"] = "Please enter your monthly installment (e.g. 20k, 50000)"
                    state["waiting_for"] = "install_mi"
                    return state
            else:
                state["agent_message"] = "What monthly installment works for you?"
                state["waiting_for"] = "install_mi"
                return state

        # 3c — Installment Duration (Years)
        if not state.get("years"):
            if waiting == "install_years":
                d = _digits(user_input)
                if d:
                    yrs = int(d)
                    if 1 <= yrs <= 15:
                        state["years"] = yrs
                        state["waiting_for"] = None
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

        # 3d — Calculate total budget
        if not state.get("budget_valid"):
            state["budget"] = (
                state["Downpayment"] +
                state["monthlyinstall"] * 12 * state["years"]
            )
            state["budget_valid"] = True
            print(f"  💰 Installment budget: DP={state['Downpayment']:,} + {state['monthlyinstall']:,}/mo × {state['years']}y = {state['budget']:,}")

    return state