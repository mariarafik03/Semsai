import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

# Use Groq cloud LLM (works on HF Spaces, no local Ollama needed)
model = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.3,
)


def ask_ollama(prompt: str) -> str:
    """
    Main helper to call the LLM.
    Kept the name 'ask_ollama' for compatibility with existing agents,
    now using Groq as the backend.
    """
    response = model.invoke(prompt)
    return response.content.strip()
