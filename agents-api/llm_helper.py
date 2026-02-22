"""
LLM helper — uses Groq (free, fast, cloud-based).
Drop-in replacement for the old Ollama helper.
"""
import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

_groq_key = os.getenv("GROQ_API_KEY", "")

llm = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=_groq_key,
    temperature=0.3,
)


def ask_llm(prompt: str) -> str:
    """Send a prompt to Groq and return the text response."""
    response = llm.invoke(prompt)
    return response.content.strip()
