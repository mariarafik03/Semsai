"""
state_manager.py — Redis-based state persistence with Pydantic support.

ARCHITECTURE
────────────
1. Uses Pydantic models (from state.py) for type safety
2. Serializes to JSON for Redis storage
3. Handles migration from old dict-based state
4. Automatic state validation on load

USAGE
─────
# Saving state
await save_state(session_id, state)

# Loading state
state = await load_state(session_id)

# Checking existence
exists = await state_exists(session_id)

# Cleanup
await delete_state(session_id)
"""

import json
import redis.asyncio as redis
from typing import Optional, Union
from datetime import datetime

# Import our Pydantic models
from state import (
    AgentState,
    make_initial_state,
    state_to_dict,
    dict_to_state
)

# ═══════════════════════════════════════════════════════════════════════════
# REDIS CONNECTION
# ═══════════════════════════════════════════════════════════════════════════

# Global Redis client (initialized by API startup)
_redis_client: Optional[redis.Redis] = None


def init_redis(host: str = "localhost", port: int = 6379, db: int = 0): #called in the main 
    """
    Initialize Redis connection.
    
    Call this once at API startup.
    
    Example:
        init_redis("localhost", 6379, 0)
    """
    global _redis_client
    _redis_client = redis.Redis(
        host=host,
        port=port,
        db=db,
        decode_responses=True,  # Auto-decode bytes to str
        socket_connect_timeout=5,
        socket_timeout=5
    )


def get_redis() -> redis.Redis:
    """
    Get the Redis client instance.
    
    Raises:
        RuntimeError: If Redis not initialized
    """
    if _redis_client is None:
        raise RuntimeError(
            "Redis not initialized. Call init_redis() first."
        )
    return _redis_client


# ═══════════════════════════════════════════════════════════════════════════
# STATE KEY MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

def _make_state_key(session_id: str) -> str:
    """
    Generate Redis key for a session's state.
    
    Format: "session:{session_id}:state"
    """
    return f"session:{session_id}:state"


# ═══════════════════════════════════════════════════════════════════════════
# STATE PERSISTENCE
# ═══════════════════════════════════════════════════════════════════════════

async def save_state(
    session_id: str,
    state: Union[AgentState, dict],
    ttl: int = 86400  # 24 hours default
) -> bool:
    """
    Save state to Redis.
    
    Parameters
    ----------
    session_id : str
        Unique session identifier
    state : AgentState or dict
        State to save (Pydantic model or dict)
    ttl : int
        Time-to-live in seconds (default 24 hours)
    
    Returns
    -------
    bool
        True if saved successfully
    
    Example
    -------
    >>> state = make_initial_state("session_123")
    >>> await save_state("session_123", state)
    True
    """
    try:
        redis_client = get_redis()
        key = _make_state_key(session_id)
        
        # Convert Pydantic model to dict if needed
        if isinstance(state, AgentState):
            state_dict = state_to_dict(state)
        else:
            state_dict = state
        
        # Update timestamp
        state_dict.setdefault("metadata", {})
        state_dict["metadata"]["last_updated_at"] = datetime.utcnow().isoformat()
        
        # Serialize to JSON
        state_json = json.dumps(state_dict, ensure_ascii=False)
        
        # Save to Redis with TTL
        await redis_client.setex(key, ttl, state_json)
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to save state for {session_id}: {e}")
        return False


async def load_state(session_id: str) -> AgentState:
    """
    Load state from Redis.
    
    If state doesn't exist, returns a fresh initial state.
    
    Parameters
    ----------
    session_id : str
        Unique session identifier
    
    Returns
    -------
    AgentState
        Loaded state (or fresh state if not found)
    
    Example
    -------
    >>> state = await load_state("session_123")
    >>> print(state.context.location)
    None
    """
    try:
        redis_client = get_redis()
        key = _make_state_key(session_id)
        
        # Try to load from Redis
        state_json = await redis_client.get(key)
        
        if not state_json:
            # No state found → create fresh one
            print(f"ℹ️  No state found for {session_id}, creating fresh state")
            return make_initial_state(session_id)
        
        # Deserialize JSON
        state_dict = json.loads(state_json)
        
        # Convert to Pydantic model
        # This validates all fields automatically
        state = dict_to_state(state_dict)
        
        return state
        
    except json.JSONDecodeError as e:
        print(f"⚠️  Corrupted state for {session_id}: {e}")
        print("   Creating fresh state...")
        return make_initial_state(session_id)
        
    except Exception as e:
        print(f"❌ Error loading state for {session_id}: {e}")
        print("   Creating fresh state...")
        return make_initial_state(session_id)


async def state_exists(session_id: str) -> bool:
    """
    Check if state exists in Redis.
    
    Parameters
    ----------
    session_id : str
        Unique session identifier
    
    Returns
    -------
    bool
        True if state exists
    """
    try:
        redis_client = get_redis()
        key = _make_state_key(session_id)
        return await redis_client.exists(key) > 0
    except Exception as e:
        print(f"❌ Error checking state existence for {session_id}: {e}")
        return False


async def delete_state(session_id: str) -> bool:
    """
    Delete state from Redis.
    
    Use this when user explicitly resets conversation.
    
    Parameters
    ----------
    session_id : str
        Unique session identifier
    
    Returns
    -------
    bool
        True if deleted successfully
    """
    try:
        redis_client = get_redis()
        key = _make_state_key(session_id)
        deleted = await redis_client.delete(key)
        return deleted > 0
    except Exception as e:
        print(f"❌ Error deleting state for {session_id}: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════
# MIGRATION HELPERS (Temporary - Remove in Phase 3)
# ═══════════════════════════════════════════════════════════════════════════

async def migrate_old_state(session_id: str) -> bool:
    """
    Convert old dict-based state to new Pydantic structure.
    
    Only needed if you have existing sessions in Redis.
    
    Returns
    -------
    bool
        True if migration successful
    """
    try:
        redis_client = get_redis()
        key = _make_state_key(session_id)
        
        # Load raw state
        state_json = await redis_client.get(key)
        if not state_json:
            return False
        
        old_state = json.loads(state_json)
        
        # Check if already migrated
        if "context" in old_state and isinstance(old_state["context"], dict):
            print(f"ℹ️  State {session_id} already migrated")
            return True
        
        # Create new state with migrated data
        new_state = make_initial_state(session_id)
        
        # Copy legacy fields to context
        new_state.context.location = old_state.get("location")
        new_state.context.property_type = old_state.get("typeofproperty")
        new_state.context.payment_type = old_state.get("payment_type")
        new_state.context.budget = old_state.get("budget")
        new_state.context.downpayment = old_state.get("Downpayment")
        new_state.context.monthly_installment = old_state.get("monthlyinstall")
        new_state.context.budget_valid = old_state.get("budget_valid", False)
        
        # Sync to legacy fields (for backward compatibility)
        new_state.sync_to_legacy()
        
        # Copy other important fields
        new_state.waiting_for = old_state.get("waiting_for")
        new_state.agent_message = old_state.get("agent_message")
        new_state.candidate_compounds = old_state.get("candidate_compounds", [])
        new_state.final_compounds = old_state.get("final_compounds", [])
        # ... copy other fields as needed
        
        # Save migrated state
        await save_state(session_id, new_state)
        
        print(f"✅ Migrated state for {session_id}")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed for {session_id}: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════
# BATCH OPERATIONS (For analytics/debugging)
# ═══════════════════════════════════════════════════════════════════════════

async def get_all_session_ids() -> list[str]:
    """
    Get all active session IDs from Redis.
    
    Useful for debugging or analytics.
    
    Returns
    -------
    list[str]
        List of session IDs
    """
    try:
        redis_client = get_redis()
        keys = await redis_client.keys("session:*:state")
        # Extract session_id from key format: session:{id}:state
        return [key.split(":")[1] for key in keys]
    except Exception as e:
        print(f"❌ Error getting session IDs: {e}")
        return []


async def cleanup_expired_states(dry_run: bool = True) -> int:
    """
    Remove states that haven't been updated in 7+ days.
    
    Parameters
    ----------
    dry_run : bool
        If True, only count without deleting
    
    Returns
    -------
    int
        Number of states cleaned up
    """
    try:
        session_ids = await get_all_session_ids()
        cleaned = 0
        cutoff = datetime.utcnow().timestamp() - (7 * 86400)  # 7 days ago
        
        for session_id in session_ids:
            state = await load_state(session_id)
            
            if state.metadata.last_updated_at:
                last_update = datetime.fromisoformat(state.metadata.last_updated_at)
                if last_update.timestamp() < cutoff:
                    print(f"  Stale: {session_id} (last update: {last_update})")
                    if not dry_run:
                        await delete_state(session_id)
                    cleaned += 1
        
        return cleaned
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        return 0


# ═══════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════

async def health_check() -> dict:
    """
    Check Redis connection health.
    
    Returns
    -------
    dict
        Status info
    """
    try:
        redis_client = get_redis()
        await redis_client.ping()
        
        # Get stats
        session_count = len(await get_all_session_ids())
        
        return {
            "status": "healthy",
            "active_sessions": session_count,
            "redis_connected": True
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "redis_connected": False
        }