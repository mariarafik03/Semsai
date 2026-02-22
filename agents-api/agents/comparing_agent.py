"""
Comparing Agent — selects TOP 3 compounds using LLM + fallback scoring.
No user input needed — runs autonomously.
"""
import os
import re
import json
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from pymongo import MongoClient
import certifi

from llm_helper import ask_llm


# ---------- Prompt ----------

BEST_ONLY_PROMPT = """
!!!! CRITICAL INSTRUCTION !!!!
DO NOT WRITE ANY TEXT BEFORE OR AFTER THE JSON.
YOUR ENTIRE RESPONSE MUST BE VALID JSON AND NOTHING ELSE.

TASK: Analyze compounds and return TOP 3 as pure JSON only.

Purpose meanings:
- end_user → family living, comfort, community
- investment → ROI, scale, mixed-use, market strength
- business → offices, commercial, accessibility

REQUIRED OUTPUT:
{
  "top_choices": [
    {"rank": 1, "compound_id": "ID", "name": "NAME", "purpose_used": "PURPOSE", "reasons": ["r1","r2","r3"], "confidence": 0.85},
    {"rank": 2, "compound_id": "ID", "name": "NAME", "purpose_used": "PURPOSE", "reasons": ["r1","r2","r3"], "confidence": 0.75},
    {"rank": 3, "compound_id": "ID", "name": "NAME", "purpose_used": "PURPOSE", "reasons": ["r1","r2","r3"], "confidence": 0.65}
  ]
}

RULES:
- Return EXACTLY 3 compounds, 3-6 reasons each
- First char MUST be {, last char MUST be }
- NO TEXT BEFORE OR AFTER THE JSON

START WITH { NOW:
"""


# ---------- Helpers ----------

def _normalize_purpose(p: Any) -> str:
    if not p:
        return "end_user"
    s = str(p).strip().lower()
    if s in {"invest", "investment", "investing"}:
        return "investment"
    if s in {"business", "commercial", "office"}:
        return "business"
    return "end_user"


def _extract_compound_names(final_candidates: list) -> List[str]:
    if not final_candidates:
        return []
    names = []
    for dev in final_candidates:
        if not isinstance(dev, dict):
            continue
        for n in (dev.get("matched_compound_names") or []):
            if isinstance(n, str) and n.strip():
                names.append(n.strip())
    seen = set()
    out = []
    for n in names:
        k = n.lower()
        if k not in seen:
            seen.add(k)
            out.append(n)
    return out


def _fetch_compounds_desc(db, names: List[str]) -> List[Dict[str, Any]]:
    if not names:
        return []
    docs = list(db["compounds"].find(
        {"name": {"$in": names}},
        {"_id": 1, "name": 1, "description": 1, "location": 1, "image_url": 1}
    ))
    if len(docs) < min(3, len(names)):
        ors = [{"name": {"$regex": f"^{re.escape(n)}$", "$options": "i"}} for n in names if n.strip()]
        if ors:
            docs = list(db["compounds"].find({"$or": ors}, {"_id": 1, "name": 1, "description": 1, "location": 1, "image_url": 1}))
    return [
        {
            "compound_id": str(d["_id"]),
            "name": d.get("name", ""),
            "description": (d.get("description") or "").strip(),
            "location": d.get("location", ""),
            "image_url": d.get("image_url", ""),
        }
        for d in docs if (d.get("description") or "").strip()
    ]


def _clean_markdown(text: str) -> str:
    text = re.sub(r'^```json\s*', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'^```\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
    return text.strip()


def _extract_json(text: str) -> Optional[str]:
    if not text:
        return None
    text = _clean_markdown(text)
    start = text.find("{")
    if start == -1:
        return None
    in_str = False
    escaped = False
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _ask_json_retries(prompt: str, retries: int = 3) -> Dict[str, Any]:
    for attempt in range(retries):
        p = prompt
        if attempt == 1:
            p = "SYSTEM: You are a JSON-only API. Output ONLY valid JSON.\n\n" + prompt
        elif attempt >= 2:
            p = "!!!!! JSON-ONLY MODE !!!!! First char: { Last char: }\n\n" + prompt

        raw = (ask_llm(p) or "").strip()
        if not raw:
            continue

        for text in [raw, _clean_markdown(raw)]:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        extracted = _extract_json(raw)
        if extracted:
            try:
                return json.loads(extracted)
            except json.JSONDecodeError:
                pass

    raise ValueError("Failed to get valid JSON after retries")


# ---------- Fallback scoring ----------

def _score_candidate(purpose: str, desc: str) -> Tuple[float, List[str]]:
    d = (desc or "").lower()
    reasons: List[str] = []
    score = 0.0

    def chk(keywords, pts, reason):
        nonlocal score
        for w in keywords:
            if w in d:
                score += pts
                if reason not in reasons:
                    reasons.append(reason)
                return

    chk(["security", "gated", "24/7"], 1.0, "Features security and gated access")
    chk(["clubhouse", "community", "parks", "green"], 1.0, "Community facilities and green spaces")
    chk(["mall", "retail", "shops", "commercial"], 1.0, "Has retail/commercial components")
    chk(["schools", "university", "education"], 1.0, "Near educational institutions")
    chk(["hospital", "medical", "clinic"], 1.0, "Access to medical facilities")
    chk(["road", "axis", "access", "minutes from"], 1.0, "Good accessibility")

    if purpose == "end_user":
        chk(["family", "kids", "comfort", "living"], 1.5, "Family-friendly environment")
        chk(["spa", "gym", "pool", "sports"], 1.2, "Daily-life amenities")
    elif purpose == "investment":
        chk(["mixed-use", "mixed use"], 2.0, "Mixed-use investment opportunity")
        chk(["phases", "towers", "master plan"], 1.5, "Large-scale development")
        chk(["luxury", "premium", "brand"], 1.3, "Premium positioning")
    elif purpose == "business":
        chk(["office", "business", "workspace"], 2.0, "Business/office spaces")
        chk(["commercial", "retail"], 1.5, "Commercial infrastructure")

    if len(d) >= 600:
        score += 0.5
    return score, reasons


def _fallback(purpose: str, candidates: list) -> Dict[str, Any]:
    scored = []
    for c in candidates:
        s, r = _score_candidate(purpose, c.get("description", ""))
        scored.append({"c": c, "score": s, "reasons": r})
    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:3]
    padding = ["Good project details", "Established developer", "Accessible location"]
    choices = []
    for rank, item in enumerate(top, 1):
        r = item["reasons"][:6]
        while len(r) < 3:
            r.append(padding[len(r)] if len(r) < len(padding) else "Reasonable option")
        conf = max(0.3, min(0.6, item["score"] / 10.0) - (rank - 1) * 0.1)
        choices.append({
            "rank": rank,
            "compound_id": item["c"].get("compound_id"),
            "name": item["c"].get("name"),
            "location": item["c"].get("location", ""),
            "image_url": item["c"].get("image_url", ""),
            "purpose_used": purpose,
            "reasons": r,
            "confidence": round(conf, 2),
        })
    return {"top_choices": choices}


# ---------- Main ----------

def comparing_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Select top 3 compounds using LLM with fallback."""
    purpose = _normalize_purpose(state.get("purpose"))
    final_cands = state.get("final_candidates") or []
    names = _extract_compound_names(final_cands)
    if not names:
        return state

    load_dotenv()
    uri = os.getenv("MONGO_URI")
    if not uri:
        return state

    client = MongoClient(uri, tlsCAFile=certifi.where())
    try:
        db = client.get_default_database()
        candidates = _fetch_compounds_desc(db, names)[:12]
        if not candidates:
            return state

        # Try LLM
        try:
            payload = {"purpose": purpose, "candidates": candidates}
            full_prompt = BEST_ONLY_PROMPT + "\n\nINPUT JSON:\n" + json.dumps(payload, ensure_ascii=False, indent=2)
            result = _ask_json_retries(full_prompt)

            top_choices = result.get("top_choices", [])
            if isinstance(top_choices, list) and len(top_choices) >= 3:
                # Enrich with location + image_url from candidates
                cand_map = {c["compound_id"]: c for c in candidates}
                for choice in top_choices:
                    cid = choice.get("compound_id")
                    if cid and cid in cand_map:
                        choice["location"] = cand_map[cid].get("location", "")
                        choice["image_url"] = cand_map[cid].get("image_url", "")
                state["top_choices"] = top_choices
                return state
        except Exception:
            pass

        # Fallback
        fb = _fallback(purpose, candidates)
        state["top_choices"] = fb["top_choices"]
        return state

    finally:
        client.close()
