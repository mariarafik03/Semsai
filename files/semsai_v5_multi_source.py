"""
SEMSAI AGENTIC LUXURY APPRAISER — v5.0 (MULTI-SOURCE)
======================================================
3-source price aggregator: Nawy + PropertyFinder + Aqarmap + CatBoost ML

ARCHITECTURE:
  ┌─────────────┐  ┌──────────────────┐  ┌────────────┐  ┌────────┐
  │  nawy.com   │  │ propertyfinder.eg│  │ aqarmap.eg │  │ ML     │
  │  (Tavily)   │  │ (direct HTTP)    │  │ (API+HTTP) │  │CatBoost│
  └──────┬──────┘  └────────┬─────────┘  └─────┬──────┘  └───┬────┘
         │                  │                   │             │
         └──────────────────┴───────────────────┴─────────────┘
                                    │
                         ┌──────────▼──────────┐
                         │   Smart Merge Logic  │
                         │  - Outlier removal   │
                         │  - Cluster split     │
                         │  - Source weighting  │
                         │  - Confidence flags  │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼──────────┐
                         │   Final Appraisal    │
                         │   + Audit Trail      │
                         └─────────────────────┘

WEIGHT SCHEME (adaptive):
  Source          Base weight   Adjustments
  ──────────────  ──────────    ──────────────────────────────────────
  Nawy            40%           -10% if LOW_CONFIDENCE
  PropertyFinder  30%           -10% if LOW_CONFIDENCE
  Aqarmap         20%           -10% if LOW_CONFIDENCE
  ML model        10%           +30% total if all web sources fail

  If a source returns no prices → its weight is redistributed
  proportionally to the remaining sources.

CONFIDENCE FLAGS:
  LOW_CONFIDENCE per source: n≤2, high variance (CV>50%), ppm>180k
  GLOBAL LOW_CONFIDENCE:     fewer than 2 web sources returned prices
"""

import pandas as pd
import re
import json
import time
import statistics
import numpy as np
import requests
from catboost import CatBoostRegressor, Pool
from langgraph.graph import StateGraph
from typing import TypedDict

import scraper_nawy          as nawy_scraper
import scraper_propertyfinder as pf_scraper
import scraper_aqarmap        as aq_scraper

# ── Config ────────────────────────────────────────────────────
TAVILY_API_KEY = "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"

# Base weights (must sum to 1.0)
BASE_WEIGHTS = {
    "nawy":          0.40,
    "propertyfinder": 0.30,
    "aqarmap":        0.20,
    "ml":             0.10,
}

LOW_CONF_PENALTY  = 0.10   # deducted from a source weight if it's low-confidence
ML_FLOOR_WEIGHT   = 0.25   # ML minimum weight when all web sources fail

cat_features = [
    "property_type", "finishing", "sale_type",
    "compound_name", "location_TRIMMED", "developer_name"
]

# ── Load model ────────────────────────────────────────────────
print("Loading SEMSAI v5.0 Multi-Source Appraiser...")
import os, sys

# Search for the model in common locations
_MODEL_CANDIDATES = [
    "catboost_true_model.cbm",                          # same folder
    os.path.join(os.path.dirname(__file__), "catboost_true_model.cbm"),
    os.path.join(os.path.expanduser("~"), "catboost_true_model.cbm"),
    r"C:\Users\user\OneDrive\Desktop\modelandweb\OneDrive\Desktop\agent\catboost_true_model.cbm",
]

model = None
for _path in _MODEL_CANDIDATES:
    if os.path.exists(_path):
        try:
            model = CatBoostRegressor()
            model.load_model(_path)
            print(f" ✅ CatBoost model loaded from: {_path}\n")
            break
        except Exception as e:
            print(f" ⚠️  Found {_path} but failed to load: {e}")

if model is None:
    print(" ⚠️  catboost_true_model.cbm not found — ML prediction disabled.")
    print("     Place the .cbm file in the same folder as this script.\n")

# ── User input ────────────────────────────────────────────────
def get_numeric_input(prompt, type_func=float):
    while True:
        try:
            return type_func(input(prompt))
        except ValueError:
            print("  -> Please enter a number.")


def get_categorical_input(prompt, options):
    opts = " / ".join(options)
    while True:
        choice = input(f"{prompt} ({opts}):\n> ").strip().lower()
        for o in options:
            if choice == o.lower():
                return o
        print("  -> Invalid choice.")


def get_user_input():
    print("=" * 55 + "\n   SEMSAI v5.0 — ENTER PROPERTY DETAILS\n" + "=" * 55)
    return {
        "area":          get_numeric_input("1. Area (sqm)?\n> ", float),
        "bedrooms":      get_numeric_input("2. Bedrooms?\n> ", int),
        "bathrooms":     get_numeric_input("3. Bathrooms?\n> ", int),
        "delivery_year": get_numeric_input("4. Delivery Year?\n> ", int),
        "property_type": get_categorical_input("5. Property Type?", ["Apartment", "Villa", "Chalet"]),
        "finishing":     get_categorical_input("6. Finishing?", ["Finished", "semi-finished", "not finished", "Furnished"]),
        "sale_type":     get_categorical_input("7. Sale Type?", ["Resale", "Developer Sale"]),
        "compound":      input("8. Compound Name:\n> ").strip(),
        "location":      input("9. Location:\n> ").strip(),
        "developer":     input("10. Developer Name:\n> ").strip(),
    }

# ── LangGraph state ───────────────────────────────────────────
class GraphState(TypedDict):
    u:              dict           # user input
    nawy_result:    dict
    pf_result:      dict
    aq_result:      dict
    ml_price:       float
    final_price:    float
    audit:          dict

# ── Serialise ScraperResult to plain dict ─────────────────────
def _r2d(r) -> dict:
    return {
        "source":   r.source,
        "prices":   r.prices,
        "median":   r.median,
        "ppm":      r.ppm,
        "n":        r.n,
        "low_conf": r.low_conf,
        "fallback": r.fallback,
        "urls":     r.urls,
        "error":    r.error,
        "ok":       bool(r),
    }

def _empty(source):
    return {
        "source": source, "prices": [], "median": 0, "ppm": 0,
        "n": 0, "low_conf": True, "fallback": False, "urls": [], "error": "not run", "ok": False
    }

# ── Node 1: Nawy ──────────────────────────────────────────────
def node_nawy(state: GraphState) -> dict:
    u = state["u"]
    print("\n" + "━"*55)
    print("  SOURCE 1/3: Nawy.com")
    print("━"*55)
    try:
        r = nawy_scraper.scrape(
            compound  = u["compound"],
            area      = u["area"],
            bedrooms  = u["bedrooms"],
            ptype     = u["property_type"],
            sale_type = u["sale_type"],
            location  = u["location"],
        )
        d = _r2d(r)
    except Exception as e:
        print(f"   [NAWY ERROR] {e}")
        d = _empty("nawy")
        d["error"] = str(e)
    print(f"   → {d['n']} prices, median={d['median']:,.0f}" if d["ok"] else f"   → {d['error']}")
    return {"nawy_result": d}


# ── Node 2: PropertyFinder ────────────────────────────────────
def node_pf(state: GraphState) -> dict:
    u = state["u"]
    print("\n" + "━"*55)
    print("  SOURCE 2/3: PropertyFinder Egypt")
    print("━"*55)
    try:
        r = pf_scraper.scrape(
            compound  = u["compound"],
            area      = u["area"],
            bedrooms  = u["bedrooms"],
            ptype     = u["property_type"],
            sale_type = u["sale_type"],
            location  = u["location"],
        )
        d = _r2d(r)
    except Exception as e:
        print(f"   [PF ERROR] {e}")
        d = _empty("propertyfinder")
        d["error"] = str(e)
    print(f"   → {d['n']} prices, median={d['median']:,.0f}" if d["ok"] else f"   → {d['error']}")
    return {"pf_result": d}


# ── Node 3: Aqarmap ───────────────────────────────────────────
def node_aq(state: GraphState) -> dict:
    u = state["u"]
    print("\n" + "━"*55)
    print("  SOURCE 3/3: Aqarmap Egypt")
    print("━"*55)
    try:
        r = aq_scraper.scrape(
            compound  = u["compound"],
            area      = u["area"],
            bedrooms  = u["bedrooms"],
            ptype     = u["property_type"],
            sale_type = u["sale_type"],
            location  = u["location"],
        )
        d = _r2d(r)
    except Exception as e:
        print(f"   [AQ ERROR] {e}")
        d = _empty("aqarmap")
        d["error"] = str(e)
    print(f"   → {d['n']} prices, median={d['median']:,.0f}" if d["ok"] else f"   → {d['error']}")
    return {"aq_result": d}


# ── Node 4: ML ────────────────────────────────────────────────
def node_ml(state: GraphState) -> dict:
    print("\n" + "━"*55)
    print("  ML: CatBoost Prediction")
    print("━"*55)
    u = state["u"]
    if model is None:
        print("   [ML] Model not loaded — using 0")
        return {"ml_price": 0.0}
    try:
        f = u.copy()
        f.update({
            "years_to_delivery": f["delivery_year"] - 2026,
            "total_rooms":       f["bedrooms"] + f["bathrooms"],
            "area_per_bedroom":  f["area"] / f["bedrooms"] if f["bedrooms"] > 0 else f["area"],
            "bath_to_bed_ratio": f["bathrooms"] / f["bedrooms"] if f["bedrooms"] > 0 else 0,
            "area_squared":      f["area"] ** 2,
            "is_ultra_luxury":   1 if f["area"] >= 500 else 0,
            "compound_name":     f["compound"],
            "location_TRIMMED":  f["location"],
            "developer_name":    f["developer"],
        })
        df      = pd.DataFrame([f])[model.feature_names_]
        ppm     = model.predict(Pool(df, cat_features=cat_features))[0]
        ml_val  = float(ppm * u["area"])
        print(f"   → {ml_val:,.0f} EGP  ({ppm:,.0f}/sqm)")
        return {"ml_price": ml_val}
    except Exception as e:
        print(f"   [ML ERROR] {e}")
        return {"ml_price": 0.0}


# ── Node 5: Smart merge ───────────────────────────────────────
def node_merge(state: GraphState) -> dict:
    print("\n" + "━"*55)
    print("  MERGING ALL SOURCES")
    print("━"*55)

    u        = state["u"]
    area     = u["area"]
    nawy     = state["nawy_result"]
    pf       = state["pf_result"]
    aq       = state["aq_result"]
    ml_price = state["ml_price"]

    sources = {
        "nawy":           nawy,
        "propertyfinder": pf,
        "aqarmap":        aq,
    }

    # ── 1. Compute raw weights ────────────────────────────────
    weights = dict(BASE_WEIGHTS)

    for name, res in sources.items():
        if not res["ok"]:
            # Source has no prices — redistribute its weight to ML
            weights["ml"] += weights[name]
            weights[name]  = 0.0
        elif res["low_conf"]:
            # Source is low confidence — penalise and redistribute
            penalty = LOW_CONF_PENALTY
            weights[name] -= penalty
            weights["ml"] += penalty * 0.5
            # Spread rest to other active sources
            active_others = [k for k, r in sources.items() if r["ok"] and k != name]
            if active_others:
                for k in active_others:
                    weights[k] += penalty * 0.5 / len(active_others)

    # Ensure ML doesn't exceed 75%
    weights["ml"] = min(weights["ml"], 0.75)

    # Re-normalise to sum to 1.0
    total = sum(weights.values())
    if total > 0:
        weights = {k: v / total for k, v in weights.items()}

    # ── 2. Cross-source outlier check ────────────────────────
    # If two sources broadly agree and one disagrees → flag the outlier
    active_medians = {
        name: res["median"]
        for name, res in sources.items()
        if res["ok"] and res["median"] > 0
    }

    if len(active_medians) >= 2:
        mvals  = list(active_medians.values())
        global_median = statistics.median(mvals)
        for name, med in active_medians.items():
            pct_diff = abs(med - global_median) / global_median * 100
            if pct_diff > 35:
                print(f"   [CROSS-CHECK] {name} median {med/1e6:.1f}M differs {pct_diff:.0f}% from cross-median — downweighting")
                weights["ml"] += weights[name] * 0.5
                weights[name] *= 0.5
        # Re-normalise again
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

    # ── 3. Compute final weighted price ─────────────────────
    final = 0.0
    for name, res in sources.items():
        if res["ok"] and res["median"] > 0:
            contribution = weights[name] * res["median"]
            final += contribution
            print(f"   {name:16}  median={res['median']/1e6:.2f}M  weight={weights[name]:.1%}  → {contribution/1e6:.2f}M")

    if ml_price > 0:
        contribution = weights["ml"] * ml_price
        final += contribution
        print(f"   {'ML':16}  pred  ={ml_price/1e6:.2f}M  weight={weights['ml']:.1%}  → {contribution/1e6:.2f}M")

    if final == 0:
        final = ml_price  # total fallback

    # ── 4. Global confidence flag ────────────────────────────
    n_active  = sum(1 for r in sources.values() if r["ok"])
    global_lc = n_active < 2

    # ── 5. Build audit trail ─────────────────────────────────
    audit = {
        "sources": {
            name: {
                "median":   res["median"],
                "ppm":      res["ppm"],
                "n":        res["n"],
                "weight":   weights[name],
                "low_conf": res["low_conf"],
                "ok":       res["ok"],
                "error":    res["error"],
                "urls":     res["urls"],
            }
            for name, res in sources.items()
        },
        "ml": {
            "price":  ml_price,
            "weight": weights["ml"],
        },
        "final_price":     final,
        "final_ppm":       final / area,
        "global_low_conf": global_lc,
        "n_sources_active": n_active,
        "weights":         weights,
    }

    print(f"\n   ✅ Final price: {final:,.0f} EGP  ({final/area:,.0f}/sqm)")
    if global_lc:
        print(f"   ⚠️  GLOBAL LOW CONFIDENCE — only {n_active}/3 sources returned prices")

    return {"final_price": final, "audit": audit}


# ── Graph ─────────────────────────────────────────────────────
builder = StateGraph(GraphState)
for name, fn in [
    ("nawy", node_nawy),
    ("pf",   node_pf),
    ("aq",   node_aq),
    ("ml",   node_ml),
    ("merge",node_merge),
]:
    builder.add_node(name, fn)

builder.set_entry_point("nawy")
builder.add_edge("nawy", "pf")
builder.add_edge("pf",   "aq")
builder.add_edge("aq",   "ml")
builder.add_edge("ml",   "merge")
builder.set_finish_point("merge")

agent = builder.compile()

# ── Report printer ────────────────────────────────────────────
def print_report(u: dict, audit: dict):
    area  = u["area"]

    print("\n" + "⭐" * 28)
    print("   SEMSAI v5.0 — FINAL APPRAISAL REPORT")
    print("⭐" * 28)
    print(f"🏠  {u['compound']}  |  {area:.0f} sqm  |  {u['location']}")
    print(f"👷  {u['developer']}")
    print(f"📐  {u['bedrooms']}BR / {u['bathrooms']}BA  |  {u['finishing']}  |  {u['sale_type']}")
    print("─" * 58)

    # Per-source breakdown
    print(f"\n{'SOURCE':<18} {'MEDIAN':>13} {'PPM':>10} {'N':>4} {'WEIGHT':>8}  STATUS")
    print("─" * 58)
    for name, s in audit["sources"].items():
        if s["ok"]:
            flags = ""
            if s["low_conf"]: flags += " [LC]"
            if res.get(f"{name}_result", {}).get("fallback"): flags += " [FB]"
            print(f"  {name:<16} {s['median']:>13,.0f} {s['ppm']:>10,.0f} {s['n']:>4} {s['weight']:>7.1%}  ✅{flags}")
        else:
            print(f"  {name:<16} {'—':>13} {'—':>10} {'0':>4} {s['weight']:>7.1%}  ❌ {s['error'] or 'no data'}")

    ml = audit["ml"]
    print(f"  {'ML (CatBoost)':<16} {ml['price']:>13,.0f} {ml['price']/area:>10,.0f} {'—':>4} {ml['weight']:>7.1%}  🧠")
    print("─" * 58)

    final = audit["final_price"]
    ppm   = audit["final_ppm"]
    print(f"\n🎯  FINAL APPRAISAL  :  {final:>15,.0f} EGP")
    print(f"    Per sqm          :  {ppm:>15,.0f} EGP/sqm")
    print(f"    Active sources   :  {audit['n_sources_active']}/3")

    if audit["global_low_conf"]:
        print(f"\n  ⚠️  LOW CONFIDENCE — fewer than 2 web sources returned prices.")
        print(f"      Final value relies heavily on ML prediction.")

    # Source URLs
    print("\n🔗  SOURCE URLs:")
    for name, s in audit["sources"].items():
        if s["urls"]:
            print(f"  {name.upper()}:")
            for url in s["urls"][:2]:
                print(f"    {url}")

    print()


# ── Main loop ─────────────────────────────────────────────────
if __name__ == "__main__":
    while True:
        u_in = get_user_input()
        print("\n" + "=" * 55)
        print("   SEMSAI v5.0: RUNNING MULTI-SOURCE WORKFLOW")
        print("=" * 55)

        initial_state = {
            "u":             u_in,
            "nawy_result":   _empty("nawy"),
            "pf_result":     _empty("propertyfinder"),
            "aq_result":     _empty("aqarmap"),
            "ml_price":      0.0,
            "final_price":   0.0,
            "audit":         {},
        }

        try:
            result = agent.invoke(initial_state)
        except Exception as e:
            print(f"\n❌ Agent error: {e}")
            if input("Appraise another? (y/n): ").lower() != "y":
                break
            continue

        audit = result.get("audit") or {}

        # Always print something useful
        final = result.get("final_price", 0)
        area  = u_in["area"]

        if not audit or final == 0:
            print(f"\n⚠️  Web sources returned no prices.")
            print(f"   ML-only estimate: {result.get('ml_price', 0):,.0f} EGP"
                  f"  ({result.get('ml_price', 0)/area:,.0f}/sqm)")
            print(f"\n   Tips:")
            print(f"   • Enter compound as just the name: 'Hyde Park' not 'Hyde park new-cairo'")
            print(f"   • Check your Tavily production key is set in tavily_client.py")
            print(f"   • PropertyFinder/Aqarmap require a paid Tavily key (not dev key)")
        else:
            print_report(u_in, audit)

        if input("\nAppraise another? (y/n): ").lower() != "y":
            break
