from state import AgentState


def lifestyle_agent(state: AgentState):
    print("\n--- Lifestyle Agent ---")

    # Q1: calm/green vs nightlife
    print("\n(1) Do you prefer calm, green surroundings or nightlife and cafes?")
    print("   1) Calm/green   2) Nightlife/cafes")
    a = input("Your choice (1/2): ").strip()

    if a == "1":
        landscapes_w, nightlife_w = 0.85, 0.15
    elif a == "2":
        landscapes_w, nightlife_w = 0.30, 0.70
    else:
        landscapes_w, nightlife_w = 0.55, 0.45

    
    print("\n(2) Do you prefer a modern practical design or a luxury prestige style?")
    print("   1) Modern/practical   2) Luxury/prestige")
    b = input("Your choice (1/2): ").strip()

    if b == "1":
        modern_w, luxury_w = 0.80, 0.40
    elif b == "2":
        modern_w, luxury_w = 0.30, 0.85
    else:
        modern_w, luxury_w = 0.60, 0.60

    
    print("\n(3) Do you prefer a closed/private compound or a large city-like one?")
    print("   1) Closed/private   2) Large/city-like")
    c = input("Your choice (1/2): ").strip()

    if c == "1":
        closed_off_w, larger_w = 0.90, 0.40
    elif c == "2":
        closed_off_w, larger_w = 0.30, 0.85
    else:
        closed_off_w, larger_w = 0.60, 0.60

    state["landscapes"] = [ landscapes_w]
    state["nightlife"] = [nightlife_w]
    state["modern_layout"] = [modern_w]
    state["luxury_layout"] = [luxury_w]
    state["closed_off_layout"] = [closed_off_w]
    state["larger_layout"] = [larger_w]
    print("landcsapes ",state["landscapes"])
    print("nightlife",state["nightlife"])
    print("modern_layout",state["modern_layout"])
    print("luxury_layout",state["luxury_layout"])
    print("closed_off_layout",state["closed_off_layout"])
    print("larger_layout",state["larger_layout"])

    return state
