"""
test_long_term_memory.py
────────────────────────
Tests for the long-term memory helpers in api/session.py.

Runs with the in-memory backend (no Redis required).
Run with:
    python test_long_term_memory.py

Each test prints PASS ✅ or FAIL ❌ with details.
"""

import asyncio
import os

# Force in-memory backend so no Redis server is needed
os.environ["SESSION_BACKEND"] = "memory"

# --- import AFTER setting env var so the module picks it up ---
import api.session as sm


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _reset():
    """Clear in-memory store between tests."""
    sm._memory_store.clear()
    sm._redis = None
    sm._redis_unavailable = False


def check(name: str, condition: bool, detail: str = ""):
    if condition:
        print(f"  PASS ✅  {name}")
    else:
        print(f"  FAIL ❌  {name}" + (f"  →  {detail}" if detail else ""))


# ─────────────────────────────────────────────────────────────
# Test cases
# ─────────────────────────────────────────────────────────────

async def test_new_user_has_empty_profile():
    _reset()
    profile = await sm.load_profile("user_001")
    check("New user returns empty profile", profile == {}, f"got: {profile}")


async def test_save_and_load_profile():
    _reset()
    state = {
        "purpose":       "buy",
        "budget":        5_000_000,
        "location":      "New Cairo",
        "typeofproperty": "apartment",
        "payment_type":  "cash",
        "Downpayment":   None,     # None values must be excluded
        "monthlyinstall": None,
        "years":         None,
        "user_input":    "some text",  # irrelevant key — must be excluded
    }
    await sm.save_profile("user_001", state)
    profile = await sm.load_profile("user_001")

    check("Profile saved — purpose",        profile.get("purpose")       == "buy")
    check("Profile saved — budget",         profile.get("budget")        == 5_000_000)
    check("Profile saved — location",       profile.get("location")      == "New Cairo")
    check("Profile saved — typeofproperty", profile.get("typeofproperty") == "apartment")
    check("Profile saved — payment_type",   profile.get("payment_type")  == "cash")
    check("None fields excluded",           "Downpayment"  not in profile, str(profile))
    check("Non-pref key excluded",          "user_input"   not in profile, str(profile))


async def test_profile_merges_on_update():
    _reset()
    await sm.save_profile("user_002", {"purpose": "rent", "budget": 3_000_000})
    await sm.save_profile("user_002", {"location": "Maadi", "budget": 4_000_000})

    profile = await sm.load_profile("user_002")
    check("Merge — old key kept (purpose)",  profile.get("purpose")  == "rent")
    check("Merge — new key added (location)", profile.get("location") == "Maadi")
    check("Merge — value updated (budget)",   profile.get("budget")   == 4_000_000)


async def test_new_user_has_empty_history():
    _reset()
    history = await sm.load_history("user_003")
    check("New user returns empty history", history == [], f"got: {history}")


async def test_append_and_load_history():
    _reset()
    summary1 = {
        "timestamp": "2026-04-01T10:00:00Z",
        "purpose":   "buy",
        "budget":    5_000_000,
        "location":  "New Cairo",
        "typeofproperty": "apartment",
        "top_result": "Compound A",
    }
    summary2 = {
        "timestamp": "2026-04-10T15:00:00Z",
        "purpose":   "invest",
        "budget":    8_000_000,
        "location":  "6th of October",
        "typeofproperty": "villa",
        "top_result": "Compound B",
    }

    await sm.append_history("user_004", "sess-111", summary1)
    await sm.append_history("user_004", "sess-222", summary2)

    history = await sm.load_history("user_004")
    check("History has 2 entries",              len(history) == 2, f"len={len(history)}")
    check("First entry session_id injected",    history[0].get("session_id") == "sess-111")
    check("Second entry session_id injected",   history[1].get("session_id") == "sess-222")
    check("Second entry top_result correct",    history[1].get("top_result") == "Compound B")
    check("First entry in order (top_result)",  history[0].get("top_result") == "Compound A")


async def test_profile_and_history_are_independent():
    _reset()
    await sm.save_profile("user_005", {"purpose": "buy", "budget": 2_000_000})
    await sm.append_history("user_005", "s-999", {"timestamp": "now", "top_result": "Z"})

    # History must not bleed into profile and vice-versa
    profile = await sm.load_profile("user_005")
    history = await sm.load_history("user_005")
    check("Profile does not contain history keys", "session_id" not in profile)
    check("History does not contain profile budget", all(
        e.get("budget") is None for e in history
    ))


async def test_short_term_session_separate_from_long_term():
    """session:{id} keys must not interfere with profile:{id} or history:{id}."""
    _reset()
    sid = "test-session-abc"
    await sm.save_state(sid, {"purpose": "buy", "budget": 1_000})
    profile = await sm.load_profile(sid)   # using same id, different namespace
    history = await sm.load_history(sid)
    check("Short-term key does not leak into profile", profile == {})
    check("Short-term key does not leak into history", history == [])


# ─────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────

async def main():
    tests = [
        ("Empty profile for new user",            test_new_user_has_empty_profile),
        ("Save & load profile",                   test_save_and_load_profile),
        ("Profile merges on update",              test_profile_merges_on_update),
        ("Empty history for new user",            test_new_user_has_empty_history),
        ("Append & load conversation history",    test_append_and_load_history),
        ("Profile and history are independent",   test_profile_and_history_are_independent),
        ("Short-term vs long-term key isolation", test_short_term_session_separate_from_long_term),
    ]

    print("\n" + "═" * 60)
    print("  Long-Term Memory — Test Suite")
    print("  Backend: in-memory (no Redis needed)")
    print("═" * 60)

    passed = 0
    failed = 0
    for title, fn in tests:
        print(f"\n▶ {title}")
        try:
            await fn()
            passed += 1
        except Exception as e:
            print(f"  ERROR 💥  unexpected exception: {e}")
            failed += 1

    print("\n" + "─" * 60)
    print(f"  Results: {passed} groups passed")
    if failed:
        print(f"  ⚠️  {failed} group(s) crashed unexpectedly")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
