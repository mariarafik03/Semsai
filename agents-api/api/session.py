"""
Session manager — stores per-user graph state in Redis.

Key format :  session:{session_id}
TTL         :  24 hours (configurable via SESSION_TTL_SECONDS)
Serialization: JSON  (all state values must be JSON-serialisable)
"""

import json
import uuid
import os
import redis.asyncio as aioredis
from typing import Optional

# ---------------------------------------------------------------------------
# Config  (override via environment variables)
# ---------------------------------------------------------------------------
REDIS_URL          = os.getenv("REDIS_URL", "redis://localhost:6379")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", 86400))   # 24 h
KEY_PREFIX         = "session:"

# ---------------------------------------------------------------------------
# Connection pool  (created once at import time)
# ---------------------------------------------------------------------------
_redis: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """Return (and lazily create) the shared async Redis client."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
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
    r = await get_redis()
    raw = await r.get(f"{KEY_PREFIX}{session_id}")
    if raw is None:
        return None
    return json.loads(raw)


async def save_state(session_id: str, state: dict) -> None:
    """
    Persist state dict to Redis with TTL refresh.
    Any non-serialisable value is converted to str as a fallback.
    """
    r = await get_redis()
    await r.setex(
        f"{KEY_PREFIX}{session_id}",
        SESSION_TTL_SECONDS,
        json.dumps(state, default=str),
    )


async def delete_session(session_id: str) -> None:
    """Remove a session from Redis (e.g. on explicit reset)."""
    r = await get_redis()
    await r.delete(f"{KEY_PREFIX}{session_id}")
