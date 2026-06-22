"""
agents/user_preferences_agent.py  (HTTP-safe refactor)
───────────────────────────────────────────────────────
Replaces all input() / stdin calls with the waiting_for pattern.

waiting_for values used
───────────────────────
"preference_input"  → sent a question to the user, waiting for their answer

State scratch-pad keys (prefixed with _ so they don't pollute domain state)
─────────────────────────────────────────────────────────────────────────────
_pref_signals       : dict  — collected {field: {raw_answer, normalized}} so far
_pref_asked         : list  — fields already asked about
_pref_history       : list  — LLM conversation history strings
_pref_turn          : int   — how many turns have been taken
_pref_last_schema   : dict  — interpretation_schema from the last LLM ask
_pref_last_question : str   — question text from the last LLM ask
"""

import json
import os
import uuid
from typing import Any, Dict, Optional
from datetime import datetime, timezone

import certifi
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

from state import AgentState
from main_helpers import ask_ollama


# ==========================================================================
# CONFIG
# ==========================================================================

PREFS_MAX_TURNS       = 4
MIN_FEATURES_BEFORE_STOP = 3

FEATURE_KEYS = [
    "project_type",
    "coastal_water_orientation",
    "amenities_breadth",
    "density_scale_proxy",
    "accessibility_context",
]

USERS_COLLECTION = "users"
EMBED_MODEL_NAME = "intfloat/e5-base-v2"

# ==========================================================================
# SINGLETONS
# ==========================================================================

_embedder: Optional[Any] = None
_db = None


def _get_db():
    global _db
    if _db is not None:
        return _db

    load_dotenv()
    uri = os.getenv("MONGO_URI")
    if not uri:
        raise ValueError("MONGO_URI not found in environment variables.")

    client = MongoClient(
        uri,
        tls=True,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=60000,
    )
    _db = client.get_default_database()
    return _db


def _get_embedder():
    global _embedder
    if _embedder is None:
        if SentenceTransformer is None:
            raise ImportError(
                "sentence_transformers is required. pip install sentence-transformers"
            )
        _embedder = SentenceTransformer(EMBED_MODEL_NAME)
    return _embedder


# ==========================================================================
# Embedding
# ==========================================================================

def _embed_text(text: str) -> list:
    if not text or not text.strip():
        return []
    vec = _get_embedder().encode(
        "passage: " + text.strip(),
        normalize_embeddings=True,
    )
    return vec.tolist()


# ==========================================================================
# JSON Parser
# ==========================================================================

def _safe_parse_json(raw: str) -> Any:
    raw = (raw or "").strip()

    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        raw = raw.replace("```", "").strip()

    try:
        return json.loads(raw)
    except Exception:
        pass

    start = raw.find("{")
    end   = raw.rfind("}")
    if start != -1 and end > start:
        return json.loads(raw[start : end + 1])

    raise ValueError("JSON Parse Error — could not extract object")


# ==========================================================================
# SYSTEM PROMPT
# ==========================================================================

def _build_system_prompt(known: Dict[str, Any]) -> str:
    return f"""
You are SEMSAI Preferences Agent.

IMPORTANT:
- Output VALID JSON only.
- No explanations.
- No markdown.
- No extra text.

Goal:
Interview the user to determine preferences for:
{FEATURE_KEYS}

Rules:
1. Ask EXACTLY ONE question per turn.
2. Provide A/B/C/D options.
3. Use action: "ask" or "stop".
4. Stop only if at least {MIN_FEATURES_BEFORE_STOP} fields collected.

Ask format:
{{
  "action": "ask",
  "question": "...",
  "interpretation_schema": {{
      "field": "...",
      "mapping": {{
          "A": "...",
          "B": "...",
          "C": "...",
          "D": "..."
      }}
  }}
}}

Stop format:
{{
  "action": "stop",
  "ranking_weights": {{
      "project_type": float,
      "coastal_water_orientation": float,
      "amenities_breadth": float,
      "density_scale_proxy": float,
      "accessibility_context": float
  }}
}}

Current Context:
{json.dumps(known)}
""".strip()


# ==========================================================================
# FREE-TEXT INTERPRETER
# ==========================================================================

def _interpret_free_text(
    question: str, mapping: Dict[str, str], user_answer: str
) -> tuple:
    """Map a free-text answer to the closest option. Returns (key, value)."""
    interpret_prompt = f"""
The user was asked: "{question}"
Available options: {json.dumps(mapping)}
User's free-text answer: "{user_answer}"

Return ONLY a JSON object like:
{{"matched_key": "A", "matched_value": "..."}}

Pick the closest matching option key. If nothing matches, pick the most reasonable one.
No explanations. No markdown. Valid JSON only.
"""
    try:
        raw_interp   = ask_ollama(interpret_prompt)
        interp       = _safe_parse_json(raw_interp)
        matched_key  = str(interp.get("matched_key", "")).upper()
        matched_value = interp.get("matched_value") or mapping.get(matched_key, user_answer)
        return matched_key, matched_value
    except Exception:
        return "?", user_answer


# ==========================================================================
# STORAGE
# ==========================================================================

def _save_preferences(
    user_id: str,
    preferences: Dict[str, Any],
    weights: Dict[str, float],
    signals: Dict[str, Any],
) -> None:
    try:
        db      = _get_db()
        user_id = str(user_id).strip()

        query = (
            {"_id": ObjectId(user_id)}
            if ObjectId.is_valid(user_id)
            else {"user_id": user_id}
        )

        signal_text      = json.dumps({"weights": weights, "signals": signals})
        embedding_vector = _embed_text(signal_text)

        db[USERS_COLLECTION].update_one(
            query,
            {
                "$set": {
                    "embedding":        embedding_vector,
                    "embedding_model":  EMBED_MODEL_NAME,
                    "updated_at":       datetime.now(timezone.utc),
                    "preferences":      preferences,
                    "weights":          weights,
                    "signals":          signals,
                },
                "$setOnInsert": {
                    "email": f"agent_{user_id}@semsai.local",
                    "created_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
        print("✅ Preferences stored in DB")
    except Exception as e:
        print(f"❌ DB Save Error: {e}")


# ==========================================================================
# VALIDATION
# ==========================================================================

def _validate_llm_output(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    if data.get("action") not in ("ask", "stop"):
        return False
    if data["action"] == "ask":
        schema = data.get("interpretation_schema", {})
        if "field" not in schema or "mapping" not in schema:
            return False
    if data["action"] == "stop":
        if "ranking_weights" not in data:
            return False
    return True


# ==========================================================================
# HELPERS — scratch-pad accessors (state.pref_scratch is a plain dict;
# AgentState itself is a Pydantic model and doesn't support dict-style
# access, so all interview scratch state lives inside this one field)
# ==========================================================================

def _get_signals(state: AgentState) -> Dict[str, Any]:
    return dict(state.pref_scratch.get("signals") or {})


def _get_asked(state: AgentState) -> set:
    return set(state.pref_scratch.get("asked") or [])


def _get_history(state: AgentState) -> list:
    return list(state.pref_scratch.get("history") or [])


def _get_turn(state: AgentState) -> int:
    return int(state.pref_scratch.get("turn") or 0)


def _flush_scratch(state: AgentState) -> None:
    """Clear the interview scratch-pad once we are done."""
    state.pref_scratch = {}


def _finalise(
    state: AgentState,
    signals: Dict[str, Any],
    weights: Dict[str, float],
    turn: int,
    status: str,
) -> AgentState:
    """Persist preferences and mark agent as done."""
    session_user_id = state.user_id or f"guest_{uuid.uuid4().hex[:8]}"
    preferences = {
        "weights": weights,
        "signals": signals,
        "turns":   turn,
        "status":  status,
    }
    _save_preferences(session_user_id, preferences, weights, signals)
    state.user_preferences = preferences
    _flush_scratch(state)
    state.waiting_for   = None
    state.agent_message = None
    print(f"\n✅ Preferences finalised — status={status}, turns={turn}")
    return state


# ==========================================================================
# MAIN AGENT
# ==========================================================================

def user_preferences_agent(state: AgentState) -> AgentState:
    """
    HTTP-safe preference interview.

    Each HTTP request lands here.  The agent either:
      • sends the next question back to the user (sets waiting_for + agent_message)
      • processes the user's answer and either asks again or finalises
    """

    # ── Already done? ────────────────────────────────────────────────────
    if state.user_preferences is not None:
        return state

    print("\n--- User Preferences Agent ---")

    waiting    = (state.waiting_for or "").strip()
    user_input = (state.user_input or "").strip()

    # ── Load scratch-pad ─────────────────────────────────────────────────
    signals = _get_signals(state)
    asked   = _get_asked(state)
    history = _get_history(state)
    turn    = _get_turn(state)

    # ═════════════════════════════════════════════════════════════════════
    # CASE A — We sent a question last turn; process the user's answer now
    # ═════════════════════════════════════════════════════════════════════
    if waiting == "preference_input" and user_input:
        last_schema   = state.pref_scratch.get("last_schema") or {}
        last_question = state.pref_scratch.get("last_question") or ""
        field         = last_schema.get("field")
        mapping       = last_schema.get("mapping") or {}

        if field and mapping:
            matched_key, matched_value = _interpret_free_text(
                question=last_question,
                mapping=mapping,
                user_answer=user_input,
            )
            signals[field] = {
                "raw_answer": user_input,
                "normalized": matched_value,
            }
            asked.add(field)
            history.append(
                f"USER:\n"
                + json.dumps({"answer": user_input, "interpreted_as": matched_value})
            )
            print(f"  ✅ [{field}] interpreted as: {matched_value}")

        turn += 1

        # Save scratch-pad back
        state.pref_scratch["signals"] = signals
        state.pref_scratch["asked"]   = list(asked)
        state.pref_scratch["history"] = history
        state.pref_scratch["turn"]    = turn
        state.waiting_for = None

        # Check termination conditions
        if len(signals) >= MIN_FEATURES_BEFORE_STOP or turn >= PREFS_MAX_TURNS:
            return _finalise(state, signals, {}, turn, "completed")

    # ═════════════════════════════════════════════════════════════════════
    # CASE B — Ask the next question
    # ═════════════════════════════════════════════════════════════════════

    # Guard against infinite loops
    if turn >= PREFS_MAX_TURNS:
        return _finalise(state, signals, {}, turn, "limit_reached")

    # Build LLM prompt
    system_prompt = _build_system_prompt(signals)

    # First call: start fresh; subsequent calls: append history
    if not history:
        full_history = [
            f"SYSTEM:\n{system_prompt}",
            "USER:\nBegin interview.",
        ]
    else:
        full_history = [f"SYSTEM:\n{system_prompt}"] + history + ["USER:\nContinue."]

    # LLM call (up to 2 retries for invalid JSON/schema)
    data = None
    for attempt in range(3):
        try:
            raw  = ask_ollama("\n\n".join(full_history))
            data = _safe_parse_json(raw)
            if _validate_llm_output(data):
                break
            history.append(
                "SYSTEM:\nInvalid schema — follow the defined JSON format strictly."
            )
        except Exception as e:
            print(f"  ⚠️  LLM attempt {attempt + 1} failed: {e}")
            data = None

    if data is None:
        # LLM failed repeatedly — finalise with whatever we have
        return _finalise(state, signals, {}, turn, "llm_error")

    # ── action: stop ─────────────────────────────────────────────────────
    if data["action"] == "stop":
        if len(signals) < MIN_FEATURES_BEFORE_STOP:
            # LLM tried to stop too early — push it to continue
            history.append(
                f"SYSTEM:\nYou must collect at least "
                f"{MIN_FEATURES_BEFORE_STOP} features before stopping. Continue."
            )
            state.pref_scratch["history"] = history
            # Recurse-by-return: waiting_for is still None, so the router
            # will route straight back into this same agent next step.
            return state

        weights = data.get("ranking_weights") or {}
        history.append(f"ASSISTANT:\n{json.dumps(data)}")
        state.pref_scratch["history"] = history
        return _finalise(state, signals, weights, turn, "completed")

    # ── action: ask ──────────────────────────────────────────────────────
    schema   = data["interpretation_schema"]
    field    = schema.get("field")
    question = data.get("question", "")
    mapping  = schema.get("mapping") or {}

    # Skip already-asked fields
    if field in asked:
        history.append(
            f"SYSTEM:\nField '{field}' already collected. Ask about a different field."
        )
        state.pref_scratch["signals"] = signals
        state.pref_scratch["asked"]   = list(asked)
        state.pref_scratch["history"] = history
        state.pref_scratch["turn"]    = turn
        # Return without waiting_for — router will re-enter this agent
        return state

    # Build option display to append to the question
    options_display = "  |  ".join(
        f"{k}) {v}" for k, v in mapping.items()
    )
    full_question = f"{question}\n({options_display})"

    # Persist state for next turn
    state.pref_scratch["signals"]      = signals
    state.pref_scratch["asked"]        = list(asked)
    state.pref_scratch["history"]      = history + [f"ASSISTANT:\n{json.dumps(data)}"]
    state.pref_scratch["turn"]         = turn
    state.pref_scratch["last_schema"]  = schema
    state.pref_scratch["last_question"] = question

    state.agent_message = full_question
    state.waiting_for    = "preference_input"

    print(f"  ❓ Asking about field: {field}")
    return state