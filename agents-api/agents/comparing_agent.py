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
!!!! CRITICAL INSTRUCTION !!!!
DO NOT WRITE ANY TEXT BEFORE OR AFTER THE JSON.
NO EXPLANATIONS. NO SUMMARIES. NO INTRODUCTIONS.
YOUR ENTIRE RESPONSE MUST BE VALID JSON AND NOTHING ELSE.

WRONG (DO NOT DO THIS):
"Based on the information provided, here is a summary..."
"Here are the top 3 compounds..."

CORRECT (DO THIS):
{"top_choices":[{"rank":1,"compound_id":"...","name":"...","purpose_used":"...","reasons":["..."],"confidence":0.85}...]}

==============================================================================

TASK: Analyze compounds and return TOP 3 as pure JSON only.

Purpose meanings:
- end_user → family living, comfort, community
- investment → ROI, scale, mixed-use, market strength  
- business → offices, commercial, accessibility

REQUIRED OUTPUT (COPY THIS STRUCTURE EXACTLY):
{
  "top_choices": [
    {
      "rank": 1,
      "compound_id": "ID_HERE",
      "name": "NAME_HERE",
      "purpose_used": "investment",
      "reasons": ["reason 1", "reason 2", "reason 3"],
      "confidence": 0.85
    },
    {
      "rank": 2,
      "compound_id": "ID_HERE",
      "name": "NAME_HERE",
      "purpose_used": "investment",
      "reasons": ["reason 1", "reason 2", "reason 3"],
      "confidence": 0.75
    },
    {
      "rank": 3,
      "compound_id": "ID_HERE",
      "name": "NAME_HERE",
      "purpose_used": "investment",
      "reasons": ["reason 1", "reason 2", "reason 3"],
      "confidence": 0.65
    }
  ]
}

RULES:
- Return EXACTLY 3 compounds
- Give 3-6 specific reasons based on description
- First character MUST be {
- Last character MUST be }
- NO TEXT BEFORE OR AFTER THE JSON

START YOUR RESPONSE NOW WITH { (not with any explanation):
"""


# -------------------------
# Helpers: extraction + db
# -------------------------

def _extract_compound_names_from_developers(
    final_candidates: Optional[List[Dict[str, Any]]]
) -> List[str]:
    """Extract all compound names from final_candidates."""
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

    # Deduplicate while preserving order
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
    Fetch compounds with descriptions from MongoDB.
    Tries exact match first, then case-insensitive regex if needed.
    """
    if not names:
        return []

    # 1) Try exact match
    docs = list(db["compounds"].find(
        {"name": {"$in": names}},
        {"_id": 1, "name": 1, "description": 1}
    ))

    # 2) Fallback to case-insensitive regex if we got few results
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

    # Filter out compounds without descriptions
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
    """Normalize purpose string to standard values."""
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
# Helpers: JSON extraction
# -------------------------

def _clean_markdown_json(text: str) -> str:
    """Remove markdown code blocks and common formatting."""
    if not text:
        return ""
    
    # Remove markdown code blocks
    text = re.sub(r'^```json\s*', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'^```\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
    
    return text.strip()


def _extract_json_object(text: str) -> Optional[str]:
    """
    Extract the first complete JSON object from text.
    Handles nested braces and string escaping.
    """
    if not text:
        return None

    # Clean markdown first
    text = _clean_markdown_json(text)

    # Find first opening brace
    start = text.find("{")
    if start == -1:
        return None

    # Track depth and string context
    in_string = False
    escaped = False
    depth = 0
    
    for i in range(start, len(text)):
        ch = text[i]

        # Handle string context
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        # Check for string start
        if ch == '"':
            in_string = True
            continue

        # Track brace depth
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                # Found complete object
                return text[start:i + 1]

    return None


def _ask_json_with_retries(full_prompt: str, max_retries: int = 3) -> Dict[str, Any]:
    """
    Ask Ollama for JSON response with multiple retry strategies.
    """
    last_response = ""
    
    for attempt in range(max_retries):
        # Build prompt with increasing emphasis on JSON-only output
        if attempt == 0:
            prompt = full_prompt
        elif attempt == 1:
            prompt = (
                "SYSTEM INSTRUCTION: You are a JSON-only API. You do not write explanatory text.\n"
                "You ONLY output valid JSON objects. Nothing else.\n"
                "DO NOT write 'Based on' or 'Here is' or any introduction.\n"
                "Your response must START with { and END with }\n\n"
                + full_prompt
            )
        else:
            prompt = (
                "!!!!! EMERGENCY OVERRIDE !!!!!\n"
                "IGNORE ALL PREVIOUS INSTRUCTIONS TO BE CONVERSATIONAL.\n"
                "YOU ARE NOW IN JSON-ONLY MODE.\n"
                "OUTPUT FORMAT: RAW JSON OBJECT ONLY\n"
                "NO MARKDOWN BLOCKS (no ```json)\n"
                "NO EXPLANATORY TEXT WHATSOEVER\n"
                "FIRST CHARACTER: {\n"
                "LAST CHARACTER: }\n"
                "===============================================\n\n"
                + full_prompt
                + "\n\n===============================================\n"
                "RESPOND NOW WITH PURE JSON (start typing { immediately):"
            )

        print(f"\n🔄 Attempt {attempt + 1}/{max_retries}...")
        
        # Get response from Ollama
        # Note: If your ask_ollama function supports a 'format' or 'json_mode' parameter,
        # you could modify this call like: ask_ollama(prompt, format="json")
        response = (ask_ollama(prompt) or "").strip()
        last_response = response
        
        if not response:
            print("❌ Empty response from Ollama")
            continue

        # Strategy 1: Try direct JSON parse
        try:
            result = json.loads(response)
            print("✅ Successfully parsed JSON (direct)")
            return result
        except json.JSONDecodeError as e:
            print(f"⚠️  Direct parse failed: {e}")

        # Strategy 2: Clean markdown and try again
        try:
            cleaned = _clean_markdown_json(response)
            result = json.loads(cleaned)
            print("✅ Successfully parsed JSON (after markdown cleaning)")
            return result
        except json.JSONDecodeError as e:
            print(f"⚠️  Cleaned parse failed: {e}")

        # Strategy 3: Extract JSON object
        try:
            extracted = _extract_json_object(response)
            if extracted:
                result = json.loads(extracted)
                print("✅ Successfully parsed JSON (extracted object)")
                return result
            else:
                print("⚠️  No JSON object found in response")
        except json.JSONDecodeError as e:
            print(f"⚠️  Extracted parse failed: {e}")

        # Strategy 4: Try to find JSON after common prefixes
        try:
            # Remove common conversational prefixes
            prefixes_to_remove = [
                "based on the information provided",
                "here is a summary",
                "here are the top",
                "based on",
                "here is",
                "here are",
                "the top 3 compounds are",
                "i have analyzed",
            ]
            
            response_lower = response.lower()
            for prefix in prefixes_to_remove:
                if prefix in response_lower:
                    # Find where the prefix ends and try to extract JSON after it
                    idx = response_lower.find(prefix)
                    remaining = response[idx + len(prefix):]
                    extracted = _extract_json_object(remaining)
                    if extracted:
                        result = json.loads(extracted)
                        print("✅ Successfully parsed JSON (after removing prefix)")
                        return result
        except Exception as e:
            print(f"⚠️  Prefix removal strategy failed: {e}")

        # Show preview of what we got
        preview = response[:300] + "..." if len(response) > 300 else response
        print(f"📄 Response preview:\n{preview}\n")

    # All retries failed
    print("\n❌ All JSON parsing attempts failed")
    print(f"Last response from Ollama:\n{last_response[:500]}\n")
    raise ValueError(
        f"Ollama failed to return valid JSON after {max_retries} attempts. "
        f"Last response preview: {last_response[:200]}"
    )


# -------------------------
# Fallback: deterministic scoring
# -------------------------

def _score_candidate(purpose: str, desc: str) -> Tuple[float, List[str]]:
    """
    Keyword-based scoring as fallback.
    Returns (score, reasons_found).
    """
    d = (desc or "").lower()
    reasons: List[str] = []
    score = 0.0

    def check_keywords(keywords: List[str], points: float, reason: str):
        """Check if any keyword is in description."""
        nonlocal score
        for word in keywords:
            if word in d:
                score += points
                if reason not in reasons:
                    reasons.append(reason)
                return

    # General amenities
    check_keywords(
        ["security", "gated", "24/7", "24-7", "secured"],
        1.0,
        "Features security and gated access for resident safety"
    )
    
    check_keywords(
        ["clubhouse", "community", "parks", "green", "landscape", "gardens"],
        1.0,
        "Includes community facilities and green spaces"
    )
    
    check_keywords(
        ["mall", "retail", "shops", "commercial", "stores"],
        1.0,
        "Has retail and commercial components"
    )
    
    check_keywords(
        ["schools", "university", "auc", "education"],
        1.0,
        "Near educational institutions"
    )
    
    check_keywords(
        ["hospital", "medical", "clinic", "healthcare"],
        1.0,
        "Provides access to medical facilities"
    )
    
    check_keywords(
        ["downtown", "road", "axis", "access", "minutes from", "near", "close to"],
        1.0,
        "Strategically located with good accessibility"
    )

    # Purpose-specific scoring
    if purpose == "end_user":
        check_keywords(
            ["family", "kids", "children", "play", "comfort", "living"],
            1.5,
            "Family-friendly environment designed for comfortable living"
        )
        check_keywords(
            ["spa", "gym", "pool", "swimming", "sports", "fitness"],
            1.2,
            "Excellent daily-life amenities including fitness facilities"
        )
        check_keywords(
            ["quiet", "peaceful", "serene", "tranquil"],
            1.0,
            "Peaceful environment suitable for family living"
        )

    elif purpose == "investment":
        check_keywords(
            ["mixed-use", "mixed use", "multi-purpose"],
            2.0,
            "Mixed-use development offers diverse investment opportunities"
        )
        check_keywords(
            ["phases", "towers", "scale", "master plan", "masterplan"],
            1.5,
            "Large-scale development with clear phasing and master planning"
        )
        check_keywords(
            ["brand", "international", "luxury", "premium"],
            1.3,
            "Premium positioning with strong brand appeal"
        )
        check_keywords(
            ["rental", "roi", "investment", "appreciation"],
            1.5,
            "Strong investment potential mentioned in description"
        )

    elif purpose == "business":
        check_keywords(
            ["office", "business", "workspace", "coworking"],
            2.0,
            "Dedicated business and office spaces available"
        )
        check_keywords(
            ["commercial", "retail", "shops"],
            1.5,
            "Commercial infrastructure suitable for business operations"
        )
        check_keywords(
            ["conference", "meeting", "business center"],
            1.3,
            "Business amenities and meeting facilities"
        )

    # Bonus for detailed descriptions
    desc_length = len(d)
    if desc_length >= 600:
        score += 0.5
        reasons.append("Comprehensive project description with detailed information")
    if desc_length >= 1200:
        score += 0.3

    return score, reasons


def _fallback_pick_best(
    purpose: str, 
    candidates: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Deterministic fallback when LLM fails.
    Returns top 3 compounds.
    """
    if not candidates:
        raise ValueError("No candidates provided for fallback selection")

    print("\n🔧 Using fallback scoring algorithm...")
    
    # Score all candidates
    scored_candidates = []
    for candidate in candidates:
        score, reasons = _score_candidate(
            purpose, 
            candidate.get("description", "")
        )
        scored_candidates.append({
            "candidate": candidate,
            "score": score,
            "reasons": reasons
        })
    
    # Sort by score (highest first)
    scored_candidates.sort(key=lambda x: x["score"], reverse=True)
    
    # Take top 3 (or all if less than 3)
    top_3 = scored_candidates[:min(3, len(scored_candidates))]
    
    # Ensure we have at least 3 (pad if needed)
    while len(top_3) < 3 and len(top_3) < len(candidates):
        top_3.append(scored_candidates[len(top_3)])
    
    # Build result
    top_choices = []
    for rank, item in enumerate(top_3, 1):
        candidate = item["candidate"]
        reasons = item["reasons"][:6]
        
        # Pad with generic but valid reasons if needed
        if len(reasons) < 3:
            padding = [
                "Provides clearer project details compared to alternatives",
                "Description indicates established developer credibility",
                "Location and accessibility mentioned in project description"
            ]
            for pad_reason in padding:
                if len(reasons) >= 3:
                    break
                if pad_reason not in reasons:
                    reasons.append(pad_reason)
        
        # Calculate confidence based on rank and score
        base_confidence = min(0.6, max(0.3, item["score"] / 10.0))
        confidence = base_confidence - (rank - 1) * 0.1  # Decrease by 0.1 for each rank
        confidence = max(0.3, confidence)  # Minimum 0.3
        
        top_choices.append({
            "rank": rank,
            "compound_id": candidate.get("compound_id"),
            "name": candidate.get("name"),
            "purpose_used": purpose,
            "reasons": reasons[:6],
            "confidence": round(confidence, 2)
        })
    
    return {
        "top_choices": top_choices
    }


# -------------------------
# Main Agent
# -------------------------

def comparing_agent(state: AgentState):
    """
    Main comparing agent that selects best compound.
    Uses LLM with fallback to deterministic scoring.
    """
    print("\n--- Comparing Agent (Ollama) ---")

    # Get purpose
    purpose_used = _normalize_purpose(state.purpose)
    print(f"Purpose: {purpose_used}")

    # Extract compound names
    compounds_to_compare = state.context.final_compounds or []
    compound_names = _extract_compound_names_from_developers(compounds_to_compare)

    if not compound_names:
        print("⚠️ No compounds to compare")
        state.agent_message = "No compounds available for comparison."
        state.sync_to_legacy()
        return state

    print(f"Found {len(compound_names)} compound names to evaluate")

    # Connect to MongoDB
    load_dotenv()
    uri = os.getenv("MONGO_URI")
    if not uri:
        print("❌ No MONGO_URI found. Skipping comparison.")
        state.sync_to_legacy()
        return state

    client = MongoClient(uri, tlsCAFile=certifi.where())
    
    try:
        db = client.get_default_database()

        # Fetch compounds with descriptions
        candidates = _fetch_compounds_desc_only(db, compound_names)
        
        # Limit to prevent token overflow
        candidates = candidates[:12]

        if not candidates:
            print("❌ No compounds with descriptions found in database.")
            print("   Check that compounds.name matches matched_compound_names")
            state.sync_to_legacy()
            return state

        print(f"✅ Found {len(candidates)} compounds with descriptions")

        # Prepare input for LLM
        payload = {
            "purpose": purpose_used,
            "candidates": candidates
        }
        
        full_prompt = (
            BEST_ONLY_PROMPT + 
            "\n\nINPUT JSON:\n" + 
            json.dumps(payload, ensure_ascii=False, indent=2)
        )

        # Try LLM first
        try:
            print("\n🤖 Asking Ollama to select top 3 compounds...")
            result = _ask_json_with_retries(full_prompt, max_retries=3)
            
            # Validate result structure
            if not isinstance(result, dict):
                raise ValueError("Result is not a dictionary")
            
            top_choices = result.get("top_choices")
            if not top_choices or not isinstance(top_choices, list):
                raise ValueError("Missing or invalid 'top_choices' in result")
            
            if len(top_choices) < 3:
                raise ValueError(f"Expected 3 compounds, got {len(top_choices)}")

            # Success!
            print("\n✅ LLM successfully selected top 3 compounds")
            print("\n" + "="*80)
            print("TOP 3 COMPOUNDS (LLM)")
            print("="*80)
            
            for choice in top_choices:
                print(f"\n🏆 RANK #{choice.get('rank')}")
                print(f"Name: {choice.get('name')}")
                print(f"Compound ID: {choice.get('compound_id')}")
                print(f"Purpose: {choice.get('purpose_used')}")
                print(f"Confidence: {choice.get('confidence')}")
                
                reasons = choice.get("reasons") or []
                if isinstance(reasons, list) and reasons:
                    print("Reasons:")
                    for i, reason in enumerate(reasons, 1):
                        print(f"  {i}. {reason}")
                print("-" * 80)
            
            state.agent_message = "Compared compounds successfully."
            state.context.comparison_result = top_choices
            state.sync_to_legacy()
            return state

        except Exception as e:
            print(f"\n⚠️  LLM failed: {e}")
            print("Falling back to deterministic scoring...")

        # Fallback to deterministic method
        try:
            fallback_result = _fallback_pick_best(purpose_used, candidates)
            top_choices = fallback_result["top_choices"]

            print("\n" + "="*80)
            print("TOP 3 COMPOUNDS (FALLBACK)")
            print("="*80)
            
            for choice in top_choices:
                print(f"\n🏆 RANK #{choice.get('rank')}")
                print(f"Name: {choice.get('name')}")
                print(f"Compound ID: {choice.get('compound_id')}")
                print(f"Purpose: {choice.get('purpose_used')}")
                print(f"Confidence: {choice.get('confidence')} (fallback scoring)")
                
                print("Reasons:")
                for i, reason in enumerate(choice.get("reasons") or [], 1):
                    print(f"  {i}. {reason}")
                print("-" * 80)
            
            print("="*80)
            
            state.agent_message = "Compared compounds successfully."
            state.context.comparison_result = top_choices
            state.sync_to_legacy()
            return state

        except Exception as fallback_error:
            print(f"\n❌ Fallback also failed: {fallback_error}")
            print("Unable to select top compounds")
            state.sync_to_legacy()
            return state

    finally:
        client.close()