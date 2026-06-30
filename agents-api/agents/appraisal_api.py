"""
SEMSAI Appraisal API — FastAPI wrapper for the agentic appraiser.
Add this file to the semsai-agents HF Space alongside existing files.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import traceback

# Import the agent — both files live in agents/ but Python root is parent
try:
    from agents.semsai_agent_v4_2 import appraiser_agent
    AGENT_AVAILABLE = True
except ImportError:
    try:
        # Fallback: if running from within agents/ directory
        from semsai_agent_v4_2 import appraiser_agent
        AGENT_AVAILABLE = True
    except Exception as e:
        print(f"⚠️  Appraisal agent import failed: {e}")
        AGENT_AVAILABLE = False

router = APIRouter(prefix="/appraisal", tags=["appraisal"])


class AppraisalRequest(BaseModel):
    area: float
    bedrooms: int
    bathrooms: int
    delivery_year: int
    property_type: str  # Apartment / Villa / Chalet
    finishing: str       # Finished / semi-finished / not finished / Furnished
    sale_type: str       # Resale / Developer Sale
    compound: str
    location: str
    developer: str
    ppm_target: Optional[float] = 0


@router.post("/run")
async def run_appraisal(req: AppraisalRequest):
    """Run the full agentic appraisal workflow."""
    if not AGENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Appraisal agent not available")

    try:
        input_features = {
            "area": req.area,
            "bedrooms": req.bedrooms,
            "bathrooms": req.bathrooms,
            "delivery_year": req.delivery_year,
            "property_type": req.property_type,
            "finishing": req.finishing,
            "sale_type": req.sale_type,
            "compound": req.compound,
            "location": req.location,
            "developer": req.developer,
            "ppm_target": req.ppm_target or 0,
        }

        result = appraiser_agent.invoke({"input_features": input_features})

        return {
            "final_price": result.get("final_price", 0),
            "model_price": result.get("model_price", 0),
            "avg_price": result.get("avg_price", 0),
            "low_confidence": result.get("low_confidence", False),
            "fallback_used": result.get("fallback_used", False),
            "sources": result.get("sources", []),
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
