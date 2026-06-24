END = "END"


def _state_get(state, key, default=None):
    """
    Uniform read helper — works for both dict state (HTTP/Redis path)
    and Pydantic AgentState objects (in-process / test path).
    """
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def _state_set(state, key, value):
    """
    Uniform write helper — works for both dict and Pydantic state.
    """
    if isinstance(state, dict):
        state[key] = value
    else:
        setattr(state, key, value)


class StateGraph:
    def __init__(self):
        self.nodes = {}
        self.edges = {}          # edges[node] = callable(state) -> next_node
        self.entry_point = None
        self._current_node = None  # internal cursor, NOT stored in state

    def add_node(self, name, func):
        self.nodes[name] = func

    def add_edge(self, from_node, condition_fn):
        """condition_fn: callable(state) -> next_node (str)"""
        self.edges[from_node] = condition_fn

    def set_entry_point(self, name):
        self.entry_point = name

    def step(self, state):
        # Restore cursor from state (HTTP mode) or use entry_point
        # NOTE: use "graph_current_node" (no leading underscore) — Pydantic ignores
        # underscore-prefixed names so the cursor would be lost across Redis round-trips.
        current_cursor = _state_get(state, "graph_current_node")
        if current_cursor is not None:
            self._current_node = current_cursor
        else:
            self._current_node = self.entry_point

        current_node = self._current_node
        _state_set(state, "graph_current_node", current_node)  # persist before agent
        fn = self.nodes[current_node]

        new_state = fn(state)       # run the agent
        if new_state is not None:
            state = new_state

        # HTTP pause mode: agent asked a question and is waiting for user input.
        # Keep cursor on the SAME node so next turn resumes this agent.
        if _state_get(state, "waiting_for"):
            self._current_node = current_node
            _state_set(state, "graph_current_node", current_node)
            return state, current_node

        edge = self.edges[current_node]
        next_node = edge(state) if callable(edge) else edge

        self._current_node = next_node  # advance cursor
        _state_set(state, "graph_current_node", next_node)   # persist for HTTP mode
        return state, next_node
