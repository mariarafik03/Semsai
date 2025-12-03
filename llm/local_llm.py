import requests

def call_local_llm(prompt, system_message=None):
    """
    Call local Qwen2.5:7b model via Ollama.
    
    Args:
        prompt: The user prompt
        system_message: Optional system message
    
    Returns:
        String response from the model
    """
    messages = []
    
    if system_message:
        messages.append({"role": "system", "content": system_message})
    
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": "qwen2.5:7b",
        "messages": messages,
        "stream": False
    }
    
    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        result = response.json()
        return result["message"]["content"]
        
    except Exception as e:
        return f"Error: {str(e)}"
response = call_local_llm("What is Python?")
print(response)