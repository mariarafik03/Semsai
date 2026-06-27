"""
agents/llm_messages.py
──────────────────────
Central LLM-powered message generator.

Every agent message that was previously a hardcoded string now goes through
this module.  Each function:
  1. Builds a focused system prompt describing the scenario.
  2. Calls ask_llm_with_history() so the model sees prior conversation turns.
  3. Returns the model's reply as a plain string.

All functions accept `state` so they can pass conversation history;
structured context is injected inline into the prompt rather than through
a separate system prompt to keep token counts low.

Design principles
─────────────────
- Every function is standalone (no shared mutable state).
- On any LLM failure the function falls back to the original hardcoded
  string so the conversation never breaks.
- Temperature is kept at 0.4 for natural but consistent phrasing.
- max_tokens is capped at 200 — these are short conversational messages.
"""

from __future__ import annotations
from typing import Optional

_SYSTEM = (
    "You are a warm, professional real estate assistant for the Egyptian property market. "
    "Write SHORT, friendly messages (1-3 sentences). "
    "Never use markdown bullet points or headers. "
    "Do not invent property data — only describe what you are told. "
    "Reply in the same language the user is using (Arabic or English)."
)


def _call(prompt: str, state=None, max_tokens: int = 200, temperature: float = 0.4) -> Optional[str]:
    """Internal wrapper — returns None on failure so callers can fall back."""
    try:
        from main_helpers import ask_llm_with_history
        history = []
        if state is not None and hasattr(state, "get_llm_messages"):
            history = state.get_llm_messages(last_n=6)
        return ask_llm_with_history(
            system_prompt=_SYSTEM,
            history=history,
            user_prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        ).strip()
    except Exception as exc:
        print(f"⚠️  llm_messages: LLM call failed ({exc}) — will use fallback")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# extraction_agent
# ─────────────────────────────────────────────────────────────────────────────

def opening_greeting(state=None) -> str:
    result = _call(
        "Write an opening greeting for a real estate search assistant. "
        "Invite the user to share: area/city, property type (apartment/villa/chalet), "
        "budget, payment method (cash or installment), and purpose (living/renting/investment). "
        "Keep it warm and under 3 sentences.",
        state,
    )
    return result or (
        "Hello! I'm your real estate assistant. Tell me a bit about what you're "
        "looking for — area, property type (apartment, villa, or chalet), "
        "budget, payment method (cash or installment), and whether it's for "
        "living, renting out, or investment. Share as much as you'd like!"
    )


# ─────────────────────────────────────────────────────────────────────────────
# location_agent
# ─────────────────────────────────────────────────────────────────────────────

def ask_for_location(state=None) -> str:
    result = _call(
        "Ask the user which city or area in Egypt they are interested in for their property search. "
        "Give 3 example areas naturally (e.g. New Cairo, North Coast, Maadi). One sentence.",
        state,
    )
    return result or "Which city or area are you interested in? (e.g., Cairo, New Cairo, North Coast)"


def location_confirmed(normalized: str, state=None) -> str:
    result = _call(
        f"The user's chosen area has been confirmed as '{normalized}'. "
        "Write a brief confirmation and say you'll search there. One sentence.",
        state,
    )
    return result or f"Great! I'll search for properties in {normalized}."


def location_retry(error: str, remaining: int, state=None) -> str:
    result = _call(
        f"The user gave an invalid location. Error: '{error}'. "
        f"They have {remaining} attempt(s) left. "
        "Politely ask them to try again and give a couple of example Egyptian cities.",
        state,
    )
    return result or f"I didn't catch that area. {error} Could you try again? (e.g., New Cairo, North Coast)"


def location_give_up(state=None) -> str:
    result = _call(
        "The user has exhausted all retries for providing a valid location. "
        "Apologise briefly and say a human agent will assist them.",
        state,
    )
    return result or "I'm having trouble understanding your location. Let me connect you with a human agent who can help better."


# ─────────────────────────────────────────────────────────────────────────────
# property_type_agent
# ─────────────────────────────────────────────────────────────────────────────

def ask_for_property_type(state=None) -> str:
    result = _call(
        "Ask the user what type of property they want: apartment, villa, or chalet. One sentence.",
        state,
    )
    return result or "What type of property are you looking for? (apartment, villa, or chalet)"


def property_type_confirmed(normalized: str, state=None) -> str:
    result = _call(
        f"The user's property type has been set to '{normalized}'. "
        "Write a one-sentence confirmation.",
        state,
    )
    return result or f"Perfect! Looking for a {normalized}."


def property_type_retry(error: str, remaining: int, state=None) -> str:
    result = _call(
        f"The user gave an invalid property type. Error: '{error}'. "
        f"They have {remaining} attempt(s) left. "
        "Ask them to choose apartment, villa, or chalet.",
        state,
    )
    return result or f"I didn't catch that. What type of property are you looking for? (apartment, villa, or chalet)"


def property_type_give_up(state=None) -> str:
    result = _call(
        "The user has exhausted all retries for property type. "
        "Apologise briefly and say a human agent will assist.",
        state,
    )
    return result or "I'm having trouble understanding your property type preference. Let me connect you with a human agent."


# ─────────────────────────────────────────────────────────────────────────────
# payment_agent
# ─────────────────────────────────────────────────────────────────────────────

def ask_for_payment_type(state=None) -> str:
    result = _call(
        "Ask the user whether they want to pay cash or in installments. One sentence.",
        state,
    )
    return result or "How would you like to pay? (cash or installment)"


def payment_type_retry(error: str, remaining: int, state=None) -> str:
    result = _call(
        f"The user's answer about payment method was unclear. Error: '{error}'. "
        f"They have {remaining} attempt(s) left. "
        "Ask them to choose between cash or installment.",
        state,
    )
    return result or "I didn't catch that. Would you prefer to pay cash or in installments?"


def payment_type_give_up(state=None) -> str:
    result = _call(
        "The user exhausted retries for payment method. Apologise and say a human agent will help.",
        state,
    )
    return result or "I'm having trouble understanding your payment preference. Let me connect you with a human agent."


def ask_for_downpayment(state=None) -> str:
    result = _call(
        "Ask the user how much they can pay as a down payment for an installment plan. One sentence.",
        state,
    )
    return result or "How much can you pay as a downpayment?"


def downpayment_retry(remaining: int, state=None) -> str:
    result = _call(
        f"The user's downpayment answer was unclear. They have {remaining} attempt(s) left. "
        "Ask them again for a specific amount in EGP.",
        state,
    )
    return result or "I didn't catch that. How much can you pay as a downpayment?"


def downpayment_give_up(state=None) -> str:
    result = _call(
        "The user exhausted retries for downpayment. Apologise and transfer to a human agent.",
        state,
    )
    return result or "I'm having trouble understanding your downpayment. Let me connect you with a human agent."


def ask_for_monthly_installment(state=None) -> str:
    result = _call(
        "Ask the user what monthly installment amount they are comfortable paying. One sentence.",
        state,
    )
    return result or "What monthly installment amount works for you?"


def monthly_installment_retry(remaining: int, state=None) -> str:
    result = _call(
        f"The user's monthly installment answer was unclear. They have {remaining} attempt(s) left. "
        "Ask them again for a specific monthly amount in EGP.",
        state,
    )
    return result or "I didn't catch that. What monthly installment amount works for you?"


def monthly_installment_give_up(state=None) -> str:
    result = _call(
        "The user exhausted retries for monthly installment. Apologise and transfer to a human agent.",
        state,
    )
    return result or "I'm having trouble understanding your installment preferences. Let me connect you with a human agent."


# ─────────────────────────────────────────────────────────────────────────────
# budget_agent  (already mostly LLM-driven — these cover the remaining cases)
# ─────────────────────────────────────────────────────────────────────────────

def budget_ask(location: str, property_type: str, payment_type: str, state=None) -> str:
    result = _call(
        f"Ask the user for their total budget for a {property_type} in {location} "
        f"with {payment_type} payment. Be warm and specific. One sentence.",
        state,
    )
    return result or f"What is your total budget for a {property_type} in {location}?"


def budget_retry(error: str, remaining: int, state=None) -> str:
    result = _call(
        f"The user's budget was unclear or invalid. Error: '{error}'. "
        f"They have {remaining} attempt(s) left. Ask for a number in EGP.",
        state,
    )
    return result or f"I didn't catch your budget. {error} Please provide a number (e.g., 3,000,000 EGP)."


def budget_give_up(state=None) -> str:
    result = _call(
        "The user exhausted retries for budget. Apologise and transfer to human agent.",
        state,
    )
    return result or "I'm having trouble understanding your budget. Let me connect you with a human agent."


def budget_confirmed(budget: float, state=None) -> str:
    result = _call(
        f"The user's budget of {budget:,.0f} EGP has been confirmed. "
        "Write a brief acknowledgement. One sentence.",
        state,
    )
    return result or f"Got it — budget of {budget:,.0f} EGP noted."


# ─────────────────────────────────────────────────────────────────────────────
# compounds_agent
# ─────────────────────────────────────────────────────────────────────────────

def compounds_location_changed(new_location: str, state=None) -> str:
    result = _call(
        f"Tell the user their search location has been updated to '{new_location}' "
        "and that you are now searching there. One sentence.",
        state,
    )
    return result or f"Location updated to {new_location}. Searching for units there..."


def compounds_property_type_changed(new_type: str, state=None) -> str:
    result = _call(
        f"Tell the user their property type preference has been updated to '{new_type}' "
        "and that you are searching now. One sentence.",
        state,
    )
    return result or f"Property type updated to {new_type}. Searching for units now..."


def compounds_no_units_options(location: str, property_type: str, budget_str: str, state=None) -> str:
    result = _call(
        f"No {property_type} units were found in {location} within {budget_str}. "
        "Sympathetically inform the user and offer three options: "
        "1) Increase budget, 2) Change location, 3) Change property type. "
        "Keep it under 4 sentences. Do not use numbered lists.",
        state,
        max_tokens=250,
    )
    return result or (
        f"I couldn't find any {property_type} units in {location} within {budget_str}. "
        "You could try increasing your budget, looking in a different area, "
        "or considering a different property type — just let me know!"
    )


def compounds_unclear_choice(state=None) -> str:
    result = _call(
        "The user's response to 'no units found' options was unclear. "
        "Politely ask them to choose: increase budget, change location, or change property type.",
        state,
    )
    return result or (
        "I didn't catch that. Would you like to increase your budget, "
        "change the location, or consider a different property type?"
    )


# ─────────────────────────────────────────────────────────────────────────────
# compound_ranking_agent
# ─────────────────────────────────────────────────────────────────────────────

def ranking_no_compounds(state=None) -> str:
    result = _call(
        "Tell the user there are no compounds to rank yet. Very short, one sentence.",
        state,
    )
    return result or "No compounds available to rank yet."


def ranking_no_user_id(state=None) -> str:
    result = _call(
        "Tell the user that personalised ranking is unavailable because user identification "
        "is missing, but you will still show results. One sentence.",
        state,
    )
    return result or "Personalised ranking is unavailable right now — showing available results."


def ranking_unavailable(state=None) -> str:
    result = _call(
        "Tell the user personalised ranking is temporarily unavailable and you are showing "
        "filtered results instead. One sentence.",
        state,
    )
    return result or "Personalised ranking is currently unavailable. Showing filtered results."


def ranking_no_valid_compounds(state=None) -> str:
    result = _call(
        "Tell the user there are no valid compounds to rank after filtering. One sentence.",
        state,
    )
    return result or "No valid compounds to rank after applying your filters."


def ranking_no_vector_results(state=None) -> str:
    result = _call(
        "Tell the user that the vector similarity search returned no results. "
        "One short sentence.",
        state,
    )
    return result or "The similarity search returned no results."


def ranking_complete(count: int, state=None) -> str:
    result = _call(
        f"Tell the user that {count} compound(s) have been ranked based on their preferences. "
        "One short sentence.",
        state,
    )
    return result or f"Ranked {count} compound(s) based on your preferences."


def ranking_failed(error: str, state=None) -> str:
    result = _call(
        f"Tell the user that ranking failed due to a technical issue ({error}) "
        "and you are showing unranked results. One sentence.",
        state,
    )
    return result or "Ranking encountered a technical issue — showing unranked results."


# ─────────────────────────────────────────────────────────────────────────────
# comparing_agent
# ─────────────────────────────────────────────────────────────────────────────

def comparing_no_compounds(state=None) -> str:
    result = _call(
        "Tell the user there are no compounds available for comparison yet. One sentence.",
        state,
    )
    return result or "No compounds available for comparison yet."


def comparing_complete(state=None) -> str:
    result = _call(
        "Tell the user that the compound comparison is done and results are ready. One sentence.",
        state,
    )
    return result or "Compound comparison complete — here are the results."


# ─────────────────────────────────────────────────────────────────────────────
# final_output_agent
# ─────────────────────────────────────────────────────────────────────────────

def no_compounds_found(state=None) -> str:
    result = _call(
        "Tell the user no compounds were found matching their criteria, "
        "and suggest they might adjust location, budget, or property type. "
        "Two sentences maximum, warm tone.",
        state,
    )
    return result or (
        "No compounds were found matching your criteria. "
        "Try adjusting your location, budget, or property type and I'll search again."
    )


def best_match_found(compound_name: str, state=None) -> str:
    result = _call(
        f"Tell the user that the best matching compound is '{compound_name}'. "
        "One short sentence, enthusiastic.",
        state,
    )
    return result or f"Found your best match: {compound_name}!"
