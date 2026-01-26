import os
from dotenv import load_dotenv
from pymongo import MongoClient
from state import AgentState

def compounds_agent(state: AgentState):
    print("\n--- Compounds Agent ---")

    load_dotenv()
    uri = os.getenv("MONGO_URI")
    if not uri:
        print("Missing MONGO_URI. Skipping compound lookup.")
        return state

    client = MongoClient(uri)
    try:
        db = client.get_default_database()

        # ---- 1) Get / compute budget ----
        budget = state.get("budget")

        if budget is None:
            downpayment = state.get("Downpayment")
            monthly_install = state.get("monthlyinstall")

            # basic validation
            

            # get installment months from payments (choose the max months plan as default)
            plan = db["payments"].find_one(
                {},
                sort=[("duration", -1)],
                projection={"duration": 1}
            )

           

            months = int(plan["duration"])
            budget = float(downpayment) + float(monthly_install) * months

            # store computed budget in state so other agents can reuse it
            state["budget"] = budget

        # ---- 2) Location filter on compounds ----
        location = state.get("location")
        comp_query = {}
        if location:
            comp_query["location"] = location

        # only fetch what you need
        compounds = list(db["compounds"].find(comp_query, {"name": 1, "location": 1}))

        # ---- 3) Loop each compound -> find min unit price ----
        candidate_compounds = []
        for comp in compounds:
            comp_id = comp["_id"]

            min_unit = db["units"].find_one(
                {"compound_id": comp_id},
                sort=[("price", 1)],
                projection={"price": 1}
            )

            if not min_unit or min_unit.get("price") is None:
                continue

            min_price = float(min_unit["price"])

            if min_price <= float(budget):
                candidate_compounds.append({
                    "compound_id": comp_id,
                    "compound_name": comp.get("name"),
                    "location": comp.get("location"),
                    "min_unit_price": min_price
                })

      # ---- 4) Sort + top 5 ----
        candidate_compounds.sort(key=lambda x: x["min_unit_price"])
        state["candidate_compounds"] = candidate_compounds

        print(f"Top compounds: {len(state['candidate_compounds'])}")
        for comp in state.get("candidate_compounds", []):
         print(comp.get("compound_name"))


    finally:
        client.close()

    return state
