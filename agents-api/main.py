import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pymongo import MongoClient
import certifi
import asyncio
import uuid

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
        "_waiting_for_agent": input_state.get("_waiting_for_agent"),  # Track which agent is waiting for input
        "done": False,
    }

def _build_graph(entry_point=None):
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
    
    # Use provided entry point or default to extraction_agent
    g.set_entry_point(entry_point or "extraction_agent")
    
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

@app.post("/agents/step")
@app.post("/conversation/step")
async def step_agents(request: Request):
    """Step-by-step conversation for Flutter chat. Receives state + user_input, returns message + state."""
    try:
        # Handle empty body gracefully
        try:
            body = await request.json()
        except:
            body = {}
        
        input_state = body.get("state") or body
        user_input = body.get("user_input") or input_state.get("user_input", "")
        
        state = _default_state(input_state)
        init_input_queue(state, user_input)
        
        # Determine entry point: use saved agent if waiting (but NOT extraction_agent - only runs once)
        entry_agent = state.get("_waiting_for_agent")
        
        # extraction_agent only runs once at the very beginning
        # After that, always use router to determine next agent
        if entry_agent == "extraction_agent" or not entry_agent:
            entry_agent = _router(state)
        
        # If we're already at END, return completion
        if entry_agent == END:
            state["done"] = True
            return {
                "session_id": body.get("session_id", str(uuid.uuid4())),
                "message": "تمت معالجة جميع الخطوات. جاري جمع التوصيات...",
                "done": True,
                "phase": "complete",
                "state": state
            }
        
        # Build graph with the next agent as entry point
        graph = _build_graph(entry_point=entry_agent)
        next_node = None
        
        try:
            while next_node != END:
                state, next_node = graph.step(state)
                if state.get("_need_input"):
                    message = state.get("assistant_message", "")
                    state["_waiting_for_agent"] = entry_agent  # Save agent for next call
                    return {"message": message, "state": state, "done": False}
        except NeedInput as e:
            # Return the actual agent's question instead of error
            question = str(e.question) if e.question else state.get("assistant_message", "جاري المعالجة...")
            # Save the current agent only if it's not extraction_agent
            if entry_agent != "extraction_agent":
                state["_waiting_for_agent"] = entry_agent
            return {"message": question, "state": state, "done": False}
        
        state["done"] = True
        message = state.get("assistant_message") or "تم جمع المعلومات بنجاح. جاري البحث عن التوصيات..."
        state["_waiting_for_agent"] = None  # Clear waiting agent when moving to next
        
        # Ensure response includes required fields for Flutter app
        return {
            "session_id": body.get("session_id", str(uuid.uuid4())),
            "message": message,
            "done": state["done"],
            "phase": "complete" if state["done"] else "processing",
            "state": state
        }
    except NeedInput as e:
        # Return the actual agent's question
        return {
            "session_id": body.get("session_id", str(uuid.uuid4())) if 'body' in locals() else str(uuid.uuid4()),
            "message": str(e.question) if e.question else "جاري المعالجة...",
            "done": False,
            "phase": "asking",
            "state": body.get("state", {}) if 'body' in locals() else {}
        }
    except Exception as e:
        error_msg = f"Error in chat: {str(e)}"
        print(f"ERROR in step_agents: {error_msg}")
        import traceback
        traceback.print_exc()
        # Return error response in expected format
        return {
            "session_id": body.get("session_id", str(uuid.uuid4())) if 'body' in locals() else str(uuid.uuid4()),
            "message": error_msg,
            "done": False,
            "phase": "error",
            "state": body.get("state", {}) if 'body' in locals() else {}
        }

@app.post("/chat/start")
async def chat_start(request: Request):
    """Start a new chat session. Handles both empty and non-empty requests."""
    try:
        # Try to get request body, but handle empty body gracefully
        try:
            body = await request.json()
        except:
            body = {}  # Empty body - start fresh conversation
        
        # Process the conversation with empty state
        state = {}
        
        try:
            state = _default_state(body)
            init_input_queue(state, body.get("user_input", ""))
            
            # Start with extraction agent
            graph = _build_graph(entry_point="extraction_agent")
            next_node = None
            
            # Process graph to get the first agent's message
            message = None
            waiting_agent = None
            try:
                while next_node != END:
                    state, next_node = graph.step(state)
                    if state.get("_need_input"):
                        message = state.get("assistant_message", "")
                        waiting_agent = "extraction_agent"  # extraction_agent asked the question
                        break
            except NeedInput as e:
                # Get the actual agent's question
                message = str(e.question) if e.question else state.get("assistant_message", "")
                waiting_agent = "extraction_agent"
            
            # If no message, get from assistant_message field
            if not message:
                message = state.get("assistant_message", "مرحبا بك في مساعد الشراء الذكي! أين تريد شراء عقار؟")
            
            state["_waiting_for_agent"] = waiting_agent
            
        except Exception as e:
            print(f"Error in chat_start graph processing: {str(e)}")
            message = "مرحبا بك في مساعد الشراء الذكي! أين تريد شراء عقار؟"
            state = _default_state({})
            state["_waiting_for_agent"] = "extraction_agent"
        
        return {
            "session_id": str(uuid.uuid4()),
            "message": message,
            "phase": "purpose",
            "done": False,
            "state": state
        }
        
    except Exception as e:
        error_msg = f"Error starting chat: {str(e)}"
        print(f"ERROR in chat_start: {error_msg}")
        import traceback
        traceback.print_exc()
        return {
            "session_id": str(uuid.uuid4()),
            "message": "مرحبا بك في مساعد الشراء الذكي! أين تريد شراء عقار؟",
            "phase": "purpose",
            "done": False,
            "state": {"_waiting_for_agent": "extraction_agent"}
        }

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
    """Respond to a user message in an ongoing conversation."""
    session_id = None
    try:
        # Handle empty body gracefully
        try:
            body = await request.json()
        except:
            body = {}
        
        session_id = body.get("session_id", str(uuid.uuid4()))
        message = body.get("message", "")
        state = body.get("state", {})
        
        if not message:
            return {
                "session_id": session_id,
                "message": "لم تكتب رسالة. يرجى محاولة مجدداً.",
                "phase": "error",
                "done": False,
                "state": state
            }
        
        # Add user message to state
        input_state = state.copy() if state else {}
        input_state["user_input"] = message
        
        # Process through the graph
        state_dict = _default_state(input_state)
        init_input_queue(state_dict, message)
        
        # Determine entry point: use saved agent if waiting (but NOT extraction_agent)
        # extraction_agent only runs once at the beginning
        entry_agent = state_dict.get("_waiting_for_agent")
        if entry_agent == "extraction_agent" or not entry_agent:
            # Move past extraction_agent - use router to find next agent
            entry_agent = _router(state_dict)
        
        # If we're already at END, we're done
        if entry_agent == END:
            state_dict["done"] = True
            return {
                "session_id": session_id,
                "message": "تمت معالجة جميع خطوات البحث. جاري جمع التوصيات...",
                "phase": "complete",
                "done": True,
                "state": state_dict
            }
        
        # Build graph with the appropriate entry point
        graph = _build_graph(entry_point=entry_agent)
        next_node = None
        
        try:
            processing_steps = 0
            while next_node != END and processing_steps < 50:
                state_dict, next_node = graph.step(state_dict)
                processing_steps += 1
                if state_dict.get("_need_input"):
                    break
        except NeedInput as e:
            # Return the actual agent's question, and save which agent to continue with
            assistant_message = str(e.question) if e.question else "جاري المعالجة..."
            # Only save waiting_for_agent if it's not extraction_agent
            if entry_agent != "extraction_agent":
                state_dict["_waiting_for_agent"] = entry_agent
            else:
                state_dict["_waiting_for_agent"] = None
            return {
                "session_id": session_id,
                "message": assistant_message,
                "phase": "asking",
                "done": False,
                "state": state_dict
            }
        
        # If we reach here, the agent chain might have progressed
        # Check if we should continue to the next agent
        next_agent = _router(state_dict)
        if next_agent != END and next_agent != entry_agent:
            # Continue with next agent - clear waiting_for_agent
            state_dict["_waiting_for_agent"] = None
            graph = _build_graph(entry_point=next_agent)
            next_node = None
            try:
                while next_node != END:
                    state_dict, next_node = graph.step(state_dict)
                    if state_dict.get("_need_input"):
                        break
            except NeedInput as e:
                assistant_message = str(e.question) if e.question else "جاري المعالجة..."
                state_dict["_waiting_for_agent"] = next_agent
                return {
                    "session_id": session_id,
                    "message": assistant_message,
                    "phase": "asking",
                    "done": False,
                    "state": state_dict
                }
        
        assistant_message = state_dict.get("assistant_message", "جاري المعالجة...")
        state_dict["_waiting_for_agent"] = None  # Clear waiting agent
        
        return {
            "session_id": session_id,
            "message": assistant_message,
            "phase": "responding",
            "done": state_dict.get("done", False),
            "state": state_dict
        }
    except Exception as e:
        print(f"ERROR in chat_respond: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "session_id": session_id or str(uuid.uuid4()),
            "message": f"حدث خطأ: {str(e)}",
            "phase": "error",
            "done": False,
            "state": body.get("state", {}) if 'body' in locals() else {}
        }

@app.get("/chat/status/{session_id}")
async def chat_status(session_id: str):
    """Get status of a chat session."""
    return {
        "session_id": session_id,
        "status": "active",
        "phase": "processing",
        "message": "جاري معالجة طلبك"
    }

@app.get("/chat/results/{session_id}")
async def chat_results(session_id: str):
    """Get final results of a chat session."""
    return {
        "session_id": session_id,
        "status": "complete",
        "phase": "complete",
        "message": "تمت معالجة الطلب",
        "results": [],
        "done": True
    }