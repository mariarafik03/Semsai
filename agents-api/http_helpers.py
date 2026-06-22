"""
HTTP mode helpers: get_user_input lets agents receive user input from HTTP request state
instead of blocking on stdin. Used when running as FastAPI server for Flutter.
"""


class NeedInput(Exception):
    """Raised when agent needs user input - pause and return current message to client."""
    def __init__(self, question: str):
        self.question = question
        super().__init__(question)


def get_user_input(state: dict, question: str = "", default: str = "") -> str:
    """
    Get user input from HTTP request state. When in HTTP mode, user_input is passed
    via state["_input_queue"]. If queue is empty, we need to ask - store question
    in state["assistant_message"] and raise NeedInput.
    """
    queue = state.get("_input_queue") or []
    if queue:
        val = queue.pop(0)
        state["_input_queue"] = queue
        return (val or default).strip()
    state["assistant_message"] = question or default
    state["_need_input"] = True
    raise NeedInput(question or default)


def init_input_queue(state: dict, user_input: str | None) -> None:
    """Initialize input queue for this HTTP step."""
    state["_input_queue"] = [user_input] if user_input else []
    state["_need_input"] = False
