"""
agents/budget_agent.py  (HTTP-safe refactor)
─────────────────────────────────────────────
waiting_for values used
───────────────────────
"payment_type"           → asked cash vs installments
"cash_budget"            → asked for total budget (direct attempt)
"cash_budget_loop_{n}"   → intelligent loop question n
"install_both"           → asked for downpayment + monthly in one go
"install_dp_loop_{n}"    → intelligent loop for down payment
"install_mi_loop_{n}"    → intelligent loop for monthly installment
"""

from state import AgentState
from main_helpers import ask_ollama

MAX_LOOP = 5   # max intelligent-question attempts before giving up


def _ask(prompt: str) -> str:
    try:
        return (ask_ollama(prompt) or "").strip()
    except Exception as e:
        print(f"[ERROR] budget_agent LLM call failed: {e}")
        return ""


def _digits(text: str) -> str:
    return "".join(filter(str.isdigit, str(text or "")))


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

def budget_agent(state: AgentState) -> AgentState:

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
                state["agent_message"] = "Sorry, could you clarify — cash or installments?"
                state["waiting_for"]   = "payment_type"
                return state

        else:
            # First time — ask
            question = _ask(
                "Ask the user if they want to pay by cash or installments "
                "in a natural, friendly way. Only ask, don't answer."
            ) or "Would you like to pay in cash or by installments?"

            state["agent_message"] = question
            state["waiting_for"]   = "payment_type"
            return state

    state["payment_type_confirmed"] = True

    # Quick exit if budget already complete
    has_cash        = state.get("payment_type") == "cash"        and state.get("budget")
    has_installments = (
        state.get("payment_type") == "installments"
        and state.get("Downpayment")
        and state.get("monthlyinstall")
    )
    if has_cash or has_installments:
        return state

    # ════════════════════════════════════════════════════════════════════
    # STEP 2a — CASH
    # ════════════════════════════════════════════════════════════════════

    if state["payment_type"] == "cash" and not state.get("budget"):

        # ── Direct first attempt ─────────────────────────────────────────
        if waiting == "cash_budget":
            d = _digits(user_input)
            if d:
                state["budget"]      = int(d)
                state["waiting_for"] = None
                return state

            # Digits not found directly — try LLM inference then loop
            guess = _ask(
                f"User said: '{user_input}'.\n"
                "Estimate a reasonable numeric budget for buying a property in Egypt. "
                "Return ONLY digits."
            )
            d = _digits(guess)
            if d:
                state["budget"]      = int(d)
                state["waiting_for"] = None
                return state

            # Enter intelligent loop
            state["_cash_loop_asked"] = []
            state["waiting_for"] = "cash_budget_loop_1"
            first_q = _ask(_cash_loop_prompt([]))
            state["agent_message"] = first_q
            return state

        # ── Intelligent loop ─────────────────────────────────────────────
        if waiting.startswith("cash_budget_loop_"):
            attempt = int(waiting.split("_")[-1])
            asked   = state.get("_cash_loop_asked") or []

            guess = _ask(
                f"User said: '{user_input}'.\n"
                "Estimate a reasonable numeric budget for buying a property in Egypt. "
                "Return ONLY digits."
            )
            d = _digits(guess)
            if d:
                state["budget"]           = int(d)
                state["waiting_for"]      = None
                state["_cash_loop_asked"] = None
                return state

            if attempt >= MAX_LOOP:
                state["agent_message"] = (
                    "I wasn't able to determine your budget. "
                    "Could you please tell me a number directly?"
                )
                state["waiting_for"] = "cash_budget"   # reset to direct question
                return state

            asked.append(user_input)
            state["_cash_loop_asked"] = asked
            next_q = _ask(_cash_loop_prompt(asked))
            state["agent_message"] = next_q
            state["waiting_for"]   = f"cash_budget_loop_{attempt + 1}"
            return state

        # ── First ask ────────────────────────────────────────────────────
        question = _ask(
            "Ask the user about their budget naturally without being direct."
        ) or "What's the approximate budget you have in mind?"

        state["agent_message"] = question
        state["waiting_for"]   = "cash_budget"
        return state

    # ════════════════════════════════════════════════════════════════════
    # STEP 2b — INSTALLMENTS
    # ════════════════════════════════════════════════════════════════════

    if state["payment_type"] == "installments" and (
        not state.get("Downpayment") or not state.get("monthlyinstall")
    ):

        # ── Handle reply to initial combined question ────────────────────
        if waiting == "install_both":
            lines = user_input.split("\n")
            # Try to parse all three values
            if len(lines) >= 3:
                d_dp = _digits(lines[0])
                d_mi = _digits(lines[1])
                d_yr = _digits(lines[2])
                if d_dp: state["Downpayment"]    = int(d_dp)
                if d_mi: state["monthlyinstall"] = int(d_mi)
                if d_yr: state["years"]          = int(d_yr)
            else:
                # Try extracting from free text
                d = _digits(user_input)
                if d and not state.get("Downpayment"):
                    state["Downpayment"] = int(d)

            if state.get("Downpayment") and state.get("monthlyinstall"):
                _finalise_installments(state)
                return state

            # Missing something — fall through to loop questions below
            state["waiting_for"] = None
            waiting = ""

        # ── Intelligent loop for missing downpayment ─────────────────────
        if not state.get("Downpayment"):

            if waiting.startswith("install_dp_loop_"):
                attempt = int(waiting.split("_")[-1])
                asked   = state.get("_dp_loop_asked") or []

                guess = _ask(
                    f"User said: '{user_input}'.\n"
                    "Estimate a reasonable down payment for buying a property in Egypt. "
                    "Return ONLY digits."
                )
                d = _digits(guess)
                if d:
                    state["Downpayment"]     = int(d)
                    state["waiting_for"]     = None
                    state["_dp_loop_asked"]  = None
                else:
                    if attempt >= MAX_LOOP:
                        state["agent_message"] = "Please tell me your down payment amount directly."
                        state["waiting_for"]   = "install_dp_loop_1"
                        return state

                    asked.append(user_input)
                    state["_dp_loop_asked"] = asked
                    next_q = _ask(_dp_loop_prompt(asked))
                    state["agent_message"]  = next_q
                    state["waiting_for"]    = f"install_dp_loop_{attempt + 1}"
                    return state

            elif waiting not in ("install_both",):
                # First time asking about downpayment
                asked = state.get("_dp_loop_asked") or []
                q = _ask(_dp_loop_prompt(asked))
                state["agent_message"] = q
                state["waiting_for"]   = "install_dp_loop_1"
                state["_dp_loop_asked"] = []
                return state

        # ── Intelligent loop for missing monthly installment ─────────────
        if not state.get("monthlyinstall"):

            if waiting.startswith("install_mi_loop_"):
                attempt = int(waiting.split("_")[-1])
                asked   = state.get("_mi_loop_asked") or []

                guess = _ask(
                    f"User said: '{user_input}'.\n"
                    "Estimate a reasonable monthly installment for buying a property in Egypt. "
                    "Return ONLY digits."
                )
                d = _digits(guess)
                if d:
                    state["monthlyinstall"]  = int(d)
                    state["waiting_for"]     = None
                    state["_mi_loop_asked"]  = None
                else:
                    if attempt >= MAX_LOOP:
                        state["agent_message"] = "Please tell me your monthly installment amount directly."
                        state["waiting_for"]   = "install_mi_loop_1"
                        return state

                    asked.append(user_input)
                    state["_mi_loop_asked"] = asked
                    next_q = _ask(_mi_loop_prompt(asked))
                    state["agent_message"]  = next_q
                    state["waiting_for"]    = f"install_mi_loop_{attempt + 1}"
                    return state

            else:
                # First time asking about monthly
                asked = state.get("_mi_loop_asked") or []
                q = _ask(_mi_loop_prompt(asked))
                state["agent_message"] = q
                state["waiting_for"]   = "install_mi_loop_1"
                state["_mi_loop_asked"] = []
                return state

        # ── First combined ask (both missing) ────────────────────────────
        if not state.get("Downpayment") and not state.get("monthlyinstall") and not waiting:
            question = _ask(
                "Ask the user about their downpayment, monthly installment, "
                "and number of years naturally without being direct. "
                "Only ask, don't answer."
            ) or (
                "Could you share your down payment, monthly installment, "
                "and how many years you'd like? (one per line is fine)"
            )
            state["agent_message"] = question
            state["waiting_for"]   = "install_both"
            return state

        # Both collected
        if state.get("Downpayment") and state.get("monthlyinstall"):
            _finalise_installments(state)

    return state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _finalise_installments(state: dict) -> None:
    years = state.get("years") or 1
    state["budget"] = (
        state["Downpayment"] + state["monthlyinstall"] * 12 * years
    )
    state["next_step"] = "location_agent"


def _cash_loop_prompt(asked: list) -> str:
    previous = "\n".join(asked)
    return f"""
You are an intelligent, empathetic real estate assistant.
The user has not clearly stated their budget.
Ask ONE subtle, natural question to guide them toward revealing it.
Never ask "What is your budget?" directly.
Make it completely different from previous questions:
{previous}
Output ONLY the question.
"""


def _dp_loop_prompt(asked: list) -> str:
    previous = "\n".join(asked)
    return f"""
You are an intelligent real estate assistant.
The user chose installments but hasn't provided their down payment.
Ask ONE natural question to guide them. Never ask directly.
Different from previous:
{previous}
Return ONLY the question.
"""


def _mi_loop_prompt(asked: list) -> str:
    previous = "\n".join(asked)
    return f"""
You are an intelligent real estate assistant.
The user chose installments but hasn't provided their monthly installment.
Ask ONE natural question to guide them. Never ask directly.
Different from previous:
{previous}
Return ONLY the question.
"""