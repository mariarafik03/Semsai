"""
api/models.py — Pydantic request/response schemas for the chat API.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Sent by the client on every turn."""

    session_id: Optional[str] = Field(
        default=None,
        description="Omit on the very first message — the server will create one.",
    )
    message: str = Field(
        ...,
        min_length=1,
        description="The user's raw text input for this turn.",
    )
    user_id: Optional[str] = Field(
        default=None,
        description="Optional user identifier for profile persistence.",
    )


class ChatResponse(BaseModel):
    """Returned by the server on every turn."""

    session_id: str
    message: str = Field(description="The assistant's reply to show the user.")
    phase: str = Field(default="processing")
    done: bool = Field(default=False)
    results: Optional[dict[str, Any]] = Field(
        default=None,
        description="Final property results when done=True.",
    )


class ErrorResponse(BaseModel):
    detail: str
