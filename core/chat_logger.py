# -*- coding: utf-8 -*-
"""
Chat Logger System
Mencatat seluruh percakapan Customer Care secara persisten ke file JSON Lines
dan database SQLite dengan perlindungan privasi penuh (HMAC anonimisasi).
Mendukung isolasi pengujian (test/eval) agar data operasional tidak tercemar.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime
from typing import Any

logger = logging.getLogger("chat_logger")

_lock = threading.RLock()
_log_failure_count = 0


def get_log_failure_count() -> int:
    """Mengembalikan total kegagalan penulisan log sejak startup."""
    with _lock:
        return _log_failure_count


def record_log_failure() -> None:
    """Mencatat adanya kegagalan logging untuk pemantauan kesehatan sistem."""
    global _log_failure_count
    with _lock:
        _log_failure_count += 1


def reset_log_failure_count() -> None:
    """Mereset counter kegagalan log (misal untuk pengujian)."""
    global _log_failure_count
    with _lock:
        _log_failure_count = 0


def is_test_mode() -> bool:
    """Mendeteksi apakah eksekusi saat ini berada di lingkungan uji/evaluasi."""
    return (
        os.getenv("CHAT_LOG_TARGET") == "eval"
        or "PYTEST_CURRENT_TEST" in os.environ
        or os.getenv("TESTING") == "1"
    )


def get_hmac_secret(penguji: str = "manusia") -> bytes:
    """
    Mengambil kunci HMAC dari environment atau .env.
    Di mode operasional (penguji='manusia' dan bukan mode uji), ketiadaan kunci
    akan memicu RuntimeError eksplisit demi perlindungan privasi.
    """
    key = os.getenv("LOG_HMAC_KEY") or os.getenv("LOG_HMAC_SECRET")
    if key and key.strip():
        return key.strip().encode("utf-8")

    # Jika sedang dalam test/eval mode, sediakan dummy test key aman
    if is_test_mode() or penguji == "otomatis":
        return b"test_hmac_secret_for_test_suite_2026"

    raise RuntimeError(
        "Kunci LOG_HMAC_KEY wajib diatur di file .env atau environment untuk mode operasional. "
        "Silakan tambahkan 'LOG_HMAC_KEY=<kunci>' ke berkas .env Anda demi privasi pelanggan."
    )


def anonymize_id(raw_id: str | int, length: int = 12, penguji: str = "manusia") -> str:
    """
    Anonimisasi pengenal pengguna / sesi menggunakan HMAC-SHA256.
    Session ID mentah (seperti ID Telegram) tidak boleh disimpan langsung.
    """
    secret = get_hmac_secret(penguji=penguji)
    return hmac.new(secret, str(raw_id).encode("utf-8"), hashlib.sha256).hexdigest()[:length]


def get_log_paths(penguji: str = "manusia") -> tuple[str, str]:
    """
    Mengembalikan (jsonl_path, db_path) sesuai isolasi mode pengujian.
    Semua tes dan skrip evaluasi menulis ke logs/eval/eval_chat_history.jsonl
    dan database uji, tidak pernah ke logs/chat_history.jsonl.
    """
    if is_test_mode() or penguji == "otomatis":
        jsonl_dir = os.path.join("logs", "eval")
        os.makedirs(jsonl_dir, exist_ok=True)
        jsonl_path = os.path.join(jsonl_dir, "eval_chat_history.jsonl")
        db_path = os.getenv("DB_PATH", os.path.join("data", "test_catalog.db"))
        return jsonl_path, db_path

    jsonl_dir = "logs"
    os.makedirs(jsonl_dir, exist_ok=True)
    jsonl_path = os.path.join(jsonl_dir, "chat_history.jsonl")
    db_path = os.getenv("DB_PATH", os.path.join("data", "catalog.db"))
    return jsonl_path, db_path


def init_chat_log_storage(db_path: str | None = None) -> None:
    """Inisialisasi tabel SQLite chat_logs beserta migrasi kolom penguji & engine_mode."""
    if db_path is None:
        _, db_path = get_log_paths()
    target_db = db_path
    os.makedirs(os.path.dirname(target_db) or ".", exist_ok=True)

    with _lock:
        conn = sqlite3.connect(target_db)
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
                latency_ms REAL,
                penguji TEXT DEFAULT 'manusia',
                engine_mode TEXT DEFAULT 'antigravity_v2',
                jalur TEXT DEFAULT 'model',
                aksi_parser TEXT,
                jenis TEXT,
                state_ringkas TEXT,
                produk_tampil TEXT,
                parser_raw TEXT,
                kartu_ditampilkan INTEGER,
                keluhan_beruntun INTEGER,
                status_fakta TEXT,
                state_setelah TEXT,
                is_emergency_fallback INTEGER,
                jumlah_retry INTEGER,
                pelanggaran TEXT,
                kartu_isi TEXT,
                produk_dibahas TEXT,
                produk_dibahas_sebelumnya TEXT,
                catatan_minimum TEXT,
                generator_calls TEXT,
                tool_calls TEXT,
                pemeriksa_catatan TEXT
            )
        """)
        # Migrasi kolom jika tabel lama belum memiliki kolom baru
        cur.execute("PRAGMA table_info(chat_logs)")
        existing_cols = {col[1] for col in cur.fetchall()}
        if "penguji" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN penguji TEXT DEFAULT 'manusia'")
        if "engine_mode" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN engine_mode TEXT DEFAULT 'antigravity_v2'")
        if "jalur" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN jalur TEXT DEFAULT 'model'")
        if "aksi_parser" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN aksi_parser TEXT")
        if "jenis" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN jenis TEXT")
        if "state_ringkas" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN state_ringkas TEXT")
        if "produk_tampil" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN produk_tampil TEXT")
        if "parser_raw" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN parser_raw TEXT")
        if "kartu_ditampilkan" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN kartu_ditampilkan INTEGER")
        if "keluhan_beruntun" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN keluhan_beruntun INTEGER")
        if "tanya_beruntun" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN tanya_beruntun INTEGER")
        if "status_fakta" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN status_fakta TEXT")
        if "state_setelah" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN state_setelah TEXT")
        if "is_emergency_fallback" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN is_emergency_fallback INTEGER")
        if "jumlah_retry" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN jumlah_retry INTEGER")
        if "pelanggaran" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN pelanggaran TEXT")
        if "kartu_isi" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN kartu_isi TEXT")
        if "produk_dibahas" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN produk_dibahas TEXT")
        if "produk_dibahas_sebelumnya" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN produk_dibahas_sebelumnya TEXT")
        if "catatan_minimum" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN catatan_minimum TEXT")
        if "permintaan_asli" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN permintaan_asli TEXT")
        if "argumen_ditolak" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN argumen_ditolak TEXT")
        if "konteks_toko" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN konteks_toko TEXT")
        if "fakta_lengkap" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN fakta_lengkap TEXT")
        if "generator_error" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN generator_error TEXT")
        if "sumber_balasan" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN sumber_balasan TEXT")
        if "generator_calls" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN generator_calls TEXT")
        if "tool_calls" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN tool_calls TEXT")
        if "pemeriksa_catatan" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN pemeriksa_catatan TEXT")
        if "error_darurat" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN error_darurat TEXT")
        if "menunggu_menit" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN menunggu_menit INTEGER")
        if "pemeriksaan_ulang" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN pemeriksaan_ulang INTEGER")
        if "balasan_sebelum_periksa" not in existing_cols:
            cur.execute("ALTER TABLE chat_logs ADD COLUMN balasan_sebelum_periksa TEXT")

        cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_logs_session ON chat_logs(session_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_logs_timestamp ON chat_logs(timestamp)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_logs_channel ON chat_logs(channel)")
        conn.commit()
        conn.close()


# Inisialisasi awal aman
try:
    init_chat_log_storage()
except Exception as exc:
    logger.warning("Gagal inisialisasi chat log storage pada modul load: %s", exc)


def log_turn(
    session_id: str,
    user_text: str,
    bot_reply: str,
    route: str | None = None,
    state_snapshot: dict[str, Any] | None = None,
    latency_ms: float = 0.0,
    penguji: str | None = None,
    engine_mode: str | None = None,
    jalur: str | None = None,
    aksi_parser: str | None = None,
    jenis: str | None = None,
    state_ringkas: dict[str, Any] | None = None,
    produk_tampil: list[str] | None = None,
    parser_raw: Any = None,
    kartu_ditampilkan: bool | None = None,
    keluhan_beruntun: int | None = None,
    tanya_beruntun: int | None = None,
    status_fakta: str | None = None,
    state_setelah: dict[str, Any] | None = None,
    is_emergency_fallback: bool | None = None,
    jumlah_retry: int | None = None,
    pelanggaran: list[str] | str | None = None,
    kartu_isi: list[dict[str, Any]] | None = None,
    produk_dibahas: Any = None,
    produk_dibahas_sebelumnya: list[dict[str, Any]] | None = None,
    catatan_minimum: Any = None,
    permintaan_asli: dict[str, Any] | None = None,
    argumen_ditolak: list[dict[str, Any]] | None = None,
    konteks_toko: dict[str, Any] | None = None,
    fakta_lengkap: dict[str, Any] | None = None,
    generator_error: str | None = None,
    sumber_balasan: str | None = None,
    generator_calls: list[dict[str, Any]] | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    llm_calls: list[dict[str, Any]] | None = None,
    pemeriksa_catatan: Any = None,
    error_darurat: str | None = None,
    menunggu_menit: int | None = None,
    pemeriksaan_ulang: bool | None = None,
    balasan_sebelum_periksa: str | None = None,
) -> dict[str, Any]:
    """
    Mencatat 1 turn percakapan pelanggan dan jawaban bot.
    Menyimpan ke file JSONL dan tabel SQLite secara aman dan terisolasi.
    """
    effective_penguji = penguji or ("otomatis" if is_test_mode() else "manusia")
    effective_engine = engine_mode or os.getenv("CHAT_ENGINE_MODE", "agentic_tool")

    # Anonimisasi session_id mentah dengan HMAC
    anon_session = anonymize_id(session_id, penguji=effective_penguji)

    state = state_snapshot or {}
    now_iso = datetime.now().isoformat()
    log_id = f"log_{uuid.uuid4().hex[:12]}"

    # Deteksi channel
    channel = "telegram" if str(session_id).startswith("tg_") else "web"

    fsm_stage = state.get("fsm_stage", "UNKNOWN")
    active_category = state.get("category") or state.get("kategori")
    persona_name = state.get("persona_name") or state.get("persona")
    needs = state.get("needs", [])
    constraints = state.get("constraints", {})
    offered_products = state.get("offered_products", [])

    if state_setelah is None:
        state_setelah = {
            "kategori": state.get("kategori") or state.get("category"),
            "merek": state.get("merek"),
            "kebutuhan_teks": state.get("kebutuhan_teks"),
            "budget": state.get("budget"),
        }

    if state_ringkas is None:
        state_ringkas = {
            "kategori": state.get("kategori") or state.get("category"),
            "budget": state.get("budget"),
            "merek": state.get("merek"),
            "kebutuhan_teks": state.get("kebutuhan_teks"),
            "pemakai": state.get("persona") or state.get("pemakai") or state.get("sebutan") or state.get("persona_name"),
        }

    if produk_tampil is None:
        raw_tampil = state.get("produk_tampil", [])
        produk_tampil = [p.get("kode") for p in raw_tampil if isinstance(p, dict) and p.get("kode")]

    if kartu_ditampilkan is None:
        kartu_ditampilkan = False

    if keluhan_beruntun is None:
        keluhan_beruntun = int(state.get("keluhan_beruntun", 0) or 0)

    if tanya_beruntun is None:
        tanya_beruntun = int(state.get("tanya_beruntun", 0) or 0)

    if produk_dibahas is None:
        produk_dibahas = state.get("produk_dibahas")

    if produk_dibahas_sebelumnya is None:
        produk_dibahas_sebelumnya = state.get("produk_dibahas_sebelumnya")

    # Pastikan session_id mentah tidak pernah disimpan di record
    record = {
        "log_id": log_id,
        "type": "chat_turn",
        "timestamp": now_iso,
        "session_id": anon_session,
        "anon_session_id": anon_session,
        "channel": channel,
        "user_text": user_text,
        "bot_reply": bot_reply,
        "route": route,
        "jalur": jalur or "model",
        "aksi_parser": aksi_parser,
        "jenis": jenis,
        "status_fakta": status_fakta,
        "state_setelah": state_setelah,
        "state_ringkas": state_ringkas,
        "produk_tampil": produk_tampil,
        "parser_raw": parser_raw,
        "kartu_ditampilkan": bool(kartu_ditampilkan),
        "keluhan_beruntun": int(keluhan_beruntun),
        "tanya_beruntun": int(tanya_beruntun),
        "fsm_stage": fsm_stage,
        "active_category": active_category,
        "persona_name": persona_name,
        "needs": needs,
        "constraints": constraints,
        "offered_products": offered_products,
        "latency_ms": round(latency_ms, 2),
        "penguji": effective_penguji,
        "engine_mode": effective_engine,
        "is_emergency_fallback": bool(is_emergency_fallback),
        "jumlah_retry": int(jumlah_retry or 0),
        "pelanggaran": pelanggaran,
        "kartu_isi": kartu_isi,
        "produk_dibahas": produk_dibahas,
        "produk_dibahas_sebelumnya": produk_dibahas_sebelumnya,
        "catatan_minimum": catatan_minimum,
        "permintaan_asli": permintaan_asli,
        "argumen_ditolak": argumen_ditolak,
        "konteks_toko": konteks_toko,
        "fakta_lengkap": fakta_lengkap,
        "status_hasil": status_fakta,
        "generator_error": generator_error,
        "sumber_balasan": sumber_balasan,
        "generator_calls": generator_calls if generator_calls is not None else (llm_calls if llm_calls is not None else []),
        "llm_calls": llm_calls if llm_calls is not None else (generator_calls if generator_calls is not None else []),
        "tool_calls": tool_calls if tool_calls is not None else [],
        "pemeriksa_catatan": pemeriksa_catatan,
        "error_darurat": error_darurat,
        "menunggu_menit": menunggu_menit,
        "pemeriksaan_ulang": bool(pemeriksaan_ulang) if pemeriksaan_ulang is not None else False,
        "balasan_sebelum_periksa": balasan_sebelum_periksa,
    }

    jsonl_path, db_path = get_log_paths(penguji=effective_penguji)

    with _lock:
        # 1. Tulis ke file JSONL
        try:
            os.makedirs(os.path.dirname(jsonl_path) or ".", exist_ok=True)
            with open(jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("Gagal menulis ke %s: %s", jsonl_path, e)
            record_log_failure()
            raise

        # 2. Tulis ke SQLite
        try:
            init_chat_log_storage(db_path)
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO chat_logs (
                    log_id, timestamp, session_id, channel, user_text, bot_reply,
                    route, fsm_stage, active_category, persona_name,
                    needs_json, constraints_json, offered_products_json, latency_ms,
                    penguji, engine_mode, jalur, aksi_parser, jenis,
                    status_fakta, state_setelah,
                    state_ringkas, produk_tampil, parser_raw, kartu_ditampilkan,
                    keluhan_beruntun, tanya_beruntun,
                    is_emergency_fallback, jumlah_retry, pelanggaran, kartu_isi,
                    produk_dibahas, produk_dibahas_sebelumnya, catatan_minimum,
                    permintaan_asli, argumen_ditolak, konteks_toko, fakta_lengkap,
                    generator_error, sumber_balasan, generator_calls, tool_calls, pemeriksa_catatan,
                    error_darurat, menunggu_menit, pemeriksaan_ulang, balasan_sebelum_periksa
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log_id,
                now_iso,
                anon_session,
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
                latency_ms,
                effective_penguji,
                effective_engine,
                jalur or "model",
                aksi_parser,
                jenis,
                status_fakta,
                json.dumps(state_setelah, ensure_ascii=False) if state_setelah else None,
                json.dumps(state_ringkas, ensure_ascii=False) if state_ringkas else None,
                json.dumps(produk_tampil, ensure_ascii=False) if produk_tampil else None,
                json.dumps(parser_raw, ensure_ascii=False) if parser_raw else None,
                1 if kartu_ditampilkan else 0,
                keluhan_beruntun,
                tanya_beruntun,
                1 if is_emergency_fallback else 0,
                int(jumlah_retry or 0),
                json.dumps(pelanggaran, ensure_ascii=False) if isinstance(pelanggaran, (list, dict)) else (str(pelanggaran) if pelanggaran else None),
                json.dumps(kartu_isi, ensure_ascii=False) if kartu_isi else None,
                json.dumps(produk_dibahas, ensure_ascii=False) if isinstance(produk_dibahas, (list, dict)) else (str(produk_dibahas) if produk_dibahas else None),
                json.dumps(produk_dibahas_sebelumnya, ensure_ascii=False) if produk_dibahas_sebelumnya else None,
                json.dumps(catatan_minimum, ensure_ascii=False) if isinstance(catatan_minimum, (list, dict)) else (str(catatan_minimum) if catatan_minimum else None),
                json.dumps(permintaan_asli, ensure_ascii=False) if permintaan_asli else None,
                json.dumps(argumen_ditolak, ensure_ascii=False) if argumen_ditolak else None,
                json.dumps(konteks_toko, ensure_ascii=False) if konteks_toko else None,
                json.dumps(fakta_lengkap, ensure_ascii=False) if fakta_lengkap else None,
                generator_error,
                sumber_balasan,
                json.dumps(generator_calls, ensure_ascii=False) if generator_calls else None,
                json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
                json.dumps(pemeriksa_catatan, ensure_ascii=False) if isinstance(pemeriksa_catatan, (list, dict)) else (str(pemeriksa_catatan) if pemeriksa_catatan else None),
                error_darurat,
                menunggu_menit,
                1 if pemeriksaan_ulang else 0,
                balasan_sebelum_periksa,
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("Gagal insert ke sqlite chat_logs (%s): %s", db_path, e)
            record_log_failure()
            raise

    return record


def log_session_boundary(
    session_id: str,
    boundary_type: str,
    reason: str = "",
    penguji: str | None = None,
    engine_mode: str | None = None,
) -> dict[str, Any]:
    """
    Mencatat perpindahan sesi eksplisit (/start, /reset, atau kedaluwarsa 24 jam)
    sebagai entri log pembatas terpisah (tipe 'session_boundary').
    """
    effective_penguji = penguji or ("otomatis" if is_test_mode() else "manusia")
    effective_engine = engine_mode or os.getenv("CHAT_ENGINE_MODE", "antigravity_v2")

    anon_session = anonymize_id(session_id, penguji=effective_penguji)
    now_iso = datetime.now().isoformat()
    log_id = f"boundary_{uuid.uuid4().hex[:12]}"
    channel = "telegram" if str(session_id).startswith("tg_") else "web"

    record = {
        "log_id": log_id,
        "type": "session_boundary",
        "boundary_type": boundary_type,
        "reason": reason,
        "timestamp": now_iso,
        "session_id": anon_session,
        "anon_session_id": anon_session,
        "channel": channel,
        "user_text": f"[{boundary_type.upper()}] {reason}".strip(),
        "bot_reply": "",
        "route": "session_boundary",
        "fsm_stage": boundary_type,
        "penguji": effective_penguji,
        "engine_mode": effective_engine,
    }

    jsonl_path, db_path = get_log_paths(penguji=effective_penguji)

    with _lock:
        # 1. Tulis ke file JSONL
        try:
            os.makedirs(os.path.dirname(jsonl_path) or ".", exist_ok=True)
            with open(jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("Gagal mencatat session_boundary ke %s: %s", jsonl_path, e)
            record_log_failure()
            raise

        # 2. Tulis ke SQLite
        try:
            init_chat_log_storage(db_path)
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO chat_logs (
                    log_id, timestamp, session_id, channel, user_text, bot_reply,
                    route, fsm_stage, active_category, persona_name,
                    needs_json, constraints_json, offered_products_json, latency_ms,
                    penguji, engine_mode
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log_id,
                now_iso,
                anon_session,
                channel,
                record["user_text"],
                "",
                "session_boundary",
                boundary_type,
                None,
                None,
                "[]",
                "{}",
                "[]",
                0.0,
                effective_penguji,
                effective_engine,
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("Gagal insert boundary ke sqlite (%s): %s", db_path, e)
            record_log_failure()
            raise

    return record


def get_recent_logs(
    limit: int = 50,
    session_id: str | None = None,
    channel: str | None = None,
    penguji: str = "manusia",
) -> list[dict[str, Any]]:
    """Mengambil riwayat log terbaru untuk pemantauan dan evaluasi."""
    _, db_path = get_log_paths(penguji=penguji)
    init_chat_log_storage(db_path)

    query = "SELECT * FROM chat_logs"
    params: list[Any] = []
    clauses = []

    if session_id:
        anon_session = anonymize_id(session_id, penguji=penguji)
        clauses.append("session_id = ?")
        params.append(anon_session)
    if channel:
        clauses.append("channel = ?")
        params.append(channel)

    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    out = []
    for r in rows:
        d = dict(r)
        for field in ("needs_json", "constraints_json", "offered_products_json"):
            target_key = field.replace("_json", "")
            try:
                d[target_key] = json.loads(d.get(field) or "[]")
            except Exception:
                d[target_key] = None
        out.append(d)
    return out


def get_log_stats(penguji: str = "manusia") -> dict[str, Any]:
    """Mengambil statistik agregat percakapan pelanggan."""
    _, db_path = get_log_paths(penguji=penguji)
    init_chat_log_storage(db_path)

    conn = sqlite3.connect(db_path)
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
        "avg_latency_ms": round(avg_latency, 2),
    }


def log_foto_terkirim(
    session_id: str | int,
    kode_produk_list: list[str],
    alasan: str = "",
    foto_diminta: bool = False,
    penguji: str | None = None,
) -> dict[str, Any]:
    """Mencatat aktivitas pengiriman foto produk (Putaran 18e Butir 5).
    Tipe: 'foto_terkirim'.
    - session_id anonim dengan HMAC
    - timestamp
    - kode_produk: list kode produk yang berhasil dikirim
    - alasan: 'tidak ada produk aktif', 'tidak ada berkas', atau empty string
    """
    effective_penguji = penguji or ("otomatis" if is_test_mode() else "manusia")
    anon_session = anonymize_id(session_id, penguji=effective_penguji)
    now_iso = datetime.now().isoformat()
    log_id = f"foto_{uuid.uuid4().hex[:12]}"

    record = {
        "log_id": log_id,
        "type": "foto_terkirim",
        "session_id": anon_session,
        "timestamp": now_iso,
        "kode_produk": list(kode_produk_list),
        "alasan": alasan,
        "foto_diminta": foto_diminta,
        "penguji": effective_penguji
    }

    jsonl_path, _ = get_log_paths(penguji=effective_penguji)

    with _lock:
        try:
            os.makedirs(os.path.dirname(jsonl_path) or ".", exist_ok=True)
            with open(jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("Gagal mencatat foto_terkirim ke %s: %s", jsonl_path, e)
            record_log_failure()
            raise

    return record


def log_status_kirim(
    session_id: str | int,
    status: str,
    jumlah_percobaan: int,
    error_teks: str | None = None,
    penguji: str | None = None,
) -> dict[str, Any]:
    """Mencatat status pengiriman balasan ke pelanggan (Putaran 25 Butir 3a).
    Tipe: 'status_kirim'.
    - session_id anonim dengan HMAC
    - timestamp
    - status: 'terkirim' atau 'gagal'
    - jumlah_percobaan: int (1..3)
    - error_teks: str | None bila gagal
    """
    effective_penguji = penguji or ("otomatis" if is_test_mode() else "manusia")
    anon_session = anonymize_id(session_id, penguji=effective_penguji)
    now_iso = datetime.now().isoformat()
    log_id = f"kirim_{uuid.uuid4().hex[:12]}"

    record = {
        "log_id": log_id,
        "type": "status_kirim",
        "session_id": anon_session,
        "timestamp": now_iso,
        "status": status,
        "jumlah_percobaan": jumlah_percobaan,
        "error_teks": error_teks,
        "penguji": effective_penguji
    }

    jsonl_path, _ = get_log_paths(penguji=effective_penguji)

    with _lock:
        try:
            os.makedirs(os.path.dirname(jsonl_path) or ".", exist_ok=True)
            with open(jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("Gagal mencatat status_kirim ke %s: %s", jsonl_path, e)
            record_log_failure()
            raise

    return record

