"""
api/routes/chat.py — POST /chat endpoint
"""

import os
from fastapi import APIRouter, HTTPException

from api.models import ChatRequest, ChatResponse
from api.session import load_state, save_state, new_session_id
from graph_runner import run_graph_turn, make_initial_state

# Import your compiled graph (singleton — built once at startup)
from graph_definition import graph   # see graph_definition.py

router = APIRouter()

# Set to True only in local dev to expose raw state in responses
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Single endpoint for the entire multi-turn conversation.

    Flow
    ────
    1. Load (or create) session state from Redis
    2. Run one graph turn with the user's message
    3. Save updated state back to Redis
    4. Return the assistant's reply
    """

    # ── 1. Resolve session ───────────────────────────────────────────────
    if request.session_id:
        state = await load_state(request.session_id)
        if state is None:
            raise HTTPException(
                status_code=404,
                detail=f"Session '{request.session_id}' not found or expired. "
                       "Start a new conversation by omitting session_id.",
            )
        session_id = request.session_id
    else:
        # Brand-new conversation
        session_id = new_session_id()
        state = make_initial_state(session_id)

    # ── 2. Run one turn ──────────────────────────────────────────────────
    try:
        state, reply, is_done = await run_graph_turn(graph, state, request.message)
    except Exception as exc:
        # Don't leak internals to the client; log for debugging
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal error: {str(exc)}")

    # ── 3. Persist state ─────────────────────────────────────────────────
    await save_state(session_id, state)

    # ── 4. Respond ───────────────────────────────────────────────────────
    return ChatResponse(
        session_id=session_id,
        reply=reply,
        done=is_done,
        state_snapshot=state if DEBUG_MODE else None,
    )
