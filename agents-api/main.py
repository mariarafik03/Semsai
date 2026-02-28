import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pymongo import MongoClient
import certifi
import asyncio

from agents.extraction_agent import extraction_agent
from agents.budget_agent import budget_agent
from agents.location_agent import location_agent
from agents.compounds_agent import compounds_agent, format_price
from agents.developers_agent import developers_agent
from agents.compound_features_agent import compound_features_agent
from agents.user_prefrences_agent import user_preferences_agent
from agents.compound_ranking_agent import compound_ranking_agent
from agents.final_output_agent import final_output_agent
from agents.embedding_agent import embedding_agent
from graph import StateGraph, END
from http_helpers import init_input_queue, NeedInput

load_dotenv()

app = FastAPI(title="SemsAi Agents API")

# CORS for Flutter web/mobile with HuggingFace Spaces support
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

def _router(s):
    if s.get("abort"):
        return END
    if not s.get("location"):
        return "location_agent"
    if not s.get("typeofproperty"):
        return "location_agent"
    if not s.get("budget_valid"):
        return "budget_agent"
    if s.get("candidate_compounds") is None:
        return "compounds_agent"
    if s.get("final_compounds") is None:
        return "developers_agent"
    if s.get("compound_features_stats") is None:
        return "compound_features_agent"
    if s.get("embeddings") is None:
        return "embedding_agent"
    if s.get("user_preferences") is None:
        return "user_preferences_agent"
    if s.get("ranked_compounds") is None:
        return "compound_ranking_agent"
    if s.get("final_best_compound") is None:
        return "final_output_agent"
    return END

def _default_state(input_state: dict) -> dict:
    return {
        "user_input": input_state.get("user_input"),
        "purpose": input_state.get("purpose"),
        "pending_confirmation": input_state.get("pending_confirmation"),
        "budget": input_state.get("budget"),
        "location": input_state.get("location"),
        "next_step": input_state.get("next_step"),
        "payment_type": input_state.get("payment_type"),
        "payment_type_confirmed": input_state.get("payment_type_confirmed", False),
        "Downpayment": input_state.get("Downpayment"),
        "monthlyinstall": input_state.get("monthlyinstall"),
        "budget_valid": input_state.get("budget_valid"),
        "breakingbudget": input_state.get("breakingbudget"),
        "breakinginstallments": input_state.get("breakinginstallments"),
        "candidate_compounds": input_state.get("candidate_compounds"),
        "final_compounds": input_state.get("final_compounds"),
        "top_compounds": input_state.get("top_compounds"),
        "top_developers": input_state.get("top_developers"),
        "typeofproperty": input_state.get("typeofproperty"),
        "final_candidates": input_state.get("final_candidates"),
        "compound_features_stats": input_state.get("compound_features_stats"),
        "features_limit": input_state.get("features_limit", 0),
        "features_force_refresh": input_state.get("features_force_refresh", False),
        "candidate_units": input_state.get("candidate_units"),
        "selected_compound": input_state.get("selected_compound"),
        "raw_budget_hint": input_state.get("raw_budget_hint"),
        "_graph_current_node": input_state.get("_graph_current_node"),
        "done": False,
    }

def _build_graph():
    g = StateGraph()
    g.add_node("extraction_agent", extraction_agent)
    g.add_node("budget_agent", budget_agent)
    g.add_node("location_agent", location_agent)
    g.add_node("compounds_agent", compounds_agent)
    g.add_node("developers_agent", developers_agent)
    g.add_node("compound_features_agent", compound_features_agent)
    g.add_node("user_preferences_agent", user_preferences_agent)
    g.add_node("compound_ranking_agent", compound_ranking_agent)
    g.add_node("final_output_agent", final_output_agent)
    g.add_node("embedding_agent", embedding_agent)
    g.set_entry_point("extraction_agent")
    for node in [
        "extraction_agent", "budget_agent", "location_agent", "compounds_agent",
        "developers_agent", "compound_features_agent",
        "user_preferences_agent", "compound_ranking_agent",
        "final_output_agent", "embedding_agent",
    ]:
        g.add_edge(node, _router)
    return g

@app.get("/")
@app.head("/")
def root():
    return {"message": "SemsAi Agents API running", "status": "ok"}

@app.options("/{path:path}")
async def options_handler(path: str):
    """Handle CORS preflight requests"""
    return {"message": "OK"}

async def _handle_step(request: Request):
    """Shared handler for step endpoints with timeout."""
    state = {}
    input_state = {}
    try:
        # Set a timeout for the entire request processing
        body = await asyncio.wait_for(request.json(), timeout=25.0)
        input_state = body.get("state") or body
        user_input = body.get("user_input") or input_state.get("user_input")
        
        state = _default_state(input_state)
        init_input_queue(state, user_input)
        
        graph = _build_graph()
        next_node = None
        
        # Process graph with timeout
        while next_node != END:
            state, next_node = graph.step(state)
            if state.get("_need_input"):
                message = state.get("assistant_message", "")
                return {"message": message, "state": state, "done": False}
        
        state["done"] = True
        message = state.get("assistant_message") or "تم جمع المعلومات بنجاح. جاري البحث عن التوصيات..."
        return {"message": message, "state": state, "done": True}
    
    except asyncio.TimeoutError:
        print("Request timeout - processing took too long")
        return {
            "message": "خدمة معالجة الطلب استغرقت وقتاً طويلاً. يرجى المحاولة مجدداً.",
            "state": input_state,
            "done": False
        }
    except NeedInput as e:
        return {"message": str(e.question), "state": state or input_state, "done": False}
    except Exception as e:
        error_msg = f"حدث خطأ: {str(e)}"
        print(f"ERROR: {error_msg}")
        import traceback
        traceback.print_exc()
        return {"message": error_msg, "state": input_state or {}, "done": False}

@app.post("/agents/step")
@app.post("/conversation/step")
@app.post("/chat/start")
async def step_agents(request: Request):
    """Step-by-step conversation for Flutter chat. Receives state + user_input, returns message + state."""
    try:
        return await _handle_step(request)
    except Exception as e:
        print(f"ERROR in step_agents: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/recommendations")
async def get_recommendations(request: Request):
    """Fetch unit recommendations based on conversation state (payment, location, budget)."""
    try:
        body = await request.json()
        state = body.get("state")
        if not state:
            raise HTTPException(status_code=400, detail="State is required")

        uri = os.getenv("MONGO_URI")
        if not uri:
            raise HTTPException(status_code=500, detail="MONGO_URI not configured")

        client = MongoClient(uri, tls=True, tlsCAFile=certifi.where())
        db = client.get_default_database()
        units_collection = db["units"]

        # Build payment match
        payment_match = {}
        pt = (state.get("payment_type") or "").lower()
        if pt == "cash":
            payment_match["payment.cash"] = True
            if state.get("budget"):
                payment_match["payment.down_payment"] = {"$lte": int(float(state["budget"]))}
        elif pt == "installments":
            payment_match["payment.cash"] = False
            if state.get("Downpayment"):
                payment_match["payment.down_payment"] = {"$lte": int(float(state["Downpayment"]))}
            if state.get("monthlyinstall"):
                payment_match["payment.monthly_installment"] = {"$lte": int(float(state["monthlyinstall"]))}

        # Location match
        location_match = {}
        if state.get("location"):
            location_match["compound.location"] = {"$regex": str(state["location"]), "$options": "i"}

        pipeline = [
            {"$lookup": {"from": "payments", "localField": "_id", "foreignField": "unit_id", "as": "payment"}},
            {"$unwind": "$payment"},
        ]
        if payment_match:
            pipeline.append({"$match": payment_match})
        pipeline.extend([
            {"$lookup": {"from": "compounds", "localField": "compound_id", "foreignField": "_id", "as": "compound"}},
            {"$unwind": "$compound"},
        ])
        if location_match:
            pipeline.append({"$match": location_match})
        pipeline.extend([
            {"$lookup": {"from": "developers", "localField": "dev_id", "foreignField": "_id", "as": "developer"}},
            {"$unwind": {"path": "$developer", "preserveNullAndEmptyArrays": True}},
            {"$limit": 10},
        ])

        results = list(units_collection.aggregate(pipeline))

        clean_results = []
        for item in results:
            compound = item.get("compound", {})
            developer = item.get("developer", {})
            payment = item.get("payment", {})
            unit_fields = {k: v for k, v in item.items() if k not in ("compound", "developer", "payment")}
            clean_results.append({
                "unit": unit_fields,
                "compound": compound,
                "developer": developer,
                "payment": payment,
            })

        client.close()
        return clean_results

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/run")
async def run_agents(request: Request):
    """Full graph run (CLI style). Runs until END."""
    input_state = await request.json()
    state = _default_state(input_state)
    graph = _build_graph()
    next_node = None
    while next_node != END:
        state, next_node = graph.step(state)
    state["done"] = True
    return {"state": state}
# Additional chat endpoints for Flutter compatibility
@app.post("/chat/respond")
async def chat_respond(request: Request):
    """Alias for /chat/start - responds to user input in ongoing conversation."""
    return await _handle_step(request)

@app.get("/chat/status/{session_id}")
async def chat_status(session_id: str):
    """Get status of a chat session. Returns basic status."""
    return {
        "session_id": session_id,
        "status": "active",
        "message": "Session is processing"
    }

@app.get("/chat/results/{session_id}")
async def chat_results(session_id: str):
    """Get final results of a chat session. Returns accumulated results."""
    return {
        "session_id": session_id,
        "status": "complete",
        "results": []
    }