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
    log_foto_terkirim,
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


def test_agentic_turn_logging_tool_calls_and_pemeriksa_catatan(tmp_path):
    """Putaran 18 Butir 4: Memverifikasi pencatatan tool_calls, llm_calls, engine_mode, dan pemeriksa_catatan."""
    dummy_llm_calls = [{
        "urutan": 1,
        "prompt_eval_count": 150,
        "eval_count": 45,
        "done_reason": "stop",
        "latensi": 850.5,
        "raw_output": "Halo Kak, ada printer Epson EcoTank L3210."
    }]
    dummy_tool_calls = [{
        "nama": "cari_produk",
        "argumen": {"kategori": "printer"},
        "ringkasan_hasil": "Ditemukan 1 produk: KB-P06",
        "latensi": 12.3
    }]
    dummy_pemeriksa = ["Teks aman, tidak ada pelanggaran fakta"]

    res = log_turn(
        session_id="test_session_agentic_log",
        user_text="cari printer epson",
        bot_reply="Halo Kak, ada printer Epson EcoTank L3210.",
        route="AGENTIC_TOOL",
        engine_mode="agentic_tool",
        generator_calls=dummy_llm_calls,
        tool_calls=dummy_tool_calls,
        llm_calls=dummy_llm_calls,
        pemeriksa_catatan=dummy_pemeriksa,
        penguji="otomatis"
    )

    assert res["engine_mode"] == "agentic_tool"
    assert res["tool_calls"] == dummy_tool_calls
    assert res["pemeriksa_catatan"] == dummy_pemeriksa
    assert len(res["generator_calls"]) == 1
    assert res["generator_calls"][0]["prompt_eval_count"] == 150

    eval_log_path = os.path.join("logs", "eval", "eval_chat_history.jsonl")
    with open(eval_log_path, "r", encoding="utf-8") as f:
        last_line = f.readlines()[-1]
        data = json.loads(last_line)
        assert data["engine_mode"] == "agentic_tool"
        assert data["tool_calls"] == dummy_tool_calls
        assert data["pemeriksa_catatan"] == dummy_pemeriksa
        assert data["generator_calls"][0]["eval_count"] == 45
        assert data["llm_calls"][0]["prompt_eval_count"] == 150


def test_log_foto_terkirim_records_entries():
    """Putaran 18e Butir 5: Memverifikasi pencatatan log_foto_terkirim (berhasil kirim dan alasan jika gagal)."""
    # 1. Kasus foto berhasil dikirim
    rec_sent = log_foto_terkirim(
        session_id="tg_987654321",
        kode_produk_list=["KB-L01", "KB-D02"],
        foto_diminta=False,
        penguji="otomatis"
    )
    assert rec_sent["type"] == "foto_terkirim"
    assert rec_sent["kode_produk"] == ["KB-L01", "KB-D02"]
    assert rec_sent["alasan"] == ""
    assert rec_sent["foto_diminta"] is False
    assert "tg_987654321" not in rec_sent["session_id"]

    # 2. Kasus foto diminta tapi tidak ada produk aktif
    rec_no_prod = log_foto_terkirim(
        session_id="tg_987654321",
        kode_produk_list=[],
        alasan="tidak ada produk aktif",
        foto_diminta=True,
        penguji="otomatis"
    )
    assert rec_no_prod["type"] == "foto_terkirim"
    assert rec_no_prod["kode_produk"] == []
    assert rec_no_prod["alasan"] == "tidak ada produk aktif"
    assert rec_no_prod["foto_diminta"] is True

    # 3. Kasus foto diminta tapi tidak ada berkas
    rec_no_file = log_foto_terkirim(
        session_id="tg_987654321",
        kode_produk_list=[],
        alasan="tidak ada berkas",
        foto_diminta=True,
        penguji="otomatis"
    )
    assert rec_no_file["type"] == "foto_terkirim"
    assert rec_no_file["alasan"] == "tidak ada berkas"

    # Verifikasi baris di file log eval
    eval_log_path = os.path.join("logs", "eval", "eval_chat_history.jsonl")
    with open(eval_log_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
        last_rec = json.loads(lines[-1])
        assert last_rec["type"] == "foto_terkirim"
        assert last_rec["alasan"] == "tidak ada berkas"


def test_log_turn_pemeriksaan_ulang():
    """Memverifikasi pencatatan pemeriksaan_ulang dan balasan_sebelum_periksa di log."""
    res = log_turn(
        session_id="test_session_pemeriksaan_01",
        user_text="Laptop ready?",
        bot_reply="Stok ready.",
        pemeriksaan_ulang=True,
        balasan_sebelum_periksa="Saya cek dulu ya Kak",
        penguji="otomatis"
    )

    assert res["pemeriksaan_ulang"] is True
    assert res["balasan_sebelum_periksa"] == "Saya cek dulu ya Kak"

    # Periksa di SQLite
    test_db = os.getenv("DB_PATH", "data/test_catalog.db")
    conn = sqlite3.connect(test_db)
    cur = conn.cursor()
    cur.execute("SELECT pemeriksaan_ulang, balasan_sebelum_periksa FROM chat_logs WHERE log_id = ?", (res["log_id"],))
    row = cur.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == 1
    assert row[1] == "Saya cek dulu ya Kak"


def test_putaran27_butir3_uji_otomatis_logs():
    """Memverifikasi bahwa penguji='uji_otomatis' menulis ke logs/uji_history.jsonl dan bukan ke logs/chat_history.jsonl."""
    from core.chat_logger import get_log_paths, log_turn

    # 1. get_log_paths untuk uji_otomatis mengembalikan logs/uji_history.jsonl
    jsonl_path, _ = get_log_paths(penguji="uji_otomatis")
    assert jsonl_path == os.path.join("logs", "uji_history.jsonl")

    # 2. Catat jumlah baris prod chat_history.jsonl
    prod_path = os.path.join("logs", "chat_history.jsonl")
    initial_prod_lines = 0
    if os.path.exists(prod_path):
        with open(prod_path, "r", encoding="utf-8") as f:
            initial_prod_lines = sum(1 for line in f if line.strip())

    # 3. Jalankan log_turn dengan penguji='uji_otomatis'
    rec = log_turn(
        session_id="p27_test_session_01",
        user_text="Halo uji otomatis",
        bot_reply="Halo Kak",
        route="direct",
        penguji="uji_otomatis"
    )
    assert rec["penguji"] == "uji_otomatis"

    # Pastikan file produksi TIDAK bertambah
    current_prod_lines = 0
    if os.path.exists(prod_path):
        with open(prod_path, "r", encoding="utf-8") as f:
            current_prod_lines = sum(1 for line in f if line.strip())
    assert current_prod_lines == initial_prod_lines

    # Pastikan logs/uji_history.jsonl menerima record
    uji_path = os.path.join("logs", "uji_history.jsonl")
    assert os.path.exists(uji_path)
    with open(uji_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
        last_rec = json.loads(lines[-1])
        assert last_rec["penguji"] == "uji_otomatis"
        assert last_rec["user_text"] == "Halo uji otomatis"


