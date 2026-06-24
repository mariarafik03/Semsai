"""
state.py — Pydantic-based state schema for the real estate agent system.

ARCHITECTURE DECISIONS
──────────────────────
1. Type Safety: All fields have explicit types with Pydantic validation
2. Separation: Domain data lives in 'context', metadata separate
3. Error Tracking: Structured error records instead of string parsing
4. Future-Proof: Language support, timestamps, audit trail ready
5. Backward Compatible: Legacy fields maintained during migration

STATE LIFECYCLE
───────────────
1. Created: make_initial_state() → fresh session
2. Updated: Agents modify context/errors/waiting_for
3. Persisted: Serialized to JSON → Redis
4. Restored: Deserialized from Redis → Pydantic model
"""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════════
# ERROR TRACKING
# ═══════════════════════════════════════════════════════════════════════════

class ErrorRecord(BaseModel):
    """
    Structured error tracking for field validation failures.
    
    Replaces the old pattern of:
        waiting_for = "location_retry_2"  # string parsing 😬
    
    With:
        errors = [{"field": "location", "attempts": 2, ...}]
    """
    field: str                          # Which field failed (e.g., "location", "budget")
    attempts: int                       # How many times user has tried
    last_input: str                     # What the user actually entered
    reason: str                         # Why it failed (for user feedback)
    timestamp: str = Field(             # When it happened
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    
    class Config:
        # Allow serialization to dict for Redis
        json_schema_extra = {
            "example": {
                "field": "location",
                "attempts": 2,
                "last_input": "somewhere in egypt",
                "reason": "Could not match to any city in our database",
                "timestamp": "2024-01-15T10:30:00.000Z"
            }
        }


# ═══════════════════════════════════════════════════════════════════════════
# DOMAIN CONTEXT
# ═══════════════════════════════════════════════════════════════════════════

class AgentContext(BaseModel):
    """
    All domain-specific data lives here.
    
    This is what agents read/write to collect user requirements.
    Clean separation from conversation metadata.
    """
    
    # ── Core Requirements (Always Needed) ─────────────────────────────────
    location: Optional[str] = None                      # User-facing name (e.g., "Cairo")
    location_normalized: Optional[str] = None           # DB-normalized (e.g., "القاهرة")
    
    property_type: Optional[Literal["apartment", "villa", "chalet"]] = None
    
    payment_type: Optional[Literal["cash", "installment"]] = None
    
    budget: Optional[float] = None                      # Total budget in EGP
    
    # ── Conditional Requirements (Only if installment) ────────────────────
    downpayment: Optional[float] = None                 # Required if payment_type = installment
    monthly_installment: Optional[float] = None         # Required if payment_type = installment
    
    # ── Validation State ──────────────────────────────────────────────────
    budget_valid: bool = False                          # Has budget been validated against DB?
    min_budget_for_location: Optional[float] = None     # Cached from DB query
    
    # ── Search Results ────────────────────────────────────────────────────
    candidate_compounds: Optional[List[Dict]] = None
    top_developers: Optional[List[Dict]] = None
    final_compounds: Optional[List[Dict]] = None
    ranked_compounds: Optional[List[Dict]] = None
    selected_compound: Optional[Dict] = None
    candidate_units: Optional[List[Dict]] = None
    final_best_compound: Optional[Dict] = None
    comparison_result: Optional[Any] = None

    # ── Optional Enhancements (Future) ────────────────────────────────────
    developer_preference: Optional[str] = None          # Specific developer user wants
    amenities: List[str] = Field(default_factory=list)  # Pool, gym, security, etc.
    
    class Config:
        json_schema_extra = {
            "example": {
                "location": "Cairo",
                "location_normalized": "القاهرة",
                "property_type": "apartment",
                "payment_type": "installment",
                "budget": 500000.0,
                "downpayment": 100000.0,
                "monthly_installment": 5000.0,
                "budget_valid": True,
                "min_budget_for_location": 450000.0
            }
        }


# ═══════════════════════════════════════════════════════════════════════════
# CONVERSATION METADATA
# ═══════════════════════════════════════════════════════════════════════════

class ConversationMetadata(BaseModel):
    """
    Non-domain data: language, timestamps, session info.
    """
    language: Literal["en", "ar", "auto"] = "auto"      # Future: auto-detect from input
    conversation_started_at: Optional[str] = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    last_updated_at: Optional[str] = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    session_id: Optional[str] = None                    # For analytics
    user_agent: Optional[str] = None                    # Browser/app info
    ip_address: Optional[str] = None                    # For abuse prevention


# ═══════════════════════════════════════════════════════════════════════════
# MASTER STATE SCHEMA
# ═══════════════════════════════════════════════════════════════════════════

class AgentState(BaseModel):
    """
    Complete state schema for the real estate agent system.
    
    MIGRATION STRATEGY
    ──────────────────
    During Phase 1-2, we maintain BOTH:
      - New structure: context, errors, metadata
      - Legacy fields: location, budget, payment_type, etc.
    
    Agents will:
      1. WRITE to context (new)
      2. sync_to_legacy() for backward compatibility
      3. Router reads from context (new)
    
    Phase 3-4: Remove legacy fields entirely.
    """
    
    # ══════════════════════════════════════════════════════════════════════
    # NEW STRUCTURE (Phase 1 additions)
    # ══════════════════════════════════════════════════════════════════════
    
    # Identity
    user_id: str                                        # Session/user identifier
    
    # Domain Data (Centralized)
    context: AgentContext = Field(default_factory=AgentContext)
    
    # Conversation History
    messages: List[Dict[str, str]] = Field(default_factory=list)
    # Format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    
    # Error Tracking
    errors: List[ErrorRecord] = Field(default_factory=list)
    
    # Metadata
    metadata: ConversationMetadata = Field(default_factory=ConversationMetadata)
    
    # ══════════════════════════════════════════════════════════════════════
    # FLOW CONTROL (Existing - Keep)
    # ══════════════════════════════════════════════════════════════════════
    
    user_input: Optional[str] = None                    # Current turn's user message
    agent_message: Optional[str] = None                 # Question to show user
    waiting_for: Optional[str] = None                   # Field we're waiting for
    handoff_to_human: bool = False                      # Signal to UI or Router to handoff
    
    # ══════════════════════════════════════════════════════════════════════
    # RESULTS (Existing - Keep)
    # ══════════════════════════════════════════════════════════════════════
    
    candidate_compounds: List[Dict] = Field(default_factory=list)
    final_compounds: List[Dict] = Field(default_factory=list)
    top_compounds: Optional[List[Dict]] = None
    ranked_compounds: Optional[List[Dict]] = None
    final_best_compound: Optional[Dict] = None
    final_report: Optional[str] = None
    
    embeddings: Optional[Any] = None
    compound_features_stats: Optional[Dict] = None
    
    # ══════════════════════════════════════════════════════════════════════
    # LEGACY FIELDS (Temporary - Will be removed in Phase 3-4)
    # ══════════════════════════════════════════════════════════════════════
    
    # These duplicate context.* fields for backward compatibility
    location: Optional[str] = None
    typeofproperty: Optional[str] = None
    payment_type: Optional[str] = None
    budget: Optional[float] = None
    Downpayment: Optional[float] = None                 # Note: capital D (legacy naming)
    monthlyinstall: Optional[float] = None
    budget_valid: Optional[bool] = None
    
    # Old workflow fields
    purpose: Optional[str] = None
    pending_confirmation: Optional[str] = None
    next_step: Optional[str] = None
    payment_type_confirmed: bool = False
    retry: Optional[str] = None
    
    # Breaking flags (unclear purpose - investigate before removing)
    breakingquest: Optional[str] = None
    breakingbudget: Optional[str] = None
    breakinginstallments: Optional[str] = None
    
    # Other agents' data
    top_developers: Optional[List] = None
    final_candidates: Optional[List] = None
    candidate_units: Optional[List] = None
    selected_compound: Optional[Dict] = None
    top_investment_units: Optional[List] = None
    user_preferences: Optional[Dict] = None
    
    # Misc
    route: Optional[str] = None
    years: Optional[int] = None
    features_limit: int = 0
    features_force_refresh: bool = False
    abort: Optional[bool] = None

    # ── Unit Filter scratch-pad (used by unit_filter_node.py) ─────────────
    uf_questions: Optional[List[Dict]] = None       # generated UnitQuestion objects (serialised)
    uf_answers: Optional[Dict] = None               # {key: chosen_option} collected so far
    uf_current_q: Optional[int] = None              # index of next question to ask (0-based)
    uf_done: Optional[bool] = None                  # True once ranking is complete

    # ── Phase tracking ────────────────────────────────────────────────────
    # Agents don't write this; the router derives phase from field-presence.
    # Kept so graph_definition.state_router can read it without AttributeError.
    current_phase: Optional[Literal["discovery", "search", "comparison", "presentation"]] = None
    
    # ══════════════════════════════════════════════════════════════════════
    # GRAPH INTERNALS (Keep)
    # ══════════════════════════════════════════════════════════════════════
    
    graph_current_node: Optional[str] = None            # Graph execution cursor (was _graph_current_node — underscore prefix makes Pydantic ignore it)
    
    
    # ══════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ══════════════════════════════════════════════════════════════════════
    
    def sync_to_legacy(self) -> None:
        """
        ONE-WAY SYNC: context → legacy fields
        
        Call this after updating context to keep legacy fields in sync.
        Temporary method — will be removed in Phase 3.
        """
        self.location = self.context.location
        self.typeofproperty = self.context.property_type
        self.payment_type = self.context.payment_type
        self.budget = self.context.budget
        self.Downpayment = self.context.downpayment
        self.monthlyinstall = self.context.monthly_installment
        self.budget_valid = self.context.budget_valid
    
    
    def add_error(
        self,
        field: str,
        last_input: str,
        reason: str
    ) -> None:
        """
        Convenience method to add an error record.
        
        Automatically increments attempt count for the field.
        """
        attempts = len([e for e in self.errors if e.field == field])
        
        self.errors.append(
            ErrorRecord(
                field=field,
                attempts=attempts + 1,
                last_input=last_input,
                reason=reason
            )
        )
    
    
    def get_error_count(self, field: str) -> int:
        """Get how many times a field has failed validation."""
        return len([e for e in self.errors if e.field == field])
    
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to conversation history."""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    
    class Config:
        # Allow arbitrary types for Any fields
        arbitrary_types_allowed = True
        
        # Keep field order for readability
        validate_assignment = True


# ═══════════════════════════════════════════════════════════════════════════
# STATE FACTORY
# ═══════════════════════════════════════════════════════════════════════════

def make_initial_state(session_id: str) -> AgentState:
    """
    Create a fresh state for a new session.
    
    Returns Pydantic model (not dict) for type safety.
    Convert to dict when needed: state.model_dump()
    """
    return AgentState(
        user_id=session_id,
        metadata=ConversationMetadata(session_id=session_id)
    )


# ═══════════════════════════════════════════════════════════════════════════
# SERIALIZATION HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def state_to_dict(state: AgentState) -> dict:
    """
    Convert Pydantic model to dict for Redis/JSON storage.
    
    Uses model_dump() to handle all nested models correctly.
    """
    return state.model_dump()


def dict_to_state(data: dict) -> AgentState:
    """
    Restore Pydantic model from dict (loaded from Redis/JSON).
    
    Validates all fields during reconstruction.
    """
    return AgentState(**data)


# ═══════════════════════════════════════════════════════════════════════════
# TYPE ALIAS (for backward compatibility)
# ═══════════════════════════════════════════════════════════════════════════

# Old code expects AgentState to be Dict
# This allows gradual migration:
#   OLD: def agent(state: Dict) -> Dict
#   NEW: def agent(state: AgentState) -> AgentState
AgentStateDict = dict  # Deprecated — use AgentState model instead