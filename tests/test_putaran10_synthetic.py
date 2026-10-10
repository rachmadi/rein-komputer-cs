# -*- coding: utf-8 -*-
"""
tests/test_putaran10_synthetic.py
Pengujian unit sintetis untuk Putaran 10 (ReIn Komputer).
Semua pengujian menggunakan kalimat/kata sintetis buatan sendiri,
tanpa kalimat pelanggan nyata.
"""
import pytest
from services.session_pipeline import SessionPipeline, match_rule_greeting


def test_butir1_jalur_aturan_sapaan_dan_terima_kasih_cocok():
    """Menguji jalur aturan sapaan dan terima kasih cocok persis tanpa model."""
    # Sapaan waktu
    res_pagi = match_rule_greeting("selamat pagi kak")
    assert res_pagi is not None
    assert res_pagi[0] == "sapa"
    assert "Selamat pagi" in res_pagi[1]
    assert "ReIn Komputer" in res_pagi[1]

    res_siang = match_rule_greeting("siang kakak")
    assert res_siang is not None
    assert res_siang[0] == "sapa"
    assert "Selamat siang" in res_siang[1]

    res_sore = match_rule_greeting("selamat sore")
    assert res_sore is not None
    assert res_sore[0] == "sapa"
    assert "Selamat sore" in res_sore[1]

    res_malam = match_rule_greeting("malam kak")
    assert res_malam is not None
    assert res_malam[0] == "sapa"
    assert "Selamat malam" in res_malam[1]

    # Assalamualaikum
    res_salam = match_rule_greeting("assalamualaikum")
    assert res_salam is not None
    assert res_salam[0] == "sapa"
    assert "Waalaikumsalam" in res_salam[1]
    assert "ReIn Komputer" in res_salam[1]

    # Sapaan tanpa waktu
    res_halo = match_rule_greeting("halo kakak")
    assert res_halo is not None
    assert res_halo[0] == "sapa"
    assert "Halo, Kak!" in res_halo[1]
    assert "ReIn Komputer" in res_halo[1]

    # Terima kasih
    res_thanks = match_rule_greeting("terima kasih banyak kak")
    assert res_thanks is not None
    assert res_thanks[0] == "basa_basi"
    assert "Sama-sama" in res_thanks[1]
    assert "ReIn Komputer" in res_thanks[1]

    res_makasih = match_rule_greeting("makasih kak")
    assert res_makasih is not None
    assert res_makasih[0] == "basa_basi"

    res_eng = match_rule_greeting("thanks")
    assert res_eng is not None
    assert res_eng[0] == "basa_basi"


def test_butir1_jalur_aturan_sapaan_ada_kata_lain():
    """Menguji bahwa adanya kata lain sekecil apa pun membatalkan jalur aturan."""
    # Ada kata objek atau permintaan
    assert match_rule_greeting("halo printer") is None
    assert match_rule_greeting("selamat pagi cari perangkat") is None
    assert match_rule_greeting("assalamualaikum mau tanya") is None
    assert match_rule_greeting("makasih infonya ya") is None
    assert match_rule_greeting("terima kasih atas bantuannya") is None
    assert match_rule_greeting("hai kawan") is None


def test_butir1_pipeline_process_turn_aturan_vs_state():
    """Menguji bahwa eksekusi aturan di process_turn tidak mengubah state sesi."""
    pipeline = SessionPipeline()
    initial_state = {
        "kategori": "laptop",
        "budget": 15000000,
        "produk_tampil": [{"kode": "ACR-NITRO-01", "nama": "Acer Nitro"}]
    }

    t_res, updated_state = pipeline.process_turn("halo kak", session_state=initial_state)

    assert t_res.jalur == "aturan"
    assert t_res.aksi_terpilih == "sapa"
    assert t_res.latensi_parse_ms == 0.0
    assert t_res.latensi_generate_ms == 0.0
    assert "ReIn Komputer" in t_res.teks_jawaban

    # State tidak berubah kecuali history
    assert updated_state["kategori"] == "laptop"
    assert updated_state["budget"] == 15000000
    assert len(updated_state["produk_tampil"]) == 1
    assert len(updated_state["history"]) == 2


def test_butir2_termurah_dari_tampil():
    """Menguji pemilihan unit termurah di antara produk_tampil tanpa pencarian katalog baru."""
    from services.action_engine import ActionEngine
    from services.schema_actions import ParserOutput, ActionEnum, ActionArguments, JenisEnum, StateUpdate

    engine = ActionEngine()
    state = {
        "kategori": "laptop",
        "produk_tampil": [
            {"kode": "UNIT-MAHAL", "nama": "Laptop Alpha", "harga": 18000000},
            {"kode": "UNIT-MURAH", "nama": "Laptop Beta", "harga": 7500000},
            {"kode": "UNIT-SEDANG", "nama": "Laptop Gamma", "harga": 12000000},
        ]
    }
    parsed = ParserOutput(
        aksi=ActionEnum.LANJUTAN_HASIL,
        argumen=ActionArguments(jenis=JenisEnum.TERMURAH_DARI_TAMPIL),
        pembaruan_state=StateUpdate()
    )

    res = engine.execute(parsed, session_state=state)
    assert res.aksi == ActionEnum.LANJUTAN_HASIL
    assert res.fakta["status"] == "sukses"
    assert res.fakta["jenis_lanjutan"] == "termurah_dari_tampil"
    assert len(res.produk_list) == 1
    assert res.produk_list[0]["kode"] == "UNIT-MURAH"
    assert res.produk_list[0]["harga"] == 7500000
    assert res.fakta["produk_termurah"]["kode"] == "UNIT-MURAH"
    assert "Laptop Beta" in res.fakta["pesan"]


def test_butir2_lebih_murah_urutan_menaik():
    """Menguji bahwa hasil lanjutan_hasil lebih_murah diurutkan menaik (termurah dulu)."""
    from services.action_engine import ActionEngine
    from services.schema_actions import ParserOutput, ActionEnum, ActionArguments, JenisEnum, StateUpdate

    engine = ActionEngine()
    state = {
        "kategori": "laptop",
        "produk_tampil": [
            {"kode": "BENCH-01", "nama": "Unit Pembanding", "harga": 20000000}
        ]
    }
    parsed = ParserOutput(
        aksi=ActionEnum.LANJUTAN_HASIL,
        argumen=ActionArguments(jenis=JenisEnum.LEBIH_MURAH),
        pembaruan_state=StateUpdate()
    )

    res = engine.execute(parsed, session_state=state)
    assert res.aksi == ActionEnum.LANJUTAN_HASIL
    assert res.fakta["status"] == "sukses"
    assert len(res.produk_list) > 1

    prices = [p["harga"] for p in res.produk_list]
    # Pastikan urutan menaik (ascending)
    assert prices == sorted(prices)
    for p_val in prices:
        assert p_val < 20000000


def test_butir4_teks_emergency_tanpa_di_kontak_staf():
    """Menguji bahwa teks darurat B13 tidak memuat 'di' + KONTAK_STAF dan memakai pola baku."""
    from services.grounding_checker import EMERGENCY_FALLBACK_TEXT as CHK_EMERGENCY
    from services.llm_generator import EMERGENCY_FALLBACK_TEXT as GEN_EMERGENCY
    from core.config import KONTAK_STAF

    for text in [CHK_EMERGENCY, GEN_EMERGENCY]:
        assert f"di {KONTAK_STAF}" not in text
        assert f"menghubungi {KONTAK_STAF}" in text
        assert text.endswith(f"atau Kakak bisa menghubungi {KONTAK_STAF}.")


def test_butir6_log_diagnostik_aksi_parser_dan_jenis():
    """Menguji bahwa log_turn menyimpan aksi_parser dan jenis ke record JSONL dan DB SQLite."""
    import json
    import os
    import sqlite3
    from core.chat_logger import log_turn, get_log_paths

    res = log_turn(
        session_id="synthetic_diag_sess_99",
        user_text="sintetis cari perlengkapan",
        bot_reply="sintetis jawaban bot",
        route="cari_produk",
        penguji="otomatis",
        jalur="model",
        aksi_parser="cari_produk",
        jenis="termurah_dari_tampil",
    )

    assert res["jalur"] == "model"
    assert res["aksi_parser"] == "cari_produk"
    assert res["jenis"] == "termurah_dari_tampil"

    # Periksa di berkas JSONL uji
    jsonl_path, db_path = get_log_paths(penguji="otomatis")
    assert os.path.exists(jsonl_path)
    with open(jsonl_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
        last_rec = json.loads(lines[-1])
        assert last_rec["log_id"] == res["log_id"]
        assert last_rec["aksi_parser"] == "cari_produk"
        assert last_rec["jenis"] == "termurah_dari_tampil"
        assert last_rec["jalur"] == "model"

    # Periksa di SQLite uji
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT jalur, aksi_parser, jenis FROM chat_logs WHERE log_id = ?", (res["log_id"],))
    row = cur.fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "model"
    assert row[1] == "cari_produk"
    assert row[2] == "termurah_dari_tampil"


