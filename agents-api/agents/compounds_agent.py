import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from pymongo import MongoClient
import certifi

from state import AgentState


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _safe_price(val: Any) -> Optional[int]:
    """Convert price to int safely."""
    if val is None:
        return None

    if isinstance(val, (int, float)):
        return int(val)

    # extract digits from string
    digits = "".join(filter(str.isdigit, str(val)))
    if digits:
        return int(digits)

    return None


def _extract_compound_names(state: dict) -> List[str]:
    """Extract compound names from previous agent."""
    final_candidates = state.get("final_candidates") or []

    names = []
    for dev in final_candidates:
        arr = dev.get("matched_compound_names") or []
        for n in arr:
            if isinstance(n, str) and n.strip():
                names.append(n.strip())

    # deduplicate
    seen = set()
    out = []
    for n in names:
        k = n.lower()
        if k not in seen:
            seen.add(k)
            out.append(n)

    return out


def _fetch_compounds(db, names: List[str]) -> List[Dict[str, Any]]:
    """Fetch compounds with price + description."""

    if not names:
        return []

    # try exact match
    docs = list(db["compounds"].find(
        {"name": {"$in": names}},
        {"_id": 1, "name": 1, "price": 1, "description": 1}
    ))

    # fallback regex
    if len(docs) < len(names):
        ors = []
        for n in names:
            ors.append({"name": {"$regex": f"^{re.escape(n)}$", "$options": "i"}})

        docs = list(db["compounds"].find(
            {"$or": ors},
            {"_id": 1, "name": 1, "price": 1, "description": 1}
        ))

    results = []
    for d in docs:
        price = _safe_price(d.get("price"))

        results.append({
            "compound_id": str(d["_id"]),
            "name": d.get("name"),
            "price": price,
            "description": d.get("description") or ""
        })

    return results


# ─────────────────────────────────────────────────────────────
# Agent
# ─────────────────────────────────────────────────────────────

def compounds_agent(state: AgentState) -> AgentState:
    print("\n--- compounds_agent ---")

    # Prevent re-fetch unless needed
    if state.get("candidate_compounds") is not None:
        print("Skipping fetch (already exists)")
        return state

    # Get compound names
    compound_names = _extract_compound_names(state)

    if not compound_names:
        print("❌ No compound names found")
        state["candidate_compounds"] = []
        return state

    print(f"Found {len(compound_names)} compound names")

    # DB connection
    load_dotenv()
    uri = os.getenv("MONGO_URI")

    if not uri:
        print("❌ Missing MONGO_URI")
        state["candidate_compounds"] = []
        return state

    client = MongoClient(uri, tlsCAFile=certifi.where())

    try:
        db = client.get_default_database()

        compounds = _fetch_compounds(db, compound_names)

        if not compounds:
            print("❌ No compounds fetched from DB")
            state["candidate_compounds"] = []
            return state

        print(f"✅ Retrieved {len(compounds)} compounds")

        # ─────────────────────────────────────────────
        # 🔥 PRICE ANALYSIS (CRITICAL PART)
        # ─────────────────────────────────────────────

        prices = [c["price"] for c in compounds if c.get("price")]

        if prices:
            min_price = min(prices)
            state["min_price_in_market"] = min_price

            user_budget = state.get("budget")

            if user_budget:
                state["budget_valid"] = user_budget >= min_price
                print(f"💰 Budget: {user_budget:,}")
                print(f"🏷️ Min price: {min_price:,}")
                print(f"✅ Budget valid: {state['budget_valid']}")
            else:
                state["budget_valid"] = None

        else:
            print("⚠️ No price data available")
            state["min_price_in_market"] = None
            state["budget_valid"] = True  # don't block flow

        # Save compounds
        state["candidate_compounds"] = compounds

        return state

    finally:
        client.close()