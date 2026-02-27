import os
import traceback
from typing import List, Dict
from state import AgentState
from pymongo import MongoClient
from dotenv import load_dotenv
from bson import ObjectId
import certifi

load_dotenv()

VECTOR_INDEX_NAME = os.getenv("VECTOR_INDEX", "vector_index")


def compound_ranking_agent(state: AgentState) -> AgentState:
    """
    Vector ranking agent using MongoDB Atlas Vector Search.
    Production-safe version with error handling.
    """

    try:
        uri = os.getenv("MONGO_URI")
        if not uri:
            print("DEBUG: MONGO_URI missing")
            state["ranked_compounds"] = []
            return state

        client = MongoClient(uri, tlsCAFile=certifi.where())
        db = client.get_default_database()

        # ----------------------------
        # User Embedding
        # ----------------------------
        user_id = state.get("user_id")

        if not user_id:
            print("DEBUG: user_id missing")
            state["ranked_compounds"] = []
            return state

        # Handle both ObjectId and guest user IDs
        user = None
        user_id_str = str(user_id).strip()

        if ObjectId.is_valid(user_id_str):
            user = db.users.find_one({"_id": ObjectId(user_id_str)})

        if not user:
            # Try finding by user_id field (for guest users)
            user = db.users.find_one({"user_id": user_id_str})

        if not user or "embedding" not in user:
            print(f"DEBUG: user embedding not found for user_id={user_id_str}")
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
                    "index": VECTOR_INDEX_NAME,
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

        client.close()
        return state

    except Exception as e:
        print(f"ERROR in compound_ranking_agent: {e}")
        traceback.print_exc()
        # Don't crash the pipeline — return empty results so it can continue
        state["ranked_compounds"] = []
        return state