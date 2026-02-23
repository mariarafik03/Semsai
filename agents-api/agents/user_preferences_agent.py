"""
User Preferences Agent — collects user preferences via multi-turn conversation.
Session-based (no input() calls). Adapted from agents/user_prefrences_agent.py.
"""
import json
from typing import Any, Dict, List, Optional, Tuple

from llm_helper import ask_llm


PREFS_MAX_TURNS = 4

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
- If user indicates confusion, then the next question must be a short clarification with clear choices, or stop with balanced defaults.

UX rules:
- Always show choices (A/B/C/D) as examples, BUT the user can answer freely in natural language.
- The user is NOT required to reply with a letter.

You may either:
1) Ask a question:
{
  "action": "ask",
  "question": "One short question. Include example choices A/B/C/D. End with: 'Answer in your own words.'",
  "expected_answer_format": "free_text",
  "why_this_question": "One short sentence.",
  "interpretation_schema": {
    "field": "top_priority|has_kids|wants_mixed_use|wants_water_view|commute_need",
    "allowed": ["A","B","C","D"]
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
        "again", "repeat", "?", "what", "huh",
        "i can not understand", "i cannot understand", "dont understand",
        "don't understand",
    }
    if a in confusion_markers:
        return True
    if "not understand" in a or "can't understand" in a:
        return True
    return False


def _preclean_user_answer(ans: str) -> str:
    ans = _norm(ans)
    if _looks_like_confusion(ans):
        return ""
    return ans


def _infer_context(state: dict) -> str:
    loc = (state.get("location") or "").lower()
    purpose = (state.get("purpose") or "").lower()

    cairo_markers = ["new cairo", "cairo", "tagamo", "fifth settlement", "rehab", "zayed", "october", "nasr city", "heliopolis"]
    coast_markers = ["north coast", "sahel", "alamein", "new alamein", "sidi", "marina", "ghazala", "ras el hekma"]

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

    raw = ask_llm(prompt)
    data = _safe_parse_json(raw)

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


def _default_weights(context: str) -> Dict[str, float]:
    return _normalize_weights({
        "project_type": 0.20,
        "coastal_water_orientation": 0.05 if context == "cairo_living" else 0.20,
        "amenities_breadth": 0.25,
        "density_scale_proxy": 0.25,
        "accessibility_context": 0.25,
    })


# -----------------------
# Agent (session-based)
# -----------------------

def user_preferences_agent(state: dict[str, Any], user_input: str | None) -> dict[str, Any]:
    """
    Multi-turn preference collection.
    
    Sub-phases:
      - "generate_question": LLM generates next question
      - "process_answer": user answered, interpret + maybe clarify
      - "clarify": low-confidence answer, ask clarification
      - "process_clarify": user answered clarification
    """
    sub = state.get("sub_phase")
    context = _infer_context(state)

    # Initialize preference tracking in state
    if "pref_messages" not in state:
        state["pref_messages"] = []
        state["pref_signals"] = {}
        state["pref_turn"] = 0

    known = {
        "location": state.get("location"),
        "property_type": state.get("typeofproperty"),
        "budget": state.get("budget"),
        "payment_type": state.get("payment_type"),
        "context": context,
    }

    messages = state["pref_messages"]
    signals = state["pref_signals"]
    turn = state["pref_turn"]

    # ---- GENERATE QUESTION (first call or after processing) ----
    if sub is None or sub == "generate_question":
        if not messages:
            messages.append(("system", SYSTEM_PROMPT))
            messages.append(("user", f"Known context/state:\n{json.dumps(known, ensure_ascii=False)}"))

        prompt = "\n\n".join([f"{role.upper()}:\n{content}" for role, content in messages])
        raw = ask_llm(prompt)

        try:
            data = _safe_parse_json(raw)
        except Exception:
            # If LLM fails to return JSON, use default weights and stop
            state["user_preferences"] = {
                "context": context,
                "preferences": {"notes": "LLM failed to generate question."},
                "ranking_weights": _default_weights(context),
                "stop_reason": "llm_error",
                "turns_used": turn,
                "known": known,
                "normalized_signals": signals,
            }
            state["phase"] = "ranking"
            state["sub_phase"] = None
            state["awaiting_input"] = False
            state["agent_message"] = None
            return state

        action = data.get("action")

        if action == "ask":
            question = data.get("question") or ""
            schema = data.get("interpretation_schema") or {}

            if not question.strip():
                # No question -> stop with defaults
                state["user_preferences"] = {
                    "context": context,
                    "preferences": {"notes": "No question generated."},
                    "ranking_weights": _default_weights(context),
                    "stop_reason": "empty_question",
                    "turns_used": turn,
                    "known": known,
                    "normalized_signals": signals,
                }
                state["phase"] = "ranking"
                state["sub_phase"] = None
                state["awaiting_input"] = False
                state["agent_message"] = None
                return state

            state["pref_current_data"] = data
            state["pref_current_schema"] = schema
            state["pref_turn"] = turn + 1

            messages.append(("assistant", json.dumps(data, ensure_ascii=False)))
            state["pref_messages"] = messages

            state["sub_phase"] = "process_answer"
            state["agent_message"] = question
            state["awaiting_input"] = True
            return state

        if action == "stop":
            prefs = data.get("preferences") or {}
            weights = data.get("ranking_weights") or {}
            stop_reason = data.get("stop_reason") or "enough_signal"

            try:
                _validate_weights(weights)
                weights = _normalize_weights({k: float(weights[k]) for k in FEATURE_KEYS})
            except Exception:
                weights = _default_weights(context)

            state["user_preferences"] = {
                "context": context,
                "preferences": prefs,
                "ranking_weights": weights,
                "stop_reason": stop_reason,
                "turns_used": turn,
                "known": known,
                "normalized_signals": signals,
            }
            state["phase"] = "ranking"
            state["sub_phase"] = None
            state["awaiting_input"] = False
            state["agent_message"] = None
            return state

        # Unknown action -> stop with defaults
        state["user_preferences"] = {
            "context": context,
            "preferences": {"notes": f"Unexpected action: {action}"},
            "ranking_weights": _default_weights(context),
            "stop_reason": "unexpected_action",
            "turns_used": turn,
            "known": known,
            "normalized_signals": signals,
        }
        state["phase"] = "ranking"
        state["sub_phase"] = None
        state["awaiting_input"] = False
        state["agent_message"] = None
        return state

    # ---- PROCESS USER ANSWER ----
    if sub == "process_answer" and user_input:
        data = state.get("pref_current_data") or {}
        schema = state.get("pref_current_schema") or {}
        field = schema.get("field") or "unknown"
        question = data.get("question") or ""

        user_answer = _preclean_user_answer(user_input)

        try:
            interp = _interpret_answer(context, question, user_answer, schema)
            signals[field] = interp
            state["pref_signals"] = signals
        except Exception:
            interp = {"field": field, "normalized": None, "confidence": 0.0, "notes": "interpretation failed"}
            signals[field] = interp
            state["pref_signals"] = signals

        # Check if clarification needed
        if _needs_clarification(interp):
            state["pref_clarify_field"] = field
            state["pref_clarify_schema"] = schema
            cq = _clarify_question(field)
            state["sub_phase"] = "process_clarify"
            state["agent_message"] = cq
            state["awaiting_input"] = True
            return state

        # Add to messages for next LLM call
        messages.append(("user", json.dumps({
            "user_answer": user_input,
            "user_answer_cleaned": user_answer,
            "normalized_interpretation": signals.get(field),
            "all_normalized_signals_so_far": signals,
        }, ensure_ascii=False)))
        state["pref_messages"] = messages

        # Check if max turns reached
        if state["pref_turn"] >= PREFS_MAX_TURNS:
            state["user_preferences"] = {
                "context": context,
                "preferences": {"notes": "Max turns reached."},
                "ranking_weights": _default_weights(context),
                "stop_reason": "max_turns",
                "turns_used": state["pref_turn"],
                "known": known,
                "normalized_signals": signals,
            }
            state["phase"] = "ranking"
            state["sub_phase"] = None
            state["awaiting_input"] = False
            state["agent_message"] = None
            return state

        # Generate next question
        state["sub_phase"] = "generate_question"
        state["awaiting_input"] = False
        state["agent_message"] = None
        return state

    # ---- PROCESS CLARIFICATION ANSWER ----
    if sub == "process_clarify" and user_input:
        field = state.get("pref_clarify_field") or "unknown"
        schema = state.get("pref_clarify_schema") or {}
        cq = _clarify_question(field)

        user_answer = _preclean_user_answer(user_input)

        try:
            interp2 = _interpret_answer(context, cq, user_answer, schema)
            signals[field] = interp2
            state["pref_signals"] = signals
        except Exception:
            pass

        # Add to messages
        messages.append(("user", json.dumps({
            "user_answer": user_input,
            "user_answer_cleaned": user_answer,
            "normalized_interpretation": signals.get(field),
            "all_normalized_signals_so_far": signals,
        }, ensure_ascii=False)))
        state["pref_messages"] = messages

        # Check if max turns reached
        if state["pref_turn"] >= PREFS_MAX_TURNS:
            state["user_preferences"] = {
                "context": context,
                "preferences": {"notes": "Max turns reached."},
                "ranking_weights": _default_weights(context),
                "stop_reason": "max_turns",
                "turns_used": state["pref_turn"],
                "known": known,
                "normalized_signals": signals,
            }
            state["phase"] = "ranking"
            state["sub_phase"] = None
            state["awaiting_input"] = False
            state["agent_message"] = None
            return state

        # Generate next question
        state["sub_phase"] = "generate_question"
        state["awaiting_input"] = False
        state["agent_message"] = None
        return state

    return state
