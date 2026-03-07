import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from agents-api or project root
_here = Path(__file__).parent
load_dotenv(_here / ".env")
load_dotenv(_here.parent / ".env")

def ask_ollama(prompt: str) -> str:
    import openai
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
    try:
        client = openai.OpenAI(api_key=api_key or None)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except (AttributeError, TypeError):
        if api_key:
            openai.api_key = api_key
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()


