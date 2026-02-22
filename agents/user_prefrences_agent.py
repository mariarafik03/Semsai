import json
from typing import Any, Dict, List, Optional, Tuple

from state import AgentState
from main_helpers import ask_ollama

PREFS_MAX_TURNS = 4  # short, not boring

FEATURE_KEYS = [
    "project_type",
    "coastal_water_orientation",
    "amenities_breadth",
    "density_scale_proxy",
    "accessibility_context",
]

SYSTEM_PROMPT = """
You are SEMSAI Preferences Agent.

Goal:
Collect user preferences for ranking Egyptian real-estate compounds with MINIMAL questions (max 4 turns).
Ask ONLY one question per turn. Keep it human and short.

CRITICAL:
- Do NOT ask about the same field twice if you already have a normalized value with confidence >= 0.65.
- Do NOT repeat the exact same question wording.
- If user says "all" / "everything", treat it as "balanced" (for top_priority).
- If user indicates confusion (e.g., "I don't understand", "again", "?"), then the next question must be a short clarification with clear choices, or stop with balanced defaults.

UX rules:
- Always show choices (A/B/C/D) as examples, BUT the user can answer freely in natural language.
- The user is NOT required to reply with a letter.

Normalization rules:
- After each user answer, you MUST interpret it into a structured normalized value.
- If unclear (low confidence), ask ONE short clarification question.
- You must output JSON ONLY (no markdown, no extra text).

You will be given known state info (location, property_type, budget, payment_type) and inferred context.

You may either:
1) Ask a question:
{
  "action": "ask",
  "question": "One short question. Include example choices A/B/C/D. End with: 'Answer in your own words.'",
  "expected_answer_format": "free_text",
  "why_this_question": "One short sentence.",
  "interpretation_schema": {
    "field": "top_priority|has_kids|wants_mixed_use|wants_water_view|commute_need",
    "allowed": ["A","B","C","D"]  // or ["true","false","null"]
  }
}

2) Stop when enough info is collected:
{
  "action": "stop",
  "preferences": {
    "top_priority": "commute" | "quiet_low_density" | "amenities" | "balanced" | null,
    "wants_mixed_use": true|false|null,
    "has_kids": true|false|null,
    "wants_water_view": true|false|null,
    "notes": string|null
  },
  "ranking_weights": {
    "project_type": number,
    "coastal_water_orientation": number,
    "amenities_breadth": number,
    "density_scale_proxy": number,
    "accessibility_context": number
  },
  "stop_reason": string
}

Weights constraints:
- Must contain exactly the 5 keys: project_type, coastal_water_orientation, amenities_breadth, density_scale_proxy, accessibility_context
- Values must be floats.
- Normalize weights so sum ~= 1.0.
- Make weights context-aware and preference-aware (Cairo vs Coast).
""".strip()


# -----------------------
# Helpers
# -----------------------

def _norm(s: Optional[str]) -> str:
    return (s or "").strip()


def _looks_like_confusion(ans: str) -> bool:
    a = (ans or "").strip().lower()
    if not a:
        return True
    confusion_markers = {
        "again", "againn", "repeat", "?", "؟؟", "what", "huh",
        "i can not understand", "i cannot understand", "dont understand",
        "don't understand", "مش فاهم", "مش فاهمة", "مش فاهمه", "مش فاهمك", "مش مفهوم"
    }
    if a in confusion_markers:
        return True
    # common short confusion patterns
    if "not understand" in a or "can't understand" in a or "cannot understand" in a:
        return True
    if "مش فاهم" in a or "مش مفهوم" in a:
        return True
    return False


def _preclean_user_answer(ans: str) -> str:
    """
    Keep logic the same, but avoid feeding non-answers to the normalizer.
    If the user is confused, return empty to force clarification.
    """
    ans = _norm(ans)
    if _looks_like_confusion(ans):
        return ""
    return ans


def _infer_context(state: AgentState) -> str:
    loc = (state.get("location") or "").lower()
    purpose = (state.get("purpose") or "").lower()

    cairo_markers = ["new cairo", "cairo", "tagamo", "fifth settlement", "rehab", "zayed", "october", "nasr city", "heliopolis"]
    coast_markers = ["north coast", "sahel", "alamein", "new alamein", "sidi", "marina", "ghazala", "ras el hekma", "marsa matrouh"]

    if any(k in loc for k in cairo_markers):
        return "cairo_living"
    if any(k in loc for k in coast_markers):
        return "coast_vacation"
    if "living" in purpose or "live" in purpose:
        return "cairo_living"
    if "vacation" in purpose or "summer" in purpose:
        return "coast_vacation"
    return "general"


def _safe_parse_json(raw: str) -> Dict[str, Any]:
    raw = (raw or "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("LLM did not return valid JSON.")
        return json.loads(raw[start:end + 1])


def _validate_weights(w: Dict[str, Any]) -> None:
    if not isinstance(w, dict):
        raise ValueError("ranking_weights must be an object.")
    if set(w.keys()) != set(FEATURE_KEYS):
        raise ValueError(f"ranking_weights must contain exactly: {FEATURE_KEYS}")
    for k in FEATURE_KEYS:
        if not isinstance(w[k], (int, float)):
            raise ValueError(f"ranking_weights[{k}] must be a number.")


def _normalize_weights(w: Dict[str, float]) -> Dict[str, float]:
    total = float(sum(w.values()) or 1.0)
    return {k: round(float(v) / total, 4) for k, v in w.items()}


def _interpret_answer(context: str, question: str, user_answer: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    field = schema.get("field") or "unknown"
    allowed = schema.get("allowed") or ["true", "false", "null"]

    prompt = f"""
You are a strict answer normalizer.

Context: {context}

Question:
{question}

User answer (free text):
{user_answer}

Return JSON ONLY:
{{
  "field": "{field}",
  "normalized": one of {json.dumps(allowed)},
  "confidence": 0.0-1.0,
  "notes": string|null
}}
""".strip()

    raw = ask_ollama(prompt)
    data = _safe_parse_json(raw)

    # minimal validation
    if data.get("field") != field:
        data["field"] = field
    if "normalized" not in data:
        raise ValueError("Normalizer did not return 'normalized'.")
    if "confidence" not in data or not isinstance(data["confidence"], (int, float)):
        data["confidence"] = 0.0
    if data.get("notes") is None:
        data["notes"] = None

    return data


def _needs_clarification(interp: Dict[str, Any]) -> bool:
    try:
        return float(interp.get("confidence") or 0.0) < 0.55
    except Exception:
        return True


def _clarify_question(field: str) -> str:
    # still ONE short clarification per low confidence (same logic), but clearer choices
    if field == "has_kids":
        return "Quick check: do you need family/kids-friendly features? (A) Yes (B) No (C) Maybe later (D) Not sure"
    if field == "top_priority":
        return "What matters MOST? (A) Commute (B) Quiet/Privacy (C) Amenities (D) Balanced"
    if field == "wants_mixed_use":
        return "Do you prefer mixed-use? (A) Yes inside services (B) Residential-only (C) Either (D) Not sure"
    if field == "wants_water_view":
        return "Is water view/beach proximity important? (A) Very (B) Somewhat (C) Not important (D) Not sure"
    if field == "commute_need":
        return "Is fast access to roads/work important? (A) Yes (B) No (C) Somewhat (D) Not sure"
    return "Can you clarify your last answer in one short sentence?"


# -----------------------
# Agent
# -----------------------

def user_preferences_agent(state: AgentState) -> AgentState:
    print("\n--- User Preferences Agent (LLM-based, free-text answers) ---")

    context = _infer_context(state)
    known = {
        "location": state.get("location"),
        "property_type": state.get("typeofproperty"),
        "budget": state.get("budget"),
        "payment_type": state.get("payment_type"),
        "context": context,
    }

    messages: List[Tuple[str, str]] = []
    messages.append(("system", SYSTEM_PROMPT))
    messages.append(("user", f"Known context/state:\n{json.dumps(known, ensure_ascii=False)}"))

    normalized_signals: Dict[str, Any] = {}

    for turn in range(1, PREFS_MAX_TURNS + 1):
        prompt = "\n\n".join([f"{role.upper()}:\n{content}" for role, content in messages])

        raw = ask_ollama(prompt)
        data = _safe_parse_json(raw)

        action = data.get("action")

        if action == "ask":
            question = data.get("question") or ""
            schema = data.get("interpretation_schema") or {}
            field = schema.get("field") or "unknown"

            if not question.strip():
                raise ValueError("LLM ask action missing question.")

            print(f"Agent: {question}")
            user_answer_raw = _norm(input("You: "))
            user_answer = _preclean_user_answer(user_answer_raw)

            # Interpret free-text answer
            interp = _interpret_answer(context, question, user_answer, schema)
            normalized_signals[field] = interp

            # If unclear, ask ONE clarification question (still free text)
            if _needs_clarification(interp):
                cq = _clarify_question(field)
                print(f"Agent: {cq}")
                clarify_answer_raw = _norm(input("You: "))
                clarify_answer = _preclean_user_answer(clarify_answer_raw)

                interp2 = _interpret_answer(context, cq, clarify_answer, schema)
                normalized_signals[field] = interp2

            messages.append(("assistant", json.dumps(data, ensure_ascii=False)))
            messages.append(("user", json.dumps({
                "user_answer": user_answer_raw,  # keep original raw for transparency
                "user_answer_cleaned": user_answer,
                "normalized_interpretation": normalized_signals[field],
                "all_normalized_signals_so_far": normalized_signals,
            }, ensure_ascii=False)))

            continue

        if action == "stop":
            prefs = data.get("preferences") or {}
            weights = data.get("ranking_weights") or {}
            stop_reason = data.get("stop_reason") or "enough_signal"

            _validate_weights(weights)
            weights = _normalize_weights({k: float(weights[k]) for k in FEATURE_KEYS})

            state["user_preferences"] = {
                "context": context,
                "preferences": prefs,
                "ranking_weights": weights,
                "stop_reason": stop_reason,
                "turns_used": turn,
                "known": known,
                "normalized_signals": normalized_signals,
            }

            print("\n✅ Preferences captured.")
            print("Weights:", weights)
            print("Stop reason:", stop_reason)

            state["next_step"] = "compound_ranking_agent"
            return state

        raise ValueError(f"Unexpected action from LLM: {action}")

    fallback = _normalize_weights({
        "project_type": 0.20,
        "coastal_water_orientation": 0.05 if context == "cairo_living" else 0.20,
        "amenities_breadth": 0.25,
        "density_scale_proxy": 0.25,
        "accessibility_context": 0.25,
    })

    state["user_preferences"] = {
        "context": context,
        "preferences": {"notes": "Stopped due to max turns."},
        "ranking_weights": fallback,
        "stop_reason": "max_turns",
        "turns_used": PREFS_MAX_TURNS,
        "known": known,
        "normalized_signals": normalized_signals,
    }
    state["next_step"] = "compound_ranking_agent"
    return state