from typing import List, Dict
from state import AgentState
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from bson import ObjectId

load_dotenv()


def compound_ranking_agent(state: AgentState) -> AgentState:
    """
    Vector ranking agent using MongoDB Atlas Vector Search.
    Production-safe version.
    """

    client = MongoClient(os.getenv("MONGO_URI"))
    db = client[os.getenv("DATABASE_NAME")]

    # ----------------------------
    # User Embedding
    # ----------------------------
    user_id = state.get("user_id")

    if not user_id:
        print("DEBUG: user_id missing")
        state["ranked_compounds"] = []
        return state

    user = db.users.find_one({"_id": ObjectId(str(user_id))})

    if not user or "embedding" not in user:
        print("DEBUG: user embedding not found")
        state["ranked_compounds"] = []
        return state

    user_embedding = user["embedding"]

    # ----------------------------
    # Compound ID Filtering
    # ----------------------------
    compound_ids_raw = state.get("final_compounds", [])

    compound_ids = []

    for item in compound_ids_raw:
        cid = None

        if isinstance(item, dict):
            cid = item.get("compound_id")
        else:
            cid = item

        if cid:
            try:
                compound_ids.append(ObjectId(str(cid)))
            except Exception:
                pass

    compound_ids = list(set(compound_ids))  # remove duplicates

    if len(compound_ids) == 0:
        print("DEBUG: No valid compound IDs")
        state["ranked_compounds"] = []
        return state

    # ----------------------------
    # Vector Search Pipeline
    # ----------------------------
    pipeline = [
        {
            "$vectorSearch": {
                "index": os.getenv("VECTOR_INDEX"),
                "path": "embedding_features",
                "queryVector": user_embedding,
                "numCandidates": 200,
                "limit": 5,
                "filter": {
                    "compound_id": {"$in": compound_ids}
                }
            }
        },
        {
            "$project": {
                "_id": 1,
                "compound_name": 1,
                "score": {"$meta": "vectorSearchScore"}
            }
        }
    ]

    results = list(db.compound_features.aggregate(pipeline))

    # ----------------------------
    # Ranking Output
    # ----------------------------
    ranked_compounds = []

    for r in results:
        ranked_compounds.append({
            "compound_id": str(r["_id"]),
            "compound_name": r.get("compound_name", "Unknown"),
            "score": float(r.get("score", 0))
        })

    state["ranked_compounds"] = ranked_compounds

    # ----------------------------
    # Print Top 3
    # ----------------------------
    print("\n--- Final Top 3 Ranked Compounds ---")

    if len(ranked_compounds) == 0:
        print("No ranked compounds found.")
    else:
        for i, d in enumerate(ranked_compounds[:3], 1):
            print(f"\n{i}. Compound: {d['compound_name']}")
            print(f"   Compound ID: {d['compound_id']}")
            print(f"   Similarity Score: {d['score']:.6f}")

    return state