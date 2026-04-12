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
        node_from_state = state.get("_graph_current_node")
        if (node_from_state is None or 
            node_from_state == END or 
            node_from_state not in self.nodes):
            self._current_node = self.entry_point
        else:
            self._current_node = node_from_state
    
        # ← THIS LINE WAS MISSING
        current_node = self._current_node

        state.pop("_graph_current_node", None)
        state["_graph_current_node"] = current_node

        if current_node not in self.nodes:
            raise RuntimeError(
                f"Graph node '{current_node}' is not registered. "
                f"Known nodes: {list(self.nodes.keys())}"
            )

        fn = self.nodes[current_node]
        new_state = fn(state)
        if new_state is not None:
            state = new_state

        if state.get("waiting_for"):
            self._current_node = current_node
            state["_graph_current_node"] = current_node
            return state, current_node

        edge = self.edges[current_node]
        next_node = edge(state) if callable(edge) else edge

        self._current_node = next_node
        state["_graph_current_node"] = next_node
        return state, next_node