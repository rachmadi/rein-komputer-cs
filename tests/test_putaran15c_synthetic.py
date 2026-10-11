# -*- coding: utf-8 -*-
"""
tests/test_putaran15c_synthetic.py
Pengujian sintetis untuk Putaran 15c ReIn Komputer.
- Butir 3: Perbaikan regresi "speknya kosong" (tanya_spesifikasi menghasilkan lembar lengkap, bukan atribut_tidak_tersedia).
- Butir 4: Perbaikan resolusi referensi posisional ("3 pilihan tadi") dan nama pendek substring ("Nitro").
"""
import pytest
from services.action_engine import ActionEngine, is_general_spec_query
from services.schema_actions import ParserOutput, ActionEnum, ActionArguments, StateUpdate


def test_butir3_is_general_spec_query_detection():
    """Memastikan deteksi permintaan spesifikasi umum/komplain spek kosong bekerja secara data-driven."""
    # Frasa umum & komplain spek kosong harus True
    assert is_general_spec_query(None) is True
    assert is_general_spec_query("") is True
    assert is_general_spec_query("kosong") is True
    assert is_general_spec_query("speknya kosong") is True
    assert is_general_spec_query("spesifikasi lengkap") is True
    assert is_general_spec_query("spek lengkap") is True
    assert is_general_spec_query("mana speknya") is True
    assert is_general_spec_query("detail") is True
    assert is_general_spec_query("spesifikasi") is True

    # Atribut teknis spesifik harus False
    assert is_general_spec_query("ram") is False
    assert is_general_spec_query("gpu") is False
    assert is_general_spec_query("cpu") is False
    assert is_general_spec_query("layar") is False
    assert is_general_spec_query("cetak foto") is False
    assert is_general_spec_query("tabung tinta") is False
    assert is_general_spec_query("kamera") is False


def test_butir3_tanya_spesifikasi_spek_kosong_sukses_lembar_lengkap():
    """
    Butir 3:
    Ketika pelanggan menanyakan 'speknya kosong' atau 'spesifikasi lengkap',
    ActionEngine harus mengembalikan status 'sukses' dengan tipe_jawaban 'ringkasan_spesifikasi'
    dan lembar_spesifikasi terisi penuh, bukan 'atribut_tidak_tersedia'.
    """
    engine = ActionEngine(db_path="data/test_catalog.db")
    state = {
        "produk_tampil": [{"kode": "KB-L09", "nama": "ASUS TUF Gaming A15", "harga": 16999000}],
        "produk_terakhir_dibahas": "KB-L09",
        "produk_dibahas": ["KB-L09"]
    }

    # 1. Atribut 'kosong'
    p_kosong = ParserOutput(
        aksi=ActionEnum.TANYA_SPESIFIKASI,
        argumen=ActionArguments(produk=["KB-L09"], atribut="kosong")
    )
    res_kosong = engine.execute(p_kosong, session_state=state)
    assert res_kosong.fakta["status"] == "sukses"
    assert res_kosong.fakta.get("tipe_jawaban") == "ringkasan_spesifikasi"
    assert "lembar_spesifikasi" in res_kosong.fakta
    lembar = res_kosong.fakta["lembar_spesifikasi"]
    assert "prosesor" in lembar or "cpu" in lembar
    assert "ram" in lembar

    # 2. Atribut 'spesifikasi lengkap'
    p_lengkap = ParserOutput(
        aksi=ActionEnum.TANYA_SPESIFIKASI,
        argumen=ActionArguments(produk=["KB-L09"], atribut="spesifikasi lengkap")
    )
    res_lengkap = engine.execute(p_lengkap, session_state=state)
    assert res_lengkap.fakta["status"] == "sukses"
    assert res_lengkap.fakta.get("tipe_jawaban") == "ringkasan_spesifikasi"
    assert "lembar_spesifikasi" in res_lengkap.fakta

    # 3. Atribut non-eksisten pada printer tetap 'atribut_tidak_tersedia' (tidak ada regresi)
    p_kamera = ParserOutput(
        aksi=ActionEnum.TANYA_SPESIFIKASI,
        argumen=ActionArguments(produk=["KB-P10"], atribut="kamera")
    )
    res_kamera = engine.execute(p_kamera, session_state={})
    assert res_kamera.fakta["status"] == "atribut_tidak_tersedia"
