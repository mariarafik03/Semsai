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

        print("✅ Preferences stored in DB")

    except Exception as e:
        print(f"❌ DB Save Error: {e}")


# ==========================================================
# VALIDATION HELPERS
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
# MAIN AGENT
# ==========================================================

def user_preferences_agent(state: AgentState) -> AgentState:

    if state.get("user_preferences") is not None:
        return state

    print("\n--- User Preferences Agent ---")

    entered_uid = input("Enter Document ID (or press Enter for guest): ").strip()
    session_user_id = entered_uid if entered_uid else f"guest_{uuid.uuid4().hex}"
    state["user_id"]=entered_uid

    normalized_signals = {}
    asked_fields = set()

    system_prompt = _build_system_prompt({})
    history = [
        f"SYSTEM:\n{system_prompt}",
        "USER:\nBegin interview."
    ]

    for turn in range(1, PREFS_MAX_TURNS + 1):

        raw = ask_ollama("\n\n".join(history))

        try:
            data = _safe_parse_json(raw)
        except Exception:
            print("⚠️ Invalid JSON from model.")
            history.append("SYSTEM:\nReturn valid JSON only.")
            continue

        if not _validate_llm_output(data):
            print("⚠️ Invalid schema from model.")
            history.append("SYSTEM:\nInvalid schema. Follow the defined format strictly.")
            continue

        action = data["action"]

        # ==================================================
        # ASK
        # ==================================================
        if action == "ask":

            schema = data["interpretation_schema"]
            field = schema["field"]

            if field in asked_fields:
                history.append(
                    f"SYSTEM:\nField '{field}' already asked. Ask about a different field."
                )
                continue

            asked_fields.add(field)

            print(f"\nAgent: {data['question']}")
            ans = input("You (A/B/C/D): ").strip().upper()

            mapping = schema["mapping"]

            if ans not in mapping:
                print("❌ Invalid choice. Please answer using A, B, C, or D.")
                asked_fields.remove(field)
                continue

            normalized_signals[field] = {
                "raw_answer": ans,
                "normalized": mapping[ans]
            }

            history.append(f"ASSISTANT:\n{json.dumps(data)}")
            history.append(f"USER:\n{json.dumps({'answer': ans})}")

            continue

        # ==================================================
        # STOP
        # ==================================================
        if action == "stop":

            if len(normalized_signals) < MIN_FEATURES_BEFORE_STOP:
                history.append(
                    f"SYSTEM:\nYou must collect at least {MIN_FEATURES_BEFORE_STOP} features before stopping."
                )
                continue

            weights = data.get("ranking_weights", {})

            preferences = {
                "weights": weights,
                "signals": normalized_signals,
                "turns": turn,
                "status": "completed"
            }

            _save_preferences(
                session_user_id,
                preferences,
                weights,
                normalized_signals
            )

            state["user_preferences"] = preferences
            state["next_step"] = "compound_ranking_agent"

            return state

    # ======================================================
    # LIMIT REACHED
    # ======================================================

    final_preferences = {
        "weights": {},
        "signals": normalized_signals,
        "turns": PREFS_MAX_TURNS,
        "status": "limit_reached"
    }

    _save_preferences(
        session_user_id,
        final_preferences,
        {},
        normalized_signals
    )

    state["user_preferences"] = final_preferences
    state["next_step"] = "compound_ranking_agent"

    print(f"\n✅ Session finalized after {PREFS_MAX_TURNS} turns.")
    return state