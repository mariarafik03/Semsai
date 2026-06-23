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
# Episodic memory
# ---------------------------------------------------------------------------

EPISODIC_COLLECTION = "episodic_memory"

# Ensure the compound index exists once per process lifetime.
_episodic_index_created = False


def _ensure_episodic_index() -> None:
    """Create the compound index on episodic_memory if it doesn't exist yet."""
    global _episodic_index_created
    if _episodic_index_created:
        return
    try:
        from pymongo import DESCENDING
        db = _get_db()
        db[EPISODIC_COLLECTION].create_index(
            [("user_id", 1), ("created_at", DESCENDING)],
            background=True,
        )
        _episodic_index_created = True
    except Exception as exc:
        print(f"⚠️ episodic_memory index creation failed (non-fatal): {exc}")


def save_episode(user_id: str, summary: dict) -> None:
    """
    Insert one episode document into the episodic_memory collection.

    Expected summary keys:
        location, property_type, payment_type, budget,
        best_compound_name, units_found, session_id, created_at
    """
    try:
        _ensure_episodic_index()
        db = _get_db()
        db[EPISODIC_COLLECTION].insert_one({"user_id": str(user_id), **summary})
    except Exception as exc:
        print(f"❌ save_episode error for user {user_id}: {exc}")


def load_episodes(user_id: str, limit: int = 3) -> list:
    """
    Return up to *limit* most recent episode documents for *user_id*,
    newest first.  Returns [] if none found or on any error.

    ObjectId fields are converted to strings so callers receive plain dicts.
    """
    try:
        _ensure_episodic_index()
        db = _get_db()
        from pymongo import DESCENDING
        cursor = (
            db[EPISODIC_COLLECTION]
            .find({"user_id": str(user_id)}, {"_id": 0})
            .sort("created_at", DESCENDING)
            .limit(limit)
        )
        return list(cursor)
    except Exception as exc:
        print(f"❌ load_episodes error for user {user_id}: {exc}")
        return []
