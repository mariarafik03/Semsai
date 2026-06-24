"""
agents/episodic_memory_agent.py
────────────────────────────────
Write-only side-effect agent.

Runs at the end of a completed session (when final_best_compound is set).
Appends a structured episode summary — including candidate_units — to the
user's ``episodic_memory`` array in the ``users`` MongoDB collection.

Rules
─────
- Never raises: all DB errors are caught and logged.
- Always returns state unchanged (except setting episode_saved = True).
- Only acts when final_best_compound is truthy and episode_saved is False.
"""

from datetime import datetime
from api.db import save_episode


def episodic_memory_agent(state) -> object:
    """
    Append a session summary to the user's episodic_memory in MongoDB.

    Parameters
    ----------
    state : AgentState or dict
        Current session state (handled both ways for robustness).

    Returns
    -------
    state (unchanged except episode_saved = True)
    """
    # ── State access helpers (dict or Pydantic) ──────────────────────────────
    def _get(key, default=None):
        if isinstance(state, dict):
            return state.get(key, default)
        return getattr(state, key, default)

    def _set(key, value):
        if isinstance(state, dict):
            state[key] = value
        else:
            setattr(state, key, value)

    # ── Guard: only run once, and only when session is complete ───────────────
    if not _get("final_best_compound"):
        return state
    if _get("episode_saved"):
        return state

    user_id = _get("user_id", "")
    session_id = _get("session_id", "")

    if not user_id:
        print(f"⚠️  episodic_memory_agent: user_id is empty — episode cannot be saved. "
              "Make sure user_id is passed in the initial /chat request.")
        _set("episode_saved", True)   # prevent retry loops
        return state

    # ── Context access (object-style or dict-style) ───────────────────────────
    ctx = _get("context", {})

    def _ctx_get(key):
        if isinstance(ctx, dict):
            return ctx.get(key)
        return getattr(ctx, key, None)

    raw_units = _ctx_get("candidate_units") or []
    units_serialized = [
        u if isinstance(u, dict) else vars(u)
        for u in raw_units
    ]

    final_bc = _get("final_best_compound") or {}
    best_name = (
        final_bc.get("name")
        or final_bc.get("compound_name")
        or "unknown"
    ) if isinstance(final_bc, dict) else "unknown"

    summary = {
        "session_id":         session_id,
        "created_at":         datetime.utcnow().isoformat() + "Z",
        "location":           _ctx_get("location"),
        "property_type":      _ctx_get("property_type"),
        "payment_type":       _ctx_get("payment_type"),
        "budget":             _ctx_get("budget"),
        "best_compound_name": best_name,
        "units_found":        len(units_serialized),
        "candidate_units":    units_serialized,
    }

    try:
        save_episode(user_id, summary)
        print(f"✅ Episode saved for user {user_id} (session {session_id})")
    except Exception as exc:
        print(f"⚠️ Episode save failed for user {user_id}: {exc}")

    _set("episode_saved", True)
    return state