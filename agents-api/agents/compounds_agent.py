import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from pymongo import MongoClient
import certifi

from state import AgentState
from agents.llm_messages import (
    compounds_location_changed, compounds_property_type_changed,
    compounds_no_units_options, compounds_unclear_choice,
)
from .Normalization import normalize_location


# -----------------------
# Helpers
# -----------------------

def format_price(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{int(float(value)):,}"
    except Exception:
        return "N/A"


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _normalize_type(t: Any) -> Optional[str]:
    if not t:
        return None
    s = str(t).strip().lower()
    if s in {"apt", "apartment", "apartments"}:
        return "Apartment"
    if s in {"villa", "villas"}:
        return "Villa"
    return str(t).strip()


def _normalize_payment_type(p: Any) -> Optional[str]:
    """
    Returns: "cash" | "installments" | None
    """
    if not p:
        return None
    s = str(p).strip().lower()
    if s in {"cash", "full cash", "c"}:
        return "cash"
    if s in {"installment", "installments", "instalments", "plan", "monthly"}:
        return "installments"
    return None


def _sale_type_match_from_payment(payment_type: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Units have sale_type like:
      - "Resale"
      - "Developer Sale"
    If payment_type is:
      - cash        -> filter Resale only
      - installments-> filter Developer Sale only
      - None/other  -> no filter
    """
    if payment_type == "cash":
        return {"sale_type": {"$regex": r"^resale$", "$options": "i"}}

    if payment_type == "installments":
        # include common variations "Developer Sale", "Developer", etc.
        return {"sale_type": {"$regex": r"developer", "$options": "i"}}

    return None


def _compute_budget_if_missing(db, state: AgentState) -> Optional[float]:
    # FIX: use Pydantic attribute access (context first, then legacy field)
    budget = state.context.budget
    if budget is None:
        budget = state.budget  # legacy field
    if budget is not None:
        try:
            return float(budget)
        except Exception:
            return None

    downpayment = _safe_float(state.context.downpayment or state.Downpayment, 0.0)
    monthly_install = _safe_float(
        state.context.monthly_installment or state.monthlyinstall, 0.0
    )

    plan = db["payments"].find_one({}, sort=[("duration", -1)], projection={"duration": 1})
    if not plan or not plan.get("duration"):
        return None

    months = int(plan["duration"])
    budget = downpayment + monthly_install * months
    # Write to both context and legacy field
    state.context.budget = budget
    state.budget = budget
    return float(budget)


def _build_units_pipeline(
    wanted_type: str,
    location: Optional[str],
    budget: float,
    payment_type: Optional[str],
    limit: int = 300
) -> List[Dict[str, Any]]:

    # match type across possible fields (including nested object format)
    type_match = {
        "$or": [
            {"type": {"$regex": f"^{re.escape(wanted_type)}$", "$options": "i"}},
            {"property_type": {"$regex": f"^{re.escape(wanted_type)}$", "$options": "i"}},
            {"property_type.name": {"$regex": f"^{re.escape(wanted_type)}$", "$options": "i"}},
            {"unit_type": {"$regex": f"^{re.escape(wanted_type)}$", "$options": "i"}},
        ]
    }

    # location match on UNITS
    loc_match: Optional[Dict[str, Any]] = None
    if location:
        loc_match = {"location": {"$regex": str(location), "$options": "i"}}

    # sale_type filter based on payment choice
    sale_match = _sale_type_match_from_payment(payment_type)

    base_and: List[Dict[str, Any]] = [type_match]
    if loc_match:
        base_and.append(loc_match)
    if sale_match:
        base_and.append(sale_match)

    # Extract "$oid" safely WITHOUT using compound_id.$oid (Mongo forbids field paths starting with $)
    oid_from_export_obj = {
        "$let": {
            "vars": {"arr": {"$objectToArray": "$compound_id"}},
            "in": {
                "$first": {
                    "$map": {
                        "input": {
                            "$filter": {
                                "input": "$$arr",
                                "as": "it",
                                "cond": {"$eq": ["$$it.k", "$oid"]},
                            }
                        },
                        "as": "f",
                        "in": "$$f.v",
                    }
                }
            },
        }
    }

    # Build a string version of compound id regardless of storage shape
    compound_oid_str_expr = {
        "$switch": {
            "branches": [
                {"case": {"$eq": [{"$type": "$compound_id"}, "objectId"]}, "then": {"$toString": "$compound_id"}},
                {"case": {"$eq": [{"$type": "$compound_id"}, "string"]}, "then": "$compound_id"},
                {"case": {"$eq": [{"$type": "$compound_id"}, "object"]}, "then": oid_from_export_obj},
            ],
            "default": None,
        }
    }

    pipeline: List[Dict[str, Any]] = [
        {"$match": {"$and": base_and}},

        # effective_price = price OR price_min OR price_max
        {
            "$addFields": {
                "effective_price": {"$ifNull": ["$price", {"$ifNull": ["$price_min", "$price_max"]}]}
            }
        },
        {"$match": {"effective_price": {"$ne": None, "$lte": float(budget)}}},

        # normalize compound_id to a string we can convert to ObjectId
        {"$addFields": {"compound_oid_str": compound_oid_str_expr}},

        # convert to ObjectId (if convertible)
        {
            "$addFields": {
                "compound_oid": {
                    "$cond": [
                        {
                            "$and": [
                                {"$ne": ["$compound_oid_str", None]},
                                {"$ne": ["$compound_oid_str", ""]},
                                {"$eq": [{"$strLenCP": "$compound_oid_str"}, 24]},
                            ]
                        },
                        {"$toObjectId": "$compound_oid_str"},
                        None,
                    ]
                }
            }
        },
        {"$match": {"compound_oid": {"$ne": None}}},

        # group by compound_oid to get min price per compound
        {
            "$group": {
                "_id": "$compound_oid",
                "min_unit_price": {"$min": "$effective_price"},
                "sample_unit_location": {"$first": "$location"},
                "sample_sale_type": {"$first": "$sale_type"},
            }
        },

        {"$sort": {"min_unit_price": 1}},
        {"$limit": int(limit)},

        # lookup compound info
        {
            "$lookup": {
                "from": "compounds",
                "localField": "_id",
                "foreignField": "_id",
                "as": "compound_doc",
            }
        },
        {"$unwind": {"path": "$compound_doc", "preserveNullAndEmptyArrays": True}},

        {
            "$project": {
                "_id": 0,
                "compound_id": "$_id",
                "min_unit_price": 1,
                "sale_type_used": "$sample_sale_type",
                "compound_name": {"$ifNull": ["$compound_doc.name", "$compound_doc.compound_name"]},
                "compound_location": {"$ifNull": ["$compound_doc.location", "$sample_unit_location"]},
            }
        },
    ]

    return pipeline


def _reset_for_requery(state: AgentState) -> None:
    """
    Called whenever the user changes budget / location / property type after
    a "no units found" result. Resets the phase + result sentinels so the
    router re-enters the discovery gate (to re-validate whichever field
    changed) instead of short-circuiting to END.

    Two things matter here, both required together:
      1. current_phase must go back to "discovery" — the "search" phase
         block never looks at location/property_type/budget at all, it
         jumps straight to checking candidate_compounds. Leaving phase as
         "search" skips the re-validation entirely.
      2. candidate_compounds must become None, not [] — the router treats
         [] as "we already searched and are mid no-units-response flow",
         which makes it return END immediately. None means "hasn't
         searched yet", which is what's actually true after a field changes.
    """
    state.current_phase = "discovery"
    state.candidate_compounds = None
    state.context.candidate_compounds = None
    # Any previously found developers/final_compounds are now stale too —
    # clear them so a re-run of the search starts clean.
    state.final_compounds = None
    state.context.final_compounds = None
    state.top_developers = None
    state.context.top_developers = None


# -----------------------
# No-units intent classifier
# -----------------------

def _classify_no_units_response(user_input: str, state: AgentState):
    """
    Use the LLM to classify the user's response to "no units found" and extract
    any new values they mentioned inline.

    Returns
    -------
    (intent, extracted_location, extracted_type, extracted_budget)
      intent: "increase_budget" | "change_location" | "change_property_type" | "unclear"
      extracted_location: str | None   — e.g. "Sheikh Zayed"
      extracted_type:     str | None   — "Villa" | "Apartment" | "Chalet"
      extracted_budget:   int | None   — e.g. 10_000_000
    """
    import json as _json
    try:
        from main_helpers import ask_llm_with_history
        history = state.get_llm_messages(last_n=4) if hasattr(state, "get_llm_messages") else []
        prompt = (
            f"The user was told no properties were found and was offered three options: "
            f"1) increase budget, 2) change location, 3) change property type.\n"
            f"User replied: \"{user_input}\"\n\n"
            "Extract:\n"
            "- intent: one of 'increase_budget', 'change_location', 'change_property_type', 'unclear'\n"
            "- location: Egyptian city/area they mentioned (or null)\n"
            "- property_type: 'Villa', 'Apartment', or 'Chalet' if mentioned (or null)\n"
            "- budget: numeric budget in EGP if mentioned — convert '10m'→10000000, '500k'→500000 (or null)\n\n"
            "Rules:\n"
            "- A place name ('zayed', 'maadi', 'october', 'tagmo3', etc.) always signals change_location\n"
            "- Numbers alone (e.g. '25 m', 'raise to 10 million') signal increase_budget\n"
            "- Property type words (villa/apartment/chalet) signal change_property_type\n"
            "- Multiple signals: pick the most specific one (place name > property type > number)\n"
            "Respond ONLY with valid JSON, no markdown:\n"
            "{\"intent\": \"...\", \"location\": \"...\", \"property_type\": \"...\", \"budget\": 0}"
        )
        raw = ask_llm_with_history(
            system_prompt="You are a precise intent-extraction engine. Return ONLY valid JSON.",
            history=history,
            user_prompt=prompt,
            max_tokens=120,
            temperature=0.0,
        ).strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if "\n" in raw:
                raw = raw.split("\n", 1)[1]
        data = _json.loads(raw)
        intent    = data.get("intent", "unclear")
        loc       = data.get("location") or None
        ptype_raw = (data.get("property_type") or "").strip().capitalize()
        ptype     = ptype_raw if ptype_raw in ("Villa", "Apartment", "Chalet") else None
        budget_raw = data.get("budget")
        budget    = int(budget_raw) if isinstance(budget_raw, (int, float)) and budget_raw >= 100_000 else None
        # Normalise location through alias table for common colloquial names
        if loc:
            try:
                from agents.Normalization import LOCATION_ALIASES
            except ImportError:
                try:
                    from Normalization import LOCATION_ALIASES
                except ImportError:
                    LOCATION_ALIASES = {}
            loc_key = loc.strip().lower()
            loc = LOCATION_ALIASES.get(loc_key, loc)
        return intent, loc, ptype, budget
    except Exception as exc:
        print(f"⚠️ _classify_no_units_response LLM failed ({exc}) — falling back to keyword matching")
        # Keyword fallback
        text = user_input.lower()
        # Try to extract location via alias table
        loc = None
        try:
            from agents.Normalization import LOCATION_ALIASES, normalize_location
            loc = normalize_location(user_input)
        except Exception:
            pass
        ptype = None
        for k, v in {"villa": "Villa", "apartment": "Apartment", "flat": "Apartment", "chalet": "Chalet"}.items():
            if k in text:
                ptype = v
                break
        if loc:
            return "change_location", loc, ptype, None
        if any(w in text for w in ("increase", "raise", "more", "budget", "million", " m ", "k egp")):
            return "increase_budget", None, None, None
        if ptype:
            return "change_property_type", None, ptype, None
        # Check for any number that looks like a budget
        nums = re.findall(r'\d[\d,]*', text)
        for n in nums:
            try:
                val = int(n.replace(",", ""))
                if val >= 100_000:
                    return "increase_budget", None, None, val
            except Exception:
                pass
        if any(w in text for w in ("location", "area", "city", "where", "place")):
            return "change_location", None, None, None
        if any(w in text for w in ("type", "property", "villa", "apartment", "chalet")):
            return "change_property_type", None, None, None
        return "unclear", None, None, None


# -----------------------
# Agent
# -----------------------

def compounds_agent(state: AgentState):
    print("\n--- Compounds Agent ---")

    # FIX: Pydantic attribute access (not dict-style state.get())
    user_input = (state.user_input or "").strip()
    waiting    = state.waiting_for or ""

    # ═══════════════════════════════════════════════════════════════════════
    # Handle "no units found" choice BEFORE running any DB query
    # ═══════════════════════════════════════════════════════════════════════
    if waiting == "no_units_response":
        state.waiting_for = None
        choice_text = user_input.lower()

        # ── Use LLM to classify the user's intent and extract any new values ──
        # This handles natural phrasing like "look in zayed", "try a villa instead",
        # "raise it to 10 million", "check Sheikh Zayed for an apartment", etc.
        intent, extracted_location, extracted_type, extracted_budget = \
            _classify_no_units_response(user_input, state)

        print(f"→ No-units intent: {intent} | loc={extracted_location} | type={extracted_type} | budget={extracted_budget}")

        if intent == "change_location":
            if extracted_location:
                # Validate the extracted location against the DB before accepting it
                from agents.utils.validators import validate_location
                from database import get_db
                db = get_db()
                is_valid, normalized, error = validate_location(extracted_location, db)
                if is_valid:
                    # ✅ Location known — set it directly, skip the ask-again round trip
                    state.location = normalized
                    state.context.location = normalized
                    state.context.location_normalized = normalized
                    state.budget_valid = None
                    state.context.budget_valid = False
                    # PRESERVE property_type — user only asked to change location
                    # Also preserve payment_type and budget so they aren't re-asked
                    state.agent_message = compounds_location_changed(normalized, state)
                    print(f"✓ No-units: location validated & set to {normalized} (property_type preserved)")
                    _reset_for_requery(state)
                    state.sync_to_legacy()
                    return state
                else:
                    # Location not in DB — clear it so location_agent asks fresh
                    state.location = None
                    state.context.location = None
                    state.context.location_normalized = None
                    state.budget_valid = None
                    state.context.budget_valid = False
                    # Still preserve property_type, payment_type, budget
                    print(f"⚠️ No-units: extracted location '{extracted_location}' invalid ({error}) — asking fresh")
            else:
                # LLM couldn't find a location in the text — clear it so location_agent asks
                state.location = None
                state.context.location = None
                state.context.location_normalized = None
                state.budget_valid = None
                state.context.budget_valid = False
                # IMPORTANT: Do NOT clear property_type — user only wants to change location
                print("→ No-units: change location (will ask fresh, property_type preserved)")
            _reset_for_requery(state)
            state.sync_to_legacy()
            return state

        elif intent == "increase_budget":
            # Reset budget fields only; keep location, property_type, payment_type
            state.budget = None
            state.budget_valid = None
            state.context.budget = None
            state.context.budget_valid = False
            if state.context.payment_type == "installments" or state.payment_type == "installments":
                state.Downpayment = None
                state.monthlyinstall = None
                state.context.downpayment = None
                state.context.monthly_installment = None
            # If a new budget value was already extracted from the message, set it now
            if extracted_budget and extracted_budget >= 100_000:
                state.context.budget = float(extracted_budget)
                state.budget = float(extracted_budget)
                state.context.budget_valid = True
                state.budget_valid = True
                print(f"✓ No-units: new budget set directly to {extracted_budget:,.0f} EGP")
            _reset_for_requery(state)
            print("→ No-units choice: increase budget")
            state.sync_to_legacy()
            return state

        elif intent == "change_property_type":
            if extracted_type:
                state.typeofproperty = extracted_type
                state.context.property_type = extracted_type.lower()
                state.budget_valid = None
                state.context.budget_valid = False
                state.agent_message = compounds_property_type_changed(extracted_type, state)
                print(f"✓ No-units: property type changed to {extracted_type}")
            else:
                # Clear type so property_type_agent asks fresh
                state.typeofproperty = None
                state.context.property_type = None
                state.budget_valid = None
                state.context.budget_valid = False
                print("→ No-units: change type (will ask fresh)")
            _reset_for_requery(state)
            state.sync_to_legacy()
            return state

        else:
            # Unclear — re-ask without losing any state
            state.agent_message = compounds_unclear_choice(state)
            state.waiting_for = "no_units_response"
            state.sync_to_legacy()
            return state

    load_dotenv()
    uri = os.getenv("MONGO_URI")
    if not uri:
        print("Missing MONGO_URI. Skipping compound lookup.")
        return state

    client = MongoClient(
        uri,
        tls=True,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=20000,
        connectTimeoutMS=20000,
    )

    try:
        db = client.get_default_database()

        # FIX: use Pydantic attribute access; prefer context fields, fall back to legacy
        wanted_type  = _normalize_type(
            state.context.property_type or state.typeofproperty
        ) or "Apartment"
        location     = state.context.location_normalized or state.context.location or state.location
        payment_type = _normalize_payment_type(
            state.context.payment_type or state.payment_type
        )  # "cash" | "installments" | None

        budget = _compute_budget_if_missing(db, state)
        if budget is None:
            print("Budget missing/invalid and could not be computed.")
            state.sync_to_legacy()
            return state

        pipeline = _build_units_pipeline(
            wanted_type=wanted_type,
            location=location,
            budget=budget,
            payment_type=payment_type,
            limit=300
        )

        results = list(db["units"].aggregate(pipeline, allowDiskUse=True))

        candidate_compounds: List[Dict[str, Any]] = []
        for r in results:
            name = (r.get("compound_name") or "").strip()
            loc = (r.get("compound_location") or "").strip()

            candidate_compounds.append({
                "compound_id": r.get("compound_id"),
                "compound_name": name if name else "Unknown Compound",
                "location": loc,
                "wanted_type": wanted_type,
                "payment_type_used": payment_type or "any",
                "sale_type_used": r.get("sale_type_used"),
                "min_unit_price": float(r.get("min_unit_price") or 0),
            })

        # FIX: write to BOTH legacy and context so the router can see results
        state.candidate_compounds = candidate_compounds
        state.context.candidate_compounds = candidate_compounds

        # ─────────────────────────────────────────────────────────────────
        if not candidate_compounds:
            _loc     = state.context.location or state.location or "your selected area"
            _ptype   = state.context.property_type or state.typeofproperty or "your selected property type"
            _bval    = state.context.budget or state.budget
            _bstr    = f"{int(_bval):,} EGP" if _bval else "your budget"
            _pay     = state.context.payment_type or state.payment_type or ""

            if _pay == "installments":
                _dp  = state.context.downpayment or state.Downpayment or 0
                _mi  = state.context.monthly_installment or state.monthlyinstall or 0
                _bstr = f"down payment {_dp:,} EGP / monthly {_mi:,} EGP"

            print(f"⚠️  No units found for {_ptype} in {_loc} within {_bstr}")
            state.agent_message = compounds_no_units_options(_loc, _ptype, _bstr, state)
            # Clear both copies so the router stays in compounds_agent after user responds
            state.candidate_compounds = []
            state.context.candidate_compounds = []
            state.waiting_for = "no_units_response"
            state.sync_to_legacy()
            return state

        _pay_display = state.context.payment_type or state.payment_type or "any"
        print(f"Type used for comparison: {wanted_type}")
        print(f"Location filter (units): {location}")
        print(f"Payment type: {_pay_display} -> normalized: {payment_type or 'any'}")
        print(f"Budget: {format_price(budget)}")
        print(f"Top compounds within budget: {len(candidate_compounds)}")

        for c in candidate_compounds[:10]:
            print(
                f"- {c['compound_name']} | {c['location']} | "
                f"type={c['wanted_type']} | pay={c['payment_type_used']} | "
                f"sale_type={c.get('sale_type_used')} | min_price={format_price(c['min_unit_price'])}"
            )

        state.next_step = "developers_agent"
        state.sync_to_legacy()
        return state

    finally:
        client.close()