"""
questioning_agent.py
HTTP-safe purpose clarification agent.

If purpose is missing, asks the user to choose one of:
- live (سكن)
- invest (استثمار)
- rent (إيجار)
"""

from state import AgentState
from main_helpers import ask_ollama


def _extract_purpose(text: str) -> str | None:
    s = (text or "").strip().lower()
    if not s:
        return None

    # Fast keyword heuristics first
    rent_kw = ["rent", "rental", "lease", "ايجار", "إيجار", "تأجير"]
    invest_kw = ["invest", "investment", "roi", "استثمار", "استثماري"]
    live_kw = ["live", "living", "home", "residence", "سكن", "أسكن", "اسكن", "معيشة"]

    if any(k.lower() in s for k in rent_kw):
        return "rent"
    if any(k.lower() in s for k in invest_kw):
        return "invest"
    if any(k.lower() in s for k in live_kw):
        return "live"

    # LLM fallback
    try:
        raw = (ask_ollama(
            f"Extract ONLY the purpose from this text: '{text}'. "
            "Return exactly one word: rent, invest, live, or unknown."
        ) or "").strip().lower()
    except Exception:
        return None

    if raw in {"rent", "invest", "live"}:
        return raw

    for key in ("rent", "invest", "live"):
        if key in raw:
            return key

    return None


def questioning_agent(state: AgentState) -> AgentState:
    """Ask/resolve purpose if missing."""
    if state.get("purpose"):
        return state

    waiting = (state.get("waiting_for") or "").strip()
    user_input = (state.get("user_input") or "").strip()

    # Resume after question
    if waiting in {"purpose_input", "purpose_retry"}:
        purpose = _extract_purpose(user_input)
        if purpose:
            state["purpose"] = purpose
            state["waiting_for"] = None
            state["agent_message"] = None
            return state

        state["agent_message"] = "هل الغرض من العقار سكن ولا استثمار ولا إيجار؟"
        state["waiting_for"] = "purpose_retry"
        return state

    # First ask
    try:
        q = (ask_ollama(
            "Ask the user one short friendly question to choose purpose: "
            "live, invest, or rent. Arabic is preferred."
        ) or "").strip()
    except Exception:
        q = "إيه الغرض من العقار؟ سكن ولا استثمار ولا إيجار؟"

    if not q:
        q = "إيه الغرض من العقار؟ سكن ولا استثمار ولا إيجار؟"

    state["agent_message"] = q
    state["waiting_for"] = "purpose_input"
    return state
