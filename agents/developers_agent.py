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


def get_top_developers_by_score(state: AgentState, limit_count: int = 3):
    candidate_compounds = state.get("candidate_compounds", [])
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

        print("\n🔍 Checking compound documents...")

        # candidate_compounds is expected to contain items with compound_id
        compound_ids_as_objectid = []
        for comp in candidate_compounds:
            comp_id = comp.get("compound_id")
            if comp_id:
                compound_ids_as_objectid.append(_to_objectid_maybe(comp_id))

        if not compound_ids_as_objectid:
            print("❌ No compound_id values found in candidate_compounds")
            return []

        # Fetch compounds from DB using _id
        compounds_from_db = list(
            db["compounds"].find(
                {"_id": {"$in": compound_ids_as_objectid}},
                {"name": 1, "developer_id": 1, "developer_name": 1, "developer_nawy_id": 1}
            )
        )

        if not compounds_from_db:
            print("❌ No compounds matched in DB for provided IDs")
            return []

        # Debug sample
        sample_compound = compounds_from_db[0]
        print("\nSample compound from DB:")
        print(f"  - _id: {sample_compound.get('_id')}")
        print(f"  - name: {sample_compound.get('name')}")
        print(f"  - developer_id: {sample_compound.get('developer_id')}")
        print(f"  - developer_name: {sample_compound.get('developer_name')}")
        print(f"  - All keys: {list(sample_compound.keys())}")

        # Build developer -> compounds mapping from compounds collection
        dev_id_to_compounds = {}
        dev_id_to_name = {}
        dev_ids_obj = []

        print(f"\n🔍 Candidate compounds details:")
        for comp_doc in compounds_from_db:
            dev_id_raw = comp_doc.get("developer_id")
            dev_name = comp_doc.get("developer_name")
            comp_name = comp_doc.get("name")

            print(f"  - {comp_name}: developer_id={dev_id_raw}, developer_name={dev_name}")

            if dev_id_raw:
                dev_id = _to_objectid_maybe(dev_id_raw)
                dev_ids_obj.append(dev_id)

                dev_id_to_compounds.setdefault(str(dev_id), []).append(comp_name)
                if dev_name:
                    dev_id_to_name[str(dev_id)] = dev_name

        # Deduplicate dev ids
        dev_ids_obj = list({str(d): d for d in dev_ids_obj if d is not None}.values())

        print(f"\n🔍 Extracted developer_ids count: {len(dev_ids_obj)}")

        if not dev_ids_obj:
            print("❌ No developer_ids extracted from compounds")
            return []

        # Aggregate developers by _id (matches compounds.developer_id)
        pipeline = [
            {"$match": {"_id": {"$in": dev_ids_obj}}},
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

        # Build results list with compound_count from mapping
        results = []
        found_dev_ids = set()

        for d in dev_docs:
            dev_oid = d.get("_id")
            dev_key = str(dev_oid)
            found_dev_ids.add(dev_key)

            matched_compound_names = dev_id_to_compounds.get(dev_key, [])
            compound_count = len(matched_compound_names)

            results.append({
                "developer_id": dev_oid,  # keep as ObjectId
                "name": d.get("dev_name") or dev_id_to_name.get(dev_key, "Unknown"),
                "Developer_Class": d.get("Developer_Class", "N/A"),
                "class_score": d.get("class_score", 0),
                "compound_count": compound_count,
                "matched_compound_names": matched_compound_names,
                "website": d.get("website")
            })

        # If some developer_ids exist in compounds but not found in developers collection, add fallback rows
        for dev_obj in dev_ids_obj:
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

        # Sort by class_score then compound_count, same intention as your old pipeline
        results.sort(key=lambda r: (r.get("class_score", 0), r.get("compound_count", 0)), reverse=True)

        # Limit
        results = results[:limit_count]

        print(f"✅ Found {len(results)} developers using developer_id mapping")

        if results:
            print("\n📊 Results preview:")
            for r in results:
                print(f"  - {r.get('name')}: {r.get('compound_count')} compounds, Class: {r.get('Developer_Class')}")

        return results

    finally:
        client.close()


def developers_agent(state: AgentState):
    print("\n--- Developer Agent ---")

    candidate_compounds = state.get("candidate_compounds", [])
    if not candidate_compounds:
        print("No candidate compounds found.")
        state["top_developers"] = []
        state["final_compounds"] = []
        return state

    print(f"Searching developers for {len(candidate_compounds)} candidate compounds")

    limit_count = 3
    top_developers = get_top_developers_by_score(state, limit_count)


    state["top_developers"] = top_developers

    
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

    
    final_compounds.sort(key=lambda x: float(x.get("min_unit_price") or 1e18))
    final_compounds = final_compounds[:10]

    state["final_compounds"] = final_compounds

    print(f"\n✅ Final compounds selected: {len(final_compounds)}")
    for x in final_compounds[:10]:
        print(f"  - {x.get('compound_name')} | min_price={x.get('min_unit_price')}")

    state["next_step"] = "compound_features_agent"
    return state