from langchain_ollama import ChatOllama

ollama_model = ChatOllama(
    model="qwen2.5:7b", temperature=0.3)

def ask_ollama(prompt: str) -> str:
    response = ollama_model.invoke(prompt)
    return response.content.strip()

