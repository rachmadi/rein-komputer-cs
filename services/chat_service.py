# -*- coding: utf-8 -*-
"""
Unified Chat Service
Menangani state percakapan multi-sesi untuk Web Chat dan Bot Telegram secara modular dan independen.
"""
from __future__ import annotations

import time
import logging
from datetime import datetime
from typing import Any
from core.state import new_state, reset_state
from core.engine import step
from services.catalog_service import get_active_catalog
from core.chat_logger import log_turn, log_session_boundary, record_log_failure

logger = logging.getLogger("chat_service")

class SessionManager:
    def __init__(self, ttl_seconds: int = 3600 * 24):
        self._sessions: dict[str, dict[str, Any]] = {}
        self.ttl_seconds = ttl_seconds

    def get_session(self, session_id: str) -> dict[str, Any]:
        now = time.time()
        sess = self._sessions.get(session_id)
        if not sess or (now - sess.get("last_active", 0) > self.ttl_seconds):
            if sess and (now - sess.get("last_active", 0) > self.ttl_seconds):
                try:
                    log_session_boundary(session_id, boundary_type="expired", reason="ttl_exceeded_24h")
                except Exception as err:
                    logger.error("Gagal mencatat log session expired: %s", err, exc_info=True)
                    record_log_failure()

            sess = {
                "session_id": session_id,
                "state": new_state(),
                "created_at": datetime.now().isoformat(),
                "last_active": now,
                "messages": [
                    {
                        "sender": "bot",
                        "role": "assistant",
                        "text": "Halo, Kak! Selamat datang di Customer Care ReIn Komputer. Ada yang bisa saya bantu cari hari ini? 😊",
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
        try:
            log_session_boundary(session_id, boundary_type="reset", reason="user_reset")
        except Exception as err:
            logger.error("Gagal mencatat log session reset: %s", err, exc_info=True)
            record_log_failure()

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
CHAT_ENGINE_MODE = os.getenv("CHAT_ENGINE_MODE", "antigravity_v2")

logger.info(
    "ChatService initialized: CHAT_ENGINE_MODE=%s, DEFAULT_CHAT_MODEL=%s",
    CHAT_ENGINE_MODE, DEFAULT_CHAT_MODEL
)

_session_manager = SessionManager()
_session_pipeline = None

def get_session_manager() -> SessionManager:
    return _session_manager

def get_session_pipeline():
    global _session_pipeline
    if _session_pipeline is None:
        from services.session_pipeline import SessionPipeline
        _session_pipeline = SessionPipeline()
    return _session_pipeline

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

    # OPSI 0: ANTIGRAVITY V2 PIPELINE (LLM PARSER + DETERMINISTIC ENGINE + LLM GENERATOR)
    if CHAT_ENGINE_MODE == "antigravity_v2":
        pipeline = get_session_pipeline()
        prior_history = sess["messages"][:-1] if sess["messages"] else []
        turn_res, new_state_dict = pipeline.process_turn(
            pesan_pelanggan=user_text,
            session_state=state,
            history=prior_history
        )
        reply = turn_res.teks_jawaban
        kartu_html = turn_res.kartu_produk_html
        route = turn_res.aksi_terpilih
        latency_ms = turn_res.latensi_total_ms

        sess["state"] = new_state_dict
        _session_manager.add_message(session_id, "bot", reply, route=route)

        try:
            log_turn(
                session_id=session_id,
                user_text=user_text,
                bot_reply=reply,
                route=route,
                state_snapshot=new_state_dict,
                latency_ms=latency_ms,
                engine_mode=CHAT_ENGINE_MODE,
                jalur=turn_res.jalur,
                aksi_parser=turn_res.aksi_parser,
                jenis=turn_res.jenis,
            )
        except Exception as err:
            logger.error("Gagal menulis log chat turn: %s", err, exc_info=True)
            record_log_failure()

        raw_tampil = new_state_dict.get("produk_tampil", [])
        enriched_products = []
        for p in raw_tampil:
            p_copy = dict(p)
            cat_p = pipeline.action_engine.get_product_by_code(p.get("kode"))
            if cat_p:
                for k in ["brand", "gpu", "ram_gb", "storage_ssd_gb", "vram_gb", "gpu_vram_gb", "harga_idr"]:
                    if k in cat_p and k not in p_copy:
                        p_copy[k] = cat_p[k]
                if "vram_gb" not in p_copy and "gpu_vram_gb" in cat_p:
                    p_copy["vram_gb"] = cat_p["gpu_vram_gb"]
                if "harga_idr" not in p_copy and "harga" in p_copy:
                    p_copy["harga_idr"] = p_copy["harga"]
            enriched_products.append(p_copy)

        return {
            "session_id": session_id,
            "reply": reply,
            "kartu_produk_html": kartu_html,
            "route": route,
            "messages": sess["messages"],
            "products": enriched_products,
            "slots": {
                "merek": new_state_dict.get("merek"),
                "kategori": new_state_dict.get("kategori"),
                "persona": new_state_dict.get("persona"),
                "aktivitas": new_state_dict.get("aktivitas"),
                "kebutuhan": new_state_dict.get("kebutuhan_teks"),
                "budget": new_state_dict.get("budget_max")
            },
            "pending_question": new_state_dict.get("pending_question"),
            "fsm_stage": new_state_dict.get("pending_question"),
            "category": new_state_dict.get("kategori"),
            "persona_name": new_state_dict.get("persona"),
            "offered_products": [p.get("kode") for p in new_state_dict.get("produk_tampil", []) if p.get("kode")],
            "fakta": turn_res.fakta_eksekusi,
            "metrics": {
                "latensi_parse_ms": turn_res.latensi_parse_ms,
                "latensi_mesin_ms": turn_res.latensi_mesin_ms,
                "latensi_generate_ms": turn_res.latensi_generate_ms,
                "latensi_total_ms": turn_res.latensi_total_ms,
                "pelanggaran_pemeriksa": turn_res.pelanggaran_pemeriksa,
                "is_fallback": turn_res.is_emergency_fallback
            }
        }

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
                latency_ms=latency_ms,
                engine_mode=CHAT_ENGINE_MODE,
            )
        except Exception as err:
            logger.error("Gagal menulis log chat turn: %s", err, exc_info=True)
            record_log_failure()

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
        from services.intent_router import classify_intent

        cur_intent = classify_intent(user_text, bool(state.get("active_profile") or sess["messages"]))
        if cur_intent in ("kebutuhan-jelas", "produk-spesifik") and user_text not in state.get("needs", []):
            if "needs" not in state or not isinstance(state["needs"], list):
                state["needs"] = []
            state["needs"].append(user_text)

        tool_res = run_agentic_tool(
            user_text=user_text,
            history=sess["messages"],
            catalog=catalog,
            current_category=state.get("category"),
            current_offered_products=state.get("offered_products"),
            shown_products=state.get("shown"),
            known_needs=state.get("needs"),
            active_profile_id=state.get("active_profile"),
            previous_lowest_price=state.get("lowest_price"),
            persona_name=state.get("persona_name"),
            pending_question=state.get("pending_question"),
            slots=state.get("slots"),
            model=active_model
        )
        reply = tool_res["reply"]
        route = tool_res.get("route", "AGENTIC_TOOL")
        latency_ms = tool_res.get("latency_ms", (time.time() - t0) * 1000)

        prods = tool_res.get("products", [])
        if prods:
            state["offered_products"] = [p["kode"] for p in prods]
            if "shown" not in state or not isinstance(state["shown"], list):
                state["shown"] = []
            for p in prods:
                if p["kode"] not in state["shown"]:
                    state["shown"].append(p["kode"])
            state["fsm_stage"] = "OFFERED"
        if tool_res.get("category"):
            state["category"] = tool_res["category"]
        if "active_profile_id" in tool_res:
            state["active_profile"] = tool_res["active_profile_id"]
            state["profil_aktif"] = tool_res["active_profile_id"]
        if tool_res.get("persona_name"):
            state["persona_name"] = tool_res["persona_name"]
        if "pending_question" in tool_res:
            state["pending_question"] = tool_res["pending_question"]
        if "slots" in tool_res:
            state["slots"] = tool_res["slots"]
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
                latency_ms=latency_ms,
                engine_mode=CHAT_ENGINE_MODE,
            )
        except Exception as err:
            logger.error("Gagal menulis log chat turn: %s", err, exc_info=True)
            record_log_failure()

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
            "pending_question": new_s.get("pending_question"),
            "slots": new_s.get("slots"),
            "profil_aktif": new_s.get("profil_aktif"),
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
            latency_ms=latency_ms,
            engine_mode=CHAT_ENGINE_MODE,
        )
    except Exception as err:
        logger.error("Gagal menulis log chat turn: %s", err, exc_info=True)
        record_log_failure()

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
