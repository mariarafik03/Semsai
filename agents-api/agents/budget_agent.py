import json
import re
from state import AgentState
from main_helpers import ask_ollama


def _extract_first_number(text: str) -> int | None:
    """Extract the FIRST number from text. Handles '5M', '500k', '3,000,000', etc."""
    if not text:
        return None

    text = str(text).strip()

    # Handle shorthand like 5M, 3.5M, 500k
    m = re.search(r'(\d+(?:\.\d+)?)\s*[Mm](?:illion)?', text)
    if m:
        return int(float(m.group(1)) * 1_000_000)

    m = re.search(r'(\d+(?:\.\d+)?)\s*[Kk]', text)
    if m:
        return int(float(m.group(1)) * 1_000)

    # Find first standalone number (with optional commas)
    m = re.search(r'\b(\d{1,3}(?:,\d{3})*|\d+)\b', text)
    if m:
        return int(m.group(1).replace(",", ""))

    return None


def _llm_extract_installments(user_input: str) -> dict:
    """Use LLM to extract down_payment, monthly_installment, years from complex text."""
    prompt = f"""
User said: '{user_input}'

Extract financial details about real estate installment payments in Egypt.
If user mentions a range (e.g. "5 to 7 million"), use the middle value.
Convert shorthand: 8M = 8000000, 500k = 500000, 5 million = 5000000.

Return ONLY valid JSON, no markdown, no explanation:
{{"down_payment": number_or_null, "monthly_installment": number_or_null, "years": number_or_null}}
"""
    raw = ask_ollama(prompt).strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    # Find JSON object in response
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        raw = raw[start:end + 1]

    try:
        return json.loads(raw)
    except Exception:
        return {}


def budget_agent(state: AgentState):
    """
    Collects payment type and budget information.
    Non-blocking: uses pending_question + user_input pattern.
    """

    user_input = state.get("user_input")
    step = state.get("_budget_step", "init")

    # ── Determine starting step ──
    if step == "init":
        if state.get("payment_type"):
            if state["payment_type"] == "cash" and not state.get("budget"):
                step = "cash_budget"
            elif state["payment_type"] == "installments" and not (state.get("Downpayment") and state.get("monthlyinstall")):
                step = "installments"
            else:
                return state
        else:
            step = "payment_type"
        state["_budget_step"] = step

    # ═══════════════════════════════════════════════════════════════
    # Step: Ask payment type
    # ═══════════════════════════════════════════════════════════════
    if step == "payment_type":
        if not user_input:
            state["pending_question"] = "Would you prefer to pay in cash or installments?"
            return state

        lower = user_input.lower()
        if "cash" in lower or "كاش" in lower:
            state["payment_type"] = "cash"
            state["payment_type_confirmed"] = True
            state["user_input"] = None
            state["_budget_step"] = "cash_budget"
            return state
        elif "install" in lower or "قسط" in lower or "تقسيط" in lower:
            state["payment_type"] = "installments"
            state["payment_type_confirmed"] = True
            state["user_input"] = None
            state["_budget_step"] = "installments"
            return state
        else:
            # Try LLM
            result = ask_ollama(
                f"User said: '{user_input}'. Return exactly one word: cash or installments"
            ).strip().lower()
            if result in ("cash", "installments"):
                state["payment_type"] = result
                state["payment_type_confirmed"] = True
                state["user_input"] = None
                state["_budget_step"] = "cash_budget" if result == "cash" else "installments"
                return state

            state["pending_question"] = "Sorry, could you clarify — cash or installments?"
            state["user_input"] = None
            return state

    # ═══════════════════════════════════════════════════════════════
    # Step: Cash budget
    # ═══════════════════════════════════════════════════════════════
    if step == "cash_budget":
        if not user_input:
            state["pending_question"] = "What's your total budget for the property?"
            return state

        num = _extract_first_number(user_input)
        if num and num > 10_000:
            state["budget"] = num
            state["user_input"] = None
            state.pop("_budget_step", None)
            return state

        state["pending_question"] = "Could you please tell me your budget in EGP? (e.g. 3,000,000 or 3M)"
        state["user_input"] = None
        return state

    # ═══════════════════════════════════════════════════════════════
    # Step: Installments
    # ═══════════════════════════════════════════════════════════════
    if step == "installments":
        has_dp = state.get("Downpayment") is not None
        has_mi = state.get("monthlyinstall") is not None

        # Already have both → compute budget and done
        if has_dp and has_mi:
            years = state.get("years", 1)
            state["budget"] = state["Downpayment"] + state["monthlyinstall"] * 12 * years
            state["user_input"] = None
            state.pop("_budget_step", None)
            return state

        if user_input:
            # ── Simple case: only ONE field is missing ──
            if has_mi and not has_dp:
                # We only need down payment — ANY number user gives IS the dp
                num = _extract_first_number(user_input)
                if num and num > 0:
                    state["Downpayment"] = num
                    state["user_input"] = None
                    # Now we have both
                    years = state.get("years", 1)
                    state["budget"] = num + state["monthlyinstall"] * 12 * years
                    state.pop("_budget_step", None)
                    return state
                # Fallback: try LLM
                extracted = _llm_extract_installments(user_input)
                dp = extracted.get("down_payment")
                if dp:
                    dp_num = _extract_first_number(str(dp))
                    if dp_num and dp_num > 0:
                        state["Downpayment"] = dp_num
                        state["user_input"] = None
                        years = state.get("years", 1)
                        state["budget"] = dp_num + state["monthlyinstall"] * 12 * years
                        state.pop("_budget_step", None)
                        return state
                # Still can't extract
                state["pending_question"] = "I couldn't understand the amount. Please type just the number, e.g. 5000000"
                state["user_input"] = None
                return state

            elif has_dp and not has_mi:
                # We only need monthly installment
                num = _extract_first_number(user_input)
                if num and num > 0:
                    state["monthlyinstall"] = num
                    state["user_input"] = None
                    years = state.get("years", 1)
                    state["budget"] = state["Downpayment"] + num * 12 * years
                    state.pop("_budget_step", None)
                    return state
                state["pending_question"] = "I couldn't understand the amount. Please type just the number, e.g. 50000"
                state["user_input"] = None
                return state

            else:
                # ── Missing both: use LLM to extract from complex message ──
                extracted = _llm_extract_installments(user_input)

                dp = extracted.get("down_payment")
                mi = extracted.get("monthly_installment")
                yrs = extracted.get("years")

                if dp:
                    dp_num = _extract_first_number(str(dp))
                    if dp_num and dp_num > 0:
                        state["Downpayment"] = dp_num

                if mi:
                    mi_num = _extract_first_number(str(mi))
                    if mi_num and mi_num > 0:
                        state["monthlyinstall"] = mi_num

                if yrs:
                    y_num = _extract_first_number(str(yrs))
                    if y_num and y_num > 0:
                        state["years"] = y_num

                state["user_input"] = None

                # Check if we now have enough
                if state.get("Downpayment") and state.get("monthlyinstall"):
                    years = state.get("years", 1)
                    state["budget"] = state["Downpayment"] + state["monthlyinstall"] * 12 * years
                    state.pop("_budget_step", None)
                    return state

                # Ask about missing fields
                has_dp = state.get("Downpayment") is not None
                has_mi = state.get("monthlyinstall") is not None

        # ── No user_input OR still missing fields → ask the right question ──
        has_dp = state.get("Downpayment") is not None
        has_mi = state.get("monthlyinstall") is not None

        if has_dp and has_mi:
            # Actually have both now
            years = state.get("years", 1)
            state["budget"] = state["Downpayment"] + state["monthlyinstall"] * 12 * years
            state.pop("_budget_step", None)
            return state
        elif not has_dp and not has_mi:
            state["pending_question"] = (
                "For installment payments, I need:\n"
                "1. Down payment amount\n"
                "2. Monthly installment amount\n"
                "3. Number of years\n\n"
                "Share all at once or one at a time!"
            )
        elif not has_dp:
            state["pending_question"] = (
                f"✅ Monthly installment: {state['monthlyinstall']:,} EGP\n\n"
                "How much would you like to put as a down payment?"
            )
        elif not has_mi:
            state["pending_question"] = (
                f"✅ Down payment: {state['Downpayment']:,} EGP\n\n"
                "What monthly installment amount works for you?"
            )

        return state

    return state