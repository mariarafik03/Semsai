"""
Session manager — stores per-user graph state in Redis.

Key format :  session:{session_id}
TTL         :  24 hours (configurable via SESSION_TTL_SECONDS)
Serialization: JSON  (all state values must be JSON-serialisable)
"""

import json
import uuid
import os
import time
from typing import Optional, Any

try:
    import redis.asyncio as aioredis  # type: ignore[import-not-found]
except Exception:
    aioredis = None

# ---------------------------------------------------------------------------
# Config  (override via environment variables)
# ---------------------------------------------------------------------------
REDIS_URL          = os.getenv("REDIS_URL", "redis://localhost:6379")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", 86400))   # 24 h
KEY_PREFIX         = "session:"
SESSION_BACKEND    = os.getenv("SESSION_BACKEND", "auto").lower()

# ---------------------------------------------------------------------------
# Connection pool  (created once at import time)
# ---------------------------------------------------------------------------
_redis: Optional[Any] = None
_redis_unavailable: bool = False

# In-memory fallback store: key -> (expiry_ts, json_payload)
_memory_store: dict[str, tuple[float, str]] = {}


def _memory_key(session_id: str) -> str:
    return f"{KEY_PREFIX}{session_id}"


def _cleanup_memory() -> None:
    now = time.time()
    stale = [k for k, (exp, _) in _memory_store.items() if exp <= now]
    for k in stale:
        _memory_store.pop(k, None)


def _use_memory_backend() -> bool:
    if SESSION_BACKEND == "memory":
        return True
    if SESSION_BACKEND == "redis":
        return False
    # auto mode
    if aioredis is None:
        return True
    if not REDIS_URL:
        return True
    return False


async def get_redis() -> Optional[Any]:
    """Return shared Redis client when available, else None."""
    global _redis
    global _redis_unavailable

    if _use_memory_backend() or _redis_unavailable:
        return None

    if _redis is None:
        try:
            _redis = aioredis.from_url(
                REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
            await _redis.ping()
        except Exception:
            _redis_unavailable = True
            _redis = None
            return None

    return _redis


async def close_redis() -> None:
    """Close the Redis connection (call on app shutdown)."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def new_session_id() -> str:
    """Generate a fresh UUID-4 session identifier."""
    return str(uuid.uuid4())


async def load_state(session_id: str) -> Optional[dict]:
    """
    Load state dict from Redis.
    Returns None if the session does not exist.
    """
    _cleanup_memory()
    key = _memory_key(session_id)

    r = await get_redis()
    if r is not None:
        try:
            raw = await r.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            # Fail open to memory fallback
            pass

    item = _memory_store.get(key)
    if not item:
        return None

    exp, payload = item
    if exp <= time.time():
        _memory_store.pop(key, None)
        return None

    return json.loads(payload)


async def save_state(session_id: str, state: dict) -> None:
    """
    Persist state dict to Redis with TTL refresh.
    Any non-serialisable value is converted to str as a fallback.
    """
    payload = json.dumps(state, default=str)
    key = _memory_key(session_id)

    r = await get_redis()
    if r is not None:
        try:
            await r.setex(key, SESSION_TTL_SECONDS, payload)
            return
        except Exception:
            # Fall back to memory storage
            pass

    _cleanup_memory()
    _memory_store[key] = (time.time() + SESSION_TTL_SECONDS, payload)


async def delete_session(session_id: str) -> None:
    """Remove a session from Redis (e.g. on explicit reset)."""
    key = _memory_key(session_id)
    r = await get_redis()
    if r is not None:
        try:
            await r.delete(key)
        except Exception:
            pass
    _memory_store.pop(key, None)

# ---------------------------------------------------------------------------
# Long-term Memory Helpers (Profiles & History)
# ---------------------------------------------------------------------------

async def load_profile(user_id: str) -> dict:
    """Load long-term user preferences."""
    key = f"profile:{user_id}"
    r = await get_redis()
    if r is not None:
        try:
            raw = await r.get(key)
            if raw: return json.loads(raw)
        except Exception:
            pass
            
    item = _memory_store.get(key)
    if item:
        _, payload = item
        return json.loads(payload)
    return {}

async def save_profile(user_id: str, state: dict) -> None:
    """Save long-term user preferences, filtering for core fields."""
    pref_keys = [
        "purpose", "budget", "location", "typeofproperty", 
        "payment_type", "Downpayment", "monthlyinstall", "years"
    ]
    prefs = {k: v for k, v in state.items() if k in pref_keys and v is not None}
    
    if not prefs:
        return
        
    # Merge with existing profile if one exists
    existing = await load_profile(user_id)
    existing.update(prefs)
    
    payload = json.dumps(existing, default=str)
    key = f"profile:{user_id}"
    
    r = await get_redis()
    if r is not None:
        try:
            await r.set(key, payload) # Long term, TTL = unlimited
            return
        except Exception:
            pass
            
    _memory_store[key] = (float('inf'), payload)

async def append_history(user_id: str, session_id: str, summary: dict) -> None:
    """Append a session summary to the user's history log."""
    key = f"history:{user_id}"
    summary["session_id"] = session_id
    payload = json.dumps(summary, default=str)
    
    r = await get_redis()
    if r is not None:
        try:
            await r.rpush(key, payload)
            return
        except Exception:
            pass
            
    item = _memory_store.get(key)
    history = json.loads(item[1]) if item else []
    history.append(summary)
    _memory_store[key] = (float('inf'), json.dumps(history))

async def load_history(user_id: str) -> list:
    """Load all past session summaries for a user."""
    key = f"history:{user_id}"
    
    r = await get_redis()
    if r is not None:
        try:
            raw_list = await r.lrange(key, 0, -1)
            return [json.loads(raw) for raw in raw_list]
        except Exception:
            pass
            
    item = _memory_store.get(key)
    if item:
        return json.loads(item[1])
    return []
