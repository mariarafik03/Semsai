"""
agents/budget_agent.py
──────────────────────
Collect and validate the user's budget, then negotiate gracefully when
the figure is below the DB minimum — without any blocking input() loops.

Negotiation flow (graph-native, one turn at a time)
────────────────────────────────────────────────────
When a budget fails DB validation the agent sets
  waiting_for = "budget_negotiation"
and returns.  On the next turn the router sends the user's reply back
here, where we detect their intent and either:
  • update the budget           → re-validate
  • change the location         → update state, re-validate
  • change the property type    → update state, re-validate
  • stay unclear (max 2 tries)  → politely give up

waiting_for values used in this agent
──────────────────────────────────────
  "budget"             — asking for the budget amount for the first time
  "budget_negotiation" — user replied to "budget too low" message
"""

from __future__ import annotations

import re
from typing import Optional

from state import AgentState
from agents.utils.extractors import extract_budget
from agents.utils.validators import validate_budget
from agents.utils.error_helpers import (
    should_retry,
    get_retry_message,
    format_give_up_message,
    get_remaining_retries,
)
from database import get_db
from main_helpers import ask_llm_with_history


# ─────────────────────────────────────────────────────────────────────────────
# Small helpers
# ─────────────────────────────────────────────────────────────────────────────

def _llm(prompt: str, state: AgentState | None = None) -> str:
    """Single-turn LLM call, optionally injecting conversation history."""
    history = []
    if state is not None and hasattr(state, "get_llm_messages"):
        history = state.get_llm_messages()
    return ask_llm_with_history(
        system_prompt="You are a friendly, concise real-estate assistant for Egyptian properties.",
        history=history,
        user_prompt=prompt,
        max_tokens=256,
        temperature=0.3,
    ).strip()


def _parse_number(text: str) -> Optional[int]:
    """Best-effort parse of a numeric amount from free text."""
    val, _, _ = extract_budget(str(text))
    return int(val) if val and val >= 100_000 else None


def _detect_negotiation_intent(user_input: str) -> str:
    """
    Classify what the user wants after being told their budget is too low.
    Returns: 'change_location' | 'change_budget' | 'change_property_type' | 'unclear'
    """
    reply = _llm(
        f"The user said: '{user_input}'.\n"
        "They were told their budget is below the minimum for available properties.\n"
        "Classify their intent. Rules — a place name ALWAYS wins:\n"
        "- Mentions a city/area/neighbourhood → change_location\n"
        "- Mentions a new number, 'more', 'increase', 'raise' → change_budget\n"
        "- Mentions a property type (apartment, villa, chalet …) → change_property_type\n"
        "- Anything else → unclear\n"
        "Return ONLY one word: change_location | change_budget | change_property_type | unclear"
    ).lower()
    for valid in ("change_location", "change_budget", "change_property_type"):
        if valid in reply:
            return valid
    return "unclear"


def _extract_location(text: str) -> Optional[str]:
    result = _llm(
        f"User said: '{text}'.\n"
        "Extract the Egyptian city/area name they mentioned.\n"
        "Return ONLY the place name, or 'none' if not found."
    )
    return None if result.lower() == "none" else result.strip()


def _extract_property_type(text: str) -> Optional[str]:
    result = _llm(
        f"User said: '{text}'.\n"
        "Extract the property type (apartment / villa / chalet / townhouse / studio).\n"
        "Return ONLY the type word, or 'none' if not found."
    )
    return None if result.lower() == "none" else result.strip().capitalize()


def _min_price_message(state: AgentState, min_price: int) -> str:
    """Build the 'budget too low' negotiation prompt shown to the user."""
    ctx = state.context
    budget_fmt = f"{(ctx.budget or 0):,.0f}"
    min_fmt    = f"{min_price:,.0f}"
    return _llm(
        f"The user's budget is {budget_fmt} EGP, but the cheapest available "
        f"{ctx.property_type} in {ctx.location} starts at {min_fmt} EGP.\n"
        "Politely tell them, and offer three options:\n"
        "1. Raise their budget\n"
        "2. Try a different area in Egypt\n"
        "3. Consider a different property type\n"
        "Keep it warm and under 3 sentences. Do NOT answer for them."
    )


def _reset_search_cache(state: AgentState) -> None:
    """Clear downstream search results so the graph reruns from scratch."""
    for attr in (
        "candidate_compounds", "final_compounds", "compound_features_stats",
        "embeddings", "ranked_compounds", "final_best_compound", "candidate_units",
    ):
        if hasattr(state.context, attr):
            setattr(state.context, attr, None)
        # also clear top-level legacy keys
        if hasattr(state, attr):
            try:
                setattr(state, attr, None)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# DB helper (reuses the old approach but returns clean dict)
# ─────────────────────────────────────────────────────────────────────────────

def _get_db_minimum(state: AgentState) -> Optional[dict]:
    """
    Query MongoDB for the minimum price / down-payment in the current
    location + property_type + payment_type combination.
    Returns a dict with keys 'min_price' (cash) or
    'min_down_payment' / 'min_monthly' (installments), or None if no data.
    """
    try:
        import os, certifi
        from pymongo import MongoClient
        from dotenv import load_dotenv
        load_dotenv()
        uri = os.getenv("MONGO_URI")
        if not uri:
            return None

        ctx = state.context
        location      = ctx.location_normalized or ctx.location or ""
        property_type = ctx.property_type or ""
        payment_type  = (ctx.payment_type or "").lower()

        client = MongoClient(uri, tls=True, tlsCAFile=certifi.where(),
                             serverSelectionTimeoutMS=10_000)
        db  = client.get_default_database()
        col = db["units"]

        base_match = {
            "location":      {"$regex": location,      "$options": "i"},
            "property_type": {"$regex": f"^{property_type}$", "$options": "i"},
        }

        if payment_type == "cash":
            pipeline = [
                {"$match": {**base_match,
                            "payment_plans": {"$elemMatch": {
                                "is_cash": True,
                                "unit_price": {"$ne": None, "$gt": 0},
                            }}}},
                {"$unwind": "$payment_plans"},
                {"$match": {"payment_plans.is_cash": True,
                            "payment_plans.unit_price": {"$ne": None, "$gt": 0}}},
                {"$group": {"_id": None, "min_price": {"$min": "$payment_plans.unit_price"}}},
            ]
        else:
            pipeline = [
                {"$match": {**base_match,
                            "payment_plans": {"$elemMatch": {
                                "is_cash": False,
                                "down_payment": {"$ne": None, "$gt": 0},
                                "single_installment_amount": {"$ne": None, "$gt": 0},
                            }}}},
                {"$unwind": "$payment_plans"},
                {"$match": {"payment_plans.is_cash": False,
                            "payment_plans.down_payment": {"$ne": None, "$gt": 0},
                            "payment_plans.single_installment_amount": {"$ne": None, "$gt": 0}}},
                {"$group": {"_id": None,
                            "min_down_payment": {"$min": "$payment_plans.down_payment"},
                            "min_monthly":      {"$min": "$payment_plans.single_installment_amount"}}},
            ]

        result = list(col.aggregate(pipeline))
        client.close()
        return result[0] if result else None

    except Exception as exc:
        print(f"⚠️  _get_db_minimum error: {exc}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Negotiation handler  (called when waiting_for == "budget_negotiation")
# ─────────────────────────────────────────────────────────────────────────────

def _handle_negotiation(state: AgentState, db) -> AgentState:
    """
    Process one negotiation turn: detect intent, apply change, re-validate.
    Uses state.context.negotiation_attempts to cap retries at 2.
    """
    ctx         = state.context
    user_input  = state.user_input or ""
    attempts    = getattr(ctx, "negotiation_attempts", 0)
    intent      = _detect_negotiation_intent(user_input)

    print(f"   [budget negotiation] intent={intent!r}  attempt={attempts+1}")

    # ── Location change ──────────────────────────────────────────────────────
    if intent == "change_location":
        new_loc = _extract_location(user_input)
        if not new_loc:
            state.agent_message = _llm(
                "The user wants to change location but wasn't specific. "
                "Ask them which area or city in Egypt they'd like to look at. "
                "One sentence only."
            )
            state.waiting_for = "budget_negotiation"
            ctx.negotiation_attempts = attempts + 1
            state.sync_to_legacy()
            return state

        print(f"   ✓ Location → {new_loc}")
        ctx.location = new_loc
        ctx.location_normalized = new_loc
        _reset_search_cache(state)

    # ── Property type change ─────────────────────────────────────────────────
    elif intent == "change_property_type":
        new_type = _extract_property_type(user_input)
        if not new_type:
            state.agent_message = _llm(
                "The user wants a different property type but wasn't specific. "
                "Ask them: apartment, villa, chalet, or townhouse? One sentence only."
            )
            state.waiting_for = "budget_negotiation"
            ctx.negotiation_attempts = attempts + 1
            state.sync_to_legacy()
            return state

        print(f"   ✓ Property type → {new_type}")
        ctx.property_type = new_type
        _reset_search_cache(state)

    # ── Budget change ────────────────────────────────────────────────────────
    elif intent == "change_budget":
        new_budget = _parse_number(user_input)
        if new_budget is None:
            # LLM pass
            guess = _llm(
                f"User said: '{user_input}'. Extract the new budget as digits in EGP. "
                "Return ONLY digits, or 'none'."
            )
            if guess.lower() != "none":
                new_budget = _parse_number(guess)

        if new_budget is None:
            state.agent_message = _llm(
                "The user wants to raise their budget but I couldn't extract a number. "
                "Ask them to state the new amount clearly (e.g. '4 million'). One sentence only."
            )
            state.waiting_for = "budget_negotiation"
            ctx.negotiation_attempts = attempts + 1
            state.sync_to_legacy()
            return state

        print(f"   ✓ Budget → {new_budget:,}")
        ctx.budget = new_budget

    # ── Unclear — give up after 2 attempts ───────────────────────────────────
    else:
        if attempts >= 2:
            state.agent_message = _llm(
                "The user keeps responding unclearly after being told their budget is too low. "
                "Politely say you're unable to find a match right now and suggest they "
                "contact a human advisor or restart with updated details. Keep it warm, 2 sentences."
            )
            state.waiting_for    = None
            ctx.budget_valid     = False
            state.handoff_to_human = True
            state.sync_to_legacy()
            return state

        # Gentle re-prompt
        state.agent_message = _llm(
            f"The user replied '{user_input}' but I couldn't understand what they want to change. "
            "Gently re-offer the three options: raise budget, change location, or change property type. "
            "Keep it under 2 sentences."
        )
        ctx.negotiation_attempts = attempts + 1
        state.waiting_for = "budget_negotiation"
        state.sync_to_legacy()
        return state

    # ── Re-validate after any change ─────────────────────────────────────────
    ctx.budget_valid          = False
    ctx.negotiation_attempts  = 0

    db_min = _get_db_minimum(state)

    if db_min is None:
        # No data at all for new location/type — ask them to reconsider
        state.agent_message = _llm(
            f"We don't have data for {ctx.property_type} in {ctx.location} yet. "
            "Apologise briefly and ask if they'd like to try another area or property type."
        )
        state.waiting_for = "budget_negotiation"
        state.sync_to_legacy()
        return state

    payment_type = (ctx.payment_type or "").lower()

    if payment_type == "cash":
        min_price  = int(db_min.get("min_price", 0))
        user_value = int(ctx.budget or 0)
        if user_value >= min_price:
            # ✅ Valid now
            is_valid, _, _ = validate_budget(ctx.budget, ctx.location_normalized,
                                             ctx.property_type, db)
            ctx.budget_valid  = True
            state.waiting_for = None
            state.agent_message = _llm(
                f"The user's budget of {ctx.budget:,.0f} EGP now works for "
                f"{ctx.property_type} in {ctx.location}. "
                "Confirm briefly and say you're searching now."
            )
        else:
            ctx.budget       = ctx.budget  # keep whatever they said
            state.agent_message = _min_price_message(state, min_price)
            state.waiting_for   = "budget_negotiation"

    else:  # installments
        min_down    = int(db_min.get("min_down_payment", 0))
        min_monthly = int(db_min.get("min_monthly", 0))
        user_down   = int(ctx.downpayment or 0)
        user_mo     = int(ctx.monthly_installment or 0)

        if user_down >= min_down and user_mo >= min_monthly:
            ctx.budget_valid  = True
            state.waiting_for = None
            state.agent_message = _llm(
                f"The installment plan ({ctx.downpayment:,.0f} down, "
                f"{ctx.monthly_installment:,.0f}/month) is now valid for "
                f"{ctx.property_type} in {ctx.location}. "
                "Confirm briefly and say you're searching now."
            )
        else:
            issues = []
            if user_down < min_down:
                issues.append(f"down payment needs to be at least {min_down:,.0f} EGP")
            if user_mo < min_monthly:
                issues.append(f"monthly installment needs to be at least {min_monthly:,.0f} EGP")
            state.agent_message = _llm(
                f"For {ctx.property_type} in {ctx.location}: {' and '.join(issues)}. "
                "Politely inform them and re-offer: raise figures, change location, or change property type. "
                "Under 3 sentences."
            )
            state.waiting_for = "budget_negotiation"

    state.sync_to_legacy()
    return state


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def budget_agent(state: AgentState) -> AgentState:
    """
    Validate budget against location and property type constraints.
    Negotiates gracefully (graph-native, one turn at a time) when the
    figure is below the DB minimum.
    """
    print("\n--- Budget Agent ---")

    # Prerequisites
    if not state.context.location_normalized or not state.context.property_type:
        print("⚠️  Budget validation requires location + property_type first")
        state.sync_to_legacy()
        return state

    db = get_db()

    # ── Resume negotiation ───────────────────────────────────────────────────
    if state.waiting_for == "budget_negotiation":
        return _handle_negotiation(state, db)

    # ── Resume normal budget collection ─────────────────────────────────────
    if state.waiting_for == "budget":
        extracted, confidence, _ = extract_budget(state.user_input)

        if not extracted:
            if should_retry(state, "budget"):
                remaining = get_remaining_retries(state, "budget")
                state.agent_message = get_retry_message(
                    "budget",
                    "I didn't catch that. What's your budget? (e.g. 5 million, 500k)",
                    remaining,
                )
                state.add_error("budget", state.user_input, "Could not extract")
            else:
                state.agent_message = format_give_up_message("budget")
                state.waiting_for   = None
                state.handoff_to_human = True
            state.sync_to_legacy()
            return state

        # Validate against DB
        is_valid, min_budget, error = validate_budget(
            extracted, state.context.location_normalized,
            state.context.property_type, db,
        )

        if is_valid:
            # Also check DB minimum (validator is lenient; DB check is strict)
            db_min = _get_db_minimum(state)
            state.context.budget = extracted

            if db_min is not None:
                payment_type = (state.context.payment_type or "").lower()
                min_price = int(db_min.get("min_price", 0)) if payment_type == "cash" else 0
                if payment_type == "cash" and extracted < min_price:
                    # Trigger negotiation on the very first answer
                    state.context.negotiation_attempts = 0
                    state.agent_message = _min_price_message(state, min_price)
                    state.waiting_for   = "budget_negotiation"
                    state.sync_to_legacy()
                    return state

            state.context.budget_valid = True
            state.waiting_for = None
            state.current_phase = "search"
            state.agent_message = (
                f"Got it! I'll look for {state.context.property_type}s "
                f"in {state.context.location} within {extracted:,.0f} EGP."
            )
            print(f"✓ Budget validated: {extracted:,.0f} EGP")

        else:
            # Possibly a too-low DB minimum — check and negotiate
            db_min = _get_db_minimum(state)
            if db_min:
                payment_type = (state.context.payment_type or "").lower()
                min_price = int(db_min.get("min_price", 0)) if payment_type == "cash" else 0
                if payment_type == "cash" and extracted < min_price:
                    state.context.budget = extracted
                    state.context.negotiation_attempts = 0
                    state.agent_message = _min_price_message(state, min_price)
                    state.waiting_for   = "budget_negotiation"
                    state.sync_to_legacy()
                    return state

            # Generic validation failure — retry or give up
            if should_retry(state, "budget"):
                remaining = get_remaining_retries(state, "budget")
                state.agent_message = get_retry_message("budget", error, remaining)
                state.add_error("budget", str(extracted), error)
            else:
                state.agent_message = format_give_up_message("budget")
                state.waiting_for   = None
                state.handoff_to_human = True

        state.sync_to_legacy()
        return state

    # ── Pre-filled budget (from extraction_agent) — validate now ────────────
    if state.context.budget and not state.context.budget_valid:
        is_valid, min_budget, error = validate_budget(
            state.context.budget, state.context.location_normalized,
            state.context.property_type, db,
        )
        if is_valid:
            db_min = _get_db_minimum(state)
            if db_min:
                payment_type = (state.context.payment_type or "").lower()
                min_price = int(db_min.get("min_price", 0)) if payment_type == "cash" else 0
                if payment_type == "cash" and state.context.budget < min_price:
                    state.context.negotiation_attempts = 0
                    state.agent_message = _min_price_message(state, min_price)
                    state.waiting_for   = "budget_negotiation"
                    state.sync_to_legacy()
                    return state

            state.context.budget_valid = True
            state.current_phase = "search"
            state.agent_message = (
                f"Got it! Budget of {state.context.budget:,.0f} EGP for "
                f"{state.context.property_type} in {state.context.location}."
            )
            print(f"✓ Budget validated (pre-filled): {state.context.budget:,.0f} EGP")
        else:
            print(f"⚠️  Pre-filled budget failed: {error}")
            state.context.budget = None
            # Fall through to ask

    # ── Ask for budget ───────────────────────────────────────────────────────
    if not state.context.budget or not state.context.budget_valid:
        state.agent_message = (
            f"What's your budget for a {state.context.property_type} "
            f"in {state.context.location}? (e.g. 5 million, 500k)"
        )
        state.waiting_for = "budget"

    state.sync_to_legacy()
    return state