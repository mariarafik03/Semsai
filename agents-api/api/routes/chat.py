"""
api/routes/chat.py — Single /chat endpoint for the entire conversation.

Flow (every turn)
─────────────────
POST /chat  { session_id?, message, user_id? }
  1. No session_id  → create session, run first turn (extraction/greeting)
     Has session_id → load state from Redis, validate it exists
  2. Run one graph turn with the user's message
  3. Save updated state back to Redis
  4. Return the assistant's reply + phase + done flag
  5. When done=True, include final property results
"""

import traceback
import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException

from api.models import ChatRequest, ChatResponse
from api.session import load_state, save_state, new_session_id
from api.db import update_user_chat_preferences
from graph_runner import run_graph_turn, make_initial_state
from graph_definition import graph

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _phase(state: dict) -> str:
    """Derive a human-readable phase label from state."""
    ctx = state.get("context") or {}
    if state.get("final_best_compound") or ctx.get("final_best_compound"):
        return "complete"
    if state.get("waiting_for"):
        return "asking"
    return state.get("current_phase") or state.get("graph_current_node") or "processing"


def _results(state: dict) -> dict:
    """Extract final property recommendation payload from state."""
    ctx = state.get("context") or {}
    best  = state.get("final_best_compound") or ctx.get("final_best_compound")
    units = state.get("candidate_units")    or ctx.get("candidate_units") or []

    # Stringify ObjectIds so the payload is always JSON-safe
    safe_units = []
    for u in (units[:20] if isinstance(units, list) else []):
        if isinstance(u, dict):
            safe_units.append({
                k: str(v) if type(v).__name__ == "ObjectId" else v
                for k, v in u.items()
            })

    return {
        "best_compound": best or {"status": "no_compound_found"},
        "top_units":     safe_units,
        "location":      state.get("location")      or ctx.get("location"),
        "property_type": state.get("typeofproperty") or ctx.get("property_type"),
        "budget":        state.get("budget")         or ctx.get("budget"),
        "payment_type":  state.get("payment_type")   or ctx.get("payment_type"),
    }


async def _persist_user_data(user_id: str, session_id: str, state: dict) -> None:
    """
    Fire-and-forget: write chat preferences to MongoDB.
    Errors are logged but never surfaced to the caller.
    """
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, update_user_chat_preferences, user_id, state
        )
    except Exception as exc:
        print(f"⚠️  _persist_user_data error (non-fatal): {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Single endpoint for the entire multi-turn conversation.

    • First message  : omit session_id (or pass null) — server creates a session.
    • Later messages : include the session_id returned by the first response.
    • On done=True   : the results field contains the final recommendations.
    """

    # ── 1. Resolve / create session ──────────────────────────────────────────
    if request.session_id:
        state = await load_state(request.session_id)
        if state is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Session '{request.session_id}' not found or expired. "
                    "Start a new conversation by omitting session_id."
                ),
            )
        session_id = request.session_id
        print(f"\n{'='*60}\n💬 /chat — session_id: {session_id}\n{'='*60}")
        print(f"✓ State loaded from Redis")
    else:
        session_id = new_session_id()
        state = make_initial_state(session_id)
        # Attach real user_id if provided
        if request.user_id:
            if isinstance(state, dict):
                state["user_id"] = request.user_id
            else:
                state.user_id = request.user_id
        print(f"\n{'='*60}\n🆕 /chat — new session_id: {session_id}\n{'='*60}")

    # Ensure state is always a plain dict for graph_runner
    if hasattr(state, "model_dump"):
        state = state.model_dump()
    elif not isinstance(state, dict):
        state = dict(state)

    print(f"📨 User message: {request.message}")
    print(f"🔍 Current waiting_for: {state.get('waiting_for')}")

    # ── 2. Run one graph turn ─────────────────────────────────────────────────
    try:
        state, reply, is_done = await run_graph_turn(graph, state, request.message)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")

    # Normalize back to dict (agents may return Pydantic models)
    if hasattr(state, "model_dump"):
        state = state.model_dump()
    elif not isinstance(state, dict):
        state = dict(state)

    # ── 3. Persist state ──────────────────────────────────────────────────────
    await save_state(session_id, state)
    print(f"✓ State saved | phase: {_phase(state)} | done: {is_done}")
    print(f"✓ Reply: {reply[:100]}...")

    # ── 4. On completion: persist user preferences (non-blocking) ────────────
    if is_done and request.user_id:
        asyncio.create_task(_persist_user_data(request.user_id, session_id, state))

    # ── 5. Build response ─────────────────────────────────────────────────────
    return ChatResponse(
        session_id=session_id,
        message=reply,
        phase=_phase(state),
        done=is_done,
        results=_results(state) if is_done else None,
    )
