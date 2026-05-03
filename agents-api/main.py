"""
main.py — FastAPI application entry point
"""

import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.routes.chat import router as chat_router
from api.session import close_redis, load_state, save_state, new_session_id
from graph_runner import run_graph_turn, make_initial_state
from graph_definition import graph


# ---------------------------------------------------------------------------
# Lifespan  (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────
    print("🚀  Real-estate assistant API starting…")
    yield
    # ── Shutdown ─────────────────────────────────────────────────────────
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

# ── CORS  (adjust origins for production) ───────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten this in production!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ───────────────────────────────────────────────────────────────────
app.include_router(chat_router, prefix="/api/v1", tags=["chat"])


def _json_safe(data):
    return json.loads(json.dumps(data, default=str))


def _phase_from_state(state: dict) -> str:
    if state.get("final_best_compound"):
        return "complete"
    if state.get("waiting_for"):
        return "asking"
    return state.get("_graph_current_node") or "processing"


def _build_results(state: dict) -> dict:
    best = state.get("final_best_compound")
    units = state.get("candidate_units") or []

    # Build top_compounds from the new top_compounds_with_units
    top_compounds_raw = state.get("top_compounds_with_units") or []
    top_compounds = []
    for tc in top_compounds_raw:
        tc_units = tc.get("units") or []
        top_compounds.append({
            "compound_id": tc.get("compound_id"),
            "compound_name": tc.get("compound_name", "Unknown"),
            "location": tc.get("location", ""),
            "score": tc.get("score", 0),
            "units": _json_safe(tc_units[:10]),  # limit to 10 units per compound
            "above_budget": tc.get("above_budget", False),
        })

    return {
        "purpose": state.get("purpose"),
        "budget": state.get("budget"),
        "location": state.get("location"),
        "property_type": state.get("typeofproperty"),
        "payment_type": state.get("payment_type"),
        "best_compound": best or {"status": "no_compound_found"},
        "top_units": _json_safe(units[:5]),
        "top_compounds": top_compounds,  # NEW: top 3 with units
    }


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
# Backward-compatible chat endpoints (used by Flutter app)
# ---------------------------------------------------------------------------

@app.post("/chat/start")
async def chat_start(request: Request):
    """Start a new session and return the first assistant question."""
    try:
        try:
            body = await request.json()
        except Exception:
            body = {}

        session_id = body.get("session_id") or new_session_id()
        state = make_initial_state(session_id)

        state, reply, done = await run_graph_turn(graph, state, "")
        await save_state(session_id, state)

        response = {
            "session_id": session_id,
            "message": reply,
            "phase": _phase_from_state(state),
            "done": done,
            "state": _json_safe(state),
        }
        if done:
            response["results"] = _build_results(state)
        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"chat_start failed: {e}") from e


@app.post("/chat/respond")
async def chat_respond(request: Request):
    """Continue an existing session with one user message."""
    try:
        try:
            body = await request.json()
        except Exception:
            body = {}
            
        session_id = body.get("session_id")
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")

        message = (body.get("message") or "").strip()
        if not message:
            return {
                "session_id": session_id,
                "message": "لم تكتب رسالة. يرجى المحاولة مرة أخرى.",
                "phase": "error",
                "done": False,
                "state": _json_safe(body.get("state") or {}),
            }

        state = body.get("state") if isinstance(body.get("state"), dict) else None
        if state is None:
            state = await load_state(session_id)

        if state is None:
            raise HTTPException(
                status_code=404,
                detail="Session not found or expired. Start a new chat.",
            )

        state, reply, done = await run_graph_turn(graph, state, message)
        await save_state(session_id, state)

        response = {
            "session_id": session_id,
            "message": reply,
            "phase": _phase_from_state(state),
            "done": done,
            "state": _json_safe(state),
        }
        if done:
            response["results"] = _build_results(state)
        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"chat_respond failed: {e}") from e


@app.get("/chat/status/{session_id}")
async def chat_status(session_id: str):
    state = await load_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")

    done = bool(state.get("final_best_compound"))
    return {
        "session_id": session_id,
        "phase": _phase_from_state(state),
        "done": done,
        "has_results": done,
    }


@app.get("/chat/results/{session_id}")
async def chat_results(session_id: str):
    state = await load_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if not state.get("final_best_compound"):
        raise HTTPException(status_code=400, detail="Conversation not finished yet")

    return _build_results(state)


# ---------------------------------------------------------------------------
# Dev runner  (uvicorn main:app --reload)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)