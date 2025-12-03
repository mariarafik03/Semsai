import requests

def call_api_llm(prompt, system_message=None, api_key=None):
    """
    Call API-based LLM (OpenAI, Anthropic, etc.).
    
    Args:
        prompt: The user prompt
        system_message: Optional system message
        api_key: Your API key (or set as environment variable)
    
    Returns:
        String response from the model
    """
    import os

    
    # Get API key from parameter or environment
    if api_key is None:
        api_key = os.getenv("API_KEY")
    
    messages = []
    
    if system_message:
        messages.append({"role": "system", "content": system_message})
    
    messages.append({"role": "user", "content": prompt})
    
    # For OpenAI API
    payload = {
        "model": "gpt-3.5-turbo",  # Change to your preferred model
        "messages": messages
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
        
    except Exception as e:
        return f"Error: {str(e)}"
response = call_api_llm(
        prompt="What is Python?",
        api_key="your-api-key-here"
    )
print(response)
    