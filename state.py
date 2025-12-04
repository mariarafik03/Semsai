from typing import TypedDict, Optional

class AgentState(TypedDict):
    user_input: Optional[str]
    purpose: Optional[str]
    pending_confirmation: Optional[str]
    budget: Optional[int]
    location: Optional[str]
    next_step: Optional[str]
    payment_type: Optional[str]
    Downpayment: Optional[str]
    monthlyinstall: Optional[str]
