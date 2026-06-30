import os
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
from state import AgentState


CLASS_RANK = {
    "A+": 5,
    "A": 4,
    "B": 3,
    "C": 2,
    "D": 1
}


def _to_objectid_maybe(x):
    """Convert to ObjectId if possible, otherwise return original."""
    if x is None:
        return None
    if isinstance(x, ObjectId):
        return x
    if isinstance(x, str):
        try:
            return ObjectId(x)
        except Exception:
            return x
    return x


def get_top_developers_by_score(state: AgentState):
    # FIX: Pydantic attribute access; context first, legacy fallback
    candidate_compounds = (
        state.context.candidate_compounds
        or state.candidate_compounds
        or []
    )
    if not candidate_compounds:
        print("No candidate compounds found.")
        return []

    load_dotenv()
    uri = os.getenv("MONGO_URI")
    if not uri:
        print("No MONGO_URI found in environment")
        return []

    import certifi
    client = MongoClient(uri, tlsCAFile=certifi.where())

    try:
        db = client.get_default_database()

        # ----------------------------------------
        # Collect compound IDs
        # ----------------------------------------
        compound_ids = []
        for comp in candidate_compounds:
            comp_id = comp.get("compound_id")
            if comp_id:
                compound_ids.append(_to_objectid_maybe(comp_id))

        if not compound_ids:
            print("❌ No compound IDs found.")
            return []

        # ----------------------------------------
        # Fetch compounds
        # ----------------------------------------
        compounds_from_db = list(
            db["compounds"].find(
                {"_id": {"$in": compound_ids}},
                {
                    "name": 1,
                    "developer_id": 1,
                    "developer_name": 1
                }
            )
        )

        if not compounds_from_db:
            print("❌ No compounds matched in DB.")
            return []

        # ----------------------------------------
        # Build developer mappings
        # ----------------------------------------
        dev_id_to_compounds = {}
        dev_id_to_name = {}
        dev_ids = []

        for comp_doc in compounds_from_db:
            dev_id_raw = comp_doc.get("developer_id")
            dev_name = comp_doc.get("developer_name")
            comp_name = comp_doc.get("name")

            if not dev_id_raw:
                continue

            dev_id = _to_objectid_maybe(dev_id_raw)
            dev_key = str(dev_id)

            dev_ids.append(dev_id)
            dev_id_to_compounds.setdefault(dev_key, []).append(comp_name)

            if dev_name:
                dev_id_to_name[dev_key] = dev_name

        # Deduplicate developer IDs
        dev_ids = list({str(d): d for d in dev_ids if d}.values())

        if not dev_ids:
            print("❌ No developer IDs extracted.")
            return []

        # ----------------------------------------
        # Fetch developers
        # ----------------------------------------
        pipeline = [
            {"$match": {"_id": {"$in": dev_ids}}},
            {
                "$addFields": {
                    "class_score": {
                        "$switch": {
                            "branches": [
                                {"case": {"$eq": ["$Developer_Class", "A+"]}, "then": 5},
                                {"case": {"$eq": ["$Developer_Class", "A"]},  "then": 4},
                                {"case": {"$eq": ["$Developer_Class", "B"]},  "then": 3},
                                {"case": {"$eq": ["$Developer_Class", "C"]},  "then": 2},
                                {"case": {"$eq": ["$Developer_Class", "D"]},  "then": 1},
                            ],
                            "default": 0
                        }
                    }
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "dev_name": 1,
                    "Developer_Class": 1,
                    "class_score": 1,
                    "website": 1
                }
            }
        ]

        dev_docs = list(db["developers"].aggregate(pipeline))

        results = []
        found_dev_ids = set()

        for d in dev_docs:
            dev_oid = d.get("_id")
            dev_key = str(dev_oid)
            found_dev_ids.add(dev_key)

            matched_compounds = dev_id_to_compounds.get(dev_key, [])
            compound_count = len(matched_compounds)

            results.append({
                "developer_id": dev_oid,
                "name": d.get("dev_name") or dev_id_to_name.get(dev_key, "Unknown"),
                "Developer_Class": d.get("Developer_Class", "N/A"),
                "class_score": d.get("class_score", 0),
                "compound_count": compound_count,
                "matched_compound_names": matched_compounds,
                "website": d.get("website")
            })

        # ----------------------------------------
        # Fallback if developer missing in collection
        # ----------------------------------------
        for dev_obj in dev_ids:
            dev_key = str(dev_obj)
            if dev_key not in found_dev_ids:
                results.append({
                    "developer_id": dev_obj,
                    "name": dev_id_to_name.get(dev_key, "Unknown"),
                    "Developer_Class": "N/A",
                    "class_score": 0,
                    "compound_count": len(dev_id_to_compounds.get(dev_key, [])),
                    "matched_compound_names": dev_id_to_compounds.get(dev_key, []),
                    "website": None
                })

        if not results:
            return []

        # ----------------------------------------
        # 🔥 NEW LOGIC: Return ONLY highest class
        # ----------------------------------------

        # Sort by class_score first, then compound_count
        results.sort(
            key=lambda r: (r.get("class_score", 0), r.get("compound_count", 0)),
            reverse=True
        )

        highest_score = results[0].get("class_score", 0)

        # Keep only developers with highest class_score
        results = [
            r for r in results
            if r.get("class_score", 0) == highest_score
        ]

        print(f"\n🏆 Returning ALL developers with highest class_score = {highest_score}")
        for r in results:
            print(f"  - {r.get('name')} | Class: {r.get('Developer_Class')} | Compounds: {r.get('compound_count')}")

        return results

    finally:
        client.close()


def developers_agent(state: AgentState):
    print("\n--- Developer Agent ---")

    # FIX: Pydantic attribute access; check both context and legacy
    candidate_compounds = (
        state.context.candidate_compounds
        or state.candidate_compounds
        or []
    )
    if not candidate_compounds:
        state.top_developers = []
        state.final_compounds = []
        state.context.final_compounds = []
        state.sync_to_legacy()
        return state

    print(f"Searching developers for {len(candidate_compounds)} candidate compounds")

    top_developers = get_top_developers_by_score(state)
    # FIX: write to both legacy and context
    state.top_developers = top_developers
    state.context.top_developers = top_developers

    # ----------------------------------------
    # Match compounds belonging to top developers
    # ----------------------------------------
    matched_names = set()
    for dev in top_developers:
        for nm in (dev.get("matched_compound_names") or []):
            if isinstance(nm, str) and nm.strip():
                matched_names.add(" ".join(nm.strip().lower().split()))

    final_compounds = []
    for c in candidate_compounds:
        cname = c.get("compound_name")
        if not cname:
            continue

        cname_norm = " ".join(str(cname).strip().lower().split())

        if cname_norm in matched_names:
            final_compounds.append({
                "compound_id": c.get("compound_id"),
                "compound_name": c.get("compound_name"),
                "location": c.get("location"),
                "min_unit_price": c.get("min_unit_price"),
            })

    # Sort compounds by price ascending
    final_compounds.sort(
        key=lambda x: float(x.get("min_unit_price") or 1e18)
    )

    # FIX: write to BOTH legacy and context so the router can see final_compounds
    state.final_compounds = final_compounds
    state.context.final_compounds = final_compounds

    print(f"\n\u2705 Final compounds selected: {len(final_compounds)}")
    for x in final_compounds:
        print(f"  - {x.get('compound_name')} | min_price={x.get('min_unit_price')}")

    state.next_step = "compound_features_agent"
    state.current_phase = "comparison"
    print("✓ Phase transition: search → comparison")
    state.sync_to_legacy()
    return state