import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
import certifi

from state import AgentState

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
    return (t[: n - 3] + "...") if len(t) > n else t


def _pick_best_item(state: AgentState) -> Optional[Dict[str, Any]]:
    """
    Prefer ranked_compounds/top_compounds; otherwise fallback to final_compounds/candidate_compounds.
    If list has a score, pick max score; else pick lowest min price.
    """
    for key in ["ranked_compounds", "top_compounds", "final_compounds", "candidate_compounds"]:
        items = state.get(key)
        if not (isinstance(items, list) and items):
            continue

        # score can be under different names (keep backward compatibility)
        score_keys = ("score", "total_score", "final_score", "rank_score")

        if any(any(sk in x and x.get(sk) is not None for sk in score_keys) for x in items):
            def sk(x: Dict[str, Any]) -> float:
                for kk in score_keys:
                    if kk in x and x.get(kk) is not None:
                        try:
                            return float(x.get(kk))
                        except Exception:
                            pass
                return 0.0

            return max(items, key=sk)

        # price can be under different names
        price_keys = ("min_unit_price", "min_price", "price_min")

        def pk(x: Dict[str, Any]) -> float:
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
        {"compound_id": 1, "compound_name": 1, "features": 1, "missing_evidence": 1, "updated_at": 1},
    )


def final_output_agent(state: AgentState) -> AgentState:
    print("\n" + "=" * 90)
    print("✅ FINAL OUTPUT (SEMSAI) — BEST COMPOUND")
    print("=" * 90)

    # Header summary
    purpose = state.get("purpose") or "N/A"
    location = state.get("location") or "N/A"
    prop_type = state.get("typeofproperty") or "N/A"
    payment_type = state.get("payment_type") or "N/A"
    budget = state.get("budget")

    print("\nUser request:")
    print(f"- Purpose: {purpose}")
    print(f"- Location: {location}")
    print(f"- Property type: {prop_type}")
    print(f"- Payment: {payment_type}")
    print(f"- Budget: {_format_money(budget) if budget else 'N/A'}")

    # Pick best compound
    best = _pick_best_item(state)
    if not best:
        print("\n❌ No compound available to output.")
        # Set a sentinel so the router doesn't loop back here forever,
        # then signal abort so the graph terminates cleanly.
        state["final_best_compound"] = {"status": "no_compound_found"}
        state["final_report"] = "No compound available."
        state["abort"] = True
        return state

    compound_name = (best.get("compound_name") or best.get("name") or "Unknown").strip()
    dev_name = (best.get("developer_name") or "").strip()
    loc = (best.get("location") or "").strip()

    # pick price from any known key
    min_price = best.get("min_unit_price")
    if min_price is None:
        min_price = best.get("min_price")
    if min_price is None:
        min_price = best.get("price_min")

    # pick score from any known key
    score = best.get("score")
    if score is None:
        score = best.get("total_score")
    if score is None:
        score = best.get("final_score")
    if score is None:
        score = best.get("rank_score")

    reasons = best.get("reasons") or best.get("why") or []

    comp_oid = _to_objectid(best.get("compound_id")) or _to_objectid(best.get("_id"))

    # Load features from DB (if possible)
    features_doc = None
    load_dotenv()
    uri = os.getenv("MONGO_URI")

    if comp_oid and uri:
        client = MongoClient(
            uri,
            tls=True,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=20000,
            connectTimeoutMS=20000,
            socketTimeoutMS=20000,
        )
        try:
            db = client.get_default_database()
            features_doc = _load_features(db, comp_oid)
        finally:
            client.close()

    feats = (features_doc or {}).get("features") or []

    # Print BEST recommendation
    print("\n" + "-" * 90)
    print("🏆 Best compound for this user:")
    print("-" * 90)
    print(f"Name: {compound_name}")
    if score is not None:
        print(f"Score: {score}")
    if dev_name:
        print(f"Developer: {dev_name}")
    if loc:
        print(f"Location: {loc}")
    if min_price is not None:
        print(f"Min unit price (from units): {_format_money(min_price)}")
    if comp_oid:
        print(f"Compound ID: {str(comp_oid)}")

    # Reasons
    if isinstance(reasons, list) and reasons:
        print("\nWhy this is the best match:")
        for r in reasons[:5]:
            print(f"  • {_short(r)}")
    else:
        print("\nWhy this is the best match:")
        print("  • Selected as top option based on available scoring/filters (budget/type/location).")

    # Extracted decision features
    if isinstance(feats, list) and feats:
        print("\nDecision features (from description):")
        for f in feats:
            k = f.get("key")
            v = f.get("value")
            conf = f.get("confidence")
            ev = f.get("evidence") or []
            ev1 = ev[0] if isinstance(ev, list) and ev else None
            print(f"  - {k}: {v} (conf={conf})")
            if ev1:
                print(f"    evidence: “{_short(ev1, 180)}”")
    else:
        print("\nDecision features: (not found in DB yet)")

    # Save for frontend/logging
    state["final_best_compound"] = {
        "compound_id": str(comp_oid) if comp_oid else None,
        "compound_name": compound_name,
        "developer_name": dev_name or None,
        "location": loc or None,
        "min_unit_price": min_price,
        "score": score,
        "reasons": reasons if isinstance(reasons, list) else [],
        "features": feats if isinstance(feats, list) else [],
    }

    # --------------------------------------------------------------------------------
    # Save selected compound and fetch candidate units for unit_agent
    # --------------------------------------------------------------------------------
    state["selected_compound"] = {"id": str(comp_oid), "name": compound_name}
    candidate_units = []
    
    if uri and comp_oid:
        import re
        try:
            client = MongoClient(
                uri,
                tls=True,
                tlsCAFile=certifi.where(),
                serverSelectionTimeoutMS=20000,
                connectTimeoutMS=20000,
                socketTimeoutMS=20000,
            )
            db = client.get_default_database()
            
            wanted_type = str(state.get("typeofproperty") or "Apartment").strip().lower()
            if wanted_type in ["apt", "apartments"]: wanted_type = "apartment"
            if wanted_type in ["villas"]: wanted_type = "villa"
            
            budget_val = state.get("budget")
            if budget_val is not None:
                try: budget_val = float(budget_val)
                except: budget_val = None
            
            pay_type = state.get("payment_type")
            if pay_type:
                pay_type = str(pay_type).strip().lower()
                if pay_type in ["cash", "full cash", "c"]: pay_type = "cash"
                elif pay_type in ["installment", "installments", "instalments", "plan", "monthly"]: pay_type = "installments"
                else: pay_type = None

            type_match = {
                "$or": [
                    {"type": {"$regex": f"^{re.escape(wanted_type)}$", "$options": "i"}},
                    {"property_type": {"$regex": f"^{re.escape(wanted_type)}$", "$options": "i"}},
                    {"unit_type": {"$regex": f"^{re.escape(wanted_type)}$", "$options": "i"}},
                ]
            }

            sale_match = None
            if pay_type == "cash":
                sale_match = {"sale_type": {"$regex": r"^resale$", "$options": "i"}}
            elif pay_type == "installments":
                sale_match = {"sale_type": {"$regex": r"developer", "$options": "i"}}
                
            comp_str = str(comp_oid)
            comp_match = {"compound_id": {"$in": [comp_oid, comp_str]}}

            query = {"$and": [comp_match, type_match]}
            if sale_match:
                query["$and"].append(sale_match)

            units_cursor = db["units"].find(query)
            
            for u in units_cursor:
                eff_price = u.get("price") or u.get("price_min") or u.get("price_max")
                if budget_val is not None and eff_price is not None:
                    try:
                        if float(eff_price) > budget_val:
                            continue
                    except: pass
                candidate_units.append(u)
                
            print(f"\n✅ Found {len(candidate_units)} candidate units in {compound_name} matching your budget and preferences.")
            
        finally:
            client.close()

    state["candidate_units"] = candidate_units
    state["final_report"] = f"BEST: {compound_name}"
    return state