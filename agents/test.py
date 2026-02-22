"""
maps_scoring_v7_accuracy_fixed.py

COMPREHENSIVE ACCURACY FIXES:
-----------------------------
1. Multi-layer validation (types, keywords, exclusions, details)
2. Smarter text search with location-aware queries
3. Business status verification (operational/closed)
4. Distance sanity checks
5. Name similarity scoring to avoid unrelated results
6. Exclusion keywords to filter false positives
7. Rating threshold for quality assurance
8. Better Arabic language handling
9. Improved deduplication with name similarity
10. Highway scoring with proper error handling

What this script does:
---------------------
1) Reads A+ developers from MongoDB (developers.Developer_Class == "A+")
2) Finds compounds belonging to those developers that have lat/lng
3) Scores each compound using essential services:
   - hospital
   - school
   - shopping_mall
   - public_transport
4) Highway scoring (with graceful fallback if Roads API unavailable)

Saved in MongoDB:
----------------
DATABASE_NAME.maps_scoring (upsert by compound_id)

ENV required:
-------------
MONGO_URI
DATABASE_NAME
GOOGLE_MAPS_API_KEY

Optional:
---------
SCORING_LIMIT=50
FORCE_RESCAN=0 or 1
SLEEP_BETWEEN_COMPOUNDS=0.25
MIN_RATING=0.0  # Minimum rating to include a place (e.g., 3.0)
"""

import os
import time
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Set
from difflib import SequenceMatcher

import requests
import googlemaps
from googlemaps.exceptions import ApiError
from dotenv import load_dotenv
from pymongo import MongoClient

# ==========================================================
# CONFIG: essential services with exclusions
# ==========================================================

ESSENTIAL_AMENITIES: Dict[str, Dict[str, Any]] = {
    "hospital": {
        "radius_m": 4000,
        "nearby_types": ["hospital", "doctor", "health"],
        "text_queries": ["hospital", "مستشفى", "clinic عيادة", "medical center مركز طبي"],
        # CRITICAL: Exclude these to avoid false positives
        "exclude_keywords": [
            "pharmacy", "صيدلية", "drugstore", 
            "laboratory", "lab", "معمل", "تحاليل",
            "dental", "dentist", "أسنان", "طب أسنان",
            "veterinary", "vet", "بيطري",
            "optical", "نظارات", "عيون",
        ],
        # Must have at least ONE of these types
        "required_types_any": {"hospital", "doctor", "health", "clinic"},
    },
    "school": {
        "radius_m": 3000,
        "nearby_types": ["school", "university", "secondary_school", "primary_school"],
        "text_queries": ["school مدرسة", "academy أكاديمية", "university جامعة", "institute معهد"],
        "exclude_keywords": [
            "driving school", "تعليم قيادة", "قيادة",
            "language school", "لغات",  # unless specifically educational
            "playground", "ملعب",
            "nursery", "حضانة",  # some might want this, configure as needed
        ],
        "required_types_any": {"school", "university", "secondary_school", "primary_school"},
    },
    "shopping_mall": {
        "radius_m": 6000,
        "nearby_types": ["shopping_mall"],
        "text_queries": ["mall مول", "shopping center", "city center سيتي سنتر"],
        "exclude_keywords": [
            "supermarket", "سوبر ماركت",
            "store", "محل", "متجر",
            "shop", "دكان",
            "market", "سوق",
            "grocery", "بقالة",
        ],
        "required_types_any": {"shopping_mall"},
    },
    "public_transport": {
        "radius_m": 2500,
        "nearby_types": ["transit_station", "bus_station", "subway_station", "train_station"],
        "text_queries": ["metro station محطة مترو", "bus station محطة اتوبيس", "train station محطة قطار"],
        "exclude_keywords": [
            "gas station", "محطة بنزين", "محطة وقود",
            "petrol", "diesel", "وقود",
            "service station", "صيانة",
        ],
        "required_types_any": {"transit_station", "bus_station", "subway_station", "train_station"},
    },
}

# Weights (sum=100 for essentials)
ESSENTIAL_WEIGHTS: Dict[str, int] = {
    "shopping_mall": 35,
    "public_transport": 30,
    "school": 20,
    "hospital": 15,
}

# Highway contribution (final = 80% essentials + 20% highways)
FINAL_ESSENTIALS_RATIO = 0.80
FINAL_HIGHWAY_RATIO = 0.20

# API Configuration
MAX_PAGES = 2  # Reduced to save API calls - quality over quantity
PAGE_DELAY_SEC = 2.0
REQUEST_DELAY_SEC = 0.2
TOP_K_CLOSEST = 5
MIN_NEARBY_RESULTS_BEFORE_TEXT_FALLBACK = 3  # Increased threshold

# Roads API
ROADS_NEAREST_URL = "https://roads.googleapis.com/v1/nearestRoads"

VERSION = "maps_scoring_v7_accuracy_fixed"

# Minimum rating threshold (configurable via env)
MIN_RATING_THRESHOLD = float(os.getenv("MIN_RATING", "0.0"))

# ==========================================================
# Enhanced Helpers
# ==========================================================

def _safe_lower(x: Any) -> str:
    """Safely convert to lowercase string"""
    return (x or "").strip().lower()

def normalize_arabic(text: str) -> str:
    """Normalize Arabic text for better matching"""
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ة", "ه")
    text = text.replace("ى", "ي")
    return text

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distance in KM between two (lat,lng) points."""
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * (2 * math.asin(math.sqrt(a)))

def distance_score_km(dkm: float, best_km: float, worst_km: float) -> float:
    """Distance -> score 0..1 (linear)."""
    if dkm <= best_km:
        return 1.0
    if dkm >= worst_km:
        return 0.0
    return 1.0 - ((dkm - best_km) / (worst_km - best_km))

def category_distance_score(avg_km: float, category: str) -> float:
    """Egypt-realistic distance scoring"""
    if category == "public_transport":
        return distance_score_km(avg_km, best_km=0.6, worst_km=4.0)
    if category == "school":
        return distance_score_km(avg_km, best_km=1.0, worst_km=5.0)
    if category == "hospital":
        return distance_score_km(avg_km, best_km=1.5, worst_km=7.0)
    if category == "shopping_mall":
        return distance_score_km(avg_km, best_km=2.0, worst_km=10.0)
    return distance_score_km(avg_km, best_km=1.0, worst_km=6.0)

def string_similarity(a: str, b: str) -> float:
    """Calculate string similarity (0.0 to 1.0)"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def dedupe_by_place_id_and_name(places: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Advanced deduplication:
    - Remove duplicate place_ids
    - Remove near-duplicate names at same location
    """
    seen_ids = set()
    seen_names: List[Tuple[str, float, float]] = []
    out = []
    
    for p in places:
        pid = p.get("place_id")
        name = _safe_lower(p.get("name", ""))
        
        # Check place_id
        if pid and pid in seen_ids:
            continue
        
        # Check name similarity with existing places at similar locations
        is_duplicate = False
        if name:
            p_lat = p.get("lat", 0)
            p_lng = p.get("lng", 0)
            
            for seen_name, seen_lat, seen_lng in seen_names:
                # If very similar name AND very close location
                if (string_similarity(name, seen_name) > 0.85 and
                    haversine_km(p_lat, p_lng, seen_lat, seen_lng) < 0.1):
                    is_duplicate = True
                    break
        
        if not is_duplicate:
            if pid:
                seen_ids.add(pid)
            if name:
                seen_names.append((name, p.get("lat", 0), p.get("lng", 0)))
            out.append(p)
    
    return out

def check_exclusion_keywords(name: str, exclude_list: List[str]) -> bool:
    """
    Returns True if name contains any exclusion keyword
    """
    name_lower = _safe_lower(name)
    name_normalized = normalize_arabic(name_lower)
    
    for keyword in exclude_list:
        kw_lower = _safe_lower(keyword)
        kw_normalized = normalize_arabic(kw_lower)
        
        if kw_lower in name_lower or kw_normalized in name_normalized:
            return True
    
    return False

# ==========================================================
# Enhanced Places API with Multi-Layer Filtering
# ==========================================================

def gmaps_places_nearby_paged(
    gmaps: googlemaps.Client,
    location: Tuple[float, float],
    radius_m: int,
    place_type: str,
    counters: Dict[str, int],
    max_pages: int = MAX_PAGES,
) -> List[Dict[str, Any]]:
    """Nearby search with paging"""
    results: List[Dict[str, Any]] = []
    page_token: Optional[str] = None

    for page in range(max_pages):
        if page_token:
            time.sleep(PAGE_DELAY_SEC)

        try:
            counters["places_nearby_calls"] += 1
            resp = gmaps.places_nearby(
                location=location,
                radius=radius_m,
                type=place_type,
                page_token=page_token,
            )

            status = resp.get("status")
            if status not in ("OK", "ZERO_RESULTS"):
                msg = resp.get("error_message") or ""
                print(f"  Warning: Places Nearby status={status} {msg}")
                break

            results.extend(resp.get("results", []) or [])
            page_token = resp.get("next_page_token")

            if not page_token or status == "ZERO_RESULTS":
                break

            time.sleep(REQUEST_DELAY_SEC)
            
        except Exception as e:
            print(f"  Error in nearby search: {e}")
            break

    return results

def gmaps_text_search(
    gmaps: googlemaps.Client,
    query: str,
    location: Tuple[float, float],
    radius_m: int,
    counters: Dict[str, int],
) -> List[Dict[str, Any]]:
    """Text search with error handling"""
    try:
        counters["places_text_calls"] += 1
        resp = gmaps.places(query=query, location=location, radius=radius_m)
        status = resp.get("status")
        
        if status not in ("OK", "ZERO_RESULTS"):
            msg = resp.get("error_message") or ""
            print(f"  Warning: Text Search status={status} {msg}")
            return []
            
        return resp.get("results", []) or []
        
    except Exception as e:
        print(f"  Error in text search: {e}")
        return []

def verify_place_with_details(
    gmaps: googlemaps.Client,
    place_id: str,
    category: str,
    counters: Dict[str, int],
) -> Tuple[bool, Dict[str, Any]]:
    """
    STRONGEST ACCURACY MEASURE:
    Verify place via Place Details API
    
    Returns: (is_valid, details_dict)
    """
    try:
        counters["place_details_calls"] += 1
        
        # Request comprehensive fields
        det = gmaps.place(
            place_id=place_id,
            fields=["name", "types", "business_status", "rating", "user_ratings_total", "vicinity", "formatted_address"]
        )
        
        result = (det or {}).get("result") or {}
        
        # Extract data
        types = set(_safe_lower(t) for t in (result.get("types") or []))
        name = _safe_lower(result.get("name", ""))
        business_status = _safe_lower(result.get("business_status", ""))
        rating = result.get("rating")
        num_ratings = result.get("user_ratings_total", 0)
        
        # Check 1: Business must be operational
        if business_status and "closed" in business_status:
            return False, {}
        
        # Check 2: Must have required types
        cfg = ESSENTIAL_AMENITIES[category]
        required_types = cfg.get("required_types_any", set())
        
        if required_types and not (types & required_types):
            return False, {}
        
        # Check 3: Exclusion keywords
        exclude_list = cfg.get("exclude_keywords", [])
        if check_exclusion_keywords(name, exclude_list):
            return False, {}
        
        # Check 4: Rating threshold (if configured)
        if MIN_RATING_THRESHOLD > 0 and rating is not None:
            if float(rating) < MIN_RATING_THRESHOLD:
                return False, {}
        
        # Check 5: Must have reasonable number of ratings for trust
        # (Skip for transport as they may have fewer reviews)
        if category != "public_transport":
            if rating and num_ratings < 3:  # Too few ratings to trust
                return False, {}
        
        return True, result
        
    except ApiError as e:
        print(f"  API Error in place details: {e}")
        return False, {}
    except Exception as e:
        print(f"  Error in place details: {e}")
        return False, {}

def quick_filter_place(category: str, place: Dict[str, Any]) -> bool:
    """
    FIRST PASS: Quick filter before expensive Details API call
    Returns True if place MIGHT be valid (needs verification)
    """
    name = place.get("name", "")
    types = set(_safe_lower(t) for t in (place.get("types") or []))
    
    cfg = ESSENTIAL_AMENITIES[category]
    
    # Check 1: Exclusion keywords (fast rejection)
    exclude_list = cfg.get("exclude_keywords", [])
    if check_exclusion_keywords(name, exclude_list):
        return False
    
    # Check 2: Must have at least one required type
    required_types = cfg.get("required_types_any", set())
    if required_types and not (types & required_types):
        return False
    
    # Check 3: Rating check (if available in initial data)
    if MIN_RATING_THRESHOLD > 0:
        rating = place.get("rating")
        if rating is not None and float(rating) < MIN_RATING_THRESHOLD:
            return False
    
    return True

def collect_places_for_category(
    gmaps: googlemaps.Client,
    category: str,
    lat: float,
    lng: float,
    counters: Dict[str, int],
) -> Dict[str, Any]:
    """
    COMPREHENSIVE place collection with multi-layer filtering:
    1. Nearby Search across types
    2. Quick filter (types + exclusions)
    3. Distance validation
    4. Deduplication
    5. Place Details verification
    6. Final sorting and selection
    """
    cfg = ESSENTIAL_AMENITIES[category]
    radius_m = int(cfg["radius_m"])
    location = (lat, lng)

    raw: List[Dict[str, Any]] = []

    # STEP 1: Nearby search across all configured types
    for place_type in cfg["nearby_types"]:
        nearby_results = gmaps_places_nearby_paged(gmaps, location, radius_m, place_type, counters)
        raw.extend(nearby_results)

    raw = dedupe_by_place_id_and_name(raw)
    
    initial_count = len(raw)

    # STEP 2: If results are insufficient, try text search
    if len(raw) < MIN_NEARBY_RESULTS_BEFORE_TEXT_FALLBACK:
        for query_template in cfg.get("text_queries", []):
            # More targeted text search
            query = f"{query_template} in Cairo Egypt"
            text_results = gmaps_text_search(gmaps, query, location, radius_m, counters)
            raw.extend(text_results)
        
        raw = dedupe_by_place_id_and_name(raw)

    # STEP 3: Convert to distance list with quick filter
    candidates: List[Dict[str, Any]] = []
    
    for p in raw:
        # Quick rejection
        if not quick_filter_place(category, p):
            continue
        
        # Extract location
        loc = (p.get("geometry") or {}).get("location") or {}
        plat = loc.get("lat")
        plng = loc.get("lng")
        
        if plat is None or plng is None:
            continue

        # Calculate distance
        dkm = haversine_km(lat, lng, float(plat), float(plng))
        
        # Distance sanity check - reject if beyond radius
        if dkm > (radius_m / 1000.0):
            continue
        
        candidates.append({
            "name": p.get("name"),
            "place_id": p.get("place_id"),
            "vicinity": p.get("vicinity"),
            "rating": p.get("rating"),
            "user_ratings_total": p.get("user_ratings_total", 0),
            "distance_km": round(float(dkm), 3),
            "types": (p.get("types") or [])[:15],
            "lat": float(plat),
            "lng": float(plng),
        })

    # Sort by distance
    candidates.sort(key=lambda x: x["distance_km"])
    
    filtered_count = len(candidates)

    # STEP 4: Strong verification via Place Details for top candidates
    # Check more candidates than we need to ensure we get TOP_K_CLOSEST valid ones
    candidates_to_verify = candidates[:min(TOP_K_CLOSEST * 3, 15)]
    
    verified: List[Dict[str, Any]] = []
    
    for candidate in candidates_to_verify:
        pid = candidate.get("place_id")
        if not pid:
            continue
        
        is_valid, details = verify_place_with_details(gmaps, pid, category, counters)
        
        if is_valid:
            # Enrich with details data
            candidate["verified"] = True
            candidate["business_status"] = details.get("business_status", "OPERATIONAL")
            candidate["formatted_address"] = details.get("formatted_address")
            
            # Update rating if available in details
            if details.get("rating"):
                candidate["rating"] = details["rating"]
            if details.get("user_ratings_total"):
                candidate["user_ratings_total"] = details["user_ratings_total"]
            
            verified.append(candidate)
        
        # Stop if we have enough verified places
        if len(verified) >= TOP_K_CLOSEST:
            break
        
        time.sleep(0.05)  # Small delay between detail calls

    # STEP 5: Final selection
    verified.sort(key=lambda x: x["distance_km"])
    closest = verified[:TOP_K_CLOSEST]

    count = len(closest)
    avg_km = (sum(x["distance_km"] for x in closest) / count) if count else None

    return {
        "radius_m": radius_m,
        "places": closest,
        "count": count,
        "avg_km": avg_km,
        "stats": {
            "initial_raw": initial_count,
            "after_quick_filter": filtered_count,
            "after_details_verification": len(verified),
            "final_selected": count,
        }
    }

# ==========================================================
# Highways with proper error handling
# ==========================================================

def get_nearest_road_point(
    api_key: str,
    lat: float,
    lng: float,
    counters: Dict[str, int]
) -> Optional[Tuple[float, float]]:
    """Get nearest road point using Roads API"""
    try:
        counters["roads_calls"] += 1
        params = {"points": f"{lat},{lng}", "key": api_key}
        r = requests.get(ROADS_NEAREST_URL, params=params, timeout=20)
        
        if r.status_code != 200:
            return None
            
        data = r.json() or {}
        snapped = (data.get("snappedPoints") or [])
        
        if not snapped:
            return None
            
        loc = (snapped[0].get("location") or {})
        slat = loc.get("latitude")
        slng = loc.get("longitude")
        
        if slat is None or slng is None:
            return None
            
        return float(slat), float(slng)
        
    except Exception as e:
        print(f"  Roads API error: {e}")
        return None

def road_class_hint(
    gmaps: googlemaps.Client,
    lat: float,
    lng: float,
    counters: Dict[str, int]
) -> str:
    """Determine road class from reverse geocode"""
    try:
        counters["reverse_geocode_calls"] += 1
        res = gmaps.reverse_geocode((lat, lng))
        
        if not res:
            return "unknown"
            
        addr = _safe_lower((res[0] or {}).get("formatted_address", ""))
        
        # Check for major road indicators
        major_indicators = [
            "ring", "ring road", "الطريق الدائري", "الدائري",
            "highway", "motorway", "autostrade", "الصحراوي",
            "طريق", "شارع رئيسي"
        ]
        
        for indicator in major_indicators:
            if indicator in addr:
                return "major"
        
        return "local"
        
    except Exception as e:
        print(f"  Reverse geocode error: {e}")
        return "unknown"

def score_highways(
    gmaps: googlemaps.Client,
    api_key: str,
    lat: float,
    lng: float,
    counters: Dict[str, int]
) -> Dict[str, Any]:
    """
    Score highway access with graceful degradation
    """
    try:
        snapped = get_nearest_road_point(api_key, lat, lng, counters)
        
        if not snapped:
            return {
                "highway_score": 0.0,
                "nearest_road_distance_km": None,
                "road_class_hint": "unavailable",
                "note": "Roads API unavailable or returned no results",
                "error": None,
            }
        
        rlat, rlng = snapped
        dkm = haversine_km(lat, lng, rlat, rlng)
        
        # Get road classification
        hint = road_class_hint(gmaps, rlat, rlng, counters)

        # Distance scoring: 0.3km best, 8km worst
        dist_score = distance_score_km(dkm, best_km=0.3, worst_km=8.0)

        # Boost for major roads
        multiplier = 1.15 if hint == "major" else 1.0
        final_score = clamp(dist_score * multiplier, 0.0, 1.0)

        return {
            "highway_score": round(final_score * 100.0, 2),
            "nearest_road_distance_km": round(float(dkm), 3),
            "road_class_hint": hint,
            "snapped_point": {"lat": rlat, "lng": rlng},
            "error": None,
        }
        
    except Exception as e:
        print(f"  Highway scoring error: {e}")
        return {
            "highway_score": 0.0,
            "nearest_road_distance_km": None,
            "road_class_hint": "error",
            "note": "Error during highway scoring",
            "error": str(e),
        }

# ==========================================================
# Scoring with dynamic weight normalization
# ==========================================================

def score_essentials(
    gmaps: googlemaps.Client,
    lat: float,
    lng: float,
    counters: Dict[str, int],
) -> Dict[str, Any]:
    """
    Score essentials with dynamic renormalization
    """
    breakdown: Dict[str, Any] = {}
    available_weights: Dict[str, int] = {}

    # Collect places for each category
    collected: Dict[str, Dict[str, Any]] = {}
    
    for cat in ESSENTIAL_AMENITIES.keys():
        print(f"  Collecting {cat}...", end=" ")
        collected[cat] = collect_places_for_category(gmaps, cat, lat, lng, counters)
        print(f"found {collected[cat]['count']}")
        
        if collected[cat]["count"] > 0:
            available_weights[cat] = int(ESSENTIAL_WEIGHTS.get(cat, 0))

    weight_sum = sum(available_weights.values())

    # If nothing found at all
    if weight_sum <= 0:
        for cat, info in collected.items():
            breakdown[cat] = {
                "radius_m": info["radius_m"],
                "weight": ESSENTIAL_WEIGHTS.get(cat, 0),
                "effective_weight": 0,
                "count": info["count"],
                "avg_distance_km": None,
                "distance_score_0_1": 0.0,
                "closest_places": info["places"],
                "stats": info.get("stats", {}),
            }
        return {
            "essentials_score": 0.0,
            "breakdown": breakdown,
            "effective_weight_sum": 0
        }

    # Renormalize weights
    effective_weights: Dict[str, float] = {
        cat: (w / weight_sum) * 100.0 for cat, w in available_weights.items()
    }

    weighted_score = 0.0

    for cat, info in collected.items():
        avg_km = info["avg_km"]
        
        if avg_km is None:
            dist_score = 0.0
            eff_w = 0.0
        else:
            dist_score = category_distance_score(float(avg_km), cat)
            eff_w = float(effective_weights.get(cat, 0.0))
            weighted_score += eff_w * dist_score

        breakdown[cat] = {
            "radius_m": info["radius_m"],
            "weight": int(ESSENTIAL_WEIGHTS.get(cat, 0)),
            "effective_weight": round(eff_w, 2),
            "count": int(info["count"]),
            "avg_distance_km": round(float(avg_km), 3) if avg_km is not None else None,
            "distance_score_0_1": round(float(dist_score), 3),
            "closest_places": info["places"],
            "stats": info.get("stats", {}),
        }

    essentials_score = weighted_score
    
    return {
        "essentials_score": round(float(essentials_score), 2),
        "breakdown": breakdown,
        "effective_weight_sum": round(float(sum(effective_weights.values())), 2),
    }

# ==========================================================
# MongoDB Integration
# ==========================================================

def main():
    load_dotenv()

    mongo_uri = os.getenv("MONGO_URI")
    db_name = os.getenv("DATABASE_NAME")
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")

    if not mongo_uri or not db_name or not api_key:
        raise RuntimeError("Missing env vars. Required: MONGO_URI, DATABASE_NAME, GOOGLE_MAPS_API_KEY")

    limit = int(os.getenv("SCORING_LIMIT", "0") or "0")
    force_rescan = (os.getenv("FORCE_RESCAN", "0") == "1")
    sleep_between = float(os.getenv("SLEEP_BETWEEN_COMPOUNDS", "0.25") or "0.25")

    print(f"Configuration:")
    print(f"  Database: {db_name}")
    print(f"  Limit: {limit if limit > 0 else 'All compounds'}")
    print(f"  Force rescan: {force_rescan}")
    print(f"  Min rating: {MIN_RATING_THRESHOLD}")
    print(f"  Version: {VERSION}\n")

    client = MongoClient(mongo_uri)
    
    try:
        db = client[db_name]
        developers_col = db["developers"]
        compounds_col = db["compounds"]
        maps_scoring_col = db["maps_scoring"]

        # Create indexes
        maps_scoring_col.create_index("compound_id", unique=True)
        maps_scoring_col.create_index([("total_score", -1)])
        maps_scoring_col.create_index([("scored_at", -1)])
        maps_scoring_col.create_index([("version", 1)])

        gmaps = googlemaps.Client(key=api_key)

        # Get A+ developers
        a_plus_devs = list(developers_col.find({"Developer_Class": "A+"}, {"_id": 1}))
        a_plus_ids_obj = [d["_id"] for d in a_plus_devs if d.get("_id")]
        a_plus_ids_str = [str(x) for x in a_plus_ids_obj]

        print(f"A+ developers found: {len(a_plus_ids_str)}\n")
        
        if not a_plus_ids_str:
            print("No A+ developers found!")
            return

        # Query compounds
        query = {
            "developer_id": {"$in": a_plus_ids_str},
            "lat": {"$exists": True, "$ne": None},
            "lng": {"$exists": True, "$ne": None},
        }

        projection = {
            "_id": 1,
            "name": 1,
            "compound_name": 1,
            "developer_id": 1,
            "developer_name": 1,
            "developer_nawy_id": 1,
            "location": 1,
            "lat": 1,
            "lng": 1,
            "nawy_id": 1,
        }

        cur = compounds_col.find(query, projection)
        compounds = list(cur)
        
        if limit and limit > 0:
            compounds = compounds[:limit]

        print(f"Compounds to score: {len(compounds)}\n")
        
        if not compounds:
            print("No compounds found to score!")
            return

        print("="*70)
        
        ok = 0
        fail = 0

        for i, comp in enumerate(compounds, 1):
            comp_id = comp["_id"]
            lat = float(comp["lat"])
            lng = float(comp["lng"])
            name = (comp.get("name") or comp.get("compound_name") or "Unknown").strip()

            # Skip if already scored (unless force rescan)
            if not force_rescan:
                existing = maps_scoring_col.find_one(
                    {"compound_id": comp_id, "version": VERSION},
                    {"_id": 1}
                )
                if existing:
                    print(f"[{i}/{len(compounds)}] SKIP (already scored): {name}")
                    continue

            print(f"\n[{i}/{len(compounds)}] Scoring: {name}")
            print(f"  Location: {comp.get('location')} ({lat}, {lng})")

            counters = {
                "places_nearby_calls": 0,
                "places_text_calls": 0,
                "place_details_calls": 0,
                "roads_calls": 0,
                "reverse_geocode_calls": 0,
            }

            try:
                # Score essentials
                essentials = score_essentials(gmaps, lat, lng, counters)
                
                # Score highways
                highways = score_highways(gmaps, api_key, lat, lng, counters)

                essentials_score = float(essentials["essentials_score"])
                highway_score = float(highways.get("highway_score", 0.0))

                # Calculate final score
                total = (FINAL_ESSENTIALS_RATIO * essentials_score) + (FINAL_HIGHWAY_RATIO * highway_score)

                # Prepare document
                doc = {
                    "compound_id": comp_id,
                    "compound_name": name,
                    "compound_nawy_id": comp.get("nawy_id"),

                    "developer_id": comp.get("developer_id"),
                    "developer_name": comp.get("developer_name"),
                    "developer_nawy_id": comp.get("developer_nawy_id"),

                    "location": comp.get("location"),
                    "coordinates": {"lat": lat, "lng": lng},

                    # Scores
                    "total_score": round(float(total), 2),
                    "essentials_score": essentials_score,
                    "highway_score": highway_score,

                    "score_breakdown": {
                        **essentials["breakdown"],
                        "highways": highways,
                    },

                    # Metadata
                    "api_usage": counters,
                    "scored_at": datetime.now(timezone.utc),
                    "version": VERSION,
                    "config": {
                        "min_rating_threshold": MIN_RATING_THRESHOLD,
                        "essentials_ratio": FINAL_ESSENTIALS_RATIO,
                        "highway_ratio": FINAL_HIGHWAY_RATIO,
                    }
                }

                # Save to database
                maps_scoring_col.update_one(
                    {"compound_id": comp_id},
                    {"$set": doc},
                    upsert=True
                )

                ok += 1
                
                print(f"  ✓ SUCCESS")
                print(f"    Total score: {doc['total_score']:.2f}/100")
                print(f"    API calls: {sum(counters.values())}")
                
                time.sleep(sleep_between)

            except Exception as e:
                fail += 1
                print(f"  ✗ FAILED: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(1.0)

        print("\n" + "="*70)
        print("SCORING COMPLETE")
        print("="*70)
        print(f"Success: {ok}")
        print(f"Failed: {fail}")
        print(f"Saved to: {db_name}.maps_scoring")
        print(f"Version: {VERSION}")
        print("="*70)

    finally:
        client.close()


if __name__ == "__main__":
    main()