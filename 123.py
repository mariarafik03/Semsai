from langgraph.graph import StateGraph, END
from langchain_ollama import ChatOllama

from langchain_ollama import ChatOllama

model = ChatOllama(
    model="qwen2.5:7b",
    temperature=0.2
)
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
from langchain_ollama import ChatOllama
import operator

class State(TypedDict):
    messages: Annotated[list, operator.add]

model = ChatOllama(model="qwen2.5:7b")

def call_model(state):
    response = model.invoke(state["messages"])
    return {"messages": [response]}

graph = StateGraph(State)
graph.add_node("model", call_model)
graph.set_entry_point("model")
graph.add_edge("model", END)

app = graph.compile()

print(app.invoke({"messages": ["hi"]}))
