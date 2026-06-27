import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
import certifi

from state import AgentState
from agents.llm_messages import no_compounds_found, best_match_found

FEATURES_COLLECTION = "compound_features"


# ─── Helpers ────────────────────────────────────────────────────────────────

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


def _ranked_list(state: AgentState) -> List[Dict[str, Any]]:
    """
    Return compounds sorted by score descending.
    Prefers ranked_compounds (already sorted by the ranking agent),
    then final_compounds, then candidate_compounds.
    """
    score_keys = ("score", "total_score", "final_score", "rank_score")
    price_keys = ("min_unit_price", "min_price", "price_min")

    for pool in (
        state.context.ranked_compounds,
        state.context.final_compounds,
        state.context.candidate_compounds,
    ):
        if not pool:
            continue
        if any(any(k in c for k in score_keys) for c in pool):
            def _score(c: Dict) -> float:
                for k in score_keys:
                    v = c.get(k)
                    if v is not None:
                        try:
                            return float(v)
                        except Exception:
                            pass
                return 0.0
            return sorted(pool, key=_score, reverse=True)
        # no score — sort cheapest first
        def _price(c: Dict) -> float:
            for k in price_keys:
                v = c.get(k)
                if v is not None:
                    try:
                        return float(v)
                    except Exception:
                        pass
            return 1e18
        return sorted(pool, key=_price)
    return []


def _load_features(db, compound_id: ObjectId) -> Optional[Dict[str, Any]]:
    return db[FEATURES_COLLECTION].find_one(
        {"compound_id": compound_id},
        {"compound_id": 1, "compound_name": 1, "features": 1,
         "missing_evidence": 1, "updated_at": 1},
    )


def _normalise_type(raw: Optional[str]) -> str:
    t = (raw or "apartment").strip().lower()
    if t in ("apt", "apartments"):
        return "apartment"
    if t in ("villas",):
        return "villa"
    return t


def _normalise_payment(raw: Optional[str]) -> Optional[str]:
    p = (raw or "").strip().lower()
    if p in ("cash", "full cash", "c"):
        return "cash"
    if p in ("installment", "installments", "instalments", "plan", "monthly"):
        return "installments"
    return None


def _fetch_units(
    db,
    comp_oid: ObjectId,
    wanted_type: str,
    pay_type: Optional[str],
    budget_val: Optional[float],
) -> List[Dict]:
    """
    Query the units collection for one compound.
    Returns a (possibly empty) list — never raises.
    """
    type_match = {
        "$or": [
            {"type":               {"$regex": f"^{re.escape(wanted_type)}$", "$options": "i"}},
            {"property_type":      {"$regex": f"^{re.escape(wanted_type)}$", "$options": "i"}},
            {"property_type.name": {"$regex": f"^{re.escape(wanted_type)}$", "$options": "i"}},
            {"unit_type":          {"$regex": f"^{re.escape(wanted_type)}$", "$options": "i"}},
        ]
    }
    comp_match = {"compound_id": {"$in": [comp_oid, str(comp_oid)]}}
    query: Dict[str, Any] = {"$and": [comp_match, type_match]}

    if pay_type == "cash":
        query["$and"].append({"sale_type": {"$regex": r"^resale$", "$options": "i"}})
    elif pay_type == "installments":
        query["$and"].append({"sale_type": {"$regex": r"developer", "$options": "i"}})

    units: List[Dict] = []
    try:
        for u in db["units"].find(query):
            if budget_val is not None:
                eff = u.get("price") or u.get("price_min") or u.get("price_max")
                if eff is not None:
                    try:
                        if float(eff) > budget_val:
                            continue
                    except Exception:
                        pass
            units.append(u)
    except Exception as exc:
        print(f"   ⚠️ Unit query failed for {comp_oid}: {exc}")
    return units


def _open_mongo(uri: str) -> MongoClient:
    return MongoClient(
        uri,
        tls=True,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=20_000,
        connectTimeoutMS=20_000,
        socketTimeoutMS=20_000,
    )


# ─── Main agent ─────────────────────────────────────────────────────────────

def final_output_agent(state: AgentState) -> AgentState:
    print("\n" + "=" * 90)
    print("✅ FINAL OUTPUT (SEMSAI) — BEST COMPOUND")
    print("=" * 90)

    purpose      = state.purpose or "N/A"
    location     = state.context.location or "N/A"
    prop_type    = state.context.property_type or "N/A"
    payment_type = state.context.payment_type or "N/A"
    budget       = state.context.budget

    print("\nUser request:")
    print(f"- Purpose: {purpose}")
    print(f"- Location: {location}")
    print(f"- Property type: {prop_type}")
    print(f"- Payment: {payment_type}")
    print(f"- Budget: {_format_money(budget) if budget else 'N/A'}")

    # ── Gather candidates in score order ─────────────────────────────────
    ranked = _ranked_list(state)
    if not ranked:
        print("\n❌ No compound available to output.")
        state.context.final_best_compound = {"status": "no_compound_found"}
        state.agent_message = no_compounds_found(state)
        state.handoff_to_human = True
        state.sync_to_legacy()
        return state

    # ── Prepare filters ───────────────────────────────────────────────────
    load_dotenv()
    uri         = os.getenv("MONGO_URI")
    wanted_type = _normalise_type(state.context.property_type)
    pay_type    = _normalise_payment(state.context.payment_type)
    budget_val: Optional[float] = None
    if budget is not None:
        try:
            budget_val = float(budget)
        except Exception:
            pass

    # ── Walk ranked list: pick first compound that has matching units ─────
    best: Optional[Dict[str, Any]]  = None
    candidate_units: List[Dict]     = []
    features_doc: Optional[Dict]    = None
    comp_oid: Optional[ObjectId]    = None

    if uri:
        client = _open_mongo(uri)
        try:
            db = client.get_default_database()

            for idx, compound in enumerate(ranked):
                c_oid = (
                    _to_objectid(compound.get("compound_id"))
                    or _to_objectid(compound.get("_id"))
                )
                name = (
                    compound.get("compound_name") or compound.get("name") or "Unknown"
                ).strip()
                rank_label = f"#{idx + 1}"

                units = _fetch_units(db, c_oid, wanted_type, pay_type, budget_val)

                if units:
                    print(
                        f"\n✅ {rank_label} {name} — "
                        f"found {len(units)} matching unit(s) → selected"
                    )
                    best            = compound
                    comp_oid        = c_oid
                    candidate_units = units
                    break
                else:
                    print(f"   ⏭  {rank_label} {name} — 0 matching units, trying next…")

            # Nothing had units → fall back to the top-ranked compound
            if best is None:
                best     = ranked[0]
                comp_oid = (
                    _to_objectid(best.get("compound_id"))
                    or _to_objectid(best.get("_id"))
                )
                print(
                    f"\n⚠️ No compound had matching units under budget. "
                    f"Defaulting to top-ranked: "
                    f"{(best.get('compound_name') or best.get('name') or 'Unknown').strip()}"
                )

            # Load features for the selected compound
            if comp_oid:
                features_doc = _load_features(db, comp_oid)

        finally:
            client.close()

    else:
        # No DB URI — just use the top-ranked compound
        best     = ranked[0]
        comp_oid = (
            _to_objectid(best.get("compound_id"))
            or _to_objectid(best.get("_id"))
        )
        print("\n⚠️ MONGO_URI not set — skipping unit check, using top-ranked compound")

    # ── Display selected compound ─────────────────────────────────────────
    compound_name = (best.get("compound_name") or best.get("name") or "Unknown").strip()
    dev_name  = (best.get("developer_name") or "").strip()
    loc       = (best.get("location") or "").strip()
    reasons   = best.get("reasons") or best.get("why") or []
    min_price = (
        best.get("min_unit_price")
        or best.get("min_price")
        or best.get("price_min")
    )
    score = (
        best.get("score")
        or best.get("total_score")
        or best.get("final_score")
        or best.get("rank_score")
    )
    feats = (features_doc or {}).get("features") or []

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
        print(f"Min unit price: {_format_money(min_price)}")
    if comp_oid:
        print(f"Compound ID: {str(comp_oid)}")

    if isinstance(reasons, list) and reasons:
        print("\nWhy this is the best match:")
        for r in reasons[:5]:
            print(f"  • {_short(r)}")
    else:
        print("\nWhy this is the best match:")
        print("  • Selected as top option based on available scoring/filters.")

    if isinstance(feats, list) and feats:
        print("\nDecision features (from description):")
        for f in feats:
            k    = f.get("key")
            v    = f.get("value")
            conf = f.get("confidence")
            ev   = f.get("evidence") or []
            ev1  = ev[0] if isinstance(ev, list) and ev else None
            print(f"  - {k}: {v} (conf={conf})")
            if ev1:
                print(f'    evidence: "{_short(ev1, 180)}"')
    else:
        print("\nDecision features: (not found in DB yet)")

    print(f"\n✅ Found {len(candidate_units)} candidate unit(s) in {compound_name}.")

    # ── Persist ───────────────────────────────────────────────────────────
    state.context.final_best_compound = {
        "compound_id":    str(comp_oid) if comp_oid else None,
        "compound_name":  compound_name,
        "developer_name": dev_name or None,
        "location":       loc or None,
        "min_unit_price": min_price,
        "score":          score,
        "reasons":        reasons if isinstance(reasons, list) else [],
        "features":       feats   if isinstance(feats,   list) else [],
    }
    state.context.selected_compound = {
        "id":   str(comp_oid) if comp_oid else None,
        "name": compound_name,
    }
    state.context.candidate_units = candidate_units
    state.agent_message = best_match_found(compound_name, state)
    state.sync_to_legacy()
    return state
