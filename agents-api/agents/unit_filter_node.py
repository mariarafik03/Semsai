"""
agents/interactive_unit_filter.py  (HTTP-safe refactor)
────────────────────────────────────────────────────────
Dynamically asks the user preference questions about available units,
then re-ranks them using the answers.

waiting_for values used
───────────────────────
"unit_filter_q_{n}"   → question n sent to user, waiting for answer (n = 1-based)

State scratch-pad keys (prefixed with _ so they don't pollute domain state)
─────────────────────────────────────────────────────────────────────────────
_uf_questions      : list[dict]   — generated UnitQuestion objects (serialised)
_uf_answers        : dict         — {key: chosen_option} collected so far
_uf_current_q      : int          — index of next question to ask (0-based)
_uf_done           : bool         — True once ranking is complete
"""

import json
from typing import Optional

from pydantic import BaseModel, ValidationError, field_validator

from main_helpers import ask_ollama
from state import AgentState


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class UnitQuestion(BaseModel):
    key: str
    question: str
    options: list[str]

    @field_validator("options")
    @classmethod
    def at_least_two_options(cls, v):
        if len(v) < 2:
            raise ValueError("Each question must have at least 2 options")
        return v


class UnitQuestions(BaseModel):
    questions: list[UnitQuestion]

    @field_validator("questions")
    @classmethod
    def at_least_one_question(cls, v):
        if len(v) == 0:
            raise ValueError("Must have at least one question")
        return v


class RankedUnits(BaseModel):
    ranked_ids: list[str]
    reasoning: Optional[str] = None

    @field_validator("ranked_ids")
    @classmethod
    def must_not_be_empty(cls, v):
        if len(v) == 0:
            raise ValueError("ranked_ids must contain at least one unit ID")
        return v


# ---------------------------------------------------------------------------
# Data summarisation helpers
# ---------------------------------------------------------------------------

def _build_unit_summary(units: list, budget: float = None) -> list[dict]:
    rows = []
    for u in units:
        price = u.get("price") or 0
        area  = u.get("area")  or 0
        row = {
            "id":            str(u.get("_id")),
            "price_egp":     price,
            "area_m2":       area,
            "bedrooms":      u.get("bedrooms"),
            "finishing":     u.get("finishing"),
            "sale_type":     u.get("sale_type"),
            "delivery_year": u.get("delivery_year"),
            "floor":         u.get("floor"),
        }
        if budget is not None:
            row["within_budget"] = price <= budget
        rows.append(row)
    return rows


def _extract_distinct_values(units: list) -> dict:
    fields = ["finishing", "sale_type", "delivery_year", "bedrooms", "floor"]
    distinct = {}
    for field in fields:
        values = list({
            u.get(field)
            for u in units
            if u.get(field) is not None
        })
        if len(values) > 1:
            distinct[field] = sorted(values, key=str)

    areas = [float(u.get("area") or 0) for u in units if u.get("area")]
    if areas and (max(areas) - min(areas)) / max(areas) > 0.10:
        distinct["area_range"] = {"min": min(areas), "max": max(areas)}

    prices = [float(u.get("price") or 0) for u in units if u.get("price")]
    if prices:
        distinct["price_range"] = {"min": min(prices), "max": max(prices)}

    return distinct


# ---------------------------------------------------------------------------
# LLM: Generate questions
# ---------------------------------------------------------------------------

def _generate_questions(
    units: list, budget: float = None
) -> Optional[UnitQuestions]:
    summary  = _build_unit_summary(units, budget)
    distinct = _extract_distinct_values(units)
    budget_note = f"The user's budget is {int(budget):,} EGP." if budget else ""

    prompt = f"""
You are a real estate advisor helping a user choose between a small set of investment units
inside a single compound they have already selected.

{budget_note}

Here are the available units:
{json.dumps(summary, indent=2)}

IMPORTANT — These are the ONLY real values that exist in the data for each field.
Do NOT invent options that are not listed here:
{json.dumps(distinct, indent=2)}

Your job: generate 2-4 concise questions that would best help differentiate these specific units.

Rules:
- Only ask about attributes that genuinely vary across the units (use the distinct values above).
- NEVER offer an option that does not exist in the data.
- When prices differ, phrase the question to include the actual prices AND whether each option
  is within the user's budget (use the within_budget field from the unit data above).
- Always include "No preference" as a final option.
- If only one field varies, ask only one question.

Respond ONLY with valid JSON matching this exact structure, no extra text:
{{
  "questions": [
    {{
      "key": "area_preference",
      "question": "Which area size do you prefer?",
      "options": ["388m² — 50,000,000 EGP (within budget)", "410m² — 51,300,000 EGP (within budget)", "No preference"]
    }}
  ]
}}
"""

    raw = ask_ollama(prompt)
    try:
        raw  = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)
        return UnitQuestions(**data)
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"   ⚠️  Question generation failed ({e}). Skipping filter.")
        return None


# ---------------------------------------------------------------------------
# LLM: Rank units
# ---------------------------------------------------------------------------

def _rank_units(
    units: list, user_answers: dict, budget: float = None
) -> Optional[RankedUnits]:
    summary     = _build_unit_summary(units, budget)
    budget_note = f"The user's budget is {int(budget):,} EGP." if budget else ""

    prompt = f"""
You are a real estate investment advisor.

{budget_note}

The user has answered the following preference questions:
{json.dumps(user_answers, indent=2)}

Here are the available units to rank:
{json.dumps(summary, indent=2)}

Instructions:
- Rank units from best to worst fit based on the user's answers.
- If the user expressed a preference but NO unit matches it exactly,
  pick the closest available option — do NOT eliminate all units.
- Only eliminate a unit if it clearly conflicts with a hard preference AND
  at least one other unit remains.
- Always keep at least 1 unit.
- State whether the recommended unit is within budget, what finishing it has,
  and why it was ranked first.

Respond ONLY with valid JSON, no extra text:
{{
  "ranked_ids": ["unit_id_1", "unit_id_2"],
  "reasoning": "Unit X ranked first: within budget at 50M EGP, semi-finished, 388m²."
}}
"""

    raw = ask_ollama(prompt)
    try:
        raw  = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)
        return RankedUnits(**data)
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"   ⚠️  Unit ranking failed ({e}). Using original order.")
        return None


# ---------------------------------------------------------------------------
# Helpers — scratch-pad accessors
# ---------------------------------------------------------------------------

def _get_questions(state: AgentState) -> Optional[list]:
    return state.get("_uf_questions")


def _get_answers(state: AgentState) -> dict:
    return dict(state.get("_uf_answers") or {})


def _get_current_q(state: AgentState) -> int:
    return int(state.get("_uf_current_q") or 0)


def _flush_scratch(state: AgentState) -> None:
    for k in ("_uf_questions", "_uf_answers", "_uf_current_q", "_uf_done"):
        state.pop(k, None)  # type: ignore[misc]


def _apply_ranking(state: AgentState, answers: dict) -> AgentState:
    """Run LLM ranking and update state["candidate_units"]."""
    units  = state.get("candidate_units") or []
    budget = state.get("budget")

    ranked_result = _rank_units(units, answers, budget=budget)

    if ranked_result is None:
        print("   Proceeding with original unit order.")
        _flush_scratch(state)
        return state

    id_to_unit   = {str(u.get("_id")): u for u in units}
    ranked_units = [
        id_to_unit[uid]
        for uid in ranked_result.ranked_ids
        if uid in id_to_unit
    ]

    # Safety net: append any units the LLM silently dropped
    ranked_ids_set = set(ranked_result.ranked_ids)
    missed         = [u for u in units if str(u.get("_id")) not in ranked_ids_set]
    ranked_units  += missed

    print(f"\n   Reasoning: {ranked_result.reasoning}")
    print(f"   {len(ranked_units)} units ranked.")

    state["candidate_units"] = ranked_units
    _flush_scratch(state)
    return state


# ---------------------------------------------------------------------------
# Main Filter Function (HTTP-safe)
# ---------------------------------------------------------------------------

def interactive_unit_filter(state: AgentState) -> AgentState:
    """
    HTTP-safe, re-entrant unit filter.

    Turn 1 : generate questions, send question #1, set waiting_for
    Turn 2+ : record answer, send next question  — OR — run ranking and finish
    """
    units  = state.get("candidate_units") or []
    budget = state.get("budget")

    # Nothing to filter
    if len(units) <= 1:
        _flush_scratch(state)
        return state

    waiting    = (state.get("waiting_for") or "").strip()
    user_input = (state.get("user_input") or "").strip()

    # ═══════════════════════════════════════════════════════════════════
    # CASE A — Returning with an answer to a unit question
    # ═══════════════════════════════════════════════════════════════════
    if waiting.startswith("unit_filter_q_"):
        questions_raw = _get_questions(state)
        answers       = _get_answers(state)
        current_q_idx = _get_current_q(state)

        if questions_raw and current_q_idx < len(questions_raw):
            q_data = questions_raw[current_q_idx]
            q_key  = q_data.get("key", f"q_{current_q_idx}")
            opts   = q_data.get("options") or []

            # Try to match answer to an option number or text
            chosen = user_input
            if user_input.isdigit():
                idx = int(user_input) - 1
                if 0 <= idx < len(opts):
                    chosen = opts[idx]

            answers[q_key] = chosen
            print(f"   ✅ [{q_key}] = {chosen}")

        state["_uf_answers"]   = answers
        state["_uf_current_q"] = current_q_idx + 1
        state["waiting_for"]   = None

        next_q_idx = current_q_idx + 1

        # Check if all questions answered
        if questions_raw is None or next_q_idx >= len(questions_raw):
            return _apply_ranking(state, answers)

        # Send next question
        q_data   = questions_raw[next_q_idx]
        question = q_data.get("question", "")
        opts     = q_data.get("options") or []
        opts_str = "\n".join(f"  {i+1}. {o}" for i, o in enumerate(opts))
        full_q   = f"{question}\n{opts_str}"

        state["agent_message"] = full_q
        state["waiting_for"]   = f"unit_filter_q_{next_q_idx + 1}"
        return state

    # ═══════════════════════════════════════════════════════════════════
    # CASE B — First time: generate questions and send question #1
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n--- Unit Filter ({len(units)} units found in compound) ---")

    unit_questions = _generate_questions(units, budget=budget)

    if unit_questions is None or not unit_questions.questions:
        print("   Proceeding with all candidate units (no questions generated).")
        _flush_scratch(state)
        return state

    # Serialise questions into state for future turns
    questions_raw = [q.model_dump() for q in unit_questions.questions]
    state["_uf_questions"]  = questions_raw
    state["_uf_answers"]    = {}
    state["_uf_current_q"]  = 0
    state["_uf_done"]       = False

    # Send first question
    q_data   = questions_raw[0]
    question = q_data.get("question", "")
    opts     = q_data.get("options") or []
    opts_str = "\n".join(f"  {i+1}. {o}" for i, o in enumerate(opts))
    full_q   = f"{question}\n{opts_str}"

    state["agent_message"] = full_q
    state["waiting_for"]   = "unit_filter_q_1"
    return state