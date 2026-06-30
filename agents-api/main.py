"""
main.py — FastAPI application entry point.

Responsibilities
────────────────
- Create the FastAPI app and register middleware
- Mount the single /chat router
- Health check and debug endpoints
- Lifespan: open/close Redis on startup/shutdown
"""

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.routes.chat import router as chat_router
from api.session import close_redis, load_state


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀  Real-estate assistant API starting…")
    # Verify graph compiles at startup so errors surface immediately
    from graph_definition import graph  # noqa: F401
    print("✓ Graph compiled successfully")
    yield
    print("🛑  Shutting down — closing Redis connection…")
    await close_redis()


# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Real Estate Assistant API",
    version="2.0.0",
    description="Multi-agent property search chatbot — single /chat endpoint",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, tags=["chat"])


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", tags=["meta"])
async def root():
    return {"message": "SemsAi Agents API running", "status": "ok"}


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}


# ─────────────────────────────────────────────────────────────────────────────
# Debug (remove or gate behind auth in production)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/debug/session/{session_id}", tags=["debug"])
async def debug_session(session_id: str):
    """Full state dump for debugging a specific session."""
    state = await load_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id":  session_id,
        "waiting_for": state.get("waiting_for"),
        "phase":       state.get("current_phase") or state.get("graph_current_node"),
        "context":     state.get("context") or {},
        "state":       state,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Dev runner
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
