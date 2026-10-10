# -*- coding: utf-8 -*-
"""
tests/test_putaran11_synthetic.py
Pengujian unit sintetis untuk Putaran 11 (ReIn Komputer).
Semua pengujian menggunakan kalimat sintetis buatan sendiri, tanpa log/percakapan nyata.
"""
import pytest
from services.llm_generator import build_generator_messages, GeneratorOutput
from services.llm_parser import build_parser_messages
from services.grounding_checker import GroundingChecker


def test_butir1_generator_menerima_pesan_dan_konteks_lengkap():
    """Menguji bahwa generator menerima pesan giliran ini, riwayat 8 entri, produk_tampil tanpa kode, dan fakta pelanggan."""
    fakta = {"status": "sukses", "produk": [{"kode": "KB-L99", "nama": "Laptop Alpha Test", "harga": 8500000}]}
    state = {
        "persona": "Papa",
        "kebutuhan_teks": "browsing dan ketik dokumen",
        "merek": "lenovo",
        "budget": 9000000,
        "pending_question": "budget",
        "produk_tampil": [{"kode": "KB-L99", "nama": "Laptop Alpha Test", "harga": 8500000}]
    }
    history = [
        {"role": "user", "content": "Halo min"},
        {"role": "assistant", "content": "Halo Kak, ada yang bisa dibantu?"},
        {"role": "user", "content": "Cari laptop buat Papa"}
    ]
    user_msg = "Cari laptop buat Papa"

    messages = build_generator_messages(
        aksi="cari_produk",
        fakta=fakta,
        state=state,
        history=history,
        pesan_pelanggan=user_msg
    )

    prompt_content = messages[-1]["content"]
    assert user_msg in prompt_content
    # Pastikan kode internal KB-L99 tidak ada di produk_tampil yang diberikan ke generator
    assert "KB-L99" not in prompt_content
    assert "Laptop Alpha Test" in prompt_content
    assert "Papa" in prompt_content
    assert "browsing dan ketik dokumen" in prompt_content


def test_butir1_grounding_checker_mengakui_produk_tampil():
    """Menguji bahwa GroundingChecker menganggap produk_tampil sebagai sumber fakta yang sah."""
    checker = GroundingChecker()
    fakta = {"status": "sukses", "pesan": "Berikut unitnya"}
    state = {
        "produk_tampil": [
            {"kode": "KB-L01", "nama": "Laptop Mitra Belajar", "harga": 5199000, "spesifikasi": {"ram_gb": 8, "storage_ssd_gb": 256}}
        ]
    }
    # Teks menyebut harga 5.199.000 (atau 5,2 juta) yang ada di produk_tampil
    teks = "Laptop Mitra Belajar ini tersedia seharga Rp5.199.000 dengan RAM 8 GB, Kak."
    is_valid, violations = checker.check(teks, fakta, state=state)
    assert is_valid is True, f"Pelanggaran tidak terduga: {violations}"


def test_butir2_generator_prompt_dan_panjang_teks():
    """Menguji bahwa prompt generator baru ringkas (<=25 baris) dan teks hingga 550 karakter lolos pemeriksa."""
    from services.llm_generator import GENERATOR_SYSTEM_PROMPT
    lines = [line for line in GENERATOR_SYSTEM_PROMPT.strip().split("\n")]
    assert len(lines) <= 25, f"Prompt generator terlalu panjang: {len(lines)} baris"
    assert "ATURAN UTAMA (BATASAN RESPONS C)" not in GENERATOR_SYSTEM_PROMPT
    assert "420 karakter" not in GENERATOR_SYSTEM_PROMPT

    # Teks alami 460 karakter lolos (sebelumnya gagal di 420 karakter)
    checker = GroundingChecker()
    teks_panjang = "Halo Kak! " + ("Kami siap membantu mencarikan perangkat yang tepat untuk kebutuhan harian. " * 6)
    assert 420 < len(teks_panjang) <= 600
    is_valid, violations = checker.check(teks_panjang, {"status": "sapaan"})
    assert is_valid is True, f"Teks wajar 460 karakter harus lolos: {violations}"


def test_butir3_parser_prompt_dan_few_shots():
    """Menguji bahwa parser prompt memuat aturan intent/konteks dan 8 few-shots sintetis."""
    from services.llm_parser import SYSTEM_PARSER_PROMPT, SYNTHETIC_8_BOUNDARY_FEW_SHOTS

    # Cek poin-poin inti prompt parser
    assert "terima_kasih" in SYSTEM_PARSER_PROMPT
    assert "perbaiki_percakapan" in SYSTEM_PARSER_PROMPT
    assert "koreksi" in SYSTEM_PARSER_PROMPT
    assert "keluhan" in SYSTEM_PARSER_PROMPT
    assert "salah_paham" in SYSTEM_PARSER_PROMPT
    assert "evaluasi_kecocokan" in SYSTEM_PARSER_PROMPT
    assert "tanya_spesifikasi" in SYSTEM_PARSER_PROMPT
    assert "jawab_pertanyaan_bot" in SYSTEM_PARSER_PROMPT

    # Few-shots berjumlah tepat 8 pasang user-assistant (16 pesan)
    assert len(SYNTHETIC_8_BOUNDARY_FEW_SHOTS) == 16
    user_turns = [m for m in SYNTHETIC_8_BOUNDARY_FEW_SHOTS if m["role"] == "user"]
    assert len(user_turns) == 8


def test_butir4_kartu_produk_tanpa_kode_internal():
    """Menguji bahwa kartu produk tidak memuat kode internal seperti [KB-xxx] dan judul bersih dari P07."""
    from services.product_card import format_product_card, format_product_cards_message

    prod = {
        "kode": "KB-L05",
        "nama": "Ultrabook Prime 14",
        "harga": 11500000,
        "spesifikasi": "Core i5 | RAM 16GB | SSD 512GB",
        "match_report": {"lolos_semua": True}
    }

    card_text = format_product_card(prod, index=1)
    assert "KB-L05" not in card_text
    assert "[KB-" not in card_text
    assert "Ultrabook Prime 14" in card_text

    msg = format_product_cards_message([prod], judul_rekomendasi="P07 — Desain Grafis")
    assert "P07" not in msg
    assert "Desain Grafis" in msg
    assert "KB-L05" not in msg


def test_butir5_token_prompt_dan_gpu():
    """Menguji bahwa prompt parser dan generator tetap berada di bawah batas konteks 4096."""
    from services.llm_parser import build_parser_messages
    from services.llm_generator import build_generator_messages

    state = {
        "persona": "Dokter",
        "kebutuhan_teks": "olah data pasien",
        "merek": "lenovo",
        "budget": 10000000,
        "produk_tampil": [{"no": 1, "nama": "Laptop Bisnis 14", "harga": 9500000}]
    }
    # Perkiraan kasar rasio karakter ke token ~3-4 char per token
    p_msgs = build_parser_messages("Cari laptop lenovo 10 juta", state=state)
    total_p_chars = sum(len(m["content"]) for m in p_msgs)
    est_p_tokens = total_p_chars / 3.0
    assert est_p_tokens < 4096, f"Estimasi token parser terlalu besar: {est_p_tokens}"

    g_msgs = build_generator_messages("cari_produk", {"status": "sukses"}, state=state, pesan_pelanggan="Cari laptop")
    total_g_chars = sum(len(m["content"]) for m in g_msgs)
    est_g_tokens = total_g_chars / 3.0
    assert est_g_tokens < 4096, f"Estimasi token generator terlalu besar: {est_g_tokens}"


def test_butir6_budget_tidak_tertimpa_pada_lanjutan_hasil():
    """Butir 6: action_engine _handle_lanjutan_hasil tidak menimpa state['budget'] pada lebih_murah."""
    from services.action_engine import ActionEngine
    from services.schema_actions import ParserOutput, ActionEnum, ActionArguments, JenisEnum, StateUpdate

    engine = ActionEngine()
    initial_budget = 15000000
    state = {
        "kategori": "laptop",
        "budget": initial_budget,
        "produk_tampil": [
            {"kode": "KB-L03", "nama": "Laptop Menengah", "harga": 12000000}
        ]
    }

    parsed = ParserOutput(
        aksi=ActionEnum.LANJUTAN_HASIL,
        argumen=ActionArguments(jenis=JenisEnum.LEBIH_MURAH),
        pembaruan_state=StateUpdate()
    )

    res = engine.execute(parsed, session_state=state)
    assert res.aksi == ActionEnum.LANJUTAN_HASIL
    # Budget pelanggan di state HARUS tetap 15000000, tidak tertimpa harga produk
    assert state.get("budget") == initial_budget


def test_butir7_aturan_sapaan_tengah_percakapan():
    """Butir 7: Sapaan di tengah percakapan tanpa 'Selamat datang' dan tanpa salam ulang."""
    from services.session_pipeline import match_rule_greeting

    hist = [{"role": "user", "content": "Halo min"}, {"role": "assistant", "content": "Halo Kak!"}]
    match = match_rule_greeting("selamat siang kak", history=hist)
    assert match is not None
    r_aksi, r_reply, r_status = match
    assert r_aksi == "sapa"
    assert "Selamat datang" not in r_reply
    assert "selamat siang" not in r_reply.lower()
    assert "Iya, Kak!" in r_reply

    # Awal percakapan (tanpa history) tetap memuat Selamat datang
    match_awal = match_rule_greeting("selamat siang kak", history=[])
    assert match_awal is not None
    assert "Selamat datang di ReIn Komputer" in match_awal[1]






