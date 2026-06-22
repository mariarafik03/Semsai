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
"""

import json

from state import AgentState
from agents.utils.extractors import extract_all_fields
from main_helpers import ask_ollama


OPENING_MESSAGE = (
    "Hello! I'm your real estate assistant. Tell me a bit about what you're "
    "looking for — area, property type (apartment, villa, or chalet), "
    "budget, payment method (cash or installment), and whether it's for "
    "living, renting out, or investment. Share as much as you'd like in one "
    "message!"
)

# Fields the LLM extractor understands and how they map onto AgentContext.
_VALID_PURPOSES = {"rent", "invest", "live"}
_VALID_PROPERTY_TYPES = {"apartment", "villa", "chalet"}
_VALID_PAYMENT_TYPES = {"cash", "installment"}


def _field_agent_for(waiting_for: str):
    """Map a waiting_for value to the agent that owns that field. Mirrors
    the waiting_for routing block in graph_definition.state_router."""
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


def _llm_extract(user_input: str) -> dict:
    """
    Use the LLM to pull every recognisable field out of one free-form
    message — same idea as the original prototype's extraction prompt.
    Returns {} (never raises) if the call fails or the response isn't
    valid JSON, so a flaky API call never breaks the conversation.
    """
    prompt = f"""
You are a real estate data extraction engine for the Egyptian market.

From the user's message below, extract as many of these fields as you can.
Only include a field if the user **clearly** mentioned it — never guess.

Fields:
- purpose             : one of "rent", "invest", "live" (null if unclear)
- location             : area/city in Egypt (e.g. "New Cairo")
- typeofproperty       : one of "apartment", "villa", "chalet"
- payment_type         : one of "cash", "installment"
- budget               : total budget in EGP as an integer
                          (convert shorthand: "3M" -> 3000000, "500k" -> 500000)
                          If the number has no unit, return null — do not guess scale.
- downpayment          : down-payment amount in EGP as an integer (only if mentioned)
- monthly_installment  : monthly installment amount in EGP as an integer (only if mentioned)

User message: "{user_input}"

Respond ONLY with valid JSON, no markdown fences, no commentary. Use null for
anything you cannot extract. Example:
{{"purpose": "live", "location": "New Cairo", "typeofproperty": "villa", "payment_type": "cash", "budget": 5000000, "downpayment": null, "monthly_installment": null}}
"""
    try:
        raw = ask_ollama(prompt).strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if "\n" in raw:
                raw = raw.split("\n", 1)[1]
        return json.loads(raw)
    except Exception as exc:
        print(f"   ⚠️ LLM extraction failed ({exc}) — falling back to rule-based extractor")
        return {}


def _apply_extraction(state: AgentState, user_input: str) -> None:
    """Extract every recognisable field from one free-form message and save
    high-confidence values to state.context (+ state.purpose, which lives
    outside context — see state.py)."""

    fields = _llm_extract(user_input)
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

    # LLM call failed outright (empty dict from an API error / bad JSON) —
    # fall back to the fast rule-based extractor so the message isn't wasted.
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
    # another agent. Shouldn't normally happen once the block above routes
    # things on, but prevents ever getting stuck repeating this node. ──────
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
    # present (e.g. POST /chat with no session_id and a message already in
    # the body) — extract immediately, no extra round trip needed. ────────
    _apply_extraction(state, state.user_input)
    state.sync_to_legacy()
    return state
