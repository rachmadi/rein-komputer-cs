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
