"""
api/routes/conversation.py
──────────────────────────
Flutter-facing conversation endpoints.

POST /chat/start                — create session + first greeting turn
POST /chat/respond              — send a user message, get a reply
GET  /chat/results/{session_id} — fetch final property recommendations
GET  /chat/history/{user_id}    — fetch user's past conversation summaries
"""

import asyncio
import traceback
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Any, List

from api.session import (
    load_state, save_state, new_session_id,
    load_profile, save_profile, append_history, load_history,
)
from api.db import update_user_chat_preferences
from graph_runner import run_graph_turn, make_initial_state
from graph_definition import graph

router = APIRouter()

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class StartRequest(BaseModel):
    user_id: str


class RespondRequest(BaseModel):
    session_id: str
    message: str


class StartResponse(BaseModel):
    session_id: str
    message: str
    phase: str
    done: bool
    returning_user: bool = False


class RespondResponse(BaseModel):
    message: str
    phase: str
    done: bool


class ResultsResponse(BaseModel):
    session_id: str
    results: Optional[Any]
    done: bool


class HistoryResponse(BaseModel):
    user_id: str
    history: List[Any]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_phase(state: dict) -> str:
    """
    Extract the current graph phase from state.
    graph_runner stores the active node in state["_graph_current_node"].
    Falls back gracefully if the key is absent.
    """
    return (
        state.get("_graph_current_node")
        or state.get("current_phase")
        or state.get("phase")
        or "extraction"
    )


def _get_results(state: dict) -> Any:
    """
    Extract final property recommendations from state.
    Returns the first non-None value found among the known result keys.
    """
    for key in (
        "final_report",
        "final_best_compound",
        "top_compounds",
        "final_candidates",
        "ranked_compounds",
        "candidate_units",
    ):
        value = state.get(key)
        if value is not None:
            return value
    return None


def _top_result_name(results: Any) -> Optional[str]:
    """
    Best-effort extraction of the top result name to store in history.
    Handles list-of-dicts and plain dicts gracefully.
    """
    if results is None:
        return None
    if isinstance(results, list) and results:
        first = results[0]
        if isinstance(first, dict):
            return first.get("name") or first.get("compound_name") or first.get("title")
    if isinstance(results, dict):
        return results.get("name") or results.get("compound_name") or results.get("title")
    return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/start", response_model=StartResponse)
async def start_conversation(request: StartRequest) -> StartResponse:
    """
    Create a brand-new session.

    1. Load the user's long-term preference profile from Redis.
    2. Build an initial state and pre-fill known preferences.
    3. Set the real user_id (from the client) in state — overriding the
       placeholder that make_initial_state would have used.
    4. Run the first graph turn with an empty message so extraction_agent
       produces its opening greeting.
    5. Return returning_user=True if a profile was found, so the Flutter
       app can show a "Welcome back" UI.
    """
    user_id = request.user_id
    session_id = new_session_id()

    # ── 1. Load long-term profile ─────────────────────────────────────────
    profile = await load_profile(user_id)
    returning_user = bool(profile)

    # ── 2. Build state and apply profile ─────────────────────────────────
    state = make_initial_state(session_id)

    # Overwrite user_id with the real auth id (make_initial_state sets None)
    state["user_id"] = user_id

    # Pre-fill any preferences we already know about this user
    for field, value in profile.items():
        if value is not None:
            state[field] = value

    # ── 3. Run first graph turn ───────────────────────────────────────────
    try:
        state, reply, is_done = await run_graph_turn(graph, state, "")
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to start conversation.")

    await save_state(session_id, state)

    return StartResponse(
        session_id=session_id,
        message=reply,
        phase=_get_phase(state),
        done=is_done,
        returning_user=returning_user,
    )


@router.post("/respond", response_model=RespondResponse)
async def respond(request: RespondRequest) -> RespondResponse:
    """
    Accept a user message for an existing session, run one graph turn,
    persist updated state, and return the assistant's reply.
    """
    state = await load_state(request.session_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Session '{request.session_id}' not found or expired. "
                "Start a new conversation via POST /chat/start."
            ),
        )

    try:
        state, reply, is_done = await run_graph_turn(graph, state, request.message)
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error processing your message.")

    await save_state(request.session_id, state)

    return RespondResponse(
        message=reply,
        phase=_get_phase(state),
        done=is_done,
    )


@router.get("/results/{session_id}", response_model=ResultsResponse)
async def get_results(session_id: str, user_id: str) -> ResultsResponse:
    """
    Return the final property recommendations stored in state.

    Also persists long-term memory:
      • Saves the user's preference profile (profile:{user_id})
      • Appends a summary entry to the history (history:{user_id})
    """
    state = await load_state(session_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found or expired.",
        )

    results = _get_results(state)

    # ── Persist long-term memory ──────────────────────────────────────────
    # 1. Redis profile (fast, used to pre-fill next session)
    await save_profile(user_id, state)

    # 2. MongoDB user doc — merge chat preferences into the existing user
    #    document that user_preferences_agent already created.
    #    PyMongo is synchronous so we run it in a thread-pool.
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, update_user_chat_preferences, user_id, state)

    # 3. Redis history (conversation summary list)
    summary = {
        "timestamp":      datetime.now(timezone.utc).isoformat(),
        "purpose":        state.get("purpose"),
        "budget":         state.get("budget"),
        "location":       state.get("location"),
        "typeofproperty": state.get("typeofproperty"),
        "top_result":     _top_result_name(results),
    }
    await append_history(user_id, session_id, summary)

    return ResultsResponse(
        session_id=session_id,
        results=results,
        done=True,
    )


@router.get("/history/{user_id}", response_model=HistoryResponse)
async def get_history(user_id: str) -> HistoryResponse:
    """
    Return the list of past conversation summaries for a user.
    Each entry contains: session_id, timestamp, purpose, budget,
    location, typeofproperty, top_result.
    """
    history = await load_history(user_id)
    return HistoryResponse(user_id=user_id, history=history)
