import os
import json
from datetime import datetime
from typing import Any, Dict, Optional, List, Tuple

from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
import certifi

from state import AgentState
from main_helpers import ask_ollama



FEATURES_COLLECTION = "compound_features"
COMPOUNDS_COLLECTION = "compounds"

MIN_DESC_CHARS = 200
DESC_MAX_CHARS = 1500


SYSTEM_PROMPT = """
You are SEMSAI Decision-Feature Extractor.

Goal:
Extract EXACTLY 5 decision features that help compare compounds for users (Egypt).

Critical rules:
- Use ONLY the provided text. NEVER invent facts.
- Do NOT output raw marketing adjectives (luxury, elite, unique) unless converted into a comparable decision feature.
- Do NOT output numeric counts unless explicitly stated in text. If not stated, use null.
- Output MUST be valid JSON only.

You MUST return these EXACT 5 keys in this order (always):
1) project_type
2) coastal_water_orientation
3) amenities_breadth
4) density_scale_proxy
5) accessibility_context

For each feature:
- value must be either an object or array or string, not random numbers.
- include 1-3 short evidence quotes from the text.
- confidence 0..1 based on clarity.

Schema:
{
  "compound_name": string|null,
  "features": [
    {"key": "...", "label": "...", "value": ..., "unit": string|null, "confidence": number, "evidence": [string], "why_it_matters": string}
  ],
  "missing_evidence": [string]
}
""".strip()


def _build_prompt(compound_name: Optional[str], description: str) -> str:
    return (
        SYSTEM_PROMPT
        + "\n\n"
        + f"Compound name: {compound_name or ''}\n\n"
        + "Description:\n"
        + description
    )


def _parse_json(raw: str) -> Dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Model did not return JSON.")
        return json.loads(raw[start:end + 1])


def _basic_validate(data: Dict[str, Any]) -> None:
    feats = data.get("features")
    if not isinstance(feats, list) or len(feats) != 5:
        raise ValueError(f"Expected exactly 5 features, got {len(feats) if isinstance(feats, list) else 'N/A'}")


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


def _pick_compounds_list_from_state(state: AgentState) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Picks the best 'post-developer-agent' list from state.
    Returns (key_name, list_of_compounds).
    """
   
    preferred_keys = [
        "final_candidates",
        "shortlisted_compounds",
        "top_compounds",
        "ranked_compounds",
        "selected_compounds",
        "final_compounds",
        # fallback
        "candidate_compounds",
    ]

    for k in preferred_keys:
        v = state.get(k)
        if isinstance(v, list) and len(v) > 0:
            return k, v

    return "none", []


def compound_features_agent(state: AgentState) -> AgentState:
    print("\n--- Post-Developer Compound Features Agent (Ollama) ---")

    
    source_key, compounds_list = _pick_compounds_list_from_state(state)

    if not compounds_list:
        print("No compounds list found in state (post-developer). Nothing to extract.")
        state["compound_features_stats"] = {
            "processed": 0,
            "skipped_existing": 0,
            "skipped_no_desc": 0,
            "failed": 0,
            "source_key": source_key,
        }
        return state

    print(f"Using compounds list from state['{source_key}'] (count={len(compounds_list)})")

    load_dotenv()
    uri = os.getenv("MONGO_URI")
    if not uri:
        print("Missing MONGO_URI.")
        return state

    client = MongoClient(
        uri,
        tls=True,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=60000,
        connectTimeoutMS=60000,
        socketTimeoutMS=60000,
    )

    try:
        db = client.get_default_database()
        db.command("ping")
        print("Mongo connected ✅")

        processed = 0
        skipped_existing = 0
        skipped_no_desc = 0
        failed = 0

       
        limit = int(state.get("features_limit") or 0)

       
        ids: List[ObjectId] = []
        name_by_id: Dict[ObjectId, str] = {}

        for item in compounds_list:
            oid = _to_objectid(item.get("compound_id"))
            if not oid:
                continue
            ids.append(oid)
            nm = (item.get("compound_name") or "").strip()
            if nm:
                name_by_id[oid] = nm

        if not ids:
            print("No valid compound_id found in the chosen list.")
            state["compound_features_stats"] = {
                "processed": 0,
                "skipped_existing": 0,
                "skipped_no_desc": 0,
                "failed": 0,
                "source_key": source_key,
            }
            return state


        existing = set(
            x["compound_id"]
            for x in db[FEATURES_COLLECTION].find({"compound_id": {"$in": ids}}, {"compound_id": 1})
        )

        
        docs = list(
            db[COMPOUNDS_COLLECTION].find(
                {"_id": {"$in": ids}},
                {"name": 1, "compound_name": 1, "description": 1, "desc": 1, "about": 1, "overview": 1, "content": 1},
            )
        )
        doc_by_id: Dict[ObjectId, Dict[str, Any]] = {d["_id"]: d for d in docs}

        for idx, oid in enumerate(ids, start=1):
            if limit and processed >= limit:
                break

            if oid in existing:
                skipped_existing += 1
                continue

            d = doc_by_id.get(oid)
            if not d:
                skipped_no_desc += 1
                continue

            name = name_by_id.get(oid) or (d.get("name") or d.get("compound_name") or "").strip() or None
            desc = (
                (d.get("description") or "").strip()
                or (d.get("desc") or "").strip()
                or (d.get("about") or "").strip()
                or (d.get("overview") or "").strip()
                or (d.get("content") or "").strip()
            )

            if not desc or len(desc) < MIN_DESC_CHARS:
                skipped_no_desc += 1
                continue

            desc_cut = desc[:DESC_MAX_CHARS]

            print(f"\n[{idx}] Extracting features for: {name or str(oid)}")

            try:
                prompt = _build_prompt(name, desc_cut)
                raw = ask_ollama(prompt)

                data = _parse_json(raw)
                _basic_validate(data)

                db[FEATURES_COLLECTION].update_one(
                    {"compound_id": oid},
                    {
                        "$set": {
                            "compound_id": oid,
                            "compound_name": data.get("compound_name") or name,
                            "features": data["features"],
                            "missing_evidence": data.get("missing_evidence", []),
                            "updated_at": datetime.utcnow(),
                            "source": "ollama_post_developer_feature_extractor_v1",
                            "source_state_key": source_key,
                        }
                    },
                    upsert=True,
                )

                processed += 1
                print(f"Saved ✅ (processed={processed})")

            except Exception as e:
                failed += 1
                print(f"Failed ❌ for {name or str(oid)}: {e}")
                db[FEATURES_COLLECTION].update_one(
                    {"compound_id": oid},
                    {
                        "$set": {
                            "compound_id": oid,
                            "compound_name": name,
                            "error": str(e),
                            "updated_at": datetime.utcnow(),
                            "source": "ollama_post_developer_feature_extractor_v1",
                            "source_state_key": source_key,
                        }
                    },
                    upsert=True,
                )

        state["compound_features_stats"] = {
            "processed": processed,
            "skipped_existing": skipped_existing,
            "skipped_no_desc": skipped_no_desc,
            "failed": failed,
            "source_key": source_key,
            "input_count": len(compounds_list),
            "valid_ids": len(ids),
        }
        

        print("\n--- Summary ---")
        print("State list used:", source_key)
        print("Input count:", len(compounds_list))
        print("Valid IDs:", len(ids))
        print("Processed:", processed)
        print("Skipped (existing):", skipped_existing)
        print("Skipped (no desc/missing doc/short):", skipped_no_desc)
        print("Failed:", failed)
        state["next_step"] = "embedding_agent"
        return state

    finally:
        client.close()