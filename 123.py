import spacy
import requests
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional
import time 
from langchain_core.messages import HumanMessage, AIMessage


END = "END"


class AgentState(TypedDict):
    user_input: str                  
    purpose: Optional[str]
    budget: Optional[int]
    budget_valid: Optional[bool]
    location: Optional[str]
    next_step: Optional[str] 
    retry_count: int


def ask_llm_simulated(prompt: str) -> str:
    """
    Simulate AI responses using simple rules or user input.
    Returns AIMessage content.
    """
    user_input = prompt.lower()
    
    
    for purpose in ["rent", "invest", "live", "buy"]:
        if purpose in user_input:
            return AIMessage(content=purpose).content
    
  
    return AIMessage(content=input("Agent: I'm not sure. Do you want to rent, invest, or live? You: ")).content


def purpose_agent(state: AgentState):
    print("\n--- Purpose Agent Thinking ---")
    current_input = state["user_input"]
    
    llm_response = ask_llm_simulated(current_input)
    
    print(f"(Debug: Simulated LLM response: '{llm_response}')")
    
    found_purpose = None
    for w in ["rent", "invest", "live"]:
        if w in llm_response.lower():
            found_purpose = w
            break
            
    if found_purpose:
        state["purpose"] = found_purpose
        state["next_step"] = "budget_agent"
        state["retry_count"] = 0 
    else:
        state["purpose"] = "unknown"
        state["next_step"] = "questioning_agent"
    
    return state

def questioning_agent(state: AgentState):
    print("\n--- Agent Needs Clarification ---")
    new_input = input("Agent: Can you clarify? You: ") 
    state["user_input"] = new_input
    state["next_step"] = "purpose_agent"
    return state

def budget_agent(state: AgentState):
    print("\n--- Budget Agent Thinking ---")
    user_input = state["user_input"]
    
    
    llm_response = AIMessage(content="".join(filter(str.isdigit, user_input))).content
    print(f"(Debug: Simulated LLM response: '{llm_response}')")
    
    if llm_response:
        state["budget"] = int(llm_response)
        state["budget_valid"] = True
        state["next_step"] = "location_agent"
    else:
        state["budget_valid"] = False
        state["next_step"] = "education_agent"
    
    return state

def education_agent(state: AgentState):
    print("\n--- Agent Needs Budget ---")
    new_budget = input("Agent: I couldn't find a valid budget. Please enter your budget (e.g., 50000): ")
    state["user_input"] = new_budget
    state["next_step"] = "budget_agent"
    return state

def location_agent(state: AgentState):
    print("\n--- Location Agent ---")
    if not state.get("location"):
        loc = input("Agent: Where would you like to look? ")
        state["location"] = loc
    state["next_step"] = END
    return state


def route_step(state: AgentState):
    return state["next_step"]


class SimpleStateGraph:
    def __init__(self, state_schema):
        self.state_schema = state_schema
        self.nodes = {}
        self.entry_point = None
    
    def add_node(self, name, func):
        self.nodes[name] = func
    
    def set_entry_point(self, name):
        self.entry_point = name
    
    def invoke(self, state):
        current = self.entry_point
        while current != END:
            agent_func = self.nodes[current]
            state = agent_func(state)
            current = route_step(state)
        return state


graph = SimpleStateGraph(AgentState)
graph.add_node("purpose_agent", purpose_agent)
graph.add_node("questioning_agent", questioning_agent)
graph.add_node("budget_agent", budget_agent)
graph.add_node("education_agent", education_agent)
graph.add_node("location_agent", location_agent)

graph.set_entry_point("purpose_agent")

print("------------------------------------------")
print("Real Estate AI: Hello! How can I help you?")
print("------------------------------------------")

first_input = input("You:   ")

initial_state = {
    "user_input": first_input,
    "purpose": None,
    "budget": None,
    "budget_valid": False,
    "location": None,
    "next_step": None,
    "retry_count": 0
}

final_state = graph.invoke(initial_state)

print("\n-----------------")
print("Final Plan:")
print(f"Goal: {final_state['purpose']}")
print(f"Budget: {final_state['budget']}")
print(f"Location: {final_state['location']}")