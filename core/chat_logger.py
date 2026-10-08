# -*- coding: utf-8 -*-
"""
Chat Logger System
Mencatat seluruh percakapan Customer Care (Web Chat & Telegram Bot) secara persisten
ke file JSON Lines (logs/chat_history.jsonl) dan database SQLite (data/catalog.db).
Memungkinkan pemantauan langsung, audit kualitas jawaban CS, dan evaluasi berkala.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import uuid
import hmac
import hashlib
from datetime import datetime
from typing import Any

logger = logging.getLogger("chat_logger")

LOG_DIR = "logs"
JSONL_LOG_PATH = os.path.join(LOG_DIR, "chat_history.jsonl")
DB_PATH = os.getenv("DB_PATH", os.path.join("data", "catalog.db"))
LOG_HMAC_SECRET = os.getenv("LOG_HMAC_SECRET", "bobby_computer_secure_salt_2026")

def anonymize_id(raw_id: str | int, length: int = 12) -> str:
    """Anonymize user / session identifier using HMAC-SHA256."""
    secret = LOG_HMAC_SECRET.encode("utf-8")
    return hmac.new(secret, str(raw_id).encode("utf-8"), hashlib.sha256).hexdigest()[:length]

_lock = threading.Lock()

def init_chat_log_storage():
    """Inisialisasi direktori log dan tabel SQLite chat_logs."""
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_id TEXT UNIQUE,
                timestamp TEXT NOT NULL,
                session_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                user_text TEXT NOT NULL,
                bot_reply TEXT NOT NULL,
                route TEXT,
                fsm_stage TEXT,
                active_category TEXT,
                persona_name TEXT,
                needs_json TEXT,
                constraints_json TEXT,
                offered_products_json TEXT,
                latency_ms REAL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_logs_session ON chat_logs(session_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_logs_timestamp ON chat_logs(timestamp)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_logs_channel ON chat_logs(channel)")
        conn.commit()
        conn.close()

# Pastikan tabel dan direktori siap saat modul dimuat
try:
    init_chat_log_storage()
except Exception as e:
    logger.warning("Gagal inisialisasi chat log storage: %s", e)


def log_turn(
    session_id: str,
    user_text: str,
    bot_reply: str,
    route: str | None = None,
    state_snapshot: dict[str, Any] | None = None,
    latency_ms: float = 0.0,
) -> dict[str, Any]:
    """
    Mencatat 1 turn percakapan pelanggan dan jawaban bot.
    Menyimpan ke file JSONL dan tabel SQLite secara aman.
    """
    state = state_snapshot or {}
    now_dt = datetime.now()
    now_iso = now_dt.isoformat()
    log_id = f"log_{uuid.uuid4().hex[:12]}"
    
    # Deteksi channel
    channel = "telegram" if session_id.startswith("tg_") else "web"
    
    fsm_stage = state.get("fsm_stage", "UNKNOWN")
    active_category = state.get("category")
    persona_name = state.get("persona_name")
    needs = state.get("needs", [])
    constraints = state.get("constraints", {})
    offered_products = state.get("offered_products", [])
    
    record = {
        "log_id": log_id,
        "timestamp": now_iso,
        "session_id": session_id,
        "anon_session_id": anonymize_id(session_id),
        "channel": channel,
        "user_text": user_text,
        "bot_reply": bot_reply,
        "route": route,
        "fsm_stage": fsm_stage,
        "active_category": active_category,
        "persona_name": persona_name,
        "needs": needs,
        "constraints": constraints,
        "offered_products": offered_products,
        "latency_ms": round(latency_ms, 2)
    }
    
    with _lock:
        # 1. Tulis ke file JSONL
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(JSONL_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("Gagal menulis ke %s: %s", JSONL_LOG_PATH, e)
            
        # 2. Tulis ke SQLite
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO chat_logs (
                    log_id, timestamp, session_id, channel, user_text, bot_reply,
                    route, fsm_stage, active_category, persona_name,
                    needs_json, constraints_json, offered_products_json, latency_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log_id,
                now_iso,
                session_id,
                channel,
                user_text,
                bot_reply,
                route,
                fsm_stage,
                active_category,
                persona_name,
                json.dumps(needs, ensure_ascii=False),
                json.dumps(constraints, ensure_ascii=False),
                json.dumps(offered_products, ensure_ascii=False),
                latency_ms
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("Gagal insert ke sqlite chat_logs: %s", e)
            
    return record


def get_recent_logs(
    limit: int = 50,
    session_id: str | None = None,
    channel: str | None = None
) -> list[dict[str, Any]]:
    """Mengambil riwayat log terbaru untuk pemantauan dan evaluasi."""
    query = "SELECT * FROM chat_logs"
    params: list[Any] = []
    clauses = []
    
    if session_id:
        clauses.append("session_id = ?")
        params.append(session_id)
    if channel:
        clauses.append("channel = ?")
        params.append(channel)
        
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
        
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    
    out = []
    for r in rows:
        d = dict(r)
        # Parse JSON fields
        for field in ("needs_json", "constraints_json", "offered_products_json"):
            target_key = field.replace("_json", "")
            try:
                d[target_key] = json.loads(d.get(field) or "[]")
            except Exception:
                d[target_key] = None
        out.append(d)
    return out


def get_log_stats() -> dict[str, Any]:
    """Mengambil statistik agregat percakapan pelanggan."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM chat_logs")
    total_messages = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(DISTINCT session_id) FROM chat_logs")
    total_sessions = cur.fetchone()[0]
    
    cur.execute("SELECT channel, COUNT(*) FROM chat_logs GROUP BY channel")
    channel_counts = dict(cur.fetchall())
    
    cur.execute("SELECT route, COUNT(*) FROM chat_logs GROUP BY route ORDER BY COUNT(*) DESC LIMIT 10")
    top_routes = dict(cur.fetchall())
    
    cur.execute("SELECT AVG(latency_ms) FROM chat_logs WHERE latency_ms > 0")
    avg_latency = cur.fetchone()[0] or 0.0
    
    conn.close()
    
    return {
        "total_messages": total_messages,
        "total_sessions": total_sessions,
        "channels": channel_counts,
        "top_routes": top_routes,
        "avg_latency_ms": round(avg_latency, 2)
    }
