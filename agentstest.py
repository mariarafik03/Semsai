import requests
from langchain_ollama import ChatOllama
from typing import TypedDict, Optional

END = "END"
import subprocess

OLLAMA_PATH = r"C:\Users\user\AppData\Local\Ollama\ollama.exe"

# Use & style in Python (full path must be correct)
subprocess.Popen([OLLAMA_PATH, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)


class AgentState(TypedDict):
    user_input: str
    purpose: Optional[str]
    budget: Optional[int]
    budget_valid: Optional[bool]
    location: Optional[str]
    next_step: Optional[str]
    retry_count: int

# === Ollama Model Setup ===
ollama_model = ChatOllama(model="qwen2.5:7b", temperature=0.2)

def ask_ollama(prompt: str) -> str:
    """Call Ollama model and return clean string response."""
    response = ollama_model.invoke(prompt)
    return response.content.strip()

# === Agents ===
def purpose_agent(state: AgentState):
    print("\n--- Purpose Agent (Ollama) ---")

    # 1️⃣ Start conversation if no user input yet
    if not state.get("user_input") and not state.get("pending_confirmation"):
        prompt = (
            "You are an extra friendly real estate assistant. "
            "Greet the user naturally and ask why they are interested in real estate. "
            "Do NOT process anything yet; just ask the question."
        )
        response_text = ask_ollama(prompt)
        print("Agent:", response_text)
        state["next_step"] = None  # wait for user reply
        return state

    # 2️⃣ If waiting to extract purpose from user input
    if not state.get("pending_confirmation"):
        # Process user input to extract purpose
        prompt = (
            f"You are a helpful real estate assistant. "
            f"Extract the purpose of buying real estate from the user's input. "
            f"User said: '{state['user_input']}' "
            "Return ONLY one of: rent, invest, live. "
            "Do NOT add extra text."
        )
        response_text = ask_ollama(prompt)
        print("Debug (extracted purpose):", response_text)

        # Determine extracted purpose
        purpose = None
        for w in ["rent", "invest", "live" ]:
            if w in response_text.lower():
                purpose = w
                break

        if purpose:
            # Ask for confirmation naturally
            confirmation_prompt = (
                f"So, you are interested in buying a property to {purpose}? "
                "Please reply yes or no."
            )
            print("Agent:", confirmation_prompt)
            state["pending_confirmation"] = purpose
            state["next_step"] = None  # wait for user confirmation
        else:
            # Could not extract purpose, ask clarification
            state["next_step"] = "questioning_agent"
        return state

    # 3️⃣ Handle user confirmation
    if state.get("pending_confirmation"):
        user_reply = state["user_input"].lower()
        if "yes" in user_reply:
            state["purpose"] = state["pending_confirmation"]
            state["next_step"] = "budget_agent"
        else:
            # User said no, need to clarify
            state["next_step"] = "questioning_agent"

        # Clear pending confirmation
        state["pending_confirmation"] = None

    return state



def questioning_agent(state: AgentState):
    print("\n--- Clarification Agent (Ollama) ---")
    new_input = input("Agent: I didn't understand your purpose. Can you clarify? You: ")
    state["user_input"] = new_input
    state["next_step"] = "purpose_agent"
    return state

def budget_agent(state: AgentState):
    print("\n--- Budget Agent (Ollama) ---")
    prompt = (
        f"Extract ONLY the numeric budget from this input. "
        f"Return just the digits.\nUser: '{state['user_input']}'"
    )
    response_text = ask_ollama(prompt)
    print("Debug:", response_text)

    digits = "".join(filter(str.isdigit, response_text))
    if digits:
        state["budget"] = int(digits)
        state["budget_valid"] = True
        state["next_step"] = "location_agent"
    else:
        state["budget_valid"] = False
        state["next_step"] = "education_agent"
    return state

def education_agent(state: AgentState):
    print("\n--- Ask Budget Again (Ollama) ---")
    new_budget = input("Agent: Please enter your budget (e.g., 50000): ")
    state["user_input"] = new_budget
    state["next_step"] = "budget_agent"
    return state

def location_agent(state: AgentState):
    print("\n--- Location Agent (Ollama) ---")
    if not state.get("location"):
        loc = input("Agent: Where do you want to buy? ")
        state["location"] = loc
    state["next_step"] = END
    return state

def route_step(state):
    return state["next_step"]

class SimpleStateGraph:
    def __init__(self, schema):
        self.nodes = {}
        self.entry_point = None

    def add_node(self, name, func):
        self.nodes[name] = func

    def set_entry_point(self, name):
        self.entry_point = name

    def step(self, state):
        """Run a single node and return updated state and next node"""
        # Determine current node
        current = self.entry_point if state.get("next_step") is None else state["next_step"]

        if current == END:
            return state, END

        fn = self.nodes[current]
        state = fn(state)
        next_node = state.get("next_step")  # may be None if waiting for user input
        return state, next_node



# Initial state
state = {
    "user_input": None,
    "purpose": None,
    "budget": None,
    "budget_valid": False,
    "location": None,
    "next_step": None,
    "retry_count": 0,
    "pending_confirmation": None,
    "payment_type": None

}
graph = SimpleStateGraph(AgentState)
graph.add_node("purpose_agent", purpose_agent)
graph.add_node("questioning_agent", questioning_agent)
graph.add_node("budget_agent", budget_agent)
graph.add_node("education_agent", education_agent)
graph.add_node("location_agent", location_agent)
graph.set_entry_point("purpose_agent")

next_node = None

# Step 1: Ollama greets and asks initial question
state, next_node = graph.step(state)

# Step 2: User replies to the greeting
state["user_input"] = input("You: ")

# Step 3: Process Purpose Agent with extraction and confirmation
state["next_step"] = "purpose_agent"
state, next_node = graph.step(state)

# Step 4: If pending confirmation, wait for user reply
if state.get("pending_confirmation"):
    state["user_input"] = input("You (confirm yes/no): ")
    state, next_node = graph.step(state)

# Step 5: Continue the rest of the graph
while next_node != END:
    fn = graph.nodes[next_node]
    state = fn(state)
    next_node = state.get("next_step", END)

print("\n--- Final Plan ---")
print("Purpose:", state["purpose"])
print("Budget:", state["budget"])
print("Location:", state["location"])