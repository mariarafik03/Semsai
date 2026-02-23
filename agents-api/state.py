"""
Conversation state shared across all agents.
Mirrors the original AgentState but adds conversation tracking.
Updated for the full 10-agent pipeline.
"""
from typing import Any, Optional


def new_state() -> dict[str, Any]:
    """Return a fresh conversation state."""
    return {
        # --- user data ---
        "user_input": None,
        "purpose": None,
        "pending_confirmation": None,
        "budget": None,
        "location": None,
        "payment_type": None,
        "Downpayment": None,
        "monthlyinstall": None,
        "typeofproperty": None,

        # --- control flags ---
        "next_step": None,
        "retry": None,
        "budget_valid": None,
        "breakingquest": None,
        "breakingbudget": None,
        "breakinginstallments": None,

        # --- results (compounds / developers) ---
        "candidate_compounds": None,
        "top_developers": None,
        "final_candidates": None,
        "final_compounds": None,
        "top_choices": None,

        # --- compound features ---
        "compound_features_stats": None,
        "features_limit": 0,
        "features_force_refresh": True,

        # --- user preferences ---
        "user_preferences": None,

        # --- ranking ---
        "ranked_compounds": None,
        "top_compounds": None,

        # --- final output ---
        "final_best_compound": None,
        "final_report": None,

        # --- conversation tracking ---
        "phase": "purpose",          # current phase name
        "sub_phase": None,           # sub-step within a phase
        "awaiting_input": True,      # True = waiting for user message
        "agent_message": None,       # last message from agent to user
        "done": False,               # True when pipeline is finished
        "asked_questions": [],        # tracks questions already asked
    }
