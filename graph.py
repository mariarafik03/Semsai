END = "END"

class SimpleStateGraph:
    def __init__(self):
        self.nodes = {}
        self.entry_point = None

    def add_node(self, name, func):
        self.nodes[name] = func

    def set_entry_point(self, name):
        self.entry_point = name

    def step(self, state):
        """Run a single node and return updated state and next node"""
        current = self.entry_point if state.get("next_step") is None else state["next_step"]

        if current == END:
            return state, END

        fn = self.nodes[current]
        state = fn(state)
        next_node = state.get("next_step")  # may be None if waiting for user input
        return state, next_node
