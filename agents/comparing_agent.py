import os
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from pymongo import MongoClient
import certifi

from state import AgentState
from main_helpers import ask_ollama


BEST_ONLY_PROMPT = """
Return STRICT JSON only.
The first character MUST be '{' and the last character MUST be '}'.
No markdown. No headings. No extra text outside JSON.

You are SEMSAI, a decision assistant for Egyptian real estate.

You will receive INPUT JSON with:
{
  "purpose": "end_user|investment|business|null",
  "candidates": [
    {"compound_id":"string","name":"string","description":"string"}
  ]
}

Task:
Choose the SINGLE best compound based ONLY on:
- purpose
- each compound description

Purpose mapping:
- end_user: livability, community, comfort, daily life, services
- investment: clarity of offering, scale, mixed-use signals, strong positioning (ONLY if explicitly in text)
- business: business/commercial readiness, accessibility (ONLY if explicitly in text)

Output STRICT JSON ONLY:
{
  "best_choice": {
    "compound_id": "...",
    "name": "...",
    "purpose_used": "end_user|investment|business",
    "reasons": ["...", "...", "..."],
    "confidence": 0.0
  }
}

Rules:
- reasons: 3 to 6 reasons, grounded ONLY in description text.
- No repetition.
"""


# -------------------------
# Helpers: extraction + db
# -------------------------

def _extract_compound_names_from_developers(
    final_candidates: Optional[List[Dict[str, Any]]]
) -> List[str]:
    if not final_candidates:
        return []

    names: List[str] = []
    for dev in final_candidates:
        if not isinstance(dev, dict):
            continue
        arr = dev.get("matched_compound_names") or []
        if isinstance(arr, list):
            for n in arr:
                if isinstance(n, str) and n.strip():
                    names.append(n.strip())

    # unique keep order
    seen = set()
    out: List[str] = []
    for n in names:
        k = n.lower()
        if k not in seen:
            seen.add(k)
            out.append(n)
    return out


def _fetch_compounds_desc_only(db, names: List[str]) -> List[Dict[str, Any]]:
    """
    Tries exact match first.
    If exact match returns few results, falls back to case-insensitive regex OR match.
    """
    if not names:
        return []

    # 1) exact
    docs = list(db["compounds"].find(
        {"name": {"$in": names}},
        {"_id": 1, "name": 1, "description": 1}
    ))

    # 2) fallback regex (case-insensitive) if weak match
    if len(docs) < min(3, len(names)):
        ors = []
        for n in names:
            n = (n or "").strip()
            if not n:
                continue
            ors.append({"name": {"$regex": f"^{re.escape(n)}$", "$options": "i"}})

        if ors:
            docs = list(db["compounds"].find(
                {"$or": ors},
                {"_id": 1, "name": 1, "description": 1}
            ))

    out: List[Dict[str, Any]] = []
    for d in docs:
        desc = (d.get("description") or "").strip()
        if not desc:
            continue
        out.append({
            "compound_id": str(d["_id"]),
            "name": d.get("name") or "",
            "description": desc
        })

    return out


def _normalize_purpose(p: Any) -> str:
    if not p:
        return "end_user"
    s = str(p).strip().lower()
    if s in {"invest", "investment", "investing"}:
        return "investment"
    if s in {"business", "commercial", "office"}:
        return "business"
    if s in {"end_user", "enduser", "living", "live", "family", "residence"}:
        return "end_user"
    return "end_user"


# -------------------------
# Helpers: JSON robustness
# -------------------------

def _extract_first_json_object(text: str) -> Optional[str]:
    if not text:
        return None

    start = text.find("{")
    if start == -1:
        return None

    in_str = False
    esc = False
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]

        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
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


def _ask_json_strict(full_prompt: str, retries: int = 2) -> Dict[str, Any]:
    last = ""
    for attempt in range(retries + 1):
        prompt = full_prompt if attempt == 0 else (
            "IMPORTANT:\n"
            "- Output MUST be VALID JSON ONLY.\n"
            "- No headings/markdown.\n"
            "- First char '{' last char '}'.\n\n"
            + full_prompt
        )

        last = (ask_ollama(prompt) or "").strip()

        # direct parse
        try:
            return json.loads(last)
        except Exception:
            pass

        # extract object
        extracted = _extract_first_json_object(last)
        if extracted:
            try:
                return json.loads(extracted)
            except Exception:
                pass

    raise ValueError(f"Ollama did not return valid JSON. Last output:\n{last[:1500]}")


# -------------------------
# Fallback: deterministic scoring
# -------------------------

def _score_candidate(purpose: str, desc: str) -> Tuple[float, List[str]]:
    """
    Simple keyword-based scorer to ALWAYS pick something if LLM fails.
    Returns (score, reasons_found)
    """
    d = (desc or "").lower()
    reasons: List[str] = []
    score = 0.0

    def hit(words: List[str], pts: float, reason: str):
        nonlocal score
        for w in words:
            if w in d:
                score += pts
                if reason not in reasons:
                    reasons.append(reason)
                return

    # Common signals
    hit(["security", "gated", "24/7"], 1.0, "Mentions security / gated living.")
    hit(["clubhouse", "community", "parks", "green", "landscape", "gardens"], 1.0, "Mentions greenery / community facilities.")
    hit(["mall", "retail", "shops", "commercial"], 1.0, "Mentions retail/commercial components.")
    hit(["schools", "university", "auc"], 1.0, "Mentions education proximity/services.")
    hit(["hospital", "medical"], 1.0, "Mentions medical access.")
    hit(["downtown", "road", "axis", "access", "minutes from", "near"], 1.0, "Mentions accessibility / key locations.")

    # Purpose-specific weighting
    if purpose == "end_user":
        hit(["family", "kids", "play", "comfort", "live"], 1.2, "End-user livability cues (family/comfort).")
        hit(["spa", "gym", "pool", "sports"], 1.0, "Mentions daily-life amenities (gym/pool/sports).")

    elif purpose == "investment":
        hit(["mixed-use", "mixed use"], 1.5, "Investment cue: mixed-use mentioned.")
        hit(["phases", "towers", "scale", "master plan"], 1.0, "Investment cue: scale/master plan clarity.")
        hit(["brand", "international", "retail brands"], 1.0, "Investment cue: commercial brand/retail angle.")

    elif purpose == "business":
        hit(["office", "business", "workspace"], 1.5, "Business cue: office/business readiness mentioned.")
        hit(["commercial", "retail"], 1.0, "Business cue: commercial activity mentioned.")

    # Small bonus for longer, more informative descriptions
    if len(d) >= 600:
        score += 0.3
    if len(d) >= 1200:
        score += 0.3

    return score, reasons


def _fallback_pick_best(purpose: str, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    best = None
    best_score = float("-inf")
    best_reasons: List[str] = []

    for c in candidates:
        score, reasons = _score_candidate(purpose, c.get("description", ""))
        if score > best_score:
            best_score = score
            best = c
            best_reasons = reasons

    if not best:
        # absolute fallback: first candidate
        best = candidates[0]

    # ensure 3-6 reasons
    reasons_out = best_reasons[:6]
    if len(reasons_out) < 3:
        # pad with generic but still grounded
        reasons_out.append("Description provides clearer details than alternatives.")
    if len(reasons_out) < 3:
        reasons_out.append("Mentions concrete amenities/services rather than vague claims.")
    if len(reasons_out) < 3:
        reasons_out.append("Has stronger explicit location/access cues in the text.")

    return {
        "best_choice": {
            "compound_id": best.get("compound_id"),
            "name": best.get("name"),
            "purpose_used": purpose,
            "reasons": reasons_out[:6],
            "confidence": 0.45  # conservative because heuristic
        }
    }


# -------------------------
# Agent
# -------------------------

def comparing_agent(state: AgentState):
    print("\n--- Comparing Agent (Ollama) ---")

    purpose_used = _normalize_purpose(state.get("purpose"))

    final_candidates = state.get("final_candidates") or []
    compound_names = _extract_compound_names_from_developers(final_candidates)

    if not compound_names:
        print("No compound names found in state.final_candidates.")
        return state

    load_dotenv()
    uri = os.getenv("MONGO_URI")
    if not uri:
        print("No MONGO_URI found. Skipping comparison.")
        return state

    client = MongoClient(uri, tlsCAFile=certifi.where())
    try:
        db = client.get_default_database()

        candidates = _fetch_compounds_desc_only(db, compound_names)
        candidates = candidates[:12]  # token control

        if not candidates:
            print("No compounds with descriptions matched by name. (Check compounds.name vs matched_compound_names)")
            return state

        # ---- Try LLM first
        payload = {"purpose": purpose_used, "candidates": candidates}
        full_prompt = BEST_ONLY_PROMPT + "\n\nINPUT JSON:\n" + json.dumps(payload, ensure_ascii=False)

        try:
            result = _ask_json_strict(full_prompt, retries=2)
            best = (result.get("best_choice") if isinstance(result, dict) else None) or {}
            if best and best.get("name"):
                print("\n--- BEST COMPOUND (LLM) ---")
                print(f"Name: {best.get('name')}")
                print(f"Purpose Used: {best.get('purpose_used')}")
                print(f"Confidence: {best.get('confidence')}")
                reasons = best.get("reasons") or []
                if isinstance(reasons, list) and reasons:
                    print("\nReasons:")
                    for i, r in enumerate(reasons, 1):
                        print(f"{i}. {r}")
                return state

            # if JSON ok but missing best_choice -> fallback
            print("LLM returned JSON but missing best_choice. Falling back.")
        except Exception as e:
            print(f"LLM failed to produce valid JSON. Falling back. Error: {e}")

        # ---- Fallback deterministic pick
        fb = _fallback_pick_best(purpose_used, candidates)
        best = fb["best_choice"]

        print("\n--- BEST COMPOUND (FALLBACK) ---")
        print(f"Name: {best.get('name')}")
        print(f"Purpose Used: {best.get('purpose_used')}")
        print(f"Confidence: {best.get('confidence')}")
        print("\nReasons:")
        for i, r in enumerate(best.get("reasons") or [], 1):
            print(f"{i}. {r}")

        return state

    finally:
        client.close()