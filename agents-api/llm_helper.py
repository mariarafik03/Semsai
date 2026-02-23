"""
LLM helper — uses Groq (cloud, llama-3.1-8b-instant).
Fast inference via Groq API.
"""
import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0.3,
    api_key=os.getenv("GROQ_API_KEY"),
)


def ask_llm(prompt: str) -> str:
    """Send a prompt to Groq and return the text response."""
    response = llm.invoke(prompt)
    return response.content.strip()
