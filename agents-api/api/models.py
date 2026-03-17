"""
Pydantic schemas for the /chat endpoint.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Sent by the client on every turn."""

    session_id: Optional[str] = Field(
        default=None,
        description="Omit (or pass null) on the very first message — the server will create one.",
    )
    message: str = Field(
        ...,
        min_length=1,
        description="The user's raw text input for this turn.",
    )


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class ChatResponse(BaseModel):
    """Returned by the server on every turn."""

    session_id: str = Field(
        description="Echo the session_id back so the client can store it."
    )
    reply: str = Field(
        description="The assistant's message to display to the user."
    )
    done: bool = Field(
        default=False,
        description="True when the conversation has fully completed (graph reached END).",
    )
    state_snapshot: Optional[dict[str, Any]] = Field(
        default=None,
        description="(Debug / admin only) Full state dict. Omit in production.",
    )


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    detail: str
