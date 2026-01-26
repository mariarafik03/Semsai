END = "END"
class StateGraph:
    def __init__(self):
        self.nodes = {}
        self.edges = {}  # edges[node] = function(state) -> next_node
        self.entry_point = None

    def add_node(self, name, func):
        self.nodes[name] = func

    def add_edge(self, from_node, condition_fn):
        """
        condition_fn: function(state) -> next_node (str)
        """
        self.edges[from_node] = condition_fn

    def set_entry_point(self, name):
        self.entry_point = name

    def step(self, state):
        current_node = state["next_step"] or self.entry_point
        fn = self.nodes[current_node]
        state = fn(state)  # run agent
        next_node = self.edges[current_node](state)
        state["next_step"] = next_node
        return state, next_node
