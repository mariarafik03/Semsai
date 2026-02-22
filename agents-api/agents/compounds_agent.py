"""
Compounds Agent — finds matching compounds from MongoDB.
No user input needed — runs autonomously.
"""
import os
import re
from typing import Any, Dict, List

from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
import certifi


def _format_price(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{int(float(value)):,}"
    except Exception:
        return "N/A"


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x) if x is not None else default
    except Exception:
        return default


def _units_match(comp_oid: ObjectId) -> Dict[str, Any]:
    comp_str = str(comp_oid)
    return {"compound_id": {"$in": [comp_oid, comp_str]}}


def _min_price_for_type(db, comp_oid: ObjectId, wanted_type: str) -> Any:
    unit_query: Dict[str, Any] = _units_match(comp_oid)
    unit_query["$or"] = [
        {"type": {"$regex": f"^{re.escape(wanted_type)}$", "$options": "i"}},
        {"property_type": {"$regex": f"^{re.escape(wanted_type)}$", "$options": "i"}},
        {"unit_type": {"$regex": f"^{re.escape(wanted_type)}$", "$options": "i"}},
    ]
    min_unit = db["units"].find_one(
        unit_query, sort=[("price", 1)], projection={"price": 1}
    )
    return min_unit.get("price") if min_unit else None


def compounds_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Find compounds matching budget/location/type."""
    load_dotenv()
    uri = os.getenv("MONGO_URI")
    if not uri:
        return state

    client = MongoClient(uri, tlsCAFile=certifi.where())
    try:
        db = client.get_default_database()
        user_type = state.get("typeofproperty")

        budget = state.get("budget")
        if budget is None:
            dp = _safe_float(state.get("Downpayment"), 0.0)
            mi = _safe_float(state.get("monthlyinstall"), 0.0)
            plan = db["payments"].find_one({}, sort=[("duration", -1)], projection={"duration": 1})
            months = int(plan["duration"]) if plan and plan.get("duration") else 120
            budget = dp + mi * months
            state["budget"] = budget

        budget = float(budget)
        location = state.get("location")
        comp_query: Dict[str, Any] = {}
        if location:
            comp_query["location"] = {"$regex": re.escape(str(location).strip()), "$options": "i"}

        compounds = list(db["compounds"].find(comp_query, {"name": 1, "compound_name": 1, "location": 1}))

        candidate_compounds: List[Dict[str, Any]] = []
        for comp in compounds:
            comp_oid = comp["_id"]
            min_apt = _min_price_for_type(db, comp_oid, "Apartment")
            min_villa = _min_price_for_type(db, comp_oid, "Villa")
            min_apt_f = float(min_apt) if min_apt is not None else None
            min_villa_f = float(min_villa) if min_villa is not None else None

            chosen = None
            if user_type:
                ut = str(user_type).strip().lower()
                if ut == "apartment":
                    chosen = min_apt_f
                elif ut == "villa":
                    chosen = min_villa_f
                else:
                    raw = _min_price_for_type(db, comp_oid, ut.capitalize())
                    chosen = float(raw) if raw is not None else None
            else:
                prices = [p for p in [min_apt_f, min_villa_f] if p is not None]
                chosen = min(prices) if prices else None

            if chosen is not None and chosen <= budget:
                candidate_compounds.append({
                    "compound_id": str(comp_oid),
                    "compound_name": (comp.get("name") or comp.get("compound_name") or "").strip(),
                    "location": comp.get("location") or "",
                    "min_apartment_price": min_apt_f,
                    "min_villa_price": min_villa_f,
                    "min_unit_price": chosen,
                })

        candidate_compounds.sort(key=lambda x: x["min_unit_price"])
        state["candidate_compounds"] = candidate_compounds
        return state
    finally:
        client.close()
