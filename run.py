#!/usr/bin/env python3
"""Run the SemsAi Agents API server (for Flutter integration)."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
