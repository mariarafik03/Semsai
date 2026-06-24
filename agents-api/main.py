import os
import sys

# Ensure the directory containing main.py is in the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.routes.chat import router as chat_router
from api.session import close_redis, load_state, save_state, new_session_id
from graph_runner import run_graph_turn, make_initial_state
from graph_definition import graph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_safe(data) -> dict:
    """Serialize anything (dict or Pydantic model) to a plain JSON-safe dict."""
    if data is None:
        return {}
    if hasattr(data, "model_dump"):        # Pydantic v2
        data = data.model_dump()
    elif hasattr(data, "dict"):            # Pydantic v1
        data = data.dict()
    return json.loads(json.dumps(data, default=str))


def _to_dict(state) -> dict:
    """
    Normalize state to a plain dict regardless of whether graph_runner /
    agents returned a dict or a Pydantic AgentState object.
    Always call this before:
      - saving to Redis
      - reading with state.get(...)
      - building response payloads
    """
    if state is None:
        return {}
    if isinstance(state, dict):
        return state
    # Pydantic model
    if hasattr(state, "model_dump"):
        return state.model_dump()
    if hasattr(state, "dict"):
        return state.dict()
    return dict(state)


def _phase_from_state(state: dict) -> str:
    if state.get("final_best_compound") or (
        state.get("context", {}) or {}
    ).get("final_best_compound"):
        return "complete"
    if state.get("waiting_for"):
        return "asking"
    return state.get("graph_current_node") or "processing"


def _build_results(state: dict) -> dict:
    # Support both legacy top-level fields and nested context
    ctx = state.get("context") or {}
    best  = state.get("final_best_compound") or ctx.get("final_best_compound")
    units = state.get("candidate_units") or ctx.get("candidate_units") or []
    return {
        "purpose":       state.get("purpose"),
        "budget":        state.get("budget") or ctx.get("budget"),
        "location":      state.get("location") or ctx.get("location"),
        "property_type": state.get("typeofproperty") or ctx.get("property_type"),
        "payment_type":  state.get("payment_type") or ctx.get("payment_type"),
        "best_compound": best or {"status": "no_compound_found"},
        "top_units":     _json_safe(units[:5]),
    }


# ---------------------------------------------------------------------------
# Lifespan  (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀  Real-estate assistant API starting…")
    yield
    print("🛑  Shutting down — closing Redis connection…")
    await close_redis()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Real Estate Assistant API",
    version="1.0.0",
    description="Multi-agent property search chatbot powered by LangGraph + Ollama",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api/v1", tags=["chat"])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/", tags=["meta"])
async def root():
    return {"message": "SemsAi Agents API running", "status": "ok"}

@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# /chat/start — begin a new session
# ---------------------------------------------------------------------------

@app.post("/chat/start")
async def chat_start(request: Request):
    """
    Start a new session and return the first assistant question.
    """
    try:
        try:
            body = await request.json()
        except Exception:
            body = {}

        session_id = body.get("session_id") or new_session_id()
        print(f"\n{'='*60}")
        print(f"📝 /chat/start — session_id: {session_id}")
        print(f"{'='*60}")

        # make_initial_state() returns a plain dict (from graph_runner.py)
        state = make_initial_state(session_id)

        # Run first graph turn (extraction_agent asks the first question)
        state, reply, done = await run_graph_turn(graph, state, "")

        # FIX: normalize to dict before saving / reading
        state = _to_dict(state)
        await save_state(session_id, state)
        print(f"✓ State saved to Redis for session {session_id}")

        response = {
            "session_id": session_id,
            "message": reply,
            "phase": _phase_from_state(state),
            "done": done,
            "state": _json_safe(state),
        }

        if done:
            response["results"] = _build_results(state)

        print(f"✓ /chat/start response: {reply[:100]}...")
        return response

    except Exception as e:
        print(f"❌ /chat/start error: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"chat_start failed: {e}") from e


# ---------------------------------------------------------------------------
# /chat/respond — continue existing session
# ---------------------------------------------------------------------------

@app.post("/chat/respond")
async def chat_respond(request: Request):
    """
    Continue an existing session with one user message.
    """
    try:
        try:
            body = await request.json()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}") from e

        session_id = body.get("session_id")
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")

        print(f"\n{'='*60}")
        print(f"💬 /chat/respond — session_id: {session_id}")
        print(f"{'='*60}")

        message = (body.get("message") or "").strip()
        if not message:
            # Re-ask if user sent nothing
            state = await load_state(session_id) or {}
            return {
                "session_id": session_id,
                "message": "لم تكتب رسالة. يرجى المحاولة مرة أخرى.",
                "phase": _phase_from_state(state),
                "done": False,
                "state": _json_safe(state),
            }

        # ── Load state ──────────────────────────────────────────────────────
        # Priority: Redis (source of truth) → body fallback (for dev/testing)
        state = await load_state(session_id)

        if state is None:
            # Fallback: client may have sent state in body (dev/mobile clients)
            body_state = body.get("state")
            if isinstance(body_state, dict) and body_state:
                state = body_state
                print("⚠️ State loaded from request body (Redis miss)")
            else:
                print(f"❌ Session {session_id} not found")
                raise HTTPException(
                    status_code=404,
                    detail=f"Session '{session_id}' not found or expired. Please start a new chat.",
                )
        else:
            print(f"✓ State loaded from Redis")

        # FIX: ensure it's a plain dict before passing to run_graph_turn
        state = _to_dict(state)

        print(f"📨 User message: {message}")
        print(f"🔍 Current waiting_for: {state.get('waiting_for')}")

        # ── Run graph ────────────────────────────────────────────────────────
        state, reply, done = await run_graph_turn(graph, state, message)

        # FIX: normalize to dict after graph run (agents may return Pydantic)
        state = _to_dict(state)

        await save_state(session_id, state)
        print(f"✓ State saved to Redis")

        response = {
            "session_id": session_id,
            "message": reply,
            "phase": _phase_from_state(state),
            "done": done,
            "state": _json_safe(state),
        }

        if done:
            response["results"] = _build_results(state)

        print(f"✓ Response: {reply[:100]}...")
        return response

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ /chat/respond error: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"chat_respond failed: {e}") from e


# ---------------------------------------------------------------------------
# /chat/status  &  /chat/results
# ---------------------------------------------------------------------------

@app.get("/chat/status/{session_id}")
async def chat_status(session_id: str):
    """Get current status of a session."""
    print(f"🔍 /chat/status — {session_id}")
    state = await load_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")

    state = _to_dict(state)
    done = bool(state.get("final_best_compound") or
                (state.get("context") or {}).get("final_best_compound"))
    return {
        "session_id": session_id,
        "phase": _phase_from_state(state),
        "done": done,
        "has_results": done,
    }


@app.get("/chat/results/{session_id}")
async def chat_results(session_id: str):
    """Get final results for a completed session."""
    print(f"📊 /chat/results — {session_id}")
    state = await load_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")

    state = _to_dict(state)
    ctx = state.get("context") or {}
    has_result = bool(state.get("final_best_compound") or ctx.get("final_best_compound"))
    if not has_result:
        raise HTTPException(status_code=400, detail="Conversation not finished yet")

    return _build_results(state)


# ---------------------------------------------------------------------------
# Debug endpoint
# ---------------------------------------------------------------------------

@app.get("/debug/session/{session_id}", tags=["debug"])
async def debug_session(session_id: str):
    """Full state dump for debugging."""
    state = await load_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")

    state = _to_dict(state)
    return {
        "session_id": session_id,
        "state": _json_safe(state),
        "waiting_for": state.get("waiting_for"),
        "phase": _phase_from_state(state),
        # Show context fields separately for easy reading
        "context": _json_safe(state.get("context") or {}),
    }


# ---------------------------------------------------------------------------
# Dev runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)