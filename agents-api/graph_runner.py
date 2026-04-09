"""
graph_runner.py — async, HTTP-safe execution engine for the StateGraph.

HOW THE PAUSE / RESUME PATTERN WORKS
─────────────────────────────────────
Turn N   : agent needs input
             → sets  state["waiting_for"]  = "<field_name>"
             → sets  state["agent_message"] = "<question to show user>"
             → runner returns ChatResponse to client immediately

Turn N+1 : client sends next message
             → runner puts message into state["user_input"]
             → KEEPS state["waiting_for"] so the agent knows which field
               it was waiting for
             → graph resumes on the SAME node
             → agent reads user_input + waiting_for, processes the answer,
               clears waiting_for itself, then returns
             → runner sees waiting_for is now None → continues stepping

CRITICAL RULES
──────────────
1. graph_runner NEVER clears waiting_for — only agents clear it.
2. user_input is set fresh every turn and consumed by the agent.
3. _graph_current_node is the cursor; it is updated by graph.step().
"""

import asyncio
from typing import Tuple
from graph import StateGraph, END

# ---------------------------------------------------------------------------
# Sentinel keys stored in state
# ---------------------------------------------------------------------------
WAITING_FOR_KEY  = "waiting_for"    # str  — which field the agent is waiting for
AGENT_MSG_KEY    = "agent_message"  # str  — the question/message shown to the user
GRAPH_NODE_KEY   = "_graph_current_node"

# Maximum steps per turn to prevent infinite loops
MAX_STEPS_PER_TURN = 60


# ---------------------------------------------------------------------------
# Initial (blank) state factory
# ---------------------------------------------------------------------------

def make_initial_state(session_id: str) -> dict:
    """Return a fresh state dict for a brand-new session."""
    return {
        # ── identity ──────────────────────────────────────────────────────
        "user_id":                session_id,
        # ── conversation ──────────────────────────────────────────────────
        "user_input":             None,
        "agent_message":          None,
        "waiting_for":            None,
        # ── domain fields ─────────────────────────────────────────────────
        "purpose":                None,
        "pending_confirmation":   None,
        "budget":                 None,
        "location":               None,
        "next_step":              None,
        "payment_type":           None,
        "payment_type_confirmed": False,
        "Downpayment":            None,
        "monthlyinstall":         None,
        "retry":                  None,
        "budget_valid":           None,
        "breakingquest":          None,
        "breakingbudget":         None,
        "breakinginstallments":   None,
        "candidate_compounds":    None,
        "final_compounds":        None,
        "top_compounds":          None,
        "top_developers":         None,
        "typeofproperty":         None,
        "final_candidates":       None,
        "compound_features_stats": None,
        "features_limit":         0,
        "features_force_refresh": False,
        "candidate_units":        None,
        "selected_compound":      None,
        "top_investment_units":   None,
        "route":                  None,
        "years":                  None,
        "ranked_compounds":       None,
        "user_preferences":       None,
        "final_best_compound":    None,
        "final_report":           None,
        "abort":                  None,
        "embeddings":             None,
        # ── graph cursor ──────────────────────────────────────────────────
        GRAPH_NODE_KEY:           None,
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
    state        : current state (loaded from Redis / session store)
    user_message : the raw text the user just sent

    Returns
    -------
    (updated_state, reply_text, is_done)
        updated_state — must be persisted by the caller
        reply_text    — the message to send back to the user
        is_done       — True when the graph has reached END
    """

    # ── 1. Inject user message ───────────────────────────────────────────
    # IMPORTANT: we set user_input but do NOT touch waiting_for.
    # The resuming agent needs waiting_for to know what it was waiting for.
    state["user_input"]   = user_message if user_message else None
    state["agent_message"] = None   # clear previous message

    # ── 2. Safety: detect stale waiting_for with empty message ──────────
    # If waiting_for is set but user sent nothing, just re-ask the question.
    if state.get(WAITING_FOR_KEY) and not user_message:
        reply = state.get(AGENT_MSG_KEY) or "Please provide the requested information."
        return state, reply, False

    # ── 3. Step through graph until pause or END ─────────────────────────
    loop = asyncio.get_event_loop()
    steps = 0
    last_node = None

    while True:
        steps += 1

        if steps > MAX_STEPS_PER_TURN:
            reply = (
                "I seem to be stuck in a loop internally. "
                "Please try rephrasing your last message."
            )
            # Reset cursor so next turn restarts from current node cleanly
            state["user_input"] = None
            return state, reply, False

        # Run the synchronous graph.step() off the event loop
        state, next_node = await loop.run_in_executor(
            None, graph.step, state
        )

        # ── Graph reached END ────────────────────────────────────────────
        if next_node == END:
            reply = (
                state.get(AGENT_MSG_KEY)
                or "✅ All done! Your property search is complete."
            )
            _clear_turn_fields(state)
            return state, reply, True

        # ── Agent needs user input → pause ───────────────────────────────
        if state.get(WAITING_FOR_KEY):
            reply = (
                state.get(AGENT_MSG_KEY)
                or "Please provide the requested information."
            )
            # Clear agent_message (already captured in reply)
            # but keep waiting_for so next turn's agent can resume.
            state[AGENT_MSG_KEY] = None
            state["user_input"]  = None   # consumed; don't leave stale value
            return state, reply, False

        # ── Abort flag set by an agent ───────────────────────────────────
        if state.get("abort"):
            reply = (
                state.get(AGENT_MSG_KEY)
                or "I'm sorry, I couldn't complete your request. Please try again."
            )
            _clear_turn_fields(state)
            return state, reply, True   # treat as done so client resets

        # ── Infinite-loop guard: same node twice with no waiting_for ─────
        current_node = state.get(GRAPH_NODE_KEY)
        if current_node == last_node and not state.get(WAITING_FOR_KEY):
            reply = (
                state.get(AGENT_MSG_KEY)
                or "Something went wrong internally. Please try again."
            )
            _clear_turn_fields(state)
            return state, reply, False

        last_node = current_node


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clear_turn_fields(state: dict) -> None:
    """
    Tidy up transient per-turn fields before persisting state.
    - Clear agent_message (already sent to client).
    - Clear user_input (consumed this turn).
    - Do NOT touch waiting_for — agents own that.
    """
    state[AGENT_MSG_KEY] = None
    state["user_input"]  = None