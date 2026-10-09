# -*- coding: utf-8 -*-
"""
Unit tests untuk sistem chat logger (Fase 1: Log dan Privasi).
Memverifikasi isolasi log uji, kepatuhan privasi (HMAC), batas sesi eksplisit,
dan pelacakan kegagalan logging.
"""
import json
import os
import sqlite3
import pytest

from core.chat_logger import (
    log_turn,
    log_session_boundary,
    anonymize_id,
    get_hmac_secret,
    get_log_failure_count,
    record_log_failure,
    reset_log_failure_count,
    get_recent_logs,
)
from services.chat_service import process_chat_message, reset_chat_session


def test_test_environment_never_writes_to_production_jsonl(tmp_path):
    """Memverifikasi bahwa eksekusi di lingkungan uji tidak pernah menambah baris ke logs/chat_history.jsonl."""
    prod_log_path = os.path.join("logs", "chat_history.jsonl")
    initial_line_count = 0
    if os.path.exists(prod_log_path):
        with open(prod_log_path, "r", encoding="utf-8") as f:
            initial_line_count = sum(1 for line in f if line.strip())

    # Jalankan log_turn di bawah lingkungan tes (otomatis)
    res = log_turn(
        session_id="test_session_isolated_01",
        user_text="tes isolasi",
        bot_reply="jawaban isolasi",
        route="direct",
        penguji="otomatis"
    )

    # Pastikan file produksi TIDAK bertambah baris sama sekali
    current_line_count = 0
    if os.path.exists(prod_log_path):
        with open(prod_log_path, "r", encoding="utf-8") as f:
            current_line_count = sum(1 for line in f if line.strip())

    assert current_line_count == initial_line_count, (
        f"Pelanggaran isolasi: logs/chat_history.jsonl bertambah dari {initial_line_count} ke {current_line_count}"
    )

    # Pastikan log ditulis ke logs/eval/eval_chat_history.jsonl
    eval_log_path = os.path.join("logs", "eval", "eval_chat_history.jsonl")
    assert os.path.exists(eval_log_path), "Log uji harus tersimpan di logs/eval/eval_chat_history.jsonl"
    with open(eval_log_path, "r", encoding="utf-8") as f:
        last_line = f.readlines()[-1]
        data = json.loads(last_line)
        assert data["penguji"] == "otomatis"
        assert data["user_text"] == "tes isolasi"


def test_missing_hmac_key_raises_runtime_error_in_operational_mode(monkeypatch):
    """Memverifikasi ketiadaan LOG_HMAC_KEY di mode operasional memicu RuntimeError."""
    monkeypatch.delenv("LOG_HMAC_KEY", raising=False)
    monkeypatch.delenv("LOG_HMAC_SECRET", raising=False)
    monkeypatch.delenv("CHAT_LOG_TARGET", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("TESTING", raising=False)

    with pytest.raises(RuntimeError, match="Kunci LOG_HMAC_KEY wajib diatur"):
        get_hmac_secret(penguji="manusia")


def test_raw_session_id_is_never_logged_directly(tmp_path):
    """Memverifikasi session_id mentah (seperti ID Telegram) selalu di-anonimkan dan tidak disimpan mentah."""
    raw_tg_id = "tg_9876543210_secret"
    res = log_turn(
        session_id=raw_tg_id,
        user_text="halo bot",
        bot_reply="halo kembali",
        penguji="otomatis"
    )

    anon_expected = anonymize_id(raw_tg_id, penguji="otomatis")
    assert res["session_id"] == anon_expected
    assert res["anon_session_id"] == anon_expected
    assert raw_tg_id not in json.dumps(res), "ID sesi mentah tidak boleh bocor ke payload log"

    # Periksa isi SQLite test
    test_db = os.getenv("DB_PATH", "data/test_catalog.db")
    conn = sqlite3.connect(test_db)
    cur = conn.cursor()
    cur.execute("SELECT session_id, user_text, penguji, engine_mode FROM chat_logs WHERE log_id = ?", (res["log_id"],))
    row = cur.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == anon_expected
    assert raw_tg_id != row[0]
    assert row[2] == "otomatis"
    assert row[3] is not None


def test_log_session_boundary_records_explicit_events():
    """Memverifikasi batas sesi (/start, /reset, atau expired) dicatat sebagai event session_boundary."""
    boundary = log_session_boundary(
        session_id="tg_12345678",
        boundary_type="reset",
        reason="user_reset",
        penguji="otomatis"
    )

    assert boundary["type"] == "session_boundary"
    assert boundary["boundary_type"] == "reset"
    assert boundary["reason"] == "user_reset"
    assert "tg_12345678" not in boundary["session_id"]

    eval_log_path = os.path.join("logs", "eval", "eval_chat_history.jsonl")
    with open(eval_log_path, "r", encoding="utf-8") as f:
        last_line = f.readlines()[-1]
        data = json.loads(last_line)
        assert data["type"] == "session_boundary"
        assert data["boundary_type"] == "reset"


def test_log_failure_counter_and_error_handling():
    """Memverifikasi bahwa kegagalan penulisan log tercatat di failure counter."""
    reset_log_failure_count()
    assert get_log_failure_count() == 0

    record_log_failure()
    assert get_log_failure_count() == 1

    record_log_failure()
    assert get_log_failure_count() == 2
    reset_log_failure_count()
    assert get_log_failure_count() == 0
