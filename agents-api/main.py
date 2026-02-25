"""
SemsAi Agents API — FastAPI server that wraps the full 10-agent pipeline.
Flutter communicates via REST. Each conversation has a session with state.

Pipeline: purpose → questioning → budget → location → compounds → developers
          → compound_features → user_preferences → compound_ranking → final_output
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
from agents.compound_features_agent import compound_features_agent
from agents.user_preferences_agent import user_preferences_agent
from agents.compound_ranking_agent import compound_ranking_agent
from agents.final_output_agent import final_output_agent

# ──────────────────────────────────────────────
# App
# ──────────────────────────────────────────────

app = FastAPI(title="SemsAi Agents API", version="2.0.0")

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
    results: dict[str, Any] | None = None


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

# Interactive agents need user_input
INTERACTIVE_PHASES = {"purpose", "questioning", "budget", "location", "user_preferences"}

# Autonomous agents run without user input
AUTONOMOUS_PHASES = {"compounds", "developers", "compound_features", "compound_ranking", "final_output"}

# Phase → next phase mapping (pipeline order)
PHASE_ORDER = [
    "purpose", "questioning", "budget", "location",
    "compounds", "developers", "compound_features",
    "user_preferences", "compound_ranking", "final_output",
]


def _run_interactive_agent(state: dict, user_input: str | None) -> dict:
    """Run the current interactive agent."""
    phase = state.get("phase", "purpose")

    if phase == "purpose":
        return purpose_agent(state, user_input)
    elif phase == "questioning":
        return questioning_agent(state, user_input)
    elif phase == "budget":
        return budget_agent(state, user_input)
    elif phase == "location":
        return location_agent(state, user_input)
    elif phase == "user_preferences":
        return user_preferences_agent(state, user_input)
    else:
        return state


def _run_processing_pipeline(state: dict) -> dict:
    """Run all autonomous agents sequentially:
    compounds → developers → compound_features → compound_ranking → final_output.
    """
    print("[pipeline] Running compounds_agent...")
    state = compounds_agent(state)
    print(f"[pipeline] Found {len(state.get('candidate_compounds') or [])} candidates")

    print("[pipeline] Running developers_agent...")
    state = developers_agent(state)
    print(f"[pipeline] Found {len(state.get('final_compounds') or [])} final compounds")

    print("[pipeline] Running compound_features_agent...")
    state = compound_features_agent(state)
    stats = state.get("compound_features_stats", {})
    print(f"[pipeline] Features extracted: {stats.get('processed', 0)}")

    # After compound_features, we need user preferences (interactive)
    state["phase"] = "user_preferences"
    state["sub_phase"] = None
    state["awaiting_input"] = False  # auto-advance to generate first question
    return state


def _run_ranking_pipeline(state: dict) -> dict:
    """Run ranking + final output after user preferences are collected."""
    print("[pipeline] Running compound_ranking_agent...")
    state = compound_ranking_agent(state)
    top = state.get("top_compounds", [])
    print(f"[pipeline] Ranked compounds: {len(state.get('ranked_compounds', []))}, top: {len(top)}")

    print("[pipeline] Running final_output_agent...")
    state = final_output_agent(state)
    print(f"[pipeline] Final report: {state.get('final_report', 'N/A')}")

    state["done"] = True
    return state


def _advance(state: dict, user_input: str | None = None) -> dict:
    """
    Keep advancing the conversation until we need user input or we're done.
    Handles auto-advancing between phases.
    """
    max_steps = 30  # safety limit
    steps = 0

    while steps < max_steps:
        steps += 1
        phase = state.get("phase", "purpose")

        # ---- Processing phase (autonomous: compounds → developers → features) ----
        if phase == "processing":
            state = _run_processing_pipeline(state)
            # Phase is now "user_preferences" — loop back to re-read it
            continue

        # ---- Ranking phase (autonomous: ranking → final_output) ----
        elif phase == "ranking":
            state = _run_ranking_pipeline(state)
            return state

        # ---- Interactive phase ----
        elif phase in INTERACTIVE_PHASES:
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
            continue

        # ---- Finished ----
        elif state.get("done"):
            return state

        # Safety: unknown phase
        print(f"[warn] Unknown phase: {phase}")
        return state

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

        # Attach results when done
        if state.get("done"):
            response.results = _build_results(state)

        # If the agent auto-advanced and has a message but needs more input
        if not state.get("awaiting_input") and not state.get("done"):
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

            if state.get("done"):
                response.results = _build_results(state)

        return response

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


def _build_results(state: dict) -> dict[str, Any]:
    """Build the results payload for the frontend."""
    best = state.get("final_best_compound") or {}
    top = state.get("top_compounds") or []

    return {
        "best_compound": best,
        "top_compounds": [
            {
                "compound_name": c.get("compound_name"),
                "location": c.get("location"),
                "score": c.get("score") or c.get("total_score"),
                "min_unit_price": c.get("min_unit_price"),
                "reasons": c.get("reasons", [])[:3],
                "units": c.get("units", []),
            }
            for c in top
        ],
        "summary": {
            "purpose": state.get("purpose"),
            "budget": state.get("budget"),
            "location": state.get("location"),
            "property_type": state.get("typeofproperty"),
            "payment_type": state.get("payment_type"),
            "downpayment": state.get("Downpayment"),
            "monthly_installment": state.get("monthlyinstall"),
        },
        "final_report": state.get("final_report"),
    }


@app.get("/chat/status/{session_id}")
async def get_status(session_id: str):
    """Check session status."""
    state = sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "phase": state.get("phase"),
        "done": state.get("done", False),
        "has_results": state.get("final_best_compound") is not None,
    }


@app.get("/chat/results/{session_id}")
async def get_results(session_id: str):
    """Get the final recommendations."""
    state = sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    if not state.get("done"):
        raise HTTPException(status_code=400, detail="Conversation not finished yet")

    return _build_results(state)


@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {"status": "ok", "service": "semsai-agents"}

@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok", "service": "semsai-agents", "version": "2.0.0"}
