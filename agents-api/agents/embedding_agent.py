import os
import json
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer
import certifi
from state import AgentState



DB_NAME = "semsai"
COLLECTION = "compound_features"

EMBED_MODEL_NAME = "intfloat/e5-base-v2"

# ===============================
# INIT
# ===============================

def embedding_agent(state: AgentState) -> AgentState:
    load_dotenv()

    MONGO_URI = os.getenv("MONGO_URI")

    client = MongoClient(
        MONGO_URI,
        tls=True,
        tlsCAFile=certifi.where()
    )

    db = client[DB_NAME]

    embedder = SentenceTransformer(EMBED_MODEL_NAME)

    print("Embedding pipeline loaded ✅")

    # ===============================
    # FEATURE TEXT BUILDER
    # ===============================

    def build_feature_embedding_text(doc):

        feature_keys = [
            "project_type",
            "coastal_water_orientation",
            "amenities_breadth",
            "density_scale_proxy",
            "accessibility_context",
        ]

        parts = []

        for feat in doc.get("features", []):
            if feat.get("key") in feature_keys:
                parts.append(
                    f"{feat.get('key')}: {json.dumps(feat.get('value'), ensure_ascii=False)}"
                )

        return "\n".join(parts)

    # ===============================
    # EMBEDDING GENERATOR
    # ===============================

    def embed_text(text):

        if not text.strip():
            return []

        text = "passage: " + text

        vec = embedder.encode(
            text,
            normalize_embeddings=True
        )

        return vec.tolist()

    # ===============================
    # PIPELINE SCANNER
    # ===============================

    def run_embedding_pipeline():

        print("\n🚀 Running SEMSAI embedding pipeline...")

        docs = list(db[COLLECTION].find({
            "embedding_features": {"$exists": False},
            "features": {"$exists": True}
        }))

        print(f"Found {len(docs)} compounds needing embedding")

        for doc in docs:

            try:
                compound_id = doc["compound_id"]

                feature_text = build_feature_embedding_text(doc)

                embedding_vector = embed_text(feature_text)

                db[COLLECTION].update_one(
                    {"compound_id": compound_id},
                    {
                        "$set": {
                            "embedding_features": embedding_vector,
                            "embedding_model": EMBED_MODEL_NAME,
                            "embedding_updated_at": datetime.utcnow()
                        }
                    }
                )

                print(f"✅ Embedded compound {compound_id}")

            except Exception as e:
                print("❌ Embedding failed:", e)

        print("✅ Pipeline finished")

    # Run pipeline inside agent
    run_embedding_pipeline()
   

    state["next_step"] = "user_preferences_agent"
    state["embeddings"] = "done"
    return state


