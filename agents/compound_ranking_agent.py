import os
import re
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
import certifi

from state import AgentState

FEATURES_COLLECTION = "compound_features"

FEATURE_KEYS = [
    "project_type",
    "coastal_water_orientation",
    "amenities_breadth",
    "density_scale_proxy",
    "accessibility_context",
]


# -----------------------
# Helpers
# -----------------------

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


def _as_text(v: Any) -> str:
    """Flatten value into searchable text."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, (int, float, bool)):
        return str(v)
    if isinstance(v, list):
        return " | ".join(_as_text(x) for x in v)
    if isinstance(v, dict):
        parts = []
        for k, vv in v.items():
            parts.append(f"{k}:{_as_text(vv)}")
        return " | ".join(parts)
    return str(v)


def _get_feature_map(features_doc: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Convert doc["features"] list into key -> feature_obj map.
    """
    out: Dict[str, Dict[str, Any]] = {}
    feats = features_doc.get("features") or []
    if not isinstance(feats, list):
        return out
    for f in feats:
        if isinstance(f, dict) and f.get("key"):
            out[str(f["key"])] = f
    return out


def _contains_any(text: str, keywords: List[str]) -> bool:
    t = (text or "").lower()
    return any(k.lower() in t for k in keywords)


def _confidence(feature_obj: Dict[str, Any]) -> float:
    c = feature_obj.get("confidence")
    try:
        c = float(c)
        if c < 0:
            c = 0.0
        if c > 1:
            c = 1.0
        return c
    except Exception:
        return 0.0


def _extract_percent(text: str) -> Optional[float]:
    # finds things like "18%" or "built-up area of 18%"
    m = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def _score_feature(
    key: str,
    feature_obj: Optional[Dict[str, Any]],
    prefs: Dict[str, Any],
) -> Tuple[float, str]:
    """
    Return (score 0..1, reason)
    Simple heuristic scoring. You can improve later.
    """
    if not feature_obj:
        return 0.5, "missing feature -> neutral"

    value_text = _as_text(feature_obj.get("value"))
    evidence_text = _as_text(feature_obj.get("evidence"))
    combined = (value_text + " " + evidence_text).strip().lower()

    base = 0.5
    conf = _confidence(feature_obj)

    wants_mixed_use = prefs.get("wants_mixed_use")
    has_kids = prefs.get("has_kids")
    top_priority = prefs.get("top_priority")  # "commute" | "quiet_low_density" | "amenities" | "balanced" | None
    wants_water = prefs.get("wants_water_view")

    if key == "project_type":
        if wants_mixed_use is True:
            if _contains_any(combined, ["mixed-use", "mixed use", "commercial", "offices", "business", "retail"]):
                return 1.0 * conf + base * (1 - conf), "matches mixed-use preference"
            if _contains_any(combined, ["residential-only", "residential only"]):
                return 0.2 * conf + base * (1 - conf), "residential-only vs mixed-use preference"
            return 0.6 * conf + base * (1 - conf), "unclear mixed-use -> slight positive"
        if wants_mixed_use is False:
            if _contains_any(combined, ["mixed-use", "mixed use"]):
                return 0.4 * conf + base * (1 - conf), "mixed-use but user prefers residential-only"
            return 0.8 * conf + base * (1 - conf), "residential aligns"
        return base, "no preference -> neutral"

    if key == "coastal_water_orientation":
        if wants_water is False:
            return 0.6 * conf + base * (1 - conf), "water not important -> neutral/ok"
        if wants_water is True:
            if _contains_any(combined, ["sea", "beach", "lagoon", "water", "lake", "mediterranean", "shore"]):
                return 1.0 * conf + base * (1 - conf), "water orientation matches"
            return 0.2 * conf + base * (1 - conf), "no water evidence"
        return base, "no preference -> neutral"

    if key == "amenities_breadth":
        if has_kids is True:
            if _contains_any(combined, ["school", "nursery", "kids", "park", "play", "clubhouse", "sports", "clinic", "medical"]):
                return 1.0 * conf + base * (1 - conf), "family-friendly amenities mentioned"
            return 0.5 * conf + base * (1 - conf), "amenities unclear for family"

        if top_priority == "amenities":
            if len(combined) > 0:
                return 0.9 * conf + base * (1 - conf), "amenities emphasized"
            return 0.3 * conf + base * (1 - conf), "amenities missing"

        if len(combined) > 0:
            return 0.75 * conf + base * (1 - conf), "amenities present"
        return base, "amenities missing -> neutral"

    if key == "density_scale_proxy":
        if top_priority == "quiet_low_density":
            if _contains_any(combined, ["low density", "built-up", "built up", "green", "landscape", "open space", "18%"]):
                pct = _extract_percent(combined)
                if pct is not None:
                    if pct <= 25:
                        return 1.0 * conf + base * (1 - conf), f"low built-up ({pct}%) supports quiet/privacy"
                    if pct >= 60:
                        return 0.2 * conf + base * (1 - conf), f"high built-up ({pct}%) hurts quiet/privacy"
                return 0.85 * conf + base * (1 - conf), "density proxy supports quiet/privacy"
            return 0.55 * conf + base * (1 - conf), "density unclear"

        if len(combined) > 0:
            return 0.65 * conf + base * (1 - conf), "density info present"
        return base, "missing density -> neutral"

    if key == "accessibility_context":
        if top_priority == "commute":
            if _contains_any(combined, ["minutes", "road", "ring", "suez", "90", "central", "adjacent", "near", "close"]):
                return 1.0 * conf + base * (1 - conf), "accessibility supports commute"
            return 0.3 * conf + base * (1 - conf), "accessibility unclear for commute"

        if len(combined) > 0:
            return 0.75 * conf + base * (1 - conf), "accessibility info present"
        return base, "missing accessibility -> neutral"

    return base, "unknown key -> neutral"


def _derive_prefs_from_state(user_prefs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Best-effort: build simple prefs object used by scoring.
    Uses preferences if present, otherwise uses normalized_signals.
    """
    prefs = (user_prefs.get("preferences") or {}).copy()
    signals = user_prefs.get("normalized_signals") or {}

    if "wants_mixed_use" not in prefs or prefs.get("wants_mixed_use") is None:
        nm = (signals.get("wants_mixed_use") or {}).get("normalized")
        if isinstance(nm, bool):
            prefs["wants_mixed_use"] = nm
        elif isinstance(nm, str):
            if nm.lower() in {"true", "yes"}:
                prefs["wants_mixed_use"] = True
            elif nm.lower() in {"false", "no"}:
                prefs["wants_mixed_use"] = False

    if "has_kids" not in prefs or prefs.get("has_kids") is None:
        nm = (signals.get("has_kids") or {}).get("normalized")
        if isinstance(nm, bool):
            prefs["has_kids"] = nm
        elif isinstance(nm, str):
            if nm.lower() in {"true", "yes", "a"}:
                prefs["has_kids"] = True
            elif nm.lower() in {"false", "no", "b"}:
                prefs["has_kids"] = False

    if "wants_water_view" not in prefs or prefs.get("wants_water_view") is None:
        nm = (signals.get("wants_water_view") or {}).get("normalized")
        if isinstance(nm, bool):
            prefs["wants_water_view"] = nm
        elif isinstance(nm, str):
            if nm.lower() in {"true", "yes", "a"}:
                prefs["wants_water_view"] = True
            elif nm.lower() in {"false", "no", "b"}:
                prefs["wants_water_view"] = False

    if not prefs.get("top_priority"):
        prefs["top_priority"] = "balanced"

    return prefs


# -----------------------
# Agent
# -----------------------

def compound_ranking_agent(state: AgentState) -> AgentState:
    print("\n--- Compound Ranking Agent ---")

    final_compounds = state.get("final_compounds", [])
    if not isinstance(final_compounds, list) or not final_compounds:
        print("No final_compounds found in state. Nothing to rank.")
        state["ranked_compounds"] = []
        state["top_compounds"] = []
        state["next_step"] = "final_output_agent"  # ✅ FIX
        return state

    user_prefs = state.get("user_preferences") or {}
    weights = user_prefs.get("ranking_weights") or {}

    if not isinstance(weights, dict) or set(weights.keys()) != set(FEATURE_KEYS):
        print("⚠️ ranking_weights missing/invalid. Using default weights.")
        weights = {
            "project_type": 0.20,
            "coastal_water_orientation": 0.05,
            "amenities_breadth": 0.25,
            "density_scale_proxy": 0.25,
            "accessibility_context": 0.25,
        }

    prefs = _derive_prefs_from_state(user_prefs)

    ids: List[ObjectId] = []
    info_by_id: Dict[ObjectId, Dict[str, Any]] = {}

    for c in final_compounds:
        oid = _to_objectid(c.get("compound_id"))
        if not oid:
            continue
        ids.append(oid)
        info_by_id[oid] = c

    if not ids:
        print("No valid compound_id in final_compounds.")
        state["ranked_compounds"] = []
        state["top_compounds"] = []
        state["next_step"] = "final_output_agent"  # ✅ FIX
        return state

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

        feature_docs = list(db[FEATURES_COLLECTION].find({"compound_id": {"$in": ids}}))
        feat_by_id = {d["compound_id"]: d for d in feature_docs if d.get("compound_id")}

        ranked: List[Dict[str, Any]] = []

        for oid in ids:
            base_info = info_by_id.get(oid, {})
            name = base_info.get("compound_name") or str(oid)

            fdoc = feat_by_id.get(oid)
            if not fdoc:
                ranked.append({
                    "compound_id": oid,
                    "compound_name": name,
                    "score": 0.5,          # ✅ ADD
                    "total_score": 0.5,    # keep
                    "breakdown": {},
                    "reasons": ["no features doc -> neutral score"],
                })
                continue

            fmap = _get_feature_map(fdoc)
            breakdown: Dict[str, float] = {}
            reasons: List[str] = []

            total = 0.0
            for k in FEATURE_KEYS:
                sc, reason = _score_feature(k, fmap.get(k), prefs)
                w = float(weights.get(k) or 0.0)
                breakdown[k] = round(sc, 4)
                total += sc * w
                reasons.append(f"{k}: {reason} (score={round(sc,2)}, w={round(w,2)})")

            final_score = round(total, 4)

            ranked.append({
                "compound_id": oid,
                "compound_name": name,
                "developer_name": base_info.get("developer_name"),
                "location": base_info.get("location"),
                "min_unit_price": base_info.get("min_unit_price"),
                "score": final_score,        # ✅ ADD (used by final_output_agent)
                "total_score": final_score,  # keep
                "breakdown": breakdown,
                "reasons": reasons[:6],
            })

        ranked.sort(key=lambda x: float(x.get("score") or 0), reverse=True)  # ✅ use score

        state["ranked_compounds"] = ranked
        state["top_compounds"] = ranked[:3]

        print("\n✅ Ranked compounds (Top 5):")
        for i, r in enumerate(ranked[:5], 1):
            print(f"{i}) {r['compound_name']} | score={r['score']} | min_price={r.get('min_unit_price')}")

        state["next_step"] = "final_output_agent"
        return state

    finally:
        client.close()