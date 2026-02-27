import os
import certifi
from pymongo import MongoClient
from dotenv import load_dotenv
from bson import ObjectId
from datetime import datetime

from state import AgentState


# ---------------------------------------------------------------------------
# Market benchmark helper
# ---------------------------------------------------------------------------

def _get_market_price_per_m2(db, location: str, property_type: str = "Apartment") -> float:
    """
    Compute the average price-per-m² from all units in the same location.
    Falls back to a broad average if no location match is found.
    """
    pipeline = [
        {
            "$match": {
                "location": {"$regex": location, "$options": "i"},
                "price": {"$gt": 0},
                "area": {"$gt": 0},
            }
        },
        {
            "$project": {
                "price_per_m2": {"$divide": ["$price", "$area"]}
            }
        },
        {
            "$group": {
                "_id": None,
                "avg_ppm2": {"$avg": "$price_per_m2"},
                "count": {"$sum": 1}
            }
        }
    ]

    result = list(db["properties"].aggregate(pipeline))

    if result and result[0]["count"] >= 5:
        return float(result[0]["avg_ppm2"])

    # Broad fallback — whole collection
    fallback = list(db["properties"].aggregate([
        {"$match": {"price": {"$gt": 0}, "area": {"$gt": 0}}},
        {"$project": {"price_per_m2": {"$divide": ["$price", "$area"]}}},
        {"$group": {"_id": None, "avg_ppm2": {"$avg": "$price_per_m2"}}}
    ]))
    return float(fallback[0]["avg_ppm2"]) if fallback else 50_000.0


# ---------------------------------------------------------------------------
# Investment Scorer
# ---------------------------------------------------------------------------

class InvestmentScorer:
    def __init__(self, units, compound, developer_score, market_price_per_m2: float):
        self.units = units
        self.compound = compound or {}
        self.developer_score = developer_score
        self.market_price_per_m2 = market_price_per_m2

        self.amenities = self.compound.get("amenities_list") or []
        # Dynamic max based on dataset observation (raise if your data has more)
        self.max_amenities = max(20, len(self.amenities))

    # ------------------------------------------------------------------
    # Individual scoring components
    # ------------------------------------------------------------------

    def _price_efficiency(self, unit) -> float:
        """
        Compare unit price/m² against the market benchmark for the area.
        Score = 1.0 when unit is at or below market; decays toward 0 as it
        gets more expensive relative to market.
        """
        price = float(unit.get("price") or 0)
        area = float(unit.get("area") or 1)
        if price == 0 or area == 0:
            return 0.0

        ppm2 = price / area
        if self.market_price_per_m2 <= 0:
            return 0.5  # no data, neutral

        ratio = self.market_price_per_m2 / ppm2
        # Cap at 1.0 (can't score better than market) and floor at 0
        return max(0.0, min(1.0, ratio))

    def _liquidity_score(self, unit) -> float:
        """2–3 bed units are easiest to sell/rent."""
        bedrooms = int(unit.get("bedrooms") or 0)
        if bedrooms in [2, 3]:
            return 1.0
        elif bedrooms == 4:
            return 0.7
        elif bedrooms == 1:
            return 0.6
        else:
            return 0.4

    def _compound_score(self) -> float:
        return min(1.0, len(self.amenities) / self.max_amenities)

    def _payment_score(self, unit) -> float:
        payment_plans = unit.get("payment_plans") or []
        if not payment_plans:
            return 0.6

        has_installment = any(
            not p.get("is_cash", True) for p in payment_plans
        )
        return 1.0 if has_installment else 0.75

    def _resale_score(self, unit) -> float:
        sale_type = str(unit.get("sale_type") or "").strip().lower()
        return 1.0 if sale_type == "resale" else 0.75

    def _finishing_score(self, unit) -> float:
        """Fully-finished units are more liquid (rent-ready/move-in-ready)."""
        finishing = str(unit.get("finishing") or "").strip().lower()
        mapping = {
            "fully finished": 1.0,
            "fully-finished": 1.0,
            "finished": 1.0,
            "semi finished": 0.65,
            "semi-finished": 0.65,
            "core and shell": 0.40,
            "core & shell": 0.40,
        }
        for key, val in mapping.items():
            if key in finishing:
                return val
        return 0.5  # unknown → neutral

    def _delivery_score(self, unit) -> float:
        """
        Penalise far-off or unknown delivery dates (delivery risk).
        Resale units have no delivery risk → full score.
        """
        sale_type = str(unit.get("sale_type") or "").strip().lower()
        if sale_type == "resale":
            return 1.0

        delivery_year = unit.get("delivery_year")
        if delivery_year is None:
            return 0.50  # unknown risk

        current_year = datetime.now().year
        years_away = int(delivery_year) - current_year

        if years_away <= 0:
            return 1.0   # already delivered / this year
        elif years_away == 1:
            return 0.85
        elif years_away == 2:
            return 0.70
        elif years_away == 3:
            return 0.55
        else:
            return 0.35  # 4+ years away — high risk

    # ------------------------------------------------------------------
    # Aggregate score
    # ------------------------------------------------------------------

    def score_unit(self, unit):
        price_eff    = self._price_efficiency(unit)
        liquidity    = self._liquidity_score(unit)
        compound_sc  = self._compound_score()
        payment_sc   = self._payment_score(unit)
        resale_sc    = self._resale_score(unit)
        finishing_sc = self._finishing_score(unit)
        delivery_sc  = self._delivery_score(unit)

        final_score = (
            0.20 * price_eff       +   # market-relative value
            0.15 * liquidity       +   # bedroom liquidity
            0.15 * self.developer_score +  # developer quality
            0.12 * compound_sc     +   # amenity breadth
            0.10 * delivery_sc     +   # delivery risk
            0.08 * finishing_sc    +   # finish quality
            0.07 * payment_sc      +   # payment flexibility
            0.03 * resale_sc           # primary/resale distinction
        )

        metrics = {
            "price_efficiency":  round(price_eff, 3),
            "liquidity":         round(liquidity, 3),
            "developer_score":   round(self.developer_score, 3),
            "compound_score":    round(compound_sc, 3),
            "delivery_score":    round(delivery_sc, 3),
            "finishing_score":   round(finishing_sc, 3),
            "payment_score":     round(payment_sc, 3),
            "resale_score":      round(resale_sc, 3),
        }

        return round(final_score, 3), metrics


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_developer_class_score(state: AgentState, compound_name: str) -> float:
    final_candidates = state.get("final_candidates") or []
    dev_class = "C"
    for dev in final_candidates:
        matched = dev.get("matched_compound_names") or []
        if isinstance(matched, list) and compound_name in matched:
            dev_class = dev.get("Developer_Class", "C")
            break

    class_map = {"A+": 1.0, "A": 0.8, "B": 0.6, "C": 0.4}
    return class_map.get(dev_class, 0.4)


def _format_unit_output(rank: int, su: dict) -> str:
    u = su["unit"]
    m = su["metrics"]
    price = int(u.get("price") or 0)
    area = float(u.get("area") or 0)
    ppm2 = int(price / area) if area > 0 else 0
    delivery = u.get("delivery_year") or "N/A"
    sale_type = u.get("sale_type") or "N/A"
    finishing = u.get("finishing") or "N/A"

    lines = [
        f"{rank}. Unit ID: {u.get('_id')}",
        f"   Price:        {price:,} EGP",
        f"   Price/m²:     {ppm2:,} EGP/m²",
        f"   Area:         {area:.0f} m²",
        f"   Bedrooms:     {u.get('bedrooms', 'N/A')}",
        f"   Finishing:    {finishing.title()}",
        f"   Sale Type:    {sale_type}",
        f"   Delivery:     {delivery}",
        f"   Score:        {su['score']:.3f}",
        f"   Score Breakdown:",
        f"     • Price vs Market:  {m['price_efficiency']:.2f}",
        f"     • Liquidity:        {m['liquidity']:.2f}",
        f"     • Developer:        {m['developer_score']:.2f}",
        f"     • Compound:         {m['compound_score']:.2f}",
        f"     • Delivery Risk:    {m['delivery_score']:.2f}",
        f"     • Finishing:        {m['finishing_score']:.2f}",
        f"     • Payment Flex:     {m['payment_score']:.2f}",
        f"   URL: {u.get('nawy_url', 'N/A')}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

def rent_agent(state: AgentState) -> dict:
    print("\n--- Investment Agent ---")

    candidate_units = state.get("candidate_units") or []
    if not candidate_units:
        print("No candidate units found.")
        return state

    selected_compound = state.get("selected_compound")
    if not selected_compound:
        print("No compound selected.")
        return state

    compound_id_str = selected_compound["id"]
    compound_name   = selected_compound["name"]

    load_dotenv()
    uri = os.getenv("MONGO_URI")
    client = MongoClient(uri, tlsCAFile=certifi.where())
    db = client.get_default_database()

    try:
        try:
            comp_oid = ObjectId(compound_id_str)
        except Exception:
            comp_oid = compound_id_str

        compound = db["compounds"].find_one({"_id": comp_oid}) or {}

        # Derive location string for market benchmark
        location = compound.get("location") or state.get("location") or ""

        # Fetch enrichment data
        market_ppm2          = _get_market_price_per_m2(db, location)
        dev_score            = _get_developer_class_score(state, compound_name)

        scorer = InvestmentScorer(
            units=candidate_units,
            compound=compound,
            developer_score=dev_score,
            market_price_per_m2=market_ppm2,
        )

        scored_units = []
        for unit in candidate_units:
            score, metrics = scorer.score_unit(unit)
            scored_units.append({"unit": unit, "score": score, "metrics": metrics})

        scored_units.sort(key=lambda x: x["score"], reverse=True)

        print(f"\nEvaluated {len(candidate_units)} units in {compound_name}")
        print(f"Market benchmark (price/m²): {int(market_ppm2):,} EGP/m²")
        print("\nTop 3 Investment Units:\n")

        for i, su in enumerate(scored_units[:3], 1):
            print(_format_unit_output(i, su))
            print()

        state["top_investment_units"] = [su["unit"] for su in scored_units[:3]]

    finally:
        client.close()

    state["_end_node_reached"] = True
    return state


def living_agent(state: AgentState) -> dict:
    print("\n--- Living Agent ---")
    print("Welcome to the Living Agent! (Implementation Pending)")
    state["_end_node_reached"] = True
    return state


def unit_agent(state: AgentState) -> dict:
    print("\n--- Unite Agent (Router) ---")
    purpose = (state.get("purpose") or "").lower()

    if "invest" in purpose:
        state["route"] = "rent"
        print("Routing to Rent Agent...")
    else:
        state["route"] = "living"
        print("Routing to Living Agent...")

    return state