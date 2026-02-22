"""
Developers Agent — matches compounds to developers & ranks them.
No user input needed — runs autonomously.
"""
import os
from typing import Any, Dict, List

from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
import certifi


def _to_objectid(x):
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


def developers_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Find top developers for candidate compounds."""
    candidates = state.get("candidate_compounds", [])
    if not candidates:
        state["top_developers"] = []
        state["final_candidates"] = []
        return state

    load_dotenv()
    uri = os.getenv("MONGO_URI")
    if not uri:
        return state

    client = MongoClient(uri, tlsCAFile=certifi.where())
    try:
        db = client.get_default_database()

        compound_ids = [_to_objectid(c.get("compound_id")) for c in candidates if c.get("compound_id")]
        if not compound_ids:
            return state

        compounds_from_db = list(db["compounds"].find(
            {"_id": {"$in": compound_ids}},
            {"name": 1, "developer_id": 1, "developer_name": 1}
        ))
        if not compounds_from_db:
            return state

        dev_id_to_compounds: Dict[str, List[str]] = {}
        dev_id_to_name: Dict[str, str] = {}
        dev_ids_obj = []

        for comp_doc in compounds_from_db:
            dev_id_raw = comp_doc.get("developer_id")
            dev_name = comp_doc.get("developer_name")
            comp_name = comp_doc.get("name")

            if dev_id_raw:
                dev_id = _to_objectid(dev_id_raw)
                dev_ids_obj.append(dev_id)
                dev_id_to_compounds.setdefault(str(dev_id), []).append(comp_name or "")
                if dev_name:
                    dev_id_to_name[str(dev_id)] = dev_name

        dev_ids_obj = list({str(d): d for d in dev_ids_obj if d is not None}.values())
        if not dev_ids_obj:
            return state

        pipeline = [
            {"$match": {"_id": {"$in": dev_ids_obj}}},
            {"$addFields": {
                "class_score": {"$switch": {
                    "branches": [
                        {"case": {"$eq": ["$Developer_Class", "A+"]}, "then": 5},
                        {"case": {"$eq": ["$Developer_Class", "A"]}, "then": 4},
                        {"case": {"$eq": ["$Developer_Class", "B"]}, "then": 3},
                        {"case": {"$eq": ["$Developer_Class", "C"]}, "then": 2},
                        {"case": {"$eq": ["$Developer_Class", "D"]}, "then": 1},
                    ],
                    "default": 0
                }}
            }},
            {"$project": {"_id": 1, "dev_name": 1, "Developer_Class": 1, "class_score": 1, "website": 1}},
        ]

        dev_docs = list(db["developers"].aggregate(pipeline))

        results = []
        found_ids = set()
        for d in dev_docs:
            key = str(d.get("_id"))
            found_ids.add(key)
            matched = dev_id_to_compounds.get(key, [])
            results.append({
                "developer_id": key,
                "name": d.get("dev_name") or dev_id_to_name.get(key, "Unknown"),
                "Developer_Class": d.get("Developer_Class", "N/A"),
                "class_score": d.get("class_score", 0),
                "compound_count": len(matched),
                "matched_compound_names": matched,
                "website": d.get("website"),
            })

        for dev_obj in dev_ids_obj:
            key = str(dev_obj)
            if key not in found_ids:
                results.append({
                    "developer_id": key,
                    "name": dev_id_to_name.get(key, "Unknown"),
                    "Developer_Class": "N/A",
                    "class_score": 0,
                    "compound_count": len(dev_id_to_compounds.get(key, [])),
                    "matched_compound_names": dev_id_to_compounds.get(key, []),
                    "website": None,
                })

        results.sort(key=lambda r: (r.get("class_score", 0), r.get("compound_count", 0)), reverse=True)
        results = results[:3]

        state["top_developers"] = results
        state["final_candidates"] = results
        return state

    finally:
        client.close()
