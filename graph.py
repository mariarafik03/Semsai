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
        # Use internal cursor; first call starts at entry_point
        if self._current_node is None:
            self._current_node = self.entry_point

        current_node = self._current_node
        fn = self.nodes[current_node]

        

        
        new_state = fn(state)       # run the agent
        if new_state is not None:
            state = new_state

        edge = self.edges[current_node]
        next_node = edge(state) if callable(edge) else edge

        self._current_node = next_node  # advance cursor
        return state, next_node
