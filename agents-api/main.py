"""
SemsAi Agents API — FastAPI server that wraps the AI agent pipeline.
Flutter communicates via REST. Each conversation has a session with state.
"""
import uuid
import traceback
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from state import new_state
from agents.purpose_agent import purpose_agent
from agents.questioning_agent import questioning_agent
from agents.budget_agent import budget_agent
from agents.location_agent import location_agent
from agents.compounds_agent import compounds_agent
from agents.developers_agent import developers_agent
from agents.comparing_agent import comparing_agent

# ──────────────────────────────────────────────
# App
# ──────────────────────────────────────────────

app = FastAPI(title="SemsAi Agents API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# In-memory session store  (good for dev/demo)
# ──────────────────────────────────────────────

sessions: dict[str, dict[str, Any]] = {}

# ──────────────────────────────────────────────
# Pydantic models
# ──────────────────────────────────────────────

class StartResponse(BaseModel):
    session_id: str
    message: str
    phase: str
    done: bool = False


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    message: str
    phase: str
    done: bool = False
    results: list[dict[str, Any]] | None = None


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _run_interactive_agent(state: dict, user_input: str | None) -> dict:
    """Run the current interactive agent (purpose/questioning/budget/location)."""
    phase = state.get("phase", "purpose")

    if phase == "purpose":
        return purpose_agent(state, user_input)
    elif phase == "questioning":
        return questioning_agent(state, user_input)
    elif phase == "budget":
        return budget_agent(state, user_input)
    elif phase == "location":
        return location_agent(state, user_input)
    else:
        return state


def _run_processing_pipeline(state: dict) -> dict:
    """Run compounds → developers → comparing (no user input needed)."""
    print("[pipeline] Running compounds_agent...")
    state = compounds_agent(state)
    print(f"[pipeline] Found {len(state.get('candidate_compounds', []))} candidates")

    print("[pipeline] Running developers_agent...")
    state = developers_agent(state)
    print(f"[pipeline] Found {len(state.get('final_candidates', []))} developers")

    print("[pipeline] Running comparing_agent...")
    state = comparing_agent(state)
    print(f"[pipeline] Got {len(state.get('top_choices', []))} top choices")

    state["done"] = True
    return state


def _advance(state: dict, user_input: str | None = None) -> dict:
    """
    Keep advancing the conversation until we need user input or we're done.
    This handles auto-advancing between phases.
    """
    max_steps = 20  # safety limit
    steps = 0

    while steps < max_steps:
        steps += 1
        phase = state.get("phase", "purpose")

        # ---- Processing phase (no user input) ----
        if phase == "processing":
            state = _run_processing_pipeline(state)
            return state

        # ---- Interactive phase ----
        state = _run_interactive_agent(state, user_input)

        # After first step, clear user_input (only used once)
        user_input = None

        # If agent needs user input, stop and return
        if state.get("awaiting_input"):
            return state

        # If done
        if state.get("done"):
            return state

        # Otherwise, continue advancing (phase may have changed)

    return state


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────

@app.post("/chat/start", response_model=StartResponse)
async def start_chat():
    """Start a new conversation session."""
    sid = str(uuid.uuid4())
    state = new_state()

    try:
        # Run the first agent to get the greeting
        state = _advance(state)
    except Exception as e:
        traceback.print_exc()
        # Fallback: still create session, use a hardcoded greeting
        state["agent_message"] = (
            "مرحباً! أنا مساعد سمسعي الذكي 🏠\n"
            "أنا هنا عشان أساعدك تلاقي العقار المناسب.\n"
            "إيه الغرض من شراء العقار؟ (سكن / استثمار / تجاري)"
        )
        state["awaiting_input"] = True
        state["phase"] = "purpose"
        state["sub_phase"] = "extract"

    sessions[sid] = state

    return StartResponse(
        session_id=sid,
        message=state.get("agent_message") or "Hello! How can I help you with real estate?",
        phase=state.get("phase", "purpose"),
    )


@app.post("/chat/respond", response_model=ChatResponse)
async def respond(req: ChatRequest):
    """Send a user message and get the next agent response."""
    state = sessions.get(req.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        state = _advance(state, req.message)
        sessions[req.session_id] = state

        response = ChatResponse(
            message=state.get("agent_message") or "",
            phase=state.get("phase", "unknown"),
            done=state.get("done", False),
        )

        if state.get("done") and state.get("top_choices"):
            response.results = state["top_choices"]

        # If the agent auto-advanced and has a message but needs more input
        # (e.g. budget_agent sends "Got it! You chose cash." then asks budget)
        # We combine the messages
        if not state.get("awaiting_input") and not state.get("done"):
            # Keep advancing
            combined_msg = state.get("agent_message") or ""
            state = _advance(state)
            sessions[req.session_id] = state

            new_msg = state.get("agent_message") or ""
            if combined_msg and new_msg:
                response.message = f"{combined_msg}\n\n{new_msg}"
            elif new_msg:
                response.message = new_msg

            response.phase = state.get("phase", "unknown")
            response.done = state.get("done", False)

            if state.get("done") and state.get("top_choices"):
                response.results = state["top_choices"]

        return response

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/status/{session_id}")
async def get_status(session_id: str):
    """Check session status."""
    state = sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "phase": state.get("phase"),
        "done": state.get("done", False),
        "has_results": state.get("top_choices") is not None,
    }


@app.get("/chat/results/{session_id}")
async def get_results(session_id: str):
    """Get the final recommendations."""
    state = sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    if not state.get("done"):
        raise HTTPException(status_code=400, detail="Conversation not finished yet")

    return {
        "purpose": state.get("purpose"),
        "budget": state.get("budget"),
        "location": state.get("location"),
        "property_type": state.get("typeofproperty"),
        "payment_type": state.get("payment_type"),
        "downpayment": state.get("Downpayment"),
        "monthly_installment": state.get("monthlyinstall"),
        "top_choices": state.get("top_choices", []),
        "candidate_count": len(state.get("candidate_compounds", [])),
        "developer_count": len(state.get("final_candidates", [])),
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "semsai-agents"}
