# -*- coding: utf-8 -*-
"""
Manajemen State Percakapan (Dialogue State Tracker) (§3, §4, FSM)
"""
from __future__ import annotations
import copy

def new_state() -> dict:
    return {
        "category": None, "active_profile_id": None,
        "needs": [],
        "persona": None,
        "user_type": None,
        "preferences": [],
        "constraints": {
            "budget_max": None,
            "budget_max_strict": False,
            "budget_min": None,
            "budget_min_strict": False,
            "budget_target": None,
            "vendor": None,
            "os": None,
            "brand": None
        },
        "offered_products": [],
        "selected_product": None,
        "last_question": None,
        "asked_slots": [],
        "pool": [],
        "shown": [],
        "spread_shown": False,
        "hide_price": False,
        "fsm_stage": "INIT",  # INIT, AWAITING_NEED, PERSONA_CLARIFY, OFFERED, NARROWING_DOWN, COMPARING
        "last_route": None,
    }

def reset_state(s: dict) -> None:
    """Reset penuh seluruh state (§4, §14A)."""
    s.clear()
    s.update(new_state())

def has_filter(s: dict) -> bool:
    c = s["constraints"]
    return any(c.get(k) is not None for k in ("budget_max", "budget_min", "budget_target", "vendor", "os", "brand"))

def has_rank(s: dict) -> bool:
    return bool(set(s["preferences"]) & {"cheapest", "most_expensive", "large_ram", "large_processor"})

def apply_budget(s: dict, b: dict) -> None:
    c = s["constraints"]
    if b["kind"] == "max":
        c["budget_max"], c["budget_max_strict"] = b["amount"], b["strict"]
        c["budget_target"] = None
    elif b["kind"] == "min":
        c["budget_min"], c["budget_min_strict"] = b["amount"], b["strict"]
        c["budget_target"] = None
    else:
        c["budget_target"] = b["amount"]
        c["budget_max"] = c["budget_min"] = None

def apply_prefs(s: dict, prefs: list[str]) -> None:
    for p in prefs:
        if p == "cheapest" and "most_expensive" in s["preferences"]:
            s["preferences"].remove("most_expensive")
        if p == "most_expensive" and "cheapest" in s["preferences"]:
            s["preferences"].remove("cheapest")
        if p not in s["preferences"]:
            s["preferences"].append(p)
