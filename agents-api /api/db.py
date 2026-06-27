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
from pymongo import MongoClient, ASCENDING

load_dotenv()

# ---------------------------------------------------------------------------
# Singleton connection (synchronous PyMongo — runs in threadpool via FastAPI)
# ---------------------------------------------------------------------------

_client: Optional[MongoClient] = None
_db = None

USERS_COLLECTION    = "users"
EPISODES_COLLECTION = "episodic_memory"   # dedicated collection

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


def _resolve_user_query(uid: str) -> dict:
    """
    Return the right MongoDB query dict to look up a user.

    • Valid ObjectId string  →  {"_id": ObjectId(uid)}
    • Anything else          →  {"user_id": uid}
    """
    return (
        {"_id": ObjectId(uid)}
        if ObjectId.is_valid(uid)
        else {"user_id": uid}
    )


def update_user_chat_preferences(user_id: str, state: dict) -> None:
    """
    Merge the chat-session preferences from *state* into the existing
    MongoDB user document as a ``chat_preferences`` sub-document.

    This does NOT overwrite the embedding, weights, signals, or any other
    field written by user_preferences_agent — it only adds / updates the
    ``chat_preferences`` key.

    Skips None values so we never erase a previously saved preference.
    """
    try:
        db  = _get_db()
        uid = str(user_id).strip()

        # Build update payload — only non-None fields
        chat_prefs = {
            field: state[field]
            for field in _CHAT_PREF_FIELDS
            if state.get(field) is not None
        }

        if not chat_prefs:
            print("⚠️  update_user_chat_preferences: nothing to save (all fields None)")
            return

        result = db[USERS_COLLECTION].update_one(
            _resolve_user_query(uid),
            {
                "$set": {
                    "chat_preferences":             chat_prefs,
                    "chat_preferences_updated_at":  datetime.now(timezone.utc),
                }
            },
            upsert=False,
        )
        if result.matched_count == 0:
            print(
                f"⚠️  update_user_chat_preferences: no user doc found for uid={uid!r}. "
                "chat_preferences NOT saved. Check that user_preferences_agent ran and "
                "created the user doc before the session ended."
            )
        else:
            print(
                f"✅ chat_preferences saved to MongoDB for user {uid}: "
                f"{list(chat_prefs.keys())}"
            )

    except Exception as exc:
        # Never crash the API response because of a DB write failure
        print(f"❌ update_user_chat_preferences error: {exc}")


# ---------------------------------------------------------------------------
# Episodic Memory helpers  —  dedicated `episodic_memory` collection
#
# Schema of each document:
# {
#   "_id":          ObjectId,           ← auto
#   "user_id":      str,                ← links back to users collection
#   "session_id":   str,
#   "created_at":   ISO-8601 str,
#   "location":     str | None,
#   "property_type":str | None,
#   "payment_type": str | None,
#   "budget":       any | None,
#   "best_compound_name": str,
#   "units_found":  int,
#   "candidate_units": [ ... ],
# }
# ---------------------------------------------------------------------------

def save_episode(user_id: str, summary: dict) -> None:
    """
    Insert one episode document into the ``episodic_memory`` collection,
    linked to the user via ``user_id``.

    Caps stored episodes per user at 10 (oldest deleted automatically).
    Never creates or modifies a user document.
    """
    db  = _get_db()
    uid = str(user_id).strip()
    col = db[EPISODES_COLLECTION]

    # Attach the user_id so every episode document is self-describing
    episode_doc = {**summary, "user_id": uid}

    try:
        col.insert_one(episode_doc)
        inserted_id = str(episode_doc.get("_id", ""))
        print(
            f"✅ save_episode: episode inserted into '{EPISODES_COLLECTION}' "
            f"for user={uid!r}  _id={inserted_id}"
        )

        # Enforce per-user cap of 10 episodes — delete oldest beyond the limit
        all_ids = list(
            col.find({"user_id": uid}, {"_id": 1})
               .sort("created_at", ASCENDING)
        )
        overflow = len(all_ids) - 10
        if overflow > 0:
            ids_to_delete = [doc["_id"] for doc in all_ids[:overflow]]
            col.delete_many({"_id": {"$in": ids_to_delete}})
            print(f"🗑️  Trimmed {overflow} old episode(s) for user={uid!r}")

    except Exception as exc:
        print(f"❌ save_episode error for user {uid}: {exc}")
        raise


def load_episodes(user_id: str, limit: int = 3) -> list:
    """
    Return the ``limit`` most recent episodes from the ``episodic_memory``
    collection for the given user, newest first.
    Returns [] if none found.
    """
    db  = _get_db()
    uid = str(user_id).strip()
    col = db[EPISODES_COLLECTION]

    try:
        cursor = (
            col.find({"user_id": uid})
               .sort("created_at", -1)   # newest first
               .limit(limit)
        )
        episodes = list(cursor)
    except Exception as exc:
        print(f"❌ load_episodes error for user {uid}: {exc}")
        return []

    # Stringify ObjectIds so the result is always JSON-safe
    cleaned = []
    for ep in episodes:
        cleaned.append(
            {
                k: str(v) if type(v).__name__ == "ObjectId" else v
                for k, v in ep.items()
            }
        )
    return cleaned


# ---------------------------------------------------------------------------
# Indexes — created once at module import (idempotent)
# ---------------------------------------------------------------------------
try:
    db = _get_db()
    db[EPISODES_COLLECTION].create_index(
        [("user_id", ASCENDING), ("created_at", ASCENDING)],
        background=True,
        name="user_id_created_at",
    )
    db[EPISODES_COLLECTION].create_index(
        [("session_id", ASCENDING)],
        background=True,
        name="session_id",
    )
    print("✅ episodic_memory indexes ensured")
except Exception as _idx_exc:
    print(f"⚠️ Could not create episodic_memory indexes: {_idx_exc}")