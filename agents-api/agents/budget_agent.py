"""
agents/budget_agent.py  (Fixed - Direct questions)
─────────────────────────────────────────────
waiting_for values used
───────────────────────
"payment_type"           → asked cash vs installments
"cash_budget"            → asked for total budget (direct)
"install_both"           → asked for downpayment + monthly
"install_dp"             → asked for down payment only
"install_mi"             → asked for monthly installment only
"""

from state import AgentState
from main_helpers import ask_ollama

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


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

def budget_agent(state: AgentState) -> AgentState:
    print("in budget agent")

    user_input = (state.get("user_input") or "").strip()
    waiting    = state.get("waiting_for") or ""

    # ════════════════════════════════════════════════════════════════════
    # STEP 1 — Confirm / collect payment type
    # ════════════════════════════════════════════════════════════════════

    if not state.get("payment_type"):

        if waiting == "payment_type":
            # User replied — extract payment type
            extracted = _ask(
                f"Extract ONLY the payment type from this input. "
                f"Return exactly one word: cash or installments, or unknown if unclear.\n"
                f"User said: '{user_input}'"
            ).lower()

            if extracted in ("cash", "installments"):
                state["payment_type"]           = extracted
                state["payment_type_confirmed"] = True
                state["waiting_for"]            = None
                # Fall through to budget collection below
            else:
                state["agent_message"] = "I didn't catch that. Would you prefer to pay in **cash** or by **installments**?"
                state["waiting_for"]   = "payment_type"
                return state

        else:
            # First time — ask directly
            state["agent_message"] = "Would you like to pay in **cash** or by **installments**?"
            state["waiting_for"]   = "payment_type"
            return state

    state["payment_type_confirmed"] = True

    # Quick exit if budget already complete
    has_cash = state.get("payment_type") == "cash" and state.get("budget")
    has_installments = (
        state.get("payment_type") == "installments"
        and state.get("Downpayment")
        and state.get("monthlyinstall")
    )
    if has_cash or has_installments:
        return state

    # ════════════════════════════════════════════════════════════════════
    # STEP 2a — CASH PAYMENT
    # ════════════════════════════════════════════════════════════════════

    if state["payment_type"] == "cash" and not state.get("budget"):

        if waiting == "cash_budget":
            # Try to extract budget from user input
            d = _digits(user_input)
            if d and len(d) >= 4:  # at least 4 digits for a valid budget
                state["budget"]      = int(d)
                state["waiting_for"] = None
                return state
            
            # Check if user says they don't know
            lower_input = user_input.lower()
            if any(phrase in lower_input for phrase in ["don't know", "not sure", "no idea", "unsure"]):
                state["agent_message"] = (
                    "No problem! To help you, could you share a **range**? "
                    "For example: 1-3 million EGP, or 500K-1M EGP?"
                )
                state["waiting_for"] = "cash_budget"
                return state
            
            # If still no number, ask again more directly
            state["agent_message"] = (
                "I need a number to proceed. What's your budget? "
                "(You can give me a range like 1-2 million EGP)"
            )
            state["waiting_for"] = "cash_budget"
            return state

        # First time asking
        state["agent_message"] = "What's your total budget for the property?"
        state["waiting_for"]   = "cash_budget"
        return state

    # ════════════════════════════════════════════════════════════════════
    # STEP 2b — INSTALLMENTS
    # ════════════════════════════════════════════════════════════════════

    if state["payment_type"] == "installments":

        # ── Handle downpayment ───────────────────────────────────────────
        if not state.get("Downpayment"):
            
            if waiting in ("install_dp", "install_both"):
                # Try to extract downpayment
                d = _digits(user_input)
                if d and len(d) >= 4:
                    state["Downpayment"] = int(d)
                    state["waiting_for"] = None
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
                        return state
                    
                    state["agent_message"] = "Please provide your down payment amount (in EGP):"
                    state["waiting_for"] = "install_dp"
                    return state
            
            else:
                # First time asking
                state["agent_message"] = "How much can you pay as a **down payment**?"
                state["waiting_for"]   = "install_dp"
                return state

        # ── Handle monthly installment ───────────────────────────────────
        if not state.get("monthlyinstall"):
            
            if waiting in ("install_mi", "install_both"):
                # Try to extract monthly installment
                d = _digits(user_input)
                if d and len(d) >= 3:
                    state["monthlyinstall"] = int(d)
                    state["waiting_for"] = None
                    # Finalize
                    _finalise_installments(state)
                    return state
                else:
                    # Check if unsure
                    lower_input = user_input.lower()
                    if any(phrase in lower_input for phrase in ["don't know", "not sure", "no idea"]):
                        state["agent_message"] = (
                            "No worries! Could you share what you're comfortable paying monthly? "
                            "For example: 10,000 EGP, 20,000 EGP, etc."
                        )
                        state["waiting_for"] = "install_mi"
                        return state
                    
                    state["agent_message"] = "Please provide your monthly installment amount:"
                    state["waiting_for"] = "install_mi"
                    return state
            
            else:
                # First time asking
                state["agent_message"] = "What **monthly installment** amount are you comfortable with?"
                state["waiting_for"]   = "install_mi"
                return state

        # Both collected
        _finalise_installments(state)

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
    state["next_step"] = "location_agent"
    state["waiting_for"] = None