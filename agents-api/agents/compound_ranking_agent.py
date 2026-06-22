import os
from typing import List, Dict, Optional
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

from state import AgentState

load_dotenv()


def compound_ranking_agent(state: AgentState) -> AgentState:
    """
    Vector ranking agent using MongoDB Atlas Vector Search.
    Uses state.context architecture (production-safe).
    """
    print("\n--- Compound Ranking Agent (Vector Search) ---")

    # Phase transition: comparison → presentation
    # Set early so any exit path (fallback, error, success) routes to final_output_agent
    state.current_phase = "presentation"
    print("✓ Phase transition: comparison → presentation")

    # ----------------------------
    # 1. Check Prerequisites
    # ----------------------------
    if not state.context.final_compounds:
        print("⚠️ No final_compounds available in context. Skipping ranking.")
        state.agent_message = "No compounds to rank yet."
        state.sync_to_legacy()
        return state

    # ----------------------------
    # 2. MongoDB Connection
    # ----------------------------
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client.get_default_database()

    try:
        # ----------------------------
        # 3. User Embedding Lookup
        # ----------------------------
        user_id = state.user_id  # FIX: AgentState uses user_id, not session_id
        
        if not user_id:
            print("⚠️ session_id missing, cannot fetch user embedding")
            state.agent_message = "User identification missing for personalized ranking."
            state.sync_to_legacy()
            return state

        # Try ObjectId first, fallback to string lookup
        user_id_str = str(user_id).strip()
        if ObjectId.is_valid(user_id_str):
            user = db.users.find_one({"_id": ObjectId(user_id_str)})
        else:
            user = db.users.find_one({"user_id": user_id_str})

        if not user or "embedding" not in user:
            print("⚠️ User embedding not found in DB, cannot perform vector search")
            # Fallback: pass compounds through unranked
            state.context.ranked_compounds = state.context.final_compounds
            state.agent_message = "Personalized ranking unavailable. Showing filtered results."
            state.sync_to_legacy()
            return state

        user_embedding = user["embedding"]

        # ----------------------------
        # 4. Extract Compound IDs from final_compounds
        # ----------------------------
        compound_ids = []
        
        for item in state.context.final_compounds:
            cid = item.get("compound_id") or item.get("_id")
            
            if cid:
                try:
                    compound_ids.append(ObjectId(str(cid)))
                except Exception:
                    pass

        # Remove duplicates
        compound_ids = list(set(compound_ids))

        if len(compound_ids) == 0:
            print("⚠️ No valid compound IDs found in final_compounds")
            state.agent_message = "No valid compounds to rank."
            state.sync_to_legacy()
            return state

        print(f"✅ Found {len(compound_ids)} compounds to rank via vector search")

        # ----------------------------
        # 5. Vector Search Pipeline
        # ----------------------------
        vector_index = os.getenv("VECTOR_INDEX", "compound_features_vector_index")
        
        pipeline = [
            {
                "$vectorSearch": {
                    "index": vector_index,
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
        # 6. Format Results
        # ----------------------------
        ranked_compounds = []

        for r in results:
            ranked_compounds.append({
                "compound_id": str(r["_id"]),
                "compound_name": r.get("compound_name", "Unknown"),
                "score": float(r.get("score", 0))
            })

        # Store in context
        state.context.ranked_compounds = ranked_compounds

        # ----------------------------
        # 7. Print Top 3
        # ----------------------------
        print(f"\n✅ Ranked {len(ranked_compounds)} compounds by semantic similarity")
        print("\n--- Top 3 Ranked Compounds ---")

        if len(ranked_compounds) == 0:
            print("No ranked compounds found.")
            state.agent_message = "Vector search returned no results."
        else:
            for i, d in enumerate(ranked_compounds[:3], 1):
                print(f"\n{i}. {d['compound_name']}")
                print(f"   Compound ID: {d['compound_id']}")
                print(f"   Similarity Score: {d['score']:.6f}")
            
            state.agent_message = f"Ranked {len(ranked_compounds)} compounds by your preferences."

        # ----------------------------
        # 8. Sync to Legacy & Return
        # ----------------------------
        state.sync_to_legacy()
        return state

    except Exception as e:
        print(f"❌ Vector search failed: {e}")
        
        # Fallback: pass compounds through unranked
        state.context.ranked_compounds = state.context.final_compounds
        state.agent_message = f"Ranking failed ({str(e)}). Showing unranked results."
        state.sync_to_legacy()
        return state

    finally:
        client.close()