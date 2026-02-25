from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize the model
model = ChatGroq(model="llama-3.3-70b-versatile", groq_api_key=os.getenv("GROQ_API_KEY"))

def ask_ollama(prompt: str) -> str:
    """
    Main helper to call the LLM. 
    Kept the name 'ask_ollama' for compatibility with existing agents,
    now using Groq as the backend.
    """
    response = model.invoke(prompt)
    return response.content.strip()

def ask_groq(prompt: str) -> str:
    return ask_ollama(prompt)

