"""
error_helpers.py — Structured error handling for the agent pipeline.

get_retry_message and format_give_up_message now generate messages via the
LLM (agents.llm_messages) so that all fallback/give-up messages are also
conversational and dynamically generated.
"""

from __future__ import annotations

_FIELD_LABELS = {
    "location": "location",
    "property_type": "property type",
    "payment_type": "payment method",
    "downpayment": "down payment",
    "monthly_installment": "monthly installment",
    "budget": "budget",
}


def should_retry(state, field: str, max_retries: int = 3) -> bool:
    """Check if the user has attempts left for a specific field."""
    return state.get_error_count(field) < max_retries


def get_remaining_retries(state, field: str, max_retries: int = 3) -> int:
    """Get the number of attempts remaining for a field."""
    return max_retries - state.get_error_count(field)


def get_retry_message(field: str, error: str, remaining: int, state=None) -> str:
    """
    LLM-generated retry message.
    Falls back to a plain string if the LLM call fails.
    """
    label = _FIELD_LABELS.get(field, field)
    try:
        from main_helpers import ask_llm_with_history
        history = []
        if state is not None and hasattr(state, "get_llm_messages"):
            history = state.get_llm_messages(last_n=4)
        result = ask_llm_with_history(
            system_prompt=(
                "You are a warm, concise real estate assistant. "
                "Write SHORT retry messages (1-2 sentences). No markdown."
            ),
            history=history,
            user_prompt=(
                f"The user gave an invalid {label}. Reason: '{error}'. "
                f"They have {remaining} attempt(s) remaining. "
                f"Politely ask them to try again."
            ),
            max_tokens=120,
            temperature=0.4,
        ).strip()
        return result
    except Exception:
        if remaining > 0:
            return (
                f"I'm sorry, I didn't quite get that. {error} "
                f"You have {remaining} more {'try' if remaining == 1 else 'tries'}."
            )
        return format_give_up_message(field)


def format_give_up_message(field: str, state=None) -> str:
    """
    LLM-generated give-up message when all retries are exhausted.
    Falls back to a plain string if the LLM call fails.
    """
    label = _FIELD_LABELS.get(field, field)
    try:
        from main_helpers import ask_llm_with_history
        history = []
        if state is not None and hasattr(state, "get_llm_messages"):
            history = state.get_llm_messages(last_n=4)
        result = ask_llm_with_history(
            system_prompt=(
                "You are a warm, concise real estate assistant. "
                "Write SHORT messages (1-2 sentences). No markdown."
            ),
            history=history,
            user_prompt=(
                f"The user has exhausted all attempts to provide a valid {label}. "
                "Apologise briefly and let them know a human agent will assist them."
            ),
            max_tokens=100,
            temperature=0.4,
        ).strip()
        return result
    except Exception:
        return (
            f"I'm having trouble understanding your {label}. "
            "Let me connect you with a human agent who can help better."
        )
