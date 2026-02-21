import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from pymongo import MongoClient
import certifi

from state import AgentState


# -----------------------
# Helpers
# -----------------------

def format_price(value: Any) -> str:
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


def _normalize_type(t: Any) -> Optional[str]:
    if not t:
        return None
    s = str(t).strip().lower()
    if s in {"apt", "apartment", "apartments"}:
        return "Apartment"
    if s in {"villa", "villas"}:
        return "Villa"
    return str(t).strip()


def _normalize_payment_type(p: Any) -> Optional[str]:
    """
    Returns: "cash" | "installments" | None
    """
    if not p:
        return None
    s = str(p).strip().lower()
    if s in {"cash", "full cash", "c"}:
        return "cash"
    if s in {"installment", "installments", "instalments", "plan", "monthly"}:
        return "installments"
    return None


def _sale_type_match_from_payment(payment_type: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Units have sale_type like:
      - "Resale"
      - "Developer Sale"
    If payment_type is:
      - cash        -> filter Resale only
      - installments-> filter Developer Sale only
      - None/other  -> no filter
    """
    if payment_type == "cash":
        return {"sale_type": {"$regex": r"^resale$", "$options": "i"}}

    if payment_type == "installments":
        # include common variations "Developer Sale", "Developer", etc.
        return {"sale_type": {"$regex": r"developer", "$options": "i"}}

    return None


def _compute_budget_if_missing(db, state: AgentState) -> Optional[float]:
    budget = state.get("budget")
    if budget is not None:
        try:
            return float(budget)
        except Exception:
            return None

    downpayment = _safe_float(state.get("Downpayment"), 0.0)
    monthly_install = _safe_float(state.get("monthlyinstall"), 0.0)

    plan = db["payments"].find_one({}, sort=[("duration", -1)], projection={"duration": 1})
    if not plan or not plan.get("duration"):
        return None

    months = int(plan["duration"])
    budget = downpayment + monthly_install * months
    state["budget"] = budget
    return float(budget)


def _build_units_pipeline(
    wanted_type: str,
    location: Optional[str],
    budget: float,
    payment_type: Optional[str],
    limit: int = 300
) -> List[Dict[str, Any]]:

    # match type across possible fields
    type_match = {
        "$or": [
            {"type": {"$regex": f"^{re.escape(wanted_type)}$", "$options": "i"}},
            {"property_type": {"$regex": f"^{re.escape(wanted_type)}$", "$options": "i"}},
            {"unit_type": {"$regex": f"^{re.escape(wanted_type)}$", "$options": "i"}},
        ]
    }

    # location match on UNITS
    loc_match: Optional[Dict[str, Any]] = None
    if location:
        loc_match = {"location": {"$regex": str(location), "$options": "i"}}

    # sale_type filter based on payment choice
    sale_match = _sale_type_match_from_payment(payment_type)

    base_and: List[Dict[str, Any]] = [type_match]
    if loc_match:
        base_and.append(loc_match)
    if sale_match:
        base_and.append(sale_match)

    # Extract "$oid" safely WITHOUT using compound_id.$oid (Mongo forbids field paths starting with $)
    oid_from_export_obj = {
        "$let": {
            "vars": {"arr": {"$objectToArray": "$compound_id"}},
            "in": {
                "$first": {
                    "$map": {
                        "input": {
                            "$filter": {
                                "input": "$$arr",
                                "as": "it",
                                "cond": {"$eq": ["$$it.k", "$oid"]},
                            }
                        },
                        "as": "f",
                        "in": "$$f.v",
                    }
                }
            },
        }
    }

    # Build a string version of compound id regardless of storage shape
    compound_oid_str_expr = {
        "$switch": {
            "branches": [
                {"case": {"$eq": [{"$type": "$compound_id"}, "objectId"]}, "then": {"$toString": "$compound_id"}},
                {"case": {"$eq": [{"$type": "$compound_id"}, "string"]}, "then": "$compound_id"},
                {"case": {"$eq": [{"$type": "$compound_id"}, "object"]}, "then": oid_from_export_obj},
            ],
            "default": None,
        }
    }

    pipeline: List[Dict[str, Any]] = [
        {"$match": {"$and": base_and}},

        # effective_price = price OR price_min OR price_max
        {
            "$addFields": {
                "effective_price": {"$ifNull": ["$price", {"$ifNull": ["$price_min", "$price_max"]}]}
            }
        },
        {"$match": {"effective_price": {"$ne": None, "$lte": float(budget)}}},

        # normalize compound_id to a string we can convert to ObjectId
        {"$addFields": {"compound_oid_str": compound_oid_str_expr}},

        # convert to ObjectId (if convertible)
        {
            "$addFields": {
                "compound_oid": {
                    "$cond": [
                        {
                            "$and": [
                                {"$ne": ["$compound_oid_str", None]},
                                {"$ne": ["$compound_oid_str", ""]},
                                {"$eq": [{"$strLenCP": "$compound_oid_str"}, 24]},
                            ]
                        },
                        {"$toObjectId": "$compound_oid_str"},
                        None,
                    ]
                }
            }
        },
        {"$match": {"compound_oid": {"$ne": None}}},

        # group by compound_oid to get min price per compound
        {
            "$group": {
                "_id": "$compound_oid",
                "min_unit_price": {"$min": "$effective_price"},
                "sample_unit_location": {"$first": "$location"},
                "sample_sale_type": {"$first": "$sale_type"},
            }
        },

        {"$sort": {"min_unit_price": 1}},
        {"$limit": int(limit)},

        # lookup compound info
        {
            "$lookup": {
                "from": "compounds",
                "localField": "_id",
                "foreignField": "_id",
                "as": "compound_doc",
            }
        },
        {"$unwind": {"path": "$compound_doc", "preserveNullAndEmptyArrays": True}},

        {
            "$project": {
                "_id": 0,
                "compound_id": "$_id",
                "min_unit_price": 1,
                "sale_type_used": "$sample_sale_type",
                "compound_name": {"$ifNull": ["$compound_doc.name", "$compound_doc.compound_name"]},
                "compound_location": {"$ifNull": ["$compound_doc.location", "$sample_unit_location"]},
            }
        },
    ]

    return pipeline


# -----------------------
# Agent
# -----------------------

def compounds_agent(state: AgentState):
    print("\n--- Compounds Agent ---")

    load_dotenv()
    uri = os.getenv("MONGO_URI")
    if not uri:
        print("Missing MONGO_URI. Skipping compound lookup.")
        return state

    client = MongoClient(
        uri,
        tls=True,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=20000,
        connectTimeoutMS=20000,
    )

    try:
        db = client.get_default_database()

        wanted_type = _normalize_type(state.get("typeofproperty")) or "Apartment"
        location = state.get("location")  # e.g. "New Cairo"
        payment_type = _normalize_payment_type(state.get("payment_type"))  # "cash" | "installments" | None

        budget = _compute_budget_if_missing(db, state)
        if budget is None:
            print("Budget missing/invalid and could not be computed.")
            return state

        pipeline = _build_units_pipeline(
            wanted_type=wanted_type,
            location=location,
            budget=budget,
            payment_type=payment_type,
            limit=300
        )

        results = list(db["units"].aggregate(pipeline, allowDiskUse=True))

        candidate_compounds: List[Dict[str, Any]] = []
        for r in results:
            name = (r.get("compound_name") or "").strip()
            loc = (r.get("compound_location") or "").strip()

            candidate_compounds.append({
                "compound_id": r.get("compound_id"),
                "compound_name": name if name else "Unknown Compound",
                "location": loc,
                "wanted_type": wanted_type,
                "payment_type_used": payment_type or "any",
                "sale_type_used": r.get("sale_type_used"),
                "min_unit_price": float(r.get("min_unit_price") or 0),
            })

        state["candidate_compounds"] = candidate_compounds

        print(f"Type used for comparison: {wanted_type}")
        print(f"Location filter (units): {location}")
        print(f"Payment type (state): {state.get('payment_type')} -> normalized: {payment_type or 'any'}")
        print(f"Budget: {format_price(budget)}")
        print(f"Top compounds within budget: {len(candidate_compounds)}")

        for c in candidate_compounds[:10]:
            print(
                f"- {c['compound_name']} | {c['location']} | "
                f"type={c['wanted_type']} | pay={c['payment_type_used']} | "
                f"sale_type={c.get('sale_type_used')} | min_price={format_price(c['min_unit_price'])}"
            )

        state["next_step"] = "developer_agent"
        return state

    finally:
        client.close()