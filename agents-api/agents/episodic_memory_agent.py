"""
agents/episodic_memory_agent.py
────────────────────────────────
Write-only side-effect agent that persists a short summary of the
completed session to MongoDB so future sessions can recall it.

This agent runs ONCE at the very end of a session, after
final_output_agent has set final_best_compound.  It is a no-op on
every other invocation.

State contract
──────────────
• Reads  : state.final_best_compound, state.context.*, state.user_id,
           state.metadata.session_id, state.episode_saved
• Writes : state.episode_saved = True  (prevents double-write)
• Never raises — all exceptions are caught and printed.
"""

from datetime import datetime, timezone
from state import AgentState
from api.db import save_episode


def episodic_memory_agent(state: AgentState) -> AgentState:
    """
    Persist a session summary to episodic_memory if the session is done.
    Returns state unchanged (episode_saved flag is the only mutation).
    """

    print("\n--- Episodic Memory Agent ---")

    # ── Guard: only run when the session is complete ──────────────────────
    final_compound = (
        state.context.final_best_compound
        or getattr(state, "final_best_compound", None)
    )
    if not final_compound:
        print("ℹ️  Session not complete yet — skipping episodic save")
        return state

    # ── Guard: prevent double-write within the same session ───────────────
    if getattr(state, "episode_saved", False):
        print("ℹ️  Episode already saved — skipping")
        return state

    # ── Build summary ─────────────────────────────────────────────────────
    ctx = state.context
    user_id = str(getattr(state, "user_id", "") or "")
    session_id = str(
        getattr(state.metadata, "session_id", None) or ""
    )

    best_compound_name = (
        final_compound.get("compound_name")
        or final_compound.get("name")
        or final_compound.get("compound")
        or "Unknown"
    )

    units_found = len(ctx.candidate_units) if ctx.candidate_units else 0

    summary = {
        "session_id":        session_id,
        "created_at":        datetime.now(timezone.utc).isoformat(),
        "location":          ctx.location or "",
        "property_type":     ctx.property_type or "",
        "payment_type":      ctx.payment_type or "",
        "budget":            ctx.budget,
        "best_compound_name": best_compound_name,
        "units_found":       units_found,
    }

    save_episode(user_id, summary)
    print(f"✅ Episode saved for user {user_id}")

    # ── Mark as done so router doesn't re-run this node ───────────────────
    state.episode_saved = True
    return state
