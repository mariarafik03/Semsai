import os
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv

# Load .env from agents-api or project root
_here = Path(__file__).parent
load_dotenv(_here / ".env")
load_dotenv(_here.parent / ".env")


def _get_openai_client():
    """Return a configured OpenAI client, raising clearly if the key is absent."""
    # pyrefly: ignore [missing-import]
    import openai
    api_key = "".join(os.getenv("OPENAI_API_KEY", "").split())
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing or empty")
    os.environ["OPENAI_API_KEY"] = api_key
    return openai.OpenAI(api_key=api_key), os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def ask_ollama(prompt: str) -> str:
    """
    Single-turn LLM call — kept for backward compatibility with all existing agents.
    Wraps ask_llm_with_history with an empty history and no system prompt.
    """
    return ask_llm_with_history(
        system_prompt="You are a helpful real estate assistant.",
        history=[],
        user_prompt=prompt,
    )


def ask_llm_with_history(
    system_prompt: str,
    history: List[Dict[str, str]],
    user_prompt: str,
    max_tokens: int = 512,
    temperature: float = 0.3,
) -> str:
    """
    Multi-turn LLM call with full conversation history.

    Parameters
    ----------
    system_prompt : str
        Sets the model's role and output format. Keep it focused — one clear
        instruction rather than a laundry list.
    history : list of {role, content} dicts
        Previous turns in OpenAI format. Pass state.get_llm_messages() here.
        Empty list is fine for turn-1 or stateless calls.
    user_prompt : str
        The new user message for this turn.
    max_tokens : int
        Cap on the response length. Default 512 covers all field-extraction
        and question-generation tasks; raise it for long-form output agents.
    temperature : float
        Lower (0.0–0.3) for structured JSON extraction; higher (0.6–0.8) for
        natural-language questions and final recommendation text.

    Returns
    -------
    str
        The model's reply, stripped of leading/trailing whitespace.

    Raises
    ------
    RuntimeError
        If the API key is missing or the OpenAI call fails after one retry.
    """
    client, model = _get_openai_client()

    # Build the full message list: system → history → new user turn
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)           # already clean {role, content} dicts
    messages.append({"role": "user", "content": user_prompt})

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"OpenAI call failed: {e}") from e


