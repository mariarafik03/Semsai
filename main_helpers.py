
from langchain_ollama import ChatOllama

 





ollama_model = ChatOllama(model="qwen2.5:7b", temperature=0.3)


def ask_ollama(prompt: str) -> str: 
    response = ollama_model.invoke(prompt) 
    return response.content.strip()
#def ask_ollama(prompt: str) -> str:
    """
    Main helper to call the LLM. 
    Kept the name 'ask_ollama' for compatibility with existing agents,
    now using Groq as the backend.
    """
   # response = model.invoke(prompt)
   # return response.content.strip()


