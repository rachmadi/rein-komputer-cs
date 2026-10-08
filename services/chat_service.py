# -*- coding: utf-8 -*-
"""
Unified Chat Service
Menangani state percakapan multi-sesi untuk Web Chat dan Bot Telegram secara modular dan independen.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any
from core.state import new_state, reset_state
from core.engine import step
from services.catalog_service import get_active_catalog
from core.chat_logger import log_turn

class SessionManager:
    def __init__(self, ttl_seconds: int = 3600 * 24):
        self._sessions: dict[str, dict[str, Any]] = {}
        self.ttl_seconds = ttl_seconds

    def get_session(self, session_id: str) -> dict[str, Any]:
        now = time.time()
        sess = self._sessions.get(session_id)
        if not sess or (now - sess.get("last_active", 0) > self.ttl_seconds):
            sess = {
                "session_id": session_id,
                "state": new_state(),
                "created_at": datetime.now().isoformat(),
                "last_active": now,
                "messages": [
                    {
                        "sender": "bot",
                        "role": "assistant",
                        "text": "Halo, Kak! Selamat datang di Customer Care Bobby Computer. Ada yang bisa saya bantu cari hari ini? 😊",
                        "time": datetime.now().strftime("%H:%M"),
                        "route": "DIRECT"
                    }
                ]
            }
            self._sessions[session_id] = sess
        else:
            sess["last_active"] = now
        return sess

    def reset_session(self, session_id: str) -> dict[str, Any]:
        sess = self.get_session(session_id)
        reset_state(sess["state"])
        sess["messages"] = [
            {
                "sender": "bot",
                "role": "assistant",
                "text": "Percakapan telah direset. Ada perangkat laptop, desktop, atau printer yang ingin dicari, Kak?",
                "time": datetime.now().strftime("%H:%M"),
                "route": "CANCEL"
            }
        ]
        sess["last_active"] = time.time()
        return sess

    def add_message(self, session_id: str, sender: str, text: str, route: str | None = None) -> dict:
        sess = self.get_session(session_id)
        msg = {
            "sender": sender,
            "role": "assistant" if sender in ("bot", "assistant") else "user",
            "text": text,
            "time": datetime.now().strftime("%H:%M"),
            "route": route
        }
        sess["messages"].append(msg)
        return msg

import os
from dotenv import load_dotenv

load_dotenv()

DEFAULT_CHAT_MODEL = os.getenv("CHAT_LLM_MODEL", "gemma4:e4b")
CHAT_ENGINE_MODE = os.getenv("CHAT_ENGINE_MODE", "agentic_tool")

_session_manager = SessionManager()

def get_session_manager() -> SessionManager:
    return _session_manager

def process_chat_message(
    session_id: str,
    user_text: str,
    model: str | None = None
) -> dict[str, Any]:
    sess = _session_manager.get_session(session_id)
    state = sess["state"]
    catalog = get_active_catalog()

    # Tentukan model LLM aktif
    active_model = model or DEFAULT_CHAT_MODEL
    if active_model in ("none", "disabled", "false", ""):
        active_model = None

    # Catat pesan user
    _session_manager.add_message(session_id, "user", user_text)

    t0 = time.time()

    # OPSI 1: DYNAMIC CONTEXT RAG ENGINE
    if CHAT_ENGINE_MODE == "dynamic_rag":
        from services.dynamic_rag_engine import run_dynamic_rag
        rag_res = run_dynamic_rag(
            user_text=user_text,
            history=sess["messages"],
            catalog=catalog,
            current_category=state.get("category"),
            current_offered_products=state.get("offered_products"),
            model=active_model
        )
        reply = rag_res["reply"]
        route = rag_res.get("route", "DYNAMIC_RAG")
        latency_ms = rag_res.get("latency_ms", (time.time() - t0) * 1000)

        prods = rag_res.get("products", [])
        state["offered_products"] = [p["kode"] for p in prods]
        state["shown"] += [p["kode"] for p in prods if p["kode"] not in state["shown"]]
        if rag_res.get("category"):
            state["category"] = rag_res["category"]
        if prods:
            state["fsm_stage"] = "OFFERED"
        new_s = state
        sess["state"] = new_s

        _session_manager.add_message(session_id, "bot", reply, route=route)

        try:
            log_turn(
                session_id=session_id,
                user_text=user_text,
                bot_reply=reply,
                route=route,
                state_snapshot=new_s,
                latency_ms=latency_ms
            )
        except Exception:
            pass

        active_products = []
        for p in prods:
            active_products.append({
                "kode": p["kode"],
                "nama": p["nama"],
                "kategori": p.get("kategori", ""),
                "brand": p.get("brand", ""),
                "harga": p.get("harga_idr", 0),
                "harga_idr": p.get("harga_idr", 0),
                "prosesor": p.get("cpu", ""),
                "cpu": p.get("cpu", ""),
                "gpu": p.get("gpu", ""),
                "ram": p.get("ram") or (f"{p.get('ram_gb', '')} GB {p.get('ram_type', '')}".strip() if p.get("ram_gb") else ""),
                "storage": p.get("storage", ""),
                "display": p.get("display", ""),
                "layar": p.get("display", ""),
                "image_url": p.get("image_url", ""),
                "usage_text": p.get("usage_text", "")
            })

        return {
            "session_id": session_id,
            "reply": reply,
            "route": route,
            "messages": sess["messages"],
            "products": active_products,
            "fsm_stage": new_s.get("fsm_stage"),
            "category": new_s.get("category"),
            "persona_name": new_s.get("persona_name"),
            "offered_products": new_s.get("offered_products", []), "metrics": rag_res.get("metrics", {})
        }

    # OPSI 2: AGENTIC TOOL CALLING ENGINE
    elif CHAT_ENGINE_MODE == "agentic_tool":
        from services.agentic_tool_engine import run_agentic_tool
        tool_res = run_agentic_tool(
            user_text=user_text,
            history=sess["messages"],
            catalog=catalog,
            current_category=state.get("category"),
            current_offered_products=state.get("offered_products"),
            active_profile_id=state.get("active_profile"),
            previous_lowest_price=state.get("lowest_price"),
            persona_name=state.get("persona_name"),
            model=active_model
        )
        reply = tool_res["reply"]
        route = tool_res.get("route", "AGENTIC_TOOL")
        latency_ms = tool_res.get("latency_ms", (time.time() - t0) * 1000)

        prods = tool_res.get("products", [])
        if prods:
            state["offered_products"] = [p["kode"] for p in prods]
            state["shown"] += [p["kode"] for p in prods if p["kode"] not in state["shown"]]
            state["fsm_stage"] = "OFFERED"
        if tool_res.get("category"):
            state["category"] = tool_res["category"]
        if "active_profile_id" in tool_res:
            state["active_profile"] = tool_res["active_profile_id"]
        if tool_res.get("persona_name"):
            state["persona_name"] = tool_res["persona_name"]
        if prods:
            prices = [p.get("harga_idr") or p.get("harga", 0) for p in prods if (p.get("harga_idr") or p.get("harga", 0)) > 0]
            if prices:
                state["lowest_price"] = min(prices)
        new_s = state
        sess["state"] = new_s

        _session_manager.add_message(session_id, "bot", reply, route=route)

        try:
            log_turn(
                session_id=session_id,
                user_text=user_text,
                bot_reply=reply,
                route=route,
                state_snapshot=new_s,
                latency_ms=latency_ms
            )
        except Exception:
            pass

        active_products = []
        for p in prods:
            active_products.append({
                "kode": p["kode"],
                "nama": p["nama"],
                "kategori": p.get("kategori", ""),
                "brand": p.get("brand", ""),
                "harga": p.get("harga_idr", 0),
                "harga_idr": p.get("harga_idr", 0),
                "prosesor": p.get("cpu", ""),
                "cpu": p.get("cpu", ""),
                "gpu": p.get("gpu", ""),
                "ram": p.get("ram") or (f"{p.get('ram_gb', '')} GB {p.get('ram_type', '')}".strip() if p.get("ram_gb") else ""),
                "storage": p.get("storage", ""),
                "display": p.get("display", ""),
                "layar": p.get("display", ""),
                "image_url": p.get("image_url", ""),
                "usage_text": p.get("usage_text", "")
            })

        return {
            "session_id": session_id,
            "reply": reply,
            "route": route,
            "messages": sess["messages"],
            "products": active_products,
            "fsm_stage": new_s.get("fsm_stage"),
            "category": new_s.get("category"),
            "persona_name": new_s.get("persona_name"),
            "offered_products": new_s.get("offered_products", []),
            "active_profile_id": new_s.get("active_profile"),
            "tools_called": [tc.get("name") for tc in tool_res.get("tool_calls", [])] if tool_res.get("tool_calls") else (tool_res.get("tools_called") or []),
            "metrics": tool_res.get("metrics", {})
        }

    # OPSI FALLBACK: RULE ENGINE FSM
    new_s, reply, route = step(state, user_text, catalog, nlu=None, llm_model=active_model)
    latency_ms = (time.time() - t0) * 1000
    sess["state"] = new_s

    # Catat balasan bot
    _session_manager.add_message(session_id, "bot", reply, route=route)

    # Catat log turn persisten (JSONL & SQLite)
    try:
        log_turn(
            session_id=session_id,
            user_text=user_text,
            bot_reply=reply,
            route=route,
            state_snapshot=new_s,
            latency_ms=latency_ms
        )
    except Exception:
        pass

    # Ambil rincian produk aktif untuk ditampilkan sebagai kartu visual di Flutter
    active_codes = new_s.get("offered_products", []) or ([new_s["selected_product"]] if new_s.get("selected_product") else [])
    active_products = []
    for c in active_codes:
        if c in catalog.by_code:
            p = catalog.by_code[c]
            active_products.append({
                "kode": p["kode"],
                "nama": p["nama"],
                "kategori": p.get("kategori", ""),
                "brand": p.get("brand", ""),
                "harga": p.get("harga_idr", 0),
                "harga_idr": p.get("harga_idr", 0),
                "prosesor": p.get("cpu", ""),
                "cpu": p.get("cpu", ""),
                "gpu": p.get("gpu", ""),
                "ram": p.get("ram") or (f"{p.get('ram_gb', '')} GB {p.get('ram_type', '')}".strip() if p.get("ram_gb") else ""),
                "storage": p.get("storage", ""),
                "display": p.get("display", ""),
                "layar": p.get("display", ""),
                "image_url": p.get("image_url", ""),
                "usage_text": p.get("usage_text", "")
            })

    return {
        "session_id": session_id,
        "reply": reply,
        "route": route,
        "messages": sess["messages"],
        "products": active_products,
        "fsm_stage": new_s.get("fsm_stage"),
        "category": new_s.get("category"),
        "persona_name": new_s.get("persona_name"),
        "offered_products": new_s.get("offered_products", []), "metrics": tool_res.get("metrics", {})
    }

def reset_chat_session(session_id: str) -> dict[str, Any]:
    sess = _session_manager.reset_session(session_id)
    return {
        "session_id": session_id,
        "messages": sess["messages"]
    }

def get_chat_history(session_id: str) -> list[dict]:
    sess = _session_manager.get_session(session_id)
    return sess["messages"]
