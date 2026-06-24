"""
extraction_agent.py — Entry-point agent: open-ended greeting + one-shot
multi-field extraction from the user's first free-form message.

This restores the behaviour of the original prototype (greet → let the user
describe everything in one message → pull out every field at once with the
LLM) while staying compatible with the HTTP pause/resume graph engine:
no blocking input(), no raw dict state — everything goes through
AgentState/AgentContext and the waiting_for pause mechanism.

WORKFLOW
────────
1. First call (no input yet): ask one open-ended question inviting the user
   to share area, property type, budget, payment method, and purpose all in
   one message. Pause with waiting_for = "initial_message".
2. Next call (the user's free-form answer arrives): send it to the LLM,
   extract every recognisable field in one pass, save high-confidence
   values to state.context, then clear waiting_for and hand off.
   If the LLM call fails or returns unusable JSON, fall back to the fast
   rule-based extractor so the user's message is never wasted.
3. The router then asks only for whatever wasn't extracted — it never
   re-asks for fields that are already filled in.
4. Defensive case: if this agent is ever resumed with waiting_for pointing
   at a field owned by another agent (location/property_type/...), delegate
   there directly instead of getting stuck repeating the opening question.

CONVERSATION HISTORY
────────────────────
The LLM extraction call now receives the last N turns of conversation history
via state.get_llm_messages(). This lets the model handle corrections and
context that span multiple messages, e.g.:
  User turn 1: "I want an apartment in New Cairo"
  Agent:        "What's your budget?"
  User turn 2:  "Actually make it a villa — budget is 5 million"
Without history, turn 2 would only extract budget. With history, the model
sees the prior mention of "apartment" and can correctly apply the correction.
"""

import json
from typing import List, Dict, Optional

from state import AgentState
from agents.utils.extractors import extract_all_fields
from main_helpers import ask_llm_with_history


OPENING_MESSAGE = (
    "Hello! I'm your real estate assistant. Tell me a bit about what you're "
    "looking for — area, property type (apartment, villa, or chalet), "
    "budget, payment method (cash or installment), and whether it's for "
    "living, renting out, or investment. Share as much as you'd like in one "
    "message!"
)

# ── Extraction system prompt ──────────────────────────────────────────────────
# Kept as a constant so it's easy to tune without touching call-site code.
_EXTRACTION_SYSTEM = """\
You are a real estate data extraction engine for the Egyptian market.

Your job is to read a conversation and extract structured property-search \
fields from the user's latest message. Use the conversation history only to \
resolve ambiguity and apply corrections (e.g. "actually make it a villa" \
overrides an earlier apartment mention).

Rules:
- Only include a field if the user CLEARLY mentioned it — never guess.
- Apply shorthand conversions: "3M" → 3000000, "500k" → 500000.
  If the number has no unit and the scale is ambiguous, return null.
- A correction in the latest message always beats an earlier value.
- Respond ONLY with valid JSON — no markdown fences, no commentary.
"""

_EXTRACTION_PROMPT = """\
From the user's message below, extract as many of these fields as you can:

Fields:
- purpose             : one of "rent", "invest", "live"  (null if unclear)
- location            : area/city in Egypt  (e.g. "New Cairo")
- typeofproperty      : one of "apartment", "villa", "chalet"
- payment_type        : one of "cash", "installment"
- budget              : total budget in EGP as an integer
- downpayment         : down-payment in EGP as an integer (only if mentioned)
- monthly_installment : monthly installment in EGP as an integer (only if mentioned)

User message: "{user_input}"

Respond ONLY with valid JSON, null for anything you cannot extract. Example:
{{"purpose": "live", "location": "New Cairo", "typeofproperty": "villa", \
"payment_type": "cash", "budget": 5000000, "downpayment": null, \
"monthly_installment": null}}
"""

_VALID_PURPOSES        = {"rent", "invest", "live"}
_VALID_PROPERTY_TYPES  = {"apartment", "villa", "chalet"}
_VALID_PAYMENT_TYPES   = {"cash", "installment"}


def _field_agent_for(waiting_for: str):
    """Map a waiting_for value to the agent that owns that field."""
    from agents.location_agent      import location_agent
    from agents.property_type_agent import property_type_agent
    from agents.payment_agent       import payment_agent
    from agents.budget_agent        import budget_agent
    from agents.compounds_agent     import compounds_agent
    from agents.developers_agent    import developers_agent

    return {
        "location":              location_agent,
        "property_type":         property_type_agent,
        "payment_type":          payment_agent,
        "downpayment":           payment_agent,
        "monthly_installment":   payment_agent,
        "budget":                budget_agent,
        "no_units_response":     compounds_agent,
        "no_developer_response": developers_agent,
    }.get(waiting_for)


def _llm_extract(
    user_input: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> dict:
    """
    Use the LLM to pull every recognisable field out of one free-form
    message, using the conversation history for context.

    Parameters
    ----------
    user_input : str
        The user's latest message (current turn).
    history : list of {role, content} dicts, optional
        Prior turns from state.get_llm_messages().  Pass an empty list
        or None for the very first message.

    Returns
    -------
    dict
        Extracted fields.  Never raises — returns {} on any failure so a
        flaky API call never breaks the conversation.
    """
    prompt = _EXTRACTION_PROMPT.format(user_input=user_input)

    try:
        raw = ask_llm_with_history(
            system_prompt=_EXTRACTION_SYSTEM,
            history=history or [],
            user_prompt=prompt,
            max_tokens=256,
            temperature=0.1,   # near-zero: we want deterministic JSON
        )

        # Strip accidental markdown fences the model sometimes adds
        if raw.startswith("```"):
            raw = raw.strip("`")
            if "\n" in raw:
                raw = raw.split("\n", 1)[1]

        return json.loads(raw)

    except Exception as exc:
        print(f"   ⚠️ LLM extraction failed ({exc}) — falling back to rule-based extractor")
        return {}


def _apply_extraction(state: AgentState, user_input: str) -> None:
    """
    Extract every recognisable field from one free-form message and save
    high-confidence values to state.context.

    Passes the full conversation history so the model can resolve
    corrections across turns (e.g. "actually make it a villa").
    """
    # Exclude the message we just appended (the runner already added it) —
    # pass only the prior turns so the model treats user_input as the *new*
    # message rather than seeing it duplicated in both history and the prompt.
    prior_history = state.get_llm_messages(last_n=10)
    # The runner appended the current user message before calling this agent,
    # so the last entry in prior_history IS the current message.  Trim it to
    # avoid the duplicate.
    if prior_history and prior_history[-1]["role"] == "user":
        prior_history = prior_history[:-1]

    fields = _llm_extract(user_input, prior_history)
    extracted_count = 0

    purpose = (fields.get("purpose") or "").strip().lower()
    if purpose in _VALID_PURPOSES:
        state.purpose = purpose
        print(f"   ✓ purpose: {purpose}")
        extracted_count += 1

    location = (fields.get("location") or "").strip()
    if location:
        state.context.location = location.title()
        print(f"   ✓ location: {state.context.location}")
        extracted_count += 1

    ptype = (fields.get("typeofproperty") or "").strip().lower()
    if ptype in _VALID_PROPERTY_TYPES:
        state.context.property_type = ptype
        print(f"   ✓ property_type: {ptype}")
        extracted_count += 1

    pay = (fields.get("payment_type") or "").strip().lower()
    if pay in _VALID_PAYMENT_TYPES:
        state.context.payment_type = pay
        print(f"   ✓ payment_type: {pay}")
        extracted_count += 1

    budget = fields.get("budget")
    if isinstance(budget, (int, float)) and budget >= 100_000:
        state.context.budget = float(budget)
        print(f"   ✓ budget: {budget:,.0f} EGP")
        extracted_count += 1

    dp = fields.get("downpayment")
    if isinstance(dp, (int, float)) and dp > 0:
        state.context.downpayment = float(dp)
        print(f"   ✓ downpayment: {dp:,.0f} EGP")
        extracted_count += 1

    mi = fields.get("monthly_installment")
    if isinstance(mi, (int, float)) and mi > 0:
        state.context.monthly_installment = float(mi)
        print(f"   ✓ monthly_installment: {mi:,.0f} EGP")
        extracted_count += 1

    # LLM call failed outright — fall back to rule-based extractor so the
    # message is never silently wasted.
    if not fields:
        for field_name, (value, confidence) in extract_all_fields(user_input).items():
            if not value or confidence != "high":
                continue
            if field_name == "location":
                state.context.location = value
            elif field_name == "property_type":
                state.context.property_type = value
            elif field_name == "payment_type":
                state.context.payment_type = value
            elif field_name == "budget":
                state.context.budget = value
            print(f"   ✓ (fallback) {field_name}: {value}")
            extracted_count += 1

    if extracted_count > 0:
        print(f"📊 Extracted {extracted_count} field(s) from the opening message")
    else:
        print("ℹ️ No fields extracted from the opening message — agents will ask one by one")


def extraction_agent(state: AgentState) -> AgentState:
    """
    Entry-point agent. See module docstring for the full workflow.
    """

    print("\n--- Extraction Agent ---")

    # ── Resuming after the user answered the open-ended opening question ──
    if state.waiting_for == "initial_message":
        state.waiting_for = None

        if not state.user_input or not state.user_input.strip():
            # Empty reply — ask again rather than silently extracting nothing.
            state.agent_message = OPENING_MESSAGE
            state.waiting_for = "initial_message"
            state.sync_to_legacy()
            return state

        _apply_extraction(state, state.user_input)
        state.sync_to_legacy()
        return state

    # ── Defensive: resumed with waiting_for pointing at a field owned by
    # another agent. Shouldn't normally happen but prevents getting stuck. ──
    if state.waiting_for:
        field_agent = _field_agent_for(state.waiting_for)
        if field_agent:
            print(f"↩️  Resuming with waiting_for='{state.waiting_for}' — delegating to {field_agent.__name__}")
            return field_agent(state)
        print(f"⚠️ Unknown waiting_for='{state.waiting_for}' — clearing and handing off to router")
        state.waiting_for = None
        state.sync_to_legacy()
        return state

    # ── Very first call: nothing collected yet, no input yet ──────────────
    if not state.user_input or not state.user_input.strip():
        print("⚠️ No user input yet — asking the open-ended opening question")
        state.agent_message = OPENING_MESSAGE
        state.waiting_for = "initial_message"
        state.sync_to_legacy()
        return state

    # ── Edge case: extraction_agent invoked directly WITH input already
    # present (e.g. POST /chat with no session_id and a message in body)
    # — extract immediately, no extra round trip needed. ──────────────────
    _apply_extraction(state, state.user_input)
    state.sync_to_legacy()
    return state
