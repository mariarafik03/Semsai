def add_to_history(state: dict, role: str, content: str) -> None:
    """Add a message to conversation history in state."""
    if "conversation_history" not in state or state["conversation_history"] is None:
        state["conversation_history"] = []
    state["conversation_history"].append({
        "role": role,
        "content": content
    })
    # Keep last 20 messages only
    state["conversation_history"] = state["conversation_history"][-20:]


def format_history(state: dict) -> str:
    """Format conversation history as a string for LLM prompts."""
    history = state.get("conversation_history") or []
    if not history:
        return "No previous conversation."
    lines = []
    for msg in history:
        role = "User" if msg["role"] == "user" else "Assistant"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)


def build_dynamic_prompt(state: dict, current_situation: str, goal: str) -> str:
    """
    Build a prompt that includes full conversation history.
    This makes the LLM aware of everything said so far.
    """
    history = format_history(state)
    known_info = {
        k: v for k, v in state.items()
        if v is not None and k in (
            "purpose", "budget", "location",
            "typeofproperty", "payment_type",
            "Downpayment", "monthlyinstall"
        )
    }

    return f"""You are a warm, knowledgeable real estate advisor in Egypt. 
You speak naturally like a trusted friend who happens to be a property expert.

CONVERSATION SO FAR:
{history}

WHAT YOU ALREADY KNOW ABOUT THE USER:
{known_info if known_info else "Nothing yet."}

CURRENT SITUATION:
{current_situation}

YOUR GOAL:
{goal}

RULES:
- If the user asks a question, answer it helpfully before moving on
- If the user shares personal context (salary, family size etc), use it to give personalized advice  
- If the user is unsure, help them decide — don't just repeat the question
- Never ask for info you already have
- Sound human, warm, Egyptian real estate market aware
- Keep responses concise — 2-3 sentences max
"""