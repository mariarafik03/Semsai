from typing import Any, TypedDict, Optional

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
    retry: Optional [str]
    budget_valid: Optional[str]
    breakingquest: Optional[str]
    breakingbudget:Optional[str]
    breakinginstallments:Optional[str]
    candidate_compounds: Optional[list]
    typeofproperty: Optional[str]
    final_candidates: Optional[list[dict[str, Any]]]
    features_limit: int = 1
    features_force_refresh: bool = True
    
    

