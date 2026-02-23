"""
Final Output Agent — picks the best compound and produces a summary report.
Autonomous (no user input needed). Adapted from agents/final_output_agent.py.
"""
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
import certifi


FEATURES_COLLECTION = "compound_features"


def _to_objectid(x: Any) -> Optional[ObjectId]:
    if x is None:
        return None
    if isinstance(x, ObjectId):
        return x
    if isinstance(x, dict) and "$oid" in x:
        x = x["$oid"]
    if isinstance(x, str):
        s = x.strip()
        if len(s) == 24:
            try:
                return ObjectId(s)
            except Exception:
                return None
    return None


def _format_money(v: Any) -> str:
    try:
        if v is None:
            return "N/A"
        return f"{int(float(v)):,} EGP"
    except Exception:
        return "N/A"


def _short(s: Any, n: int = 160) -> str:
    t = (s or "").strip()
    if not t:
        return ""
    return (t[:n - 3] + "...") if len(t) > n else t


def _pick_best_item(state: dict) -> Optional[Dict[str, Any]]:
    """Pick the best compound from available lists."""
    for key in ["ranked_compounds", "top_compounds", "final_compounds", "candidate_compounds"]:
        items = state.get(key)
        if not (isinstance(items, list) and items):
            continue

        score_keys = ("score", "total_score", "final_score", "rank_score")
        if any(any(sk in x and x.get(sk) is not None for sk in score_keys) for x in items):
            def sk(x):
                for kk in score_keys:
                    if kk in x and x.get(kk) is not None:
                        try:
                            return float(x.get(kk))
                        except Exception:
                            pass
                return 0.0
            return max(items, key=sk)

        price_keys = ("min_unit_price", "min_price", "price_min")
        def pk(x):
            for kk in price_keys:
                if x.get(kk) is not None:
                    try:
                        return float(x.get(kk))
                    except Exception:
                        pass
            return 1e18
        return min(items, key=pk)

    return None


def _load_features(db, compound_id: ObjectId) -> Optional[Dict[str, Any]]:
    return db[FEATURES_COLLECTION].find_one(
        {"compound_id": compound_id},
        {"compound_id": 1, "compound_name": 1, "features": 1, "missing_evidence": 1},
    )


def _load_units(db, compound_id: ObjectId, wanted_type: str | None = None, limit: int = 10) -> list[Dict[str, Any]]:
    """Load the cheapest units for a compound. Falls back to all types if filter yields 0."""
    base_query: Dict[str, Any] = {
        "compound_id": {"$in": [compound_id, str(compound_id)]},
        "price": {"$exists": True, "$ne": None, "$gt": 0},
    }

    # Try with type filter first
    if wanted_type:
        wt = wanted_type.strip()
        variants = list({wt, wt.lower(), wt.upper(), wt.capitalize(), wt.title()})
        filtered_query = {**base_query, "$or": [
            {"type": {"$in": variants}},
            {"property_type": {"$in": variants}},
            {"unit_type": {"$in": variants}},
        ]}
        count = db["units"].count_documents(filtered_query)
        if count > 0:
            query = filtered_query
            print(f"      _load_units: type filter '{wt}' matched {count} units")
        else:
            query = base_query
            print(f"      _load_units: type filter '{wt}' matched 0 -> fallback to all types")
    else:
        query = base_query

    units = list(
        db["units"]
        .find(query, {"price": 1, "area": 1, "type": 1, "property_type": 1, "unit_type": 1, "bedrooms": 1, "bathrooms": 1, "name": 1})
        .sort("price", 1)
        .limit(limit)
    )
    results = []
    for u in units:
        utype = u.get("type") or u.get("property_type") or u.get("unit_type") or ""
        results.append({
            "unit_id": str(u.get("_id", "")),
            "type": utype,
            "price": u.get("price"),
            "area": u.get("area"),
            "bedrooms": u.get("bedrooms"),
            "bathrooms": u.get("bathrooms"),
            "name": u.get("name") or "",
        })
    return results


def final_output_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Pick best compound, format report. Runs autonomously."""
    print("\n" + "=" * 70)
    print("✅ FINAL OUTPUT (SEMSAI) — BEST COMPOUND")
    print("=" * 70)

    purpose = state.get("purpose") or "N/A"
    location = state.get("location") or "N/A"
    prop_type = state.get("typeofproperty") or "N/A"
    payment_type = state.get("payment_type") or "N/A"
    budget = state.get("budget")

    print(f"\nUser: purpose={purpose}, location={location}, type={prop_type}, payment={payment_type}, budget={_format_money(budget)}")

    best = _pick_best_item(state)
    if not best:
        print("\n❌ No compound available to output.")
        state["final_report"] = "No compound available."
        state["final_best_compound"] = None
        return state

    compound_name = (best.get("compound_name") or best.get("name") or "Unknown").strip()
    dev_name = (best.get("developer_name") or "").strip()
    loc = (best.get("location") or "").strip()

    min_price = best.get("min_unit_price") or best.get("min_price") or best.get("price_min")
    score = best.get("score") or best.get("total_score") or best.get("final_score")
    reasons = best.get("reasons") or []

    comp_oid = _to_objectid(best.get("compound_id")) or _to_objectid(best.get("_id"))

    # Load features from DB
    feats = []
    load_dotenv()
    uri = os.getenv("MONGO_URI")

    # Also enrich top_compounds with units
    wanted_type = state.get("typeofproperty")

    if comp_oid and uri:
        client = MongoClient(
            uri, tls=True, tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=20000,
            connectTimeoutMS=20000, socketTimeoutMS=20000,
        )
        try:
            db = client.get_default_database()
            features_doc = _load_features(db, comp_oid)
            feats = (features_doc or {}).get("features") or []

            # Fetch units for the best compound
            best_units = _load_units(db, comp_oid, wanted_type)
            print(f"   🔍 Best compound units loaded: {len(best_units)} (type filter: {wanted_type})")

            # Enrich top_compounds with units
            top_compounds = state.get("top_compounds") or []
            for tc in top_compounds:
                tc_oid = _to_objectid(tc.get("compound_id"))
                if tc_oid:
                    tc_units = _load_units(db, tc_oid, wanted_type)
                    tc["units"] = tc_units
                    print(f"   🔍 {tc.get('compound_name')}: {len(tc_units)} units (oid={tc_oid})")
                else:
                    tc["units"] = []
                    print(f"   ⚠️ {tc.get('compound_name')}: no valid compound_id -> {tc.get('compound_id')}")
            state["top_compounds"] = top_compounds
        finally:
            client.close()
    else:
        best_units = []

    print(f"\n🏆 Best: {compound_name} | score={score} | price={_format_money(min_price)}")
    if dev_name:
        print(f"   Developer: {dev_name}")
    if reasons:
        for r in reasons[:3]:
            print(f"   • {_short(r)}")

    # Save for frontend
    state["final_best_compound"] = {
        "compound_id": str(comp_oid) if comp_oid else None,
        "compound_name": compound_name,
        "developer_name": dev_name or None,
        "location": loc or None,
        "min_unit_price": min_price,
        "score": score,
        "reasons": reasons if isinstance(reasons, list) else [],
        "features": feats if isinstance(feats, list) else [],
        "units": best_units,
    }
    state["final_report"] = f"BEST: {compound_name}"

    return state
