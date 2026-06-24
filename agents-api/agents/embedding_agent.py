"""
embedding_agent.py — Build embedding vectors for this session's compound
features so compound_ranking_agent can vector-search against them.

WHY THIS IS SCOPED (vs. the original prototype)
─────────────────────────────────────────────────
The original version scanned the ENTIRE compound_features collection for any
document missing an embedding, and reloaded the SentenceTransformer model
fresh on every call. In a live HTTP request/response cycle (this agent runs
inside a single chat turn via graph.step()) that's a real timeout and cost
risk — it could end up embedding compounds completely unrelated to the
current user's search, and reloading a transformer model from disk on every
turn is slow.

This version:
  1. Only embeds compounds in state.context.final_compounds (i.e. the ones
     this specific search actually surfaced) that don't have an embedding
     yet — still idempotent/incremental, just scoped to what's relevant.
  2. Reuses a process-wide cached embedder singleton (shared with
     user_preferences_agent, which already had this pattern) instead of
     reloading the model every call.
"""

import os
import json
from datetime import datetime
from typing import List

from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
import certifi

from state import AgentState
from agents.user_preferences_agent import _get_embedder


DB_NAME = "semsai"
COLLECTION = "compound_features"
EMBED_MODEL_NAME = "intfloat/e5-base-v2"

FEATURE_KEYS = [
    "project_type",
    "coastal_water_orientation",
    "amenities_breadth",
    "density_scale_proxy",
    "accessibility_context",
]


def _build_feature_embedding_text(doc) -> str:
    parts = []
    for feat in doc.get("features", []):
        if feat.get("key") in FEATURE_KEYS:
            parts.append(
                f"{feat.get('key')}: {json.dumps(feat.get('value'), ensure_ascii=False)}"
            )
    return "\n".join(parts)


def _embed_text(text: str) -> list:
    if not text or not text.strip():
        return []
    vec = _get_embedder().encode(
        "passage: " + text.strip(),
        normalize_embeddings=True,
    )
    return vec.tolist()


def _to_objectid(x) -> ObjectId | None:
    if x is None:
        return None
    if isinstance(x, ObjectId):
        return x
    try:
        return ObjectId(str(x))
    except Exception:
        return None


def embedding_agent(state: AgentState) -> AgentState:
    print("\n--- Embedding Agent ---")

    final_compounds = state.context.final_compounds or []
    compound_ids: List[ObjectId] = []
    for item in final_compounds:
        oid = _to_objectid(item.get("compound_id"))
        if oid:
            compound_ids.append(oid)

    if not compound_ids:
        print("No compound IDs available to embed — skipping.")
        state.next_step = "user_preferences_agent"
        state.embeddings = "done"
        return state

    load_dotenv()
    uri = os.getenv("MONGO_URI")
    if not uri:
        print("Missing MONGO_URI — skipping embedding step.")
        state.next_step = "user_preferences_agent"
        state.embeddings = "done"
        return state

    client = MongoClient(uri, tls=True, tlsCAFile=certifi.where())

    try:
        db = client[DB_NAME]

        docs = list(db[COLLECTION].find({
            "compound_id": {"$in": compound_ids},
            "embedding_features": {"$exists": False},
            "features": {"$exists": True},
        }))

        print(f"Found {len(docs)} compound(s) from this search needing embedding")

        embedded = 0
        failed = 0
        for doc in docs:
            try:
                compound_id = doc["compound_id"]
                feature_text = _build_feature_embedding_text(doc)
                embedding_vector = _embed_text(feature_text)

                db[COLLECTION].update_one(
                    {"compound_id": compound_id},
                    {
                        "$set": {
                            "embedding_features": embedding_vector,
                            "embedding_model": EMBED_MODEL_NAME,
                            "embedding_updated_at": datetime.utcnow(),
                        }
                    },
                )
                embedded += 1
                print(f"✅ Embedded compound {compound_id}")
            except Exception as e:
                failed += 1
                print(f"❌ Embedding failed for {doc.get('compound_id')}: {e}")

        print(f"✅ Embedding step finished — embedded={embedded}, failed={failed}")

    finally:
        client.close()

    state.next_step = "user_preferences_agent"
    state.embeddings = "done"
    return state
