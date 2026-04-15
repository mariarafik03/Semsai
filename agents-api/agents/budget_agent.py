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

MAX_LOOP = 5


def _ask(prompt: str) -> str:
    try:
        return (ask_ollama(prompt) or "").strip()
    except:
        return ""


def _digits(text: str) -> str:
    return "".join(filter(str.isdigit, str(text or "")))


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
            extracted = _ask(
                f"Extract payment type: cash or installments.\nUser: {user_input}"
            ).lower()

            if extracted in ("cash", "installments"):
                state["payment_type"] = extracted
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
            d = _digits(user_input)
            if d and len(d) >= 4:
                state["budget"] = int(d)
                state["waiting_for"] = None
                return state

        state["agent_message"] = "What budget range are you considering?"
        state["waiting_for"] = "cash_budget"
        return state

    # ═══════════════════════════════════════════════
    # STEP 3 — INSTALLMENTS
    # ═══════════════════════════════════════════════

    if state["payment_type"] == "installments":

        if not state.get("Downpayment"):
            d = _digits(user_input)
            if d:
                state["Downpayment"] = int(d)
                return state

            state["agent_message"] = "How much down payment are you considering?"
            return state

        if not state.get("monthlyinstall"):
            d = _digits(user_input)
            if d:
                state["monthlyinstall"] = int(d)

                years = state.get("years") or 8
                state["budget"] = (
                    state["Downpayment"] +
                    state["monthlyinstall"] * 12 * years
                )

                return state

            state["agent_message"] = "What monthly installment works for you?"
            return state

    return state