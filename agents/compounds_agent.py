import os
import re
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


def _min_price_for_type(db, comp_oid: ObjectId, wanted_type: str) -> Any:
    """
    Find minimum unit price for a given property type (Apartment/Villa/etc.)
    across possible fields: type, property_type, unit_type.
    """
    unit_query: Dict[str, Any] = _units_match(comp_oid)
    unit_query["$or"] = [
        {"type": {"$regex": f"^{re.escape(wanted_type)}$", "$options": "i"}},
        {"property_type": {"$regex": f"^{re.escape(wanted_type)}$", "$options": "i"}},
        {"unit_type": {"$regex": f"^{re.escape(wanted_type)}$", "$options": "i"}},
    ]

    min_unit = db["units"].find_one(
        unit_query,
        sort=[("price", 1)],
        projection={"price": 1}
    )
    if not min_unit:
        return None
    return min_unit.get("price")


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
        user_type = state.get("typeofproperty")  # user chosen type (Apartment/Villa/...)

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

            # ✅ get min apartment & min villa for EACH compound
            min_apartment_price_raw = _min_price_for_type(db, comp_oid, "Apartment")
            min_villa_price_raw = _min_price_for_type(db, comp_oid, "Villa")

            min_apartment_price = float(min_apartment_price_raw) if min_apartment_price_raw is not None else None
            min_villa_price = float(min_villa_price_raw) if min_villa_price_raw is not None else None

            # ✅ choose which price to filter/sort on based on user_type
            chosen_min_price: Any = None
            if user_type:
                if str(user_type).strip().lower() == "apartment":
                    chosen_min_price = min_apartment_price
                elif str(user_type).strip().lower() == "villa":
                    chosen_min_price = min_villa_price
                else:
                    raw_other = _min_price_for_type(db, comp_oid, str(user_type))
                    chosen_min_price = float(raw_other) if raw_other is not None else None
            else:
                prices = [p for p in [min_apartment_price, min_villa_price] if p is not None]
                chosen_min_price = min(prices) if prices else None

            if chosen_min_price is None:
                continue

            if chosen_min_price <= budget:
                candidate_compounds.append({
                    "compound_id": comp_oid,
                    "compound_name": (comp.get("name") or comp.get("compound_name") or "").strip(),
                    "location": comp.get("location") or "",
                    "min_apartment_price": min_apartment_price,
                    "min_villa_price": min_villa_price,
                    "min_unit_price": chosen_min_price,
                })

        candidate_compounds.sort(key=lambda x: x["min_unit_price"])
        state["candidate_compounds"] = candidate_compounds

        print(f"Top compounds within budget: {len(candidate_compounds)}")

        # ✅ print with difference between villa and apartment
        for c in candidate_compounds[:10]:
            apt = c.get("min_apartment_price")
            villa = c.get("min_villa_price")

            if apt is not None and villa is not None:
                diff = float(villa) - float(apt)
                diff_pct = (diff / float(apt) * 100.0) if float(apt) > 0 else None
                diff_txt = format_price(diff)
                pct_txt = f"{diff_pct:.1f}%" if diff_pct is not None else "N/A"
            else:
                diff_txt = "N/A"
                pct_txt = "N/A"

            print(
                f"- {c['compound_name']} | {c['location']} | "
                f"chosen_min={format_price(c['min_unit_price'])} | "
                f"apt_min={format_price(apt)} | "
                f"villa_min={format_price(villa)} | "
                f"Δ(villa-apt)={diff_txt} ({pct_txt})"
            )

        state["next_step"] = "comparing_agent"
        return state

    finally:
        client.close()