END = "END"


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
        if state.get("_graph_current_node") is not None:
            self._current_node = state["_graph_current_node"]
        else:
            self._current_node = self.entry_point

        current_node = self._current_node
        state["_graph_current_node"] = current_node  # persist before agent (for NeedInput)
        fn = self.nodes[current_node]

        new_state = fn(state)       # run the agent
        if new_state is not None:
            state = new_state

        # HTTP pause mode: agent asked a question and is waiting for user input.
        # Keep cursor on the SAME node so next turn resumes this agent.
        if state.get("waiting_for"):
            self._current_node = current_node
            state["_graph_current_node"] = current_node
            return state, current_node

        edge = self.edges[current_node]
        next_node = edge(state) if callable(edge) else edge

        self._current_node = next_node  # advance cursor
        state["_graph_current_node"] = next_node  # persist for HTTP mode
        return state, next_node
