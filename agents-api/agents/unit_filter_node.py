import json
from typing import Optional
from pydantic import BaseModel, ValidationError, field_validator
from main_helpers import ask_ollama  # ✅ import it at the top


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
    """
    Minimal unit representation to keep prompts lean.
    Includes a within_budget flag when budget is known so the LLM
    can surface that context to the user.
    """
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
    """
    Pull the real distinct values for every field that varies across units.
    This prevents the LLM from inventing options that don't exist in the data.
    """
    fields = ["finishing", "sale_type", "delivery_year", "bedrooms", "floor"]
    distinct = {}
    for field in fields:
        values = list({
            u.get(field)
            for u in units
            if u.get(field) is not None
        })
        if len(values) > 1:          # only include if there is actual variation
            distinct[field] = sorted(values, key=str)

    # Area buckets — only if range is meaningful (>10% spread)
    areas = [float(u.get("area") or 0) for u in units if u.get("area")]
    if areas and (max(areas) - min(areas)) / max(areas) > 0.10:
        distinct["area_range"] = {"min": min(areas), "max": max(areas)}

    # Price range — always useful context
    prices = [float(u.get("price") or 0) for u in units if u.get("price")]
    if prices:
        distinct["price_range"] = {"min": min(prices), "max": max(prices)}

    return distinct


# ---------------------------------------------------------------------------
# LLM Calls
# ---------------------------------------------------------------------------

def _generate_questions(units: list, ask_ollama, budget: float = None) -> UnitQuestions | None:
    summary     = _build_unit_summary(units, budget)
    distinct    = _extract_distinct_values(units)
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
- NEVER offer an option that does not exist in the data. For example, if finishing only contains
  "semi-finished" and "not finished", do NOT offer "fully finished" as a choice.
- When prices differ, phrase the question to include the actual prices AND whether each option
  is within the user's budget (use the within_budget field from the unit data above).
- Always include "No preference" as a final option.
- If only one field varies, ask only one question. Do not pad with irrelevant questions.

Respond ONLY with valid JSON matching this exact structure, no extra text:
{{
  "questions": [
    {{
      "key": "area_preference",
      "question": "Both units are semi-finished (no fully finished option available). Which area size do you prefer?",
      "options": ["388m² — 50,000,000 EGP (within budget)", "410m² — 51,300,000 EGP (within budget)", "No preference"]
    }}
  ]
}}
"""

    raw = ask_ollama(prompt)

    try:
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)
        return UnitQuestions(**data)
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"   Warning: Question generation failed ({e}). Skipping filter.")
        return None


def _rank_units(units: list, user_answers: dict, ask_ollama, budget: float = None) -> RankedUnits | None:
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
- If the user expressed a preference (e.g. "fully finished") but NO unit matches it exactly,
  pick the closest available option — do NOT eliminate all units.
- Only eliminate a unit if it clearly and completely conflicts with a hard preference AND
  at least one other unit remains.
- Always keep at least 1 unit.
- In your reasoning, be explicit: state whether the recommended unit is within budget,
  what finishing it actually has, and why it was ranked first despite any mismatch.

Respond ONLY with valid JSON, no extra text:
{{
  "ranked_ids": ["unit_id_1", "unit_id_2"],
  "reasoning": "Unit X ranked first: within budget at 50M EGP, semi-finished (closest to fully finished available), 388m²."
}}
"""

    raw = ask_ollama(prompt)

    try:
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)
        return RankedUnits(**data)
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"   Warning: Unit ranking failed ({e}). Using original order.")
        return None


# ---------------------------------------------------------------------------
# User Interaction
# ---------------------------------------------------------------------------

def _ask_user_questions(questions: UnitQuestions) -> dict:
    answers = {}
    print("\n--- Unit Preference Questions ---")
    print("Help us narrow down the best unit for you:\n")

    for q in questions.questions:
        print(f"  {q.question}")
        for i, opt in enumerate(q.options, 1):
            print(f"    {i}. {opt}")

        while True:
            raw = input("  Your choice (number): ").strip()
            if raw.isdigit() and 1 <= int(raw) <= len(q.options):
                answers[q.key] = q.options[int(raw) - 1]
                print()
                break
            print(f"  Please enter a number between 1 and {len(q.options)}.")

    return answers


# ---------------------------------------------------------------------------
# Main Filter Function
# ---------------------------------------------------------------------------

def interactive_unit_filter(state: AgentState) -> AgentState:
    """
    Dynamically ask users preference questions generated by the LLM based on
    the actual candidate units, then re-rank units using their answers.

    - Questions are grounded in real distinct data values — no hallucinated options.
    - Budget context is passed in and surfaced in both questions and ranking reasoning.
    - Falls back gracefully to the original unit list on any LLM or validation failure.
    """
    units  = state.get("candidate_units") or []
    budget = state.get("budget")

    if len(units) <= 1:
        return state

    print(f"\n--- Unit Filter ({len(units)} units found in compound) ---")

    # Step 1: LLM generates data-aware, grounded questions
    unit_questions = _generate_questions(units, ask_ollama, budget=budget)

    if unit_questions is None:
        print("   Proceeding with all candidate units.")
        return state

    # Step 2: Ask user
    user_answers = _ask_user_questions(unit_questions)

    # Step 3: LLM ranks with budget context and closest-match logic
    ranked_result = _rank_units(units, user_answers, ask_ollama, budget=budget)

    if ranked_result is None:
        print("   Proceeding with original unit order.")
        return state

    # Step 4: Reorder state units to match LLM ranking
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
    #print(f"   {len(ranked_units)} units ranked — passing to scoring agent.\n")

    state["candidate_units"] = ranked_units
    return state