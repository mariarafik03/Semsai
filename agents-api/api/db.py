"""
api/db.py
─────────
Shared MongoDB helper for the API layer.

Provides a lightweight singleton connection to the same MongoDB instance
that the agents use, plus a helper to merge chat-session preferences
into the existing user document (created by user_preferences_agent).
"""

import os
import certifi
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

# ---------------------------------------------------------------------------
# Singleton connection (synchronous PyMongo — runs in threadpool via FastAPI)
# ---------------------------------------------------------------------------

_client: Optional[MongoClient] = None
_db = None

USERS_COLLECTION = "users"

# Fields from chat-state that get stored under chat_preferences in the user doc
_CHAT_PREF_FIELDS = (
    "budget",
    "location",
    "typeofproperty",
    "payment_type",
    "purpose",
    "Downpayment",
    "monthlyinstall",
    "years",
)


def _get_db():
    """Return (and lazily create) the shared synchronous MongoDB client."""
    global _client, _db
    if _db is not None:
        return _db

    uri = os.getenv("MONGO_URI")
    if not uri:
        raise ValueError("MONGO_URI not set in environment variables.")

    _client = MongoClient(
        uri,
        tls=True,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=60_000,
    )
    _db = _client.get_default_database()
    return _db


def update_user_chat_preferences(user_id: str, state: dict) -> None:
    """
    Merge the chat-session preferences from *state* into the existing
    MongoDB user document as a ``chat_preferences`` sub-document.

    This does NOT overwrite the embedding, weights, signals, or any other
    field written by user_preferences_agent — it only adds / updates the
    ``chat_preferences`` key.

    Skips None values so we never erase a previously saved preference.

    Lookup strategy (same as the rest of the codebase):
      • If user_id is a valid ObjectId  →  query by ``_id``
      • Otherwise                        →  query by ``user_id`` field
    """
    try:
        db = _get_db()
        uid = str(user_id).strip()

        query = (
            {"_id": ObjectId(uid)}
            if ObjectId.is_valid(uid)
            else {"user_id": uid}
        )

        # Build update payload — only non-None fields
        chat_prefs = {
            field: state[field]
            for field in _CHAT_PREF_FIELDS
            if state.get(field) is not None
        }

        if not chat_prefs:
            print("⚠️  update_user_chat_preferences: nothing to save (all fields None)")
            return

        db[USERS_COLLECTION].update_one(
            query,
            {
                "$set": {
                    "chat_preferences":          chat_prefs,
                    "chat_preferences_updated_at": datetime.now(timezone.utc),
                }
            },
            # upsert=False: we only update — the user doc must already exist
            # (created by user_preferences_agent during the same session)
            upsert=False,
        )
        print(f"✅ chat_preferences saved to MongoDB for user {uid}: {list(chat_prefs.keys())}")

    except Exception as exc:
        # Never crash the API response because of a DB write failure
        print(f"❌ update_user_chat_preferences error: {exc}")


# ---------------------------------------------------------------------------
# Episodic Memory helpers
# ---------------------------------------------------------------------------

def save_episode(user_id: str, summary: dict) -> None:
    """
    Append one episode (including candidate_units) into the user's
    episodic_memory array inside the users collection.
    Caps the array at 10 episodes (oldest dropped).
    Never creates a new user document.
    """
    db = _get_db()
    uid = str(user_id).strip()

    # Resolve query — try ObjectId first, fall back to string _id
    query = (
        {"_id": ObjectId(uid)}
        if ObjectId.is_valid(uid)
        else {"_id": uid}
    )

    try:
        db[USERS_COLLECTION].update_one(
            query,
            {
                "$push": {
                    "episodic_memory": {
                        "$each": [summary],
                        "$slice": -10,
                    }
                },
                "$set": {"updatedAt": summary.get("created_at")},
            },
            upsert=False,
        )
    except Exception as exc:
        print(f"❌ save_episode error for user {uid}: {exc}")
        raise


def load_episodes(user_id: str, limit: int = 3) -> list:
    """
    Return the `limit` most recent episodes from the user's episodic_memory
    array, newest first. Returns [] if user not found or array is empty.
    """
    db = _get_db()
    uid = str(user_id).strip()

    query = (
        {"_id": ObjectId(uid)}
        if ObjectId.is_valid(uid)
        else {"_id": uid}
    )

    try:
        user = db[USERS_COLLECTION].find_one(
            query,
            {"episodic_memory": {"$slice": -limit}},
        )
    except Exception as exc:
        print(f"❌ load_episodes error for user {uid}: {exc}")
        return []

    if not user or "episodic_memory" not in user:
        return []

    episodes = user["episodic_memory"]
    # Reverse so newest is first; stringify any ObjectId values
    cleaned = []
    for ep in reversed(episodes):
        cleaned.append(
            {
                k: str(v) if type(v).__name__ == "ObjectId" else v
                for k, v in ep.items()
            }
        )
    return cleaned


# Create index once at module import time (idempotent)
try:
    _get_db()[USERS_COLLECTION].create_index(
        [("episodic_memory.session_id", 1)],
        background=True,
    )
except Exception as _idx_exc:
    print(f"⚠️ Could not create episodic_memory index: {_idx_exc}")
