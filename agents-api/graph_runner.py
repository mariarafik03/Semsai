"""
graph_runner.py — async, HTTP-safe execution engine for the StateGraph.

HOW THE PAUSE / RESUME PATTERN WORKS
─────────────────────────────────────
Old (CLI) flow:
    agent asks question  →  input()  →  user types  →  agent continues

New (HTTP) flow:
    Turn N  : agent needs input
              → sets  state["waiting_for"] = "<field_name>"
              → sets  state["agent_message"] = "<question to show user>"
              → returns state immediately  (graph pauses)
              → runner returns ChatResponse to client

    Turn N+1: client sends next message
              → runner puts message into  state["user_input"]
              → clears state["waiting_for"]
              → resumes graph from the same node

The graph keeps running (stepping through nodes) until either:
  • a node sets  state["waiting_for"]  (needs more input)
  • graph reaches END

IMPORTANT: agents must be refactored to check
    if state.get("waiting_for") == "<their_field>":
        answer = state.pop("user_input")   # consume the answer
        state.pop("waiting_for")           # clear the pause flag
        # ... continue processing
"""

import asyncio
from typing import Tuple
from graph import StateGraph, END

# ---------------------------------------------------------------------------
# Sentinel values stored in state
# ---------------------------------------------------------------------------
WAITING_FOR_KEY  = "waiting_for"   # str  — which field the agent is waiting for
AGENT_MSG_KEY    = "agent_message" # str  — the question/message shown to the user
GRAPH_NODE_KEY   = "_graph_current_node"


# ---------------------------------------------------------------------------
# Initial (blank) state factory
# ---------------------------------------------------------------------------

def make_initial_state(session_id: str) -> dict:
    """Return a fresh state dict for a brand-new session."""
    return {
        # ── identity ──────────────────────────────────────────────────────
        "user_id":               session_id,
        # ── conversation ──────────────────────────────────────────────────
        "user_input":            None,
        "agent_message":         None,
        "waiting_for":           None,
        # ── domain fields ─────────────────────────────────────────────────
        "purpose":               None,
        "pending_confirmation":  None,
        "budget":                None,
        "location":              None,
        "next_step":             None,
        "payment_type":          None,
        "payment_type_confirmed": False,
        "Downpayment":           None,
        "monthlyinstall":        None,
        "retry":                 None,
        "budget_valid":          None,
        "breakingquest":         None,
        "breakingbudget":        None,
        "breakinginstallments":  None,
        "candidate_compounds":   None,
        "final_compounds":       None,
        "top_compounds":         None,
        "top_developers":        None,
        "typeofproperty":        None,
        "final_candidates":      None,
        "compound_features_stats": None,
        "features_limit":        0,
        "features_force_refresh": False,
        "candidate_units":       None,
        "selected_compound":     None,
        "top_investment_units":  None,
        "route":                 None,
        "years":                 None,
        "ranked_compounds":      None,
        "user_preferences":      None,
        "final_best_compound":   None,
        "final_report":          None,
        "abort":                 None,
        "embeddings":            None,
        # ── graph cursor ──────────────────────────────────────────────────
        GRAPH_NODE_KEY:          None,
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def run_graph_turn(
    graph: StateGraph,
    state: dict,
    user_message: str,
) -> Tuple[dict, str, bool]:
    """
    Execute one conversational turn.

    Parameters
    ----------
    graph        : the compiled StateGraph instance
    state        : current state (loaded from Redis)
    user_message : the raw text the user just sent

    Returns
    -------
    (updated_state, reply_text, is_done)
        updated_state — must be persisted to Redis by the caller
        reply_text    — the message to send back to the user
        is_done       — True when the graph has reached END
    """

    # ── 1. Inject the user's message & clear the pause flag ─────────────
    state["user_input"] = user_message
    state[WAITING_FOR_KEY] = None      # agent will re-set this if it needs more

    # ── 2. Step through the graph until it pauses or ends ───────────────
    loop = asyncio.get_event_loop()

    while True:
        # run the synchronous graph.step() in a thread-pool so we don't
        # block the FastAPI event loop
        state, next_node = await loop.run_in_executor(
            None, graph.step, state
        )

        # Graph finished
        if next_node == END:
            reply = state.get(AGENT_MSG_KEY) or "✅ All done! Your property search is complete."
            _clear_turn_fields(state)
            return state, reply, True

        # Agent needs user input  → pause and return
        if state.get(WAITING_FOR_KEY):
            reply = state.get(AGENT_MSG_KEY) or "Please provide the requested information."
            _clear_turn_fields(state)
            return state, reply, False

        # Safety valve: if the next node is the same as the current node
        # and we are not waiting, something is wrong — break to avoid loop
        current = state.get(GRAPH_NODE_KEY)
        if current == next_node and not state.get(WAITING_FOR_KEY):
            reply = state.get(AGENT_MSG_KEY) or "I'm having trouble proceeding. Please try again."
            return state, reply, False


def _clear_turn_fields(state: dict) -> None:
    """
    Remove transient per-turn fields before persisting.
    We keep user_input in state so agents can read it on the next turn,
    but we clear agent_message (already sent to client).
    """
    state[AGENT_MSG_KEY] = None
