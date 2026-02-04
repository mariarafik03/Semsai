import os
from typing import Any, Dict, List
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
from state import AgentState


def format_price(value: Any) -> str:
    """Format numbers with comma separators (every 3 digits)."""
    if value is None:
        return "N/A"
    try:
        return f"{int(float(value)):,}"
    except Exception:
        return "N/A"


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _units_match(comp_oid: ObjectId) -> Dict[str, Any]:
    """
    Match units linked to this compound when compound_id is stored as:
    - ObjectId
    - string
    """
    comp_str = str(comp_oid)
    return {"compound_id": {"$in": [comp_oid, comp_str]}}


def compounds_agent(state: AgentState):
    print("\n--- Compounds Agent ---")

    load_dotenv()
    uri = os.getenv("MONGO_URI")
    if not uri:
        print("Missing MONGO_URI. Skipping compound lookup.")
        return state

    client = MongoClient(uri)
    try:
        db = client.get_default_database()

        budget = state.get("budget")
        if budget is None:
            downpayment = _safe_float(state.get("Downpayment"), 0.0)
            monthly_install = _safe_float(state.get("monthlyinstall"), 0.0)

            plan = db["payments"].find_one({}, sort=[("duration", -1)], projection={"duration": 1})
            if not plan or not plan.get("duration"):
                print("No payment plan found in payments collection (duration missing).")
                return state

            months = int(plan["duration"])
            budget = downpayment + monthly_install * months
            state["budget"] = budget

        budget = float(budget)

        location = state.get("location")
        comp_query: Dict[str, Any] = {}
        if location:
            comp_query["location"] = {"$regex": str(location), "$options": "i"}

        compounds = list(db["compounds"].find(comp_query, {"name": 1, "compound_name": 1, "location": 1}))

        candidate_compounds: List[Dict[str, Any]] = []

        for comp in compounds:
            comp_oid = comp["_id"]

            min_unit = db["units"].find_one(
                _units_match(comp_oid),
                sort=[("price", 1)],
                projection={"price": 1, "compound_id": 1}
            )

            if not min_unit:
                continue

            price = min_unit.get("price")
            if price is None:
                continue

            min_price = float(price)

            if min_price <= budget:
                candidate_compounds.append({
                    "compound_id": comp_oid,
                    "compound_name": (comp.get("name") or comp.get("compound_name") or "").strip(),
                    "location": comp.get("location") or "",
                    "min_unit_price": min_price
                })

        candidate_compounds.sort(key=lambda x: x["min_unit_price"])
        state["candidate_compounds"] = candidate_compounds

        print(f"Top compounds within budget: {len(candidate_compounds)}")

        for c in candidate_compounds[:10]:
            print(
                f"- {c['compound_name']} | {c['location']} | "
                f"min={format_price(c['min_unit_price'])}"
            )

        print("\n--- Final Plan ---")
        print(f"Purpose: {state.get('purpose')}")
        print(f"Budget: {format_price(state.get('budget'))}")
        print(f"Downpayment: {format_price(state.get('Downpayment'))}")
        print(f"Monthly Installment: {format_price(state.get('monthlyinstall'))}")
        print(f"Location: {state.get('location')}")
        print(f"Payment Type: {state.get('payment_type')}")
        print(f"Type of Property: {state.get('typeofproperty')}")

        return state

    finally:
        client.close()
