from typing import List, Dict
from state import AgentState


def compound_ranking_agent(state: AgentState) -> AgentState:
    """
    Deterministic weighted compound ranking agent.
    Uses feature alignment with extracted compound features.
    """

    compounds: List[Dict] = state.get("final_compounds", [])
    prefs: Dict = state.get("user_preferences", {})
    weights: Dict = prefs.get("ranking_weights", {})

    FEATURE_KEYS = [
        "project_type",
        "coastal_water_orientation",
        "amenities_breadth",
        "density_scale_proxy",
        "accessibility_context",
    ]

    def extract_feature_score(compound: Dict, key: str) -> float:
        """
        Converts compound feature value into numeric score (0–1).
        You may adjust mapping logic here.
        """

        features = compound.get("features", [])

        for f in features:
            if f.get("key") == key:
                val = f.get("value")

                # Example normalization logic
                if isinstance(val, dict) and "score" in val:
                    return float(val["score"])

                if isinstance(val, (int, float)):
                    return float(val)

                if isinstance(val, str):
                    # simple categorical mapping example
                    mapping = {
                        "high": 1.0,
                        "medium": 0.6,
                        "low": 0.3,
                    }
                    return mapping.get(val.lower(), 0.5)

        return 0.0


    def compute_weighted_score(compound: Dict) -> float:
        total = 0.0

        for key in FEATURE_KEYS:
            feature_score = extract_feature_score(compound, key)
            weight = weights.get(key, 0)
            total += feature_score * weight

        return round(total, 5)


    # Compute scores
    scored = []
    for compound in compounds:
        score = compute_weighted_score(compound)
        compound["final_score"] = score
        scored.append(compound)

    # Sort by weighted score
    ranked = sorted(scored, key=lambda x: x["final_score"], reverse=True)

    state["ranked_compounds"] = ranked
    state["next_step"] = "final_output_agent"

    print("\nRanked compounds:")
    for c in ranked:
        print(c.get("compound_name"), "→", c.get("final_score"))

    return state