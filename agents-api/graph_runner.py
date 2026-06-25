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
3. graph_current_node is the cursor; it is updated by graph.step().
"""

import asyncio
from datetime import datetime, timezone
from typing import Tuple
from graph import StateGraph, END

# ---------------------------------------------------------------------------
# Sentinel keys stored in state
# ---------------------------------------------------------------------------
WAITING_FOR_KEY  = "waiting_for"    # str  — which field the agent is waiting for
AGENT_MSG_KEY    = "agent_message"  # str  — the question/message shown to the user
GRAPH_NODE_KEY   = "graph_current_node"

# Maximum steps per turn to prevent infinite loops
MAX_STEPS_PER_TURN = 60


# ---------------------------------------------------------------------------
# Initial (blank) state factory
# ---------------------------------------------------------------------------

from state import AgentState, AgentContext

def _ensure_dict(state) -> dict:
    """Convert AgentState to dict if needed."""
    if state is None:
        return {}
    if isinstance(state, dict):
        return state
    if hasattr(state, "model_dump"):
        return state.model_dump()
    if hasattr(state, "dict"):
        return state.dict()
    return dict(state)

def _ensure_agent_state(state) -> AgentState:
    """Convert dict to AgentState if needed."""
    if isinstance(state, AgentState):
        return state
    if isinstance(state, dict):
        return AgentState(**state)
    raise TypeError(f"Cannot convert {type(state)} to AgentState")

def make_initial_state(session_id: str) -> dict:
    """Return a fresh state dict for a brand-new session."""
    agent_state = AgentState(
        session_id=session_id,
        user_id="",             # route handler fills this with the real MongoDB _id
        context=AgentContext()
    )
    return _ensure_dict(agent_state)


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

    state = _ensure_dict(state)

    # ── 1. Inject user message ───────────────────────────────────────────
    # IMPORTANT: we set user_input but do NOT touch waiting_for.
    state["user_input"]   = user_message if user_message else None
    state["agent_message"] = None   # clear previous message

    # ── 1a. Record user turn in conversation history ─────────────────────
    # Done once here so every agent gets history for free — agents never
    # need to append user messages themselves.
    if user_message:
        msgs = list(state.get("messages") or [])
        msgs.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        state["messages"] = msgs

    # ── 2. Safety: detect stale waiting_for with empty message ──────────
    if state.get(WAITING_FOR_KEY) and not user_message:
        reply = state.get(AGENT_MSG_KEY) or "Please provide the requested information."
        return state, reply, False

    # Convert to AgentState for graph execution
    agent_state = _ensure_agent_state(state)

    # ── 3. Step through graph until pause or END ─────────────────────────
    loop = asyncio.get_event_loop()
    steps = 0
    # Track how many times we've visited each node.  Firing the guard only
    # when the same node is visited consecutively was too aggressive: agents
    # that pass through without pausing (nothing to do yet) legitimately
    # hand off to the next node and the two consecutive graph_current_node
    # values can look identical if the router keeps choosing the same target.
    # Instead we fire only when any single node has been entered 3+ times in
    # one turn — that is always a real cycle.
    node_visit_counts: dict = {}

    while True:
        steps += 1

        if steps > MAX_STEPS_PER_TURN:
            reply = (
                "I seem to be stuck in a loop internally. "
                "Please try rephrasing your last message."
            )
            # Reset cursor so next turn restarts from current node cleanly
            agent_state.user_input = None
            state = _ensure_dict(agent_state)
            return state, reply, False

        # Run the synchronous graph.step() off the event loop
        agent_state, next_node = await loop.run_in_executor(
            None, graph.step, agent_state
        )
        
        state = _ensure_dict(agent_state)

        # ── DEBUG: trace routing decisions ──────────────────────────────
        _fbk = (state.get("context") or {}).get("final_best_compound") or state.get("final_best_compound")
        print(f"  🔀 step={steps} node={state.get(GRAPH_NODE_KEY)!r} next={next_node!r} "
              f"waiting_for={state.get(WAITING_FOR_KEY)!r} "
              f"episode_saved={state.get('episode_saved')} "
              f"final_best_compound={'SET' if _fbk else 'None'}")

        # ── Graph reached END ────────────────────────────────────────────
        if next_node == END:
            reply = (
                state.get(AGENT_MSG_KEY)
                or "✅ All done! Your property search is complete."
            )
            _record_assistant_message(state, reply)
            _clear_turn_fields(state)
            return state, reply, True

        # ── Agent needs user input → pause ───────────────────────────────
        if state.get(WAITING_FOR_KEY):
            reply = (
                state.get(AGENT_MSG_KEY)
                or "Please provide the requested information."
            )
            _record_assistant_message(state, reply)
            # Clear agent_message (already captured in reply)
            # but keep waiting_for so next turn's agent can resume.
            state[AGENT_MSG_KEY] = None
            state["user_input"]  = None   # consumed; don't leave stale value
            print(f"  ⏸️  PAUSING — waiting_for={state.get(WAITING_FOR_KEY)!r}, reply={reply[:60]!r}")
            return state, reply, False

        # ── Abort flag set by an agent ───────────────────────────────────
        if state.get("abort"):
            reply = (
                state.get(AGENT_MSG_KEY)
                or "I'm sorry, I couldn't complete your request. Please try again."
            )
            _record_assistant_message(state, reply)
            _clear_turn_fields(state)
            return state, reply, True   # treat as done so client resets

        # ── Infinite-loop guard: same node visited 3+ times this turn ──────
        current_node = state.get(GRAPH_NODE_KEY)
        if current_node and current_node != END:
            node_visit_counts[current_node] = node_visit_counts.get(current_node, 0) + 1
            if node_visit_counts[current_node] >= 3:
                reply = (
                    state.get(AGENT_MSG_KEY)
                    or "Something went wrong internally. Please try again."
                )
                _clear_turn_fields(state)
                return state, reply, False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _record_assistant_message(state: dict, reply: str) -> None:
    if not reply:
        return
    msgs = list(state.get("messages") or [])
    msgs.append({
        "role": "assistant",
        "content": reply,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    state["messages"] = msgs


def _clear_turn_fields(state: dict) -> None:
    state[AGENT_MSG_KEY] = None