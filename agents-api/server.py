"""
SemsAI Agents API — FastAPI server for Flutter integration.

Endpoints:
  POST /chat/start   → start a new session, get first greeting
  POST /chat/respond  → send user message, get agent response
  GET  /chat/status/{session_id}  → get session phase
  GET  /chat/results/{session_id} → get final results
  GET  /                          → health check
"""

import os
import uuid
import traceback
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from graph import StateGraph, END
from agents.extraction_agent import extraction_agent
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
from agents.unit_agent import unit_agent, rent_agent, living_agent
from agents.embedding_agent import embedding_agent

load_dotenv()

# ─── App ────────────────────────────────────────────────────────────────────
app = FastAPI(title="SemsAI Agents API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── In-memory session store ───────────────────────────────────────────────
sessions: Dict[str, Dict[str, Any]] = {}


# ─── Request / Response models ─────────────────────────────────────────────
class RespondRequest(BaseModel):
    session_id: str
    message: str


# ─── State Router (same logic as main.py) ──────────────────────────────────
def state_router(state: dict) -> str:
    if state.get("abort"):
        return END

    if state.get("_end_node_reached"):
        return END

    # First step: extraction agent extracts all info from initial message
    if not state.get("_extraction_done"):
        return "extraction_agent"

    if not state.get("purpose"):
        if state.get("retry"):
            return "questioning_agent"
        return "purpose_agent"

    if not state.get("location"):
        return "location_agent"

    if not state.get("typeofproperty"):
        return "location_agent"

    if not state.get("budget") and not (
        state.get("Downpayment") and state.get("monthlyinstall")
    ):
        return "budget_agent"

    if state.get("candidate_compounds") is None:
        return "compounds_agent"

    if state.get("final_compounds") is None:
        return "developers_agent"

    if state.get("compound_features_stats") is None:
        return "compound_features_agent"

    if state.get("embeddings") is None:
        return "embedding_agent"

    if state.get("user_preferences") is None:
        return "user_preferences_agent"

    if state.get("ranked_compounds") is None:
        return "compound_ranking_agent"

    if state.get("final_best_compound") is None:
        return "final_output_agent"

    if state.get("route") is None:
        return "unit_agent"

    # If route exists but final units haven't been picked, dispatch
    if state.get("top_investment_units") is None and state.get("top_living_units") is None:
        if state.get("route") == "rent":
            return "rent_agent"
        if state.get("route") in ("live", "living"):
            return "living_agent"  # This was 'unit_filter_node' before

    # If we fall through, we're done
    return END


def _detect_phase(state: dict) -> str:
    """Map current state to a user-facing phase label."""
    if not state.get("purpose"):
        return "purpose"
    if not state.get("location") or not state.get("typeofproperty"):
        return "location"
    if not state.get("budget") and not (state.get("Downpayment") and state.get("monthlyinstall")):
        return "budget"
    if state.get("candidate_compounds") is None:
        return "compounds"
    if state.get("final_compounds") is None:
        return "developers"
    if state.get("compound_features_stats") is None:
        return "compound_features_agent"
    if state.get("embeddings") is None:
        return "processing"
    if state.get("user_preferences") is None:
        return "user_preferences"
    if state.get("ranked_compounds") is None:
        return "compound_ranking"
    if state.get("final_best_compound") is None:
        return "final_output"
    if state.get("route") is None:
        return "final_output"
    return "final_output"


def _run_until_needs_input(session: dict) -> dict:
    """
    Run the agent graph step-by-step until:
    1. An agent sets state["pending_question"] (needs user input)
    2. The graph reaches END
    3. The pipeline is "done" (final results available)

    Returns the response dict for the Flutter client.
    """
    state = session["state"]
    max_auto_steps = 20  # safety limit

    for _ in range(max_auto_steps):
        # Determine next node
        next_node = state_router(state)

        if next_node == END:
            session["done"] = True
            return {
                "message": state.get("final_report") or "✅ Done! Your results are ready.",
                "phase": "done",
                "done": True,
                "results": _build_results(state),
            }

        # Run the node
        node_name = next_node
        try:
            agent_fn = _get_agent_fn(node_name)
            if agent_fn is None:
                # Unknown node — skip
                break

            new_state = agent_fn(state)
            if new_state is not None:
                state = new_state
                session["state"] = state
        except Exception as e:
            traceback.print_exc()
            return {
                "message": f"An error occurred in {node_name}. Please try again.",
                "phase": _detect_phase(state),
                "done": False,
            }

        # Check if agent needs user input
        if state.get("pending_question"):
            question = state.pop("pending_question")
            # Clear user_input so next call starts fresh
            state["user_input"] = None
            return {
                "message": question,
                "phase": _detect_phase(state),
                "done": False,
            }

        # Agent completed without needing input — clear user_input
        # so the NEXT agent in the loop doesn't get stale input
        state["user_input"] = None

    # Safety: if we ran too many steps without output
    return {
        "message": "Processing your request...",
        "phase": _detect_phase(state),
        "done": False,
    }


def _get_agent_fn(name: str):
    """Map node name to agent function."""
    agents = {
        "extraction_agent": extraction_agent,
        "purpose_agent": purpose_agent,
        "questioning_agent": questioning_agent,
        "budget_agent": budget_agent,
        "location_agent": location_agent,
        "compounds_agent": compounds_agent,
        "developers_agent": developers_agent,
        "compound_features_agent": compound_features_agent,
        "user_preferences_agent": user_preferences_agent,
        "compound_ranking_agent": compound_ranking_agent,
        "final_output_agent": final_output_agent,
        "unit_agent": unit_agent,
        "rent_agent": rent_agent,
        "living_agent": living_agent,
        "embedding_agent": embedding_agent,
    }
    return agents.get(name)


def _build_results(state: dict) -> Optional[Dict[str, Any]]:
    """Build final results for the Flutter client."""
    best = state.get("final_best_compound")
    if not best or best.get("status") == "no_compound_found":
        return None

    top_units = state.get("top_investment_units") or state.get("candidate_units") or []
    # Serialize ObjectId fields
    clean_units = []
    for u in top_units[:5]:
        cu = {}
        for k, v in u.items():
            cu[k] = str(v) if hasattr(v, '__str__') and type(v).__name__ == 'ObjectId' else v
        clean_units.append(cu)

    return {
        "best_compound": best,
        "purpose": state.get("purpose"),
        "location": state.get("location"),
        "budget": state.get("budget"),
        "payment_type": state.get("payment_type"),
        "typeofproperty": state.get("typeofproperty"),
        "top_units": clean_units,
    }


def _make_initial_state() -> dict:
    """Create a fresh agent state."""
    return {
        "user_input": None,
        "_extraction_done": False,
        "purpose": None,
        "pending_confirmation": None,
        "budget": None,
        "location": None,
        "next_step": None,
        "payment_type": None,
        "payment_type_confirmed": False,
        "Downpayment": None,
        "monthlyinstall": None,
        "retry": None,
        "budget_valid": None,
        "breakingquest": None,
        "breakingbudget": None,
        "breakinginstallments": None,
        "candidate_compounds": None,
        "final_compounds": None,
        "top_compounds": None,
        "top_developers": None,
        "typeofproperty": None,
        "final_candidates": None,
        "compound_features_stats": None,
        "features_limit": 0,
        "features_force_refresh": False,
        "candidate_units": None,
        "selected_compound": None,
        "top_investment_units": None,
        "route": None,
    }


# ─── Endpoints ─────────────────────────────────────────────────────────────

@app.get("/")
def health():
    return {"status": "ok", "service": "SemsAI Agents API"}


@app.head("/")
def health_head():
    return {}


@app.post("/chat/start")
def start_chat():
    """Create a new chat session and return the initial greeting."""
    session_id = str(uuid.uuid4())
    state = _make_initial_state()

    session = {
        "state": state,
        "done": False,
    }
    sessions[session_id] = session

    # Run extraction_agent which generates the greeting
    # The agent will set pending_question with the greeting
    result = _run_until_needs_input(session)

    return {
        "session_id": session_id,
        "message": result.get("message", "Welcome to SemsAI!"),
        "phase": result.get("phase", "purpose"),
        "done": result.get("done", False),
    }


@app.post("/chat/respond")
def respond(req: RespondRequest):
    """Process user message and return agent response."""
    session = sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["done"]:
        return {
            "message": "This conversation has concluded.",
            "phase": "done",
            "done": True,
            "results": _build_results(session["state"]),
        }

    # Inject user input into state
    state = session["state"]
    state["user_input"] = req.message

    # Run the graph until next question or completion
    result = _run_until_needs_input(session)

    return {
        "message": result.get("message", ""),
        "phase": result.get("phase", ""),
        "done": result.get("done", False),
        "results": result.get("results"),
    }


@app.get("/chat/status/{session_id}")
def get_status(session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    state = session["state"]
    return {
        "session_id": session_id,
        "phase": _detect_phase(state),
        "done": session["done"],
    }


@app.get("/chat/results/{session_id}")
def get_results(session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    results = _build_results(session["state"])
    if not results:
        raise HTTPException(status_code=404, detail="No results available yet")

    return results


# ─── Run with uvicorn ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
