import os
from typing import List, Dict, Optional
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

from state import AgentState
from agents.llm_messages import (
    ranking_no_compounds, ranking_no_user_id, ranking_unavailable,
    ranking_no_valid_compounds, ranking_no_vector_results, ranking_complete,
    ranking_failed,
)

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
        state.agent_message = ranking_no_compounds(state)
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
            state.agent_message = ranking_no_user_id(state)
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
            state.agent_message = ranking_unavailable(state)
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
            state.agent_message = ranking_no_valid_compounds(state)
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
                    # compound_id is the ACTUAL compound ObjectId stored in the
                    # compound_features document — this is what units reference.
                    "compound_id": 1,
                    "compound_name": 1,
                    "score": {"$meta": "vectorSearchScore"}
                }
            }
        ]

        results = list(db.compound_features.aggregate(pipeline))

        # Build a lookup map from compound_id → full compound data so we can
        # enrich the ranked list with location, developer, min_price, etc.
        # These are needed by final_output_agent._fetch_units().
        final_compounds_map = {
            str(c.get("compound_id") or c.get("_id")): c
            for c in state.context.final_compounds
        }

        # ----------------------------
        # 6. Format Results
        # ----------------------------
        ranked_compounds = []

        for r in results:
            # compound_id field holds the actual compound ObjectId.
            # Fall back to _id only if compound_id is missing (shouldn't happen).
            actual_compound_id = r.get("compound_id") or r["_id"]
            cid_str = str(actual_compound_id)

            # Start with whatever we know from the vector search result
            entry = {
                "compound_id": cid_str,
                "compound_name": r.get("compound_name", "Unknown"),
                "score": float(r.get("score", 0)),
            }

            # Merge full compound metadata from final_compounds so that
            # final_output_agent has developer_name, location, min_price, etc.
            base = final_compounds_map.get(cid_str, {})
            for key in ("developer_name", "location", "min_price", "min_unit_price",
                        "price_min", "sale_type", "property_type", "reasons", "why"):
                if key in base:
                    entry.setdefault(key, base[key])

            ranked_compounds.append(entry)

        # Store in context
        state.context.ranked_compounds = ranked_compounds

        # ----------------------------
        # 7. Print Top 3
        # ----------------------------
        print(f"\n✅ Ranked {len(ranked_compounds)} compounds by semantic similarity")
        print("\n--- Top 3 Ranked Compounds ---")

        if len(ranked_compounds) == 0:
            print("No ranked compounds found.")
            state.agent_message = ranking_no_vector_results(state)
        else:
            for i, d in enumerate(ranked_compounds[:3], 1):
                print(f"\n{i}. {d['compound_name']}")
                print(f"   Compound ID: {d['compound_id']}")
                print(f"   Similarity Score: {d['score']:.6f}")
            
            state.agent_message = ranking_complete(len(ranked_compounds), state)

        # ----------------------------
        # 8. Sync to Legacy & Return
        # ----------------------------
        state.sync_to_legacy()
        return state

    except Exception as e:
        print(f"❌ Vector search failed: {e}")
        
        # Fallback: pass compounds through unranked
        state.context.ranked_compounds = state.context.final_compounds
        state.agent_message = ranking_failed(str(e), state)
        state.sync_to_legacy()
        return state

    finally:
        client.close()