"""
test_integration.py
───────────────────
Offline integration test suite for the Semsai 10-agent pipeline.

All tests run WITHOUT real MongoDB / Redis / Ollama connections.
External calls are replaced with lightweight in-process stubs so the
router logic, state transitions, and agent control-flow can be verified
in isolation.

Run:
    cd agents-api
    python test_integration.py
"""

import sys
import os
import types
import copy
import traceback

# ─────────────────────────────────────────────────────────────────────────────
# Ensure the project root is on sys.path
# ─────────────────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ─────────────────────────────────────────────────────────────────────────────
# STUB SETUP — must happen BEFORE importing any project module that uses them
# ─────────────────────────────────────────────────────────────────────────────

def _stub_db():
    """Minimal in-memory DB stub with the methods agents call."""
    class Cursor:
        def __init__(self, docs): self._docs = docs
        def __iter__(self): return iter(self._docs)
        def find_one(self, *a, **kw): return self._docs[0] if self._docs else None

    class Collection:
        def __init__(self, docs=None): self._docs = docs or []
        def find_one(self, *a, **kw): return self._docs[0] if self._docs else None
        def find(self, *a, **kw): return Cursor(self._docs)
        def aggregate(self, *a, **kw): return iter(self._docs)

    class DB:
        def __getitem__(self, name): return getattr(self, name, Collection())
        locations  = Collection([
            {"_id": "loc1", "name": "القاهرة", "aliases": ["Cairo", "cairo", "القاهرة"]},
            {"_id": "loc2", "name": "التجمع الخامس", "aliases": ["New Cairo", "new cairo"]},
        ])
        compounds  = Collection([
            {"_id": "cmp1", "name": "Compound A", "description": "A great compound with pool and gym.",
             "developer_id": "dev1", "developer_name": "Emaar Misr", "location": "القاهرة"},
            {"_id": "cmp2", "name": "Compound B", "description": "A secure gated community with schools.",
             "developer_id": "dev1", "developer_name": "Emaar Misr", "location": "القاهرة"},
        ])
        units = Collection([
            {"compound_id": "cmp1", "type": "Apartment", "price": 4_000_000,
             "location": "القاهرة", "sale_type": "Developer Sale"},
            {"compound_id": "cmp2", "type": "Apartment", "price": 3_500_000,
             "location": "القاهرة", "sale_type": "Developer Sale"},
        ])
        developers = Collection([
            {"_id": "dev1", "dev_name": "Emaar Misr", "Developer_Class": "A+",
             "class_score": 5, "website": "https://emaarmisr.com"},
        ])
        payments = Collection([{"duration": 60}])
        users = Collection([])  # empty → triggers vector-search fallback
        compound_features = Collection([])

    return DB()

STUB_DB = _stub_db()

# Stub `database` module used by location_agent / budget_agent
database_stub = types.ModuleType("database")
database_stub.get_db = lambda: STUB_DB
sys.modules["database"] = database_stub

# Stub `pymongo` (used by comparing_agent / compound_ranking_agent / etc.)
pymongo_stub = types.ModuleType("pymongo")
class _FakeMongoClient:
    def __init__(self, *a, **kw): pass
    def get_default_database(self): return STUB_DB
    def close(self): pass
    def __getattr__(self, name): return STUB_DB
pymongo_stub.MongoClient = _FakeMongoClient
sys.modules["pymongo"] = pymongo_stub

# Stub `certifi`
certifi_stub = types.ModuleType("certifi")
certifi_stub.where = lambda: None
sys.modules["certifi"] = certifi_stub

# Stub `bson`
bson_stub = types.ModuleType("bson")
class _FakeObjId:
    def __init__(self, s=None): self._s = str(s) if s else "507f1f77bcf86cd799439011"
    def __str__(self): return self._s
    @staticmethod
    def is_valid(s): return isinstance(s, str) and len(s) == 24
bson_stub.ObjectId = _FakeObjId
sys.modules["bson"] = bson_stub

# Stub `dotenv`
dotenv_stub = types.ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *a, **kw: None
sys.modules["dotenv"] = dotenv_stub

# Stub `main_helpers` (ask_ollama used by comparing_agent)
OLLAMA_RESPONSE = '{"top_choices":[{"rank":1,"compound_id":"cmp1","name":"Compound A","purpose_used":"end_user","reasons":["Great pool","Good security","Family friendly"],"confidence":0.85},{"rank":2,"compound_id":"cmp2","name":"Compound B","purpose_used":"end_user","reasons":["Good schools","Gated","Green spaces"],"confidence":0.75},{"rank":3,"compound_id":"cmp1","name":"Compound A","purpose_used":"end_user","reasons":["Great amenities","Premium finish","Strategic location"],"confidence":0.65}]}'
main_helpers_stub = types.ModuleType("main_helpers")
main_helpers_stub.ask_ollama = lambda prompt: OLLAMA_RESPONSE
sys.modules["main_helpers"] = main_helpers_stub

# Stub utils.extractors (avoid real NLP/LLM dependencies)
extractors_stub = types.ModuleType("utils.extractors")
sys.modules["utils"] = types.ModuleType("utils")
sys.modules["utils.extractors"] = extractors_stub
sys.modules["agents.utils"] = types.ModuleType("agents.utils")

# Also make `from utils.extractors import X` work inside agents package
sys.modules["agents.utils.extractors"] = extractors_stub


# Default extractor stubs (tests can monkey-patch these)
def _noop_extractor(text): return (None, "low", None)
extractors_stub.extract_all_fields = lambda t: {}
extractors_stub.extract_location = _noop_extractor
extractors_stub.extract_property_type = _noop_extractor
extractors_stub.extract_payment_type = _noop_extractor
extractors_stub.extract_budget = _noop_extractor
extractors_stub.extract_downpayment = _noop_extractor
extractors_stub.extract_monthly_installment = _noop_extractor

# Stub utils.validators
validators_stub = types.ModuleType("utils.validators")
sys.modules["utils.validators"] = validators_stub
sys.modules["agents.utils.validators"] = validators_stub
validators_stub.validate_location = lambda loc, db: (True, "القاهرة", None)
validators_stub.validate_property_type = lambda pt: (True, pt, None)
validators_stub.validate_payment_type = lambda pt: (True, pt, None)
validators_stub.validate_payment_details = lambda *a: (True, None)
validators_stub.validate_budget = lambda budget, loc, ptype, db: (True, 450_000, None)

# Stub utils.error_helpers
error_helpers_stub = types.ModuleType("utils.error_helpers")
sys.modules["utils.error_helpers"] = error_helpers_stub
sys.modules["agents.utils.error_helpers"] = error_helpers_stub
error_helpers_stub.should_retry = lambda state, field: state.get_error_count(field) < 5
error_helpers_stub.get_remaining_retries = lambda state, field: 5 - state.get_error_count(field)
error_helpers_stub.get_retry_message = lambda field, msg, remaining: f"{msg} ({remaining} tries left)"
error_helpers_stub.format_give_up_message = lambda field: f"Sorry, I can't process your {field}. Transferring to human."

# Stub agents.Normalization
normalization_stub = types.ModuleType("agents.Normalization")
normalization_stub.normalize_location = lambda text: None
sys.modules["agents.Normalization"] = normalization_stub

# NOW import state and graph modules
from state import AgentState, AgentContext, make_initial_state
from graph import StateGraph, END
from graph_definition import state_router, compiled_graph


# ─────────────────────────────────────────────────────────────────────────────
# Test Harness
# ─────────────────────────────────────────────────────────────────────────────

PASS = "\033[92m✅ PASS\033[0m"
FAIL = "\033[91m❌ FAIL\033[0m"
results = []

def run_test(name, fn):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    try:
        fn()
        print(f"  {PASS}")
        results.append((name, True, None))
    except AssertionError as e:
        print(f"  {FAIL}: {e}")
        results.append((name, False, str(e)))
    except Exception as e:
        print(f"  {FAIL} (unexpected exception): {e}")
        traceback.print_exc()
        results.append((name, False, f"Exception: {e}"))


def make_state(session_id="test-session") -> AgentState:
    return make_initial_state(session_id)


def run_router_steps(state: AgentState, max_steps=30) -> list:
    """Simulate the router without actually calling agents.
    Returns list of node names the router would call in order."""
    transitions = []
    visited = {}
    for _ in range(max_steps):
        node = state_router(state)
        transitions.append(node)
        if node == END:
            break
        key = (node, state.waiting_for)
        visited[key] = visited.get(key, 0) + 1
        if visited[key] > 3:
            transitions.append("INFINITE_LOOP_DETECTED")
            break
    return transitions


def step_graph(graph: StateGraph, state, max_steps=40):
    """Step the graph once, returning (state, next_node)."""
    state, next_node = graph.step(state)
    return state, next_node


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Router — initial state → extraction_agent
# ─────────────────────────────────────────────────────────────────────────────

def test_router_initial_extraction():
    state = make_state()
    node = state_router(state)
    assert node == "extraction_agent", f"Expected extraction_agent, got {node}"
    print(f"  Initial state → {node}")


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Router — progressive collection (missing location)
# ─────────────────────────────────────────────────────────────────────────────

def test_router_progressive_missing_location():
    state = make_state()
    state.context.property_type = "apartment"   # partial info
    state.context.payment_type = "cash"
    state.context.budget = 5_000_000
    state.context.budget_valid = True
    # location is missing → should route to location_agent
    node = state_router(state)
    assert node == "location_agent", f"Expected location_agent got {node}"
    print(f"  Missing location → {node}")


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Router — waiting_for takes priority
# ─────────────────────────────────────────────────────────────────────────────

def test_router_waiting_for_priority():
    state = make_state()
    # Even if all context fields set, waiting_for must route back to that agent
    state.context.location = "Cairo"
    state.context.location_normalized = "القاهرة"
    state.context.property_type = "apartment"
    state.context.payment_type = "cash"
    state.context.budget = 5_000_000
    state.context.budget_valid = True

    for wf, expected in [
        ("location",          "location_agent"),
        ("property_type",     "property_type_agent"),
        ("payment_type",      "payment_agent"),
        ("downpayment",       "payment_agent"),
        ("monthly_installment","payment_agent"),
        ("budget",            "budget_agent"),
    ]:
        state.waiting_for = wf
        got = state_router(state)
        assert got == expected, f"waiting_for={wf!r} → expected {expected} got {got}"
        print(f"  waiting_for={wf!r} → {got}")

    state.waiting_for = None


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: Router — no_units_response before candidate_compounds check
# ─────────────────────────────────────────────────────────────────────────────

def test_router_no_units_response_priority():
    """
    When compounds_agent sets waiting_for='no_units_response' it ALSO clears
    candidate_compounds=None. The router must route to compounds_agent, NOT
    get stuck in an infinite re-trigger loop.
    """
    state = make_state()
    state.context.location = "Cairo"
    state.context.location_normalized = "القاهرة"
    state.context.property_type = "apartment"
    state.context.payment_type = "cash"
    state.context.budget = 5_000_000
    state.context.budget_valid = True
    state.context.candidate_compounds = None  # cleared by compounds_agent
    state.waiting_for = "no_units_response"

    node = state_router(state)
    assert node == "compounds_agent", f"Expected compounds_agent, got {node}"
    print(f"  no_units_response → {node}")


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: Router — handoff_to_human → END (not handoff_agent)
# ─────────────────────────────────────────────────────────────────────────────

def test_router_handoff_to_end():
    state = make_state()
    state.handoff_to_human = True
    node = state_router(state)
    assert node == END, f"Expected END on handoff, got {node!r}"
    print(f"  handoff_to_human=True → {node}")


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: Router — full happy-path sequence (no DB)
# ─────────────────────────────────────────────────────────────────────────────

def test_router_happy_path_sequence():
    """
    Walk through the router at each stage, manually advancing state as each
    agent would, and assert the correct next-node is chosen at every step.
    """
    state = make_state()

    # STEP 1 — initial → extraction_agent
    assert state_router(state) == "extraction_agent"

    # Simulate extraction_agent populating context
    state.context.location = "Cairo"
    state.context.property_type = "apartment"
    state.context.payment_type = "cash"
    state.context.budget = 5_000_000

    # STEP 2 — location needs normalizing
    assert state_router(state) == "location_agent"

    # Simulate location_agent
    state.context.location_normalized = "القاهرة"

    # STEP 3 — payment/budget valid → straight to compounds (budget needs validation)
    assert state_router(state) == "budget_agent"

    # Simulate budget_agent
    state.context.budget_valid = True

    # STEP 4 — no candidates yet → compounds_agent
    assert state_router(state) == "compounds_agent"

    # Simulate compounds_agent  (legacy + context)
    fake_candidates = [{"compound_id": "c1", "compound_name": "Test Compound",
                        "min_unit_price": 4_000_000, "location": "Cairo"}]
    state.candidate_compounds = fake_candidates
    state.context.candidate_compounds = fake_candidates

    # STEP 5 — candidates exist, no final_compounds → developers_agent
    assert state_router(state) == "developers_agent"

    # Simulate developers_agent
    state.final_compounds = fake_candidates
    state.context.final_compounds = fake_candidates

    # STEP 6 — comparison needed
    assert state_router(state) == "comparing_agent"

    # Simulate comparing_agent
    state.context.comparison_result = [{"rank": 1, "name": "Test Compound"}]

    # STEP 7 — ranking needed
    assert state_router(state) == "compound_ranking_agent"

    # Simulate compound_ranking_agent
    state.context.ranked_compounds = fake_candidates

    # STEP 8 — final output
    assert state_router(state) == "final_output_agent"

    # Simulate final_output_agent
    state.context.final_best_compound = {"compound_name": "Test Compound"}

    # STEP 9 — done
    assert state_router(state) == END

    print("  All 9 routing steps passed")


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: extraction_agent — populates context from extractors
# ─────────────────────────────────────────────────────────────────────────────

def test_extraction_agent_populates_context():
    import importlib
    import agents.extraction_agent as ea_mod

    # Patch extractors inside the module
    original = ea_mod.__dict__.get("extract_all_fields")
    ea_mod.extract_all_fields = lambda text: {
        "location":    ("Cairo",     "high"),
        "property_type": ("apartment","high"),
        "payment_type": ("cash",     "high"),
        "budget":      (5_000_000,   "high"),
    }
    try:
        state = make_state()
        state.user_input = "I want an apartment in Cairo for 5 million cash"
        result = ea_mod.extraction_agent(state)
        assert result.context.location == "Cairo", f"location={result.context.location}"
        assert result.context.property_type == "apartment"
        assert result.context.payment_type == "cash"
        assert result.context.budget == 5_000_000
        # sync_to_legacy must have run
        assert result.location == "Cairo"
        assert result.typeofproperty == "apartment"
        print("  extraction_agent: all fields extracted and synced to legacy ✓")
    finally:
        if original:
            ea_mod.extract_all_fields = original


# ─────────────────────────────────────────────────────────────────────────────
# Test 8: location_agent — validates successfully, clears waiting_for
# ─────────────────────────────────────────────────────────────────────────────

def test_location_agent_success():
    import agents.location_agent as la_mod

    # Patch extractors in module
    la_mod.extract_location = lambda text: ("Cairo", "high", None)
    la_mod.validate_location = lambda loc, db: (True, "القاهرة", None)

    state = make_state()
    state.waiting_for = "location"
    state.user_input = "Cairo"

    result = la_mod.location_agent(state)
    assert result.waiting_for is None, f"waiting_for should be None, got {result.waiting_for}"
    assert result.context.location == "Cairo"
    assert result.context.location_normalized == "القاهرة"
    # sync_to_legacy mirrors context.location ("Cairo") not normalized
    assert result.location == "Cairo", f"legacy location should be 'Cairo', got {result.location}"
    print("  location_agent: validates Cairo → القاهرة, clears waiting_for ✓")


# ─────────────────────────────────────────────────────────────────────────────
# Test 9: budget_agent — invalid budget, increments error count, retries
# ─────────────────────────────────────────────────────────────────────────────

def test_budget_agent_retry_on_low_budget():
    import agents.budget_agent as ba_mod

    ba_mod.extract_budget = lambda text: (100_000, "high", None)
    ba_mod.validate_budget = lambda b, loc, ptype, db: (
        False, 450_000, "Budget is below minimum of 450,000 EGP for this location"
    )

    state = make_state()
    state.context.location_normalized = "القاهرة"
    state.context.location = "Cairo"
    state.context.property_type = "apartment"
    state.waiting_for = "budget"
    state.user_input = "100000"

    result = ba_mod.budget_agent(state)
    assert result.waiting_for == "budget", "Should still be waiting for budget"
    assert result.get_error_count("budget") == 1, "Should have 1 error"
    assert result.context.budget is None or not result.context.budget_valid
    print("  budget_agent: low budget → error recorded, retry requested ✓")


# ─────────────────────────────────────────────────────────────────────────────
# Test 10: Vector search fallback — no user embedding → uses final_compounds
# ─────────────────────────────────────────────────────────────────────────────

def test_compound_ranking_fallback():
    """Without user embedding the ranking agent should fall back gracefully."""
    import agents.compound_ranking_agent as cra_mod

    fake_compounds = [
        {"compound_id": "c1", "compound_name": "Alpha", "min_unit_price": 3_500_000},
        {"compound_id": "c2", "compound_name": "Beta",  "min_unit_price": 4_000_000},
    ]

    state = make_state()
    state.context.final_compounds = fake_compounds
    # STUB_DB.users is empty → agent can't find embedding

    result = cra_mod.compound_ranking_agent(state)
    assert result.context.ranked_compounds is not None, "ranked_compounds should not be None"
    assert len(result.context.ranked_compounds) > 0, "ranked_compounds should not be empty"
    print(f"  compound_ranking_agent: fallback → {len(result.context.ranked_compounds)} ranked compounds ✓")


# ─────────────────────────────────────────────────────────────────────────────
# Test 11: comparing_agent — LLM succeeds, comparison_result populated
# ─────────────────────────────────────────────────────────────────────────────

def test_comparing_agent_llm_success():
    """Ollama stub returns valid JSON; agent should set comparison_result."""
    import agents.comparing_agent as ca_mod

    fake_final_compounds = [
        {"developer_id": "dev1", "matched_compound_names": ["Compound A", "Compound B"]}
    ]

    state = make_state()
    state.context.final_compounds = fake_final_compounds
    state.purpose = "end_user"

    # Patch MONGO_URI so the agent reaches the MongoClient (which is stubbed)
    import os
    _orig = os.environ.get("MONGO_URI")
    os.environ["MONGO_URI"] = "mongodb://stub-host:27017/stubdb"
    try:
        result = ca_mod.comparing_agent(state)
    finally:
        if _orig is None:
            os.environ.pop("MONGO_URI", None)
        else:
            os.environ["MONGO_URI"] = _orig

    assert result.context.comparison_result is not None, "comparison_result should be set"
    assert isinstance(result.context.comparison_result, list)
    assert len(result.context.comparison_result) >= 1
    print(f"  comparing_agent: LLM → {len(result.context.comparison_result)} top choices ✓")


# ─────────────────────────────────────────────────────────────────────────────
# Test 12: state error tracking helpers
# ─────────────────────────────────────────────────────────────────────────────

def test_state_error_tracking():
    state = make_state()
    assert state.get_error_count("budget") == 0

    state.add_error("budget", "abc", "Not a number")
    assert state.get_error_count("budget") == 1
    assert state.errors[0].attempts == 1

    state.add_error("budget", "50", "Too low")
    assert state.get_error_count("budget") == 2
    assert state.errors[1].attempts == 2

    state.add_error("location", "nowhere", "Unknown location")
    assert state.get_error_count("budget") == 2
    assert state.get_error_count("location") == 1
    print("  Error tracking: add_error / get_error_count works correctly ✓")


# ─────────────────────────────────────────────────────────────────────────────
# Test 13: sync_to_legacy mirrors context → legacy fields
# ─────────────────────────────────────────────────────────────────────────────

def test_sync_to_legacy():
    state = make_state()
    state.context.location = "New Cairo"
    state.context.property_type = "villa"
    state.context.payment_type = "cash"
    state.context.budget = 7_000_000
    state.context.budget_valid = True
    state.context.downpayment = 1_000_000
    state.context.monthly_installment = 50_000

    state.sync_to_legacy()

    assert state.location == "New Cairo"
    assert state.typeofproperty == "villa"
    assert state.payment_type == "cash"
    assert state.budget == 7_000_000
    assert state.budget_valid is True
    assert state.Downpayment == 1_000_000
    assert state.monthlyinstall == 50_000
    print("  sync_to_legacy: all 7 fields mirrored correctly ✓")


# ─────────────────────────────────────────────────────────────────────────────
# Test 14: final_output_agent — no compounds → safe sentinel
# ─────────────────────────────────────────────────────────────────────────────

def test_final_output_agent_no_compounds():
    import agents.final_output_agent as foa_mod

    state = make_state()
    # No compounds anywhere
    state.context.ranked_compounds = None
    state.context.final_compounds = None
    state.context.candidate_compounds = None
    state.context.location = "Cairo"
    state.context.property_type = "apartment"
    state.context.payment_type = "cash"
    state.context.budget = 5_000_000

    result = foa_mod.final_output_agent(state)
    # Should not crash, should set a sentinel
    assert result.context.final_best_compound is not None
    assert result.context.final_best_compound.get("status") == "no_compound_found"
    assert result.handoff_to_human is True
    print("  final_output_agent: no compounds → safe sentinel + handoff_to_human ✓")


# ─────────────────────────────────────────────────────────────────────────────
# Test 15: graph.step() — entry point and conditional edge wiring
# ─────────────────────────────────────────────────────────────────────────────

def test_graph_step_entry_point():
    """
    Verify graph.step() on a blank state lands at extraction_agent.
    Works with both AgentState (Pydantic) and dict state.
    """
    from graph import StateGraph, END as GRAPH_END

    called = []

    def fake_extraction(state):
        called.append("extraction_agent")
        # Works for both Pydantic and dict
        if hasattr(state, 'context'):
            state.context.location = "Cairo"
            state.sync_to_legacy()
        else:
            state["location"] = "Cairo"
        return state

    g = StateGraph()
    g.add_node("extraction_agent", fake_extraction)
    g.set_entry_point("extraction_agent")
    g.add_edge("extraction_agent", lambda s: GRAPH_END)

    # Test with Pydantic AgentState
    state = make_state()
    state_out, next_node = g.step(state)

    assert "extraction_agent" in called, "extraction_agent was not called"
    assert next_node == GRAPH_END
    print(f"  graph.step() [Pydantic]: extraction_agent called, next={next_node} ✓")

    # Test with plain dict
    called.clear()
    dict_state = {"graph_current_node": None, "waiting_for": None, "user_id": "test"}
    dict_out, next_node2 = g.step(dict_state)
    assert "extraction_agent" in called
    assert next_node2 == GRAPH_END
    print(f"  graph.step() [dict]: extraction_agent called, next={next_node2} ✓")


# ─────────────────────────────────────────────────────────────────────────────
# Test 16: router loop guard — same node 3× without progress → detected
# ─────────────────────────────────────────────────────────────────────────────

def test_router_loop_detection():
    """run_router_steps detects when the same (node, waiting_for) is hit 3x."""
    state = make_state()
    # Deliberately leave state empty so router keeps choosing extraction_agent
    transitions = run_router_steps(state, max_steps=15)
    assert "INFINITE_LOOP_DETECTED" in transitions, (
        f"Loop not detected. Transitions: {transitions}"
    )
    print(f"  Loop detected after {transitions.index('INFINITE_LOOP_DETECTED')} steps ✓")


# ─────────────────────────────────────────────────────────────────────────────
# Run all tests
# ─────────────────────────────────────────────────────────────────────────────

TESTS = [
    ("T01: Router — initial → extraction_agent",          test_router_initial_extraction),
    ("T02: Router — missing location → location_agent",   test_router_progressive_missing_location),
    ("T03: Router — waiting_for priority",                 test_router_waiting_for_priority),
    ("T04: Router — no_units_response before candidate check", test_router_no_units_response_priority),
    ("T05: Router — handoff_to_human → END",              test_router_handoff_to_end),
    ("T06: Router — full happy-path sequence",            test_router_happy_path_sequence),
    ("T07: extraction_agent — populates context",          test_extraction_agent_populates_context),
    ("T08: location_agent — validates and clears wait",   test_location_agent_success),
    ("T09: budget_agent — retry on low budget",           test_budget_agent_retry_on_low_budget),
    ("T10: compound_ranking — fallback (no embedding)",   test_compound_ranking_fallback),
    ("T11: comparing_agent — LLM success path",           test_comparing_agent_llm_success),
    ("T12: State error tracking",                          test_state_error_tracking),
    ("T13: sync_to_legacy correctness",                   test_sync_to_legacy),
    ("T14: final_output_agent — no compounds sentinel",   test_final_output_agent_no_compounds),
    ("T15: graph.step() — entry point + edge wiring",     test_graph_step_entry_point),
    ("T16: Router loop detection",                         test_router_loop_detection),
]


def main():
    print("\n" + "="*60)
    print("  SEMSAI INTEGRATION TEST SUITE")
    print("="*60)

    for name, fn in TESTS:
        run_test(name, fn)

    # Summary
    passed = sum(1 for _, ok, _ in results if ok)
    total  = len(results)
    print("\n" + "="*60)
    print(f"  RESULTS: {passed}/{total} tests passed")
    print("="*60)

    for name, ok, err in results:
        icon = "✅" if ok else "❌"
        print(f"  {icon} {name}")
        if err:
            print(f"       └─ {err}")

    print()
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
