"""
error_helpers.py — Structured error handling for the agent pipeline.
"""

def should_retry(state, field: str, max_retries: int = 3) -> bool:
    """Check if the user has attempts left for a specific field."""
    return state.get_error_count(field) < max_retries

def get_remaining_retries(state, field: str, max_retries: int = 3) -> int:
    """Get the number of attempts remaining for a field."""
    return max_retries - state.get_error_count(field)

def get_retry_message(field: str, error: str, remaining: int) -> str:
    """Format a user-friendly retry message."""
    if remaining > 0:
        return f"I'm sorry, I didn't quite get that. {error} You have {remaining} more {'try' if remaining == 1 else 'tries'}."
    return format_give_up_message(field)

def format_give_up_message(field: str) -> str:
    """Message shown when we stop trying to collect a field and hand off."""
    return f"I'm having trouble understanding your {field}. Let me connect you with a human agent who can help better."
