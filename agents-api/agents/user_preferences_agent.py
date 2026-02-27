import json
import os
import uuid
from typing import Any, Dict, Optional
from datetime import datetime, timezone

import certifi
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer

from state import AgentState
from main_helpers import ask_ollama

# ==========================================================
# CONFIG
# ==========================================================

PREFS_MAX_TURNS = 4
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

# ==========================================================
# SINGLETONS
# ==========================================================

_embedder: Optional[SentenceTransformer] = None
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
        _embedder = SentenceTransformer(EMBED_MODEL_NAME)
    return _embedder


# ==========================================================
# Embedding
# ==========================================================

def _embed_text(text: str) -> list:
    if not text or not text.strip():
        return []

    vec = _get_embedder().encode(
        "passage: " + text.strip(),
        normalize_embeddings=True
    )
    return vec.tolist()


# ==========================================================
# JSON Parser
# ==========================================================

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
    end = raw.rfind("}")
    if start != -1 and end > start:
        return json.loads(raw[start:end + 1])

    raise ValueError("JSON Parse Error")


# ==========================================================
# SYSTEM PROMPT
# ==========================================================

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
"""


# ==========================================================
# STORAGE
# ==========================================================

def _save_preferences(
    user_id: str,
    preferences: Dict[str, Any],
    weights: Dict[str, float],
    signals: Dict[str, Any]
):
    try:
        db = _get_db()
        user_id = str(user_id).strip()

        query = (
            {"_id": ObjectId(user_id)}
            if ObjectId.is_valid(user_id)
            else {"user_id": user_id}
        )

        signal_text = json.dumps({"weights": weights, "signals": signals})
        embedding_vector = _embed_text(signal_text)

        db[USERS_COLLECTION].update_one(
            query,
            {
                "$set": {
                    "embedding": embedding_vector,
                    "embedding_model": EMBED_MODEL_NAME,
                    "updated_at": datetime.now(timezone.utc),
                    "preferences": preferences,
                    "weights": weights,
                    "signals": signals
                }
            },
            upsert=True
        )

    except Exception as e:
        print(f"❌ DB Save Error: {e}")


# ==========================================================
# VALIDATION
# ==========================================================

def _validate_llm_output(data: Dict[str, Any]) -> bool:
    if not isinstance(data, dict):
        return False
    if data.get("action") not in ["ask", "stop"]:
        return False
    if data["action"] == "ask":
        schema = data.get("interpretation_schema", {})
        if "field" not in schema or "mapping" not in schema:
            return False
    if data["action"] == "stop":
        if "ranking_weights" not in data:
            return False
    return True


# ==========================================================
# MAIN AGENT (Non-blocking)
# ==========================================================

def user_preferences_agent(state: AgentState) -> AgentState:
    """
    Collects user preferences through A/B/C/D questions.
    Non-blocking: uses pending_question + user_input pattern.

    Internal state tracking:
      _pref_turn: current turn number
      _pref_signals: collected signals
      _pref_asked_fields: set of asked fields
      _pref_history: conversation history for LLM
      _pref_current_schema: current question schema (awaiting answer)
    """

    if state.get("user_preferences") is not None:
        return state

    user_input = state.get("user_input")

    # Initialize user ID
    if not state.get("user_id"):
        state["user_id"] = f"guest_{uuid.uuid4().hex}"

    # Initialize tracking state
    if "_pref_turn" not in state:
        state["_pref_turn"] = 0
        state["_pref_signals"] = {}
        state["_pref_asked_fields"] = []
        state["_pref_history"] = [
            f"SYSTEM:\n{_build_system_prompt({})}",
            "USER:\nBegin interview."
        ]

    # ── Process previous answer if there is one ──
    current_schema = state.get("_pref_current_schema")
    if user_input and current_schema:
        ans = user_input.strip().upper()
        field = current_schema.get("field")
        mapping = current_schema.get("mapping", {})

        if ans in mapping:
            signals = state.get("_pref_signals", {})
            signals[field] = {
                "raw_answer": ans,
                "normalized": mapping[ans]
            }
            state["_pref_signals"] = signals

            # Update history
            history = state.get("_pref_history", [])
            history.append(f"ASSISTANT:\n{json.dumps({'action': 'ask', 'interpretation_schema': current_schema})}")
            history.append(f"USER:\n{json.dumps({'answer': ans})}")
            state["_pref_history"] = history

        state["_pref_current_schema"] = None
        state["user_input"] = None

    # ── Check if we've hit the turn limit ──
    turn = state.get("_pref_turn", 0)
    if turn >= PREFS_MAX_TURNS:
        signals = state.get("_pref_signals", {})
        preferences = {
            "weights": {},
            "signals": signals,
            "turns": turn,
            "status": "limit_reached"
        }
        _save_preferences(state["user_id"], preferences, {}, signals)
        state["user_preferences"] = preferences
        state["next_step"] = "compound_ranking_agent"
        # Clean up internal state
        for k in ["_pref_turn", "_pref_signals", "_pref_asked_fields", "_pref_history", "_pref_current_schema"]:
            state.pop(k, None)
        return state

    # ── Ask next question ──
    state["_pref_turn"] = turn + 1
    history = state.get("_pref_history", [])

    raw = ask_ollama("\n\n".join(history))

    try:
        data = _safe_parse_json(raw)
    except Exception:
        history.append("SYSTEM:\nReturn valid JSON only.")
        state["_pref_history"] = history
        state["pending_question"] = "Let me rephrase... What kind of property environment do you prefer?"
        return state

    if not _validate_llm_output(data):
        history.append("SYSTEM:\nInvalid schema. Follow the defined format strictly.")
        state["_pref_history"] = history
        state["pending_question"] = "Let me try again... What features matter most to you in a property?"
        return state

    action = data["action"]

    if action == "ask":
        schema = data["interpretation_schema"]
        field = schema["field"]
        asked_fields = state.get("_pref_asked_fields", [])

        if field in asked_fields:
            history.append(f"SYSTEM:\nField '{field}' already asked. Ask about a different field.")
            state["_pref_history"] = history
            # Re-run this agent (will ask next question)
            return state

        asked_fields.append(field)
        state["_pref_asked_fields"] = asked_fields

        # Store schema for processing the answer
        state["_pref_current_schema"] = schema
        state["pending_question"] = data["question"]
        return state

    if action == "stop":
        signals = state.get("_pref_signals", {})

        if len(signals) < MIN_FEATURES_BEFORE_STOP:
            history.append(f"SYSTEM:\nYou must collect at least {MIN_FEATURES_BEFORE_STOP} features before stopping.")
            state["_pref_history"] = history
            return state

        weights = data.get("ranking_weights", {})
        preferences = {
            "weights": weights,
            "signals": signals,
            "turns": turn + 1,
            "status": "completed"
        }
        _save_preferences(state["user_id"], preferences, weights, signals)
        state["user_preferences"] = preferences
        state["next_step"] = "compound_ranking_agent"
        # Clean up internal state
        for k in ["_pref_turn", "_pref_signals", "_pref_asked_fields", "_pref_history", "_pref_current_schema"]:
            state.pop(k, None)
        return state

    return state