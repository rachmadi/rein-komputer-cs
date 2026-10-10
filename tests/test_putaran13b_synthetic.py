# -*- coding: utf-8 -*-
"""
tests/test_putaran13b_synthetic.py
Rangkaian tes sintetis murni untuk Putaran 13b ReIn Komputer:
- Butir 1: Pencegahan kebocoran teks internal ((got ...), >=, <=, cpu_tier, ram_gb, dll).
- Butir 2: Budget sebagai filter keras (tidak ada produk > budget di produk_tampil / balasan).
"""
import pytest
from services.session_pipeline import SessionPipeline
from services.action_engine import ActionEngine
from services.schema_actions import ParserOutput, ActionEnum, ActionArguments, StateUpdate
from services.catalog_search import format_natural_unmet_list, format_natural_unmet_requirements
from services.llm_generator import build_deterministic_fallback_text
from services.grounding_checker import GroundingChecker


LEAK_PATTERNS = ["(got ", ">=", "<=", "cpu_tier", "ram_gb", "storage_ssd_gb", "vram_gb", "gpu_dedicated"]


def test_butir1_format_natural_unmet_list():
    """Butir 1: Memastikan format_natural_unmet_list mengubah syarat mentah menjadi bahasa alami tanpa pola internal."""
    raw_unmet = [
        "ram_gb >= 16 (got 8)",
        "storage_ssd_gb >= 1000 (got 512)",
        "cpu_tier >= 3 (got 1)",
        "gpu_dedicated = 1 (got 0)",
        "vram_gb >= 8 (got 0)",
        "ram_gb (tidak tersedia)"
    ]
    res_list = format_natural_unmet_list(raw_unmet)
    res_text = ", ".join(res_list)

    for pat in LEAK_PATTERNS:
        assert pat not in res_text, f"Pola bocor '{pat}' ditemukan di hasil: {res_text}"

    assert any("RAM 8 GB" in r for r in res_list)
    assert any("SSD 512 GB" in r for r in res_list)
    assert any("prosesor tingkat 1" in r for r in res_list)
    assert any("GPU dedicated" in r for r in res_list)
    assert any("VRAM" in r and "8 GB" in r for r in res_list)


def test_butir1_deterministic_fallback_tanpa_kebocoran():
    """Butir 1: Memastikan build_deterministic_fallback_text untuk status belum_ada_yang_memenuhi bebas dari teks internal."""
    fakta = {
        "status": "belum_ada_yang_memenuhi",
        "produk_terdekat": {
            "nama": "Acer Aspire Lite 14",
            "kekurangan": [
                "ram_gb >= 16 (got 8)",
                "storage_ssd_gb >= 1000 (got 512)",
                "cpu_tier >= 3 (got 1)"
            ]
        }
    }
    teks = build_deterministic_fallback_text("minta_rekomendasi", fakta)
    for pat in LEAK_PATTERNS:
        assert pat not in teks, f"Pola bocor '{pat}' ditemukan di fallback text: {teks}"


def test_butir1_jaring_pengaman_output_filter():
    """Butir 1: Memastikan jaring pengaman session_pipeline mengganti teks bocor dengan respons bersih dan mencatat pelanggaran."""
    pipe = SessionPipeline()
    state = {
        "kategori": "laptop",
        "budget": 15000000,
        "kebutuhan_teks": "bikin model bisnis pakai AI lokal"
    }
    # Simulasi giliran di mana pengguna menanyakan laptop AI lokal dengan batas budget 15 juta
    res, state_after = pipe.process_turn("Tadi kamu nawarin pilihan AI lokal, budget saya 15 juta", state)
    teks_balasan = res.teks_jawaban

    for pat in LEAK_PATTERNS:
        assert pat not in teks_balasan, f"Pola bocor '{pat}' ditemukan di balasan: {teks_balasan}"


def test_butir1_skenario_budget_15jt_ai_lokal_bebas_pola():
    """Butir 1: Tes spesifik skenario 'budget 15 juta, minta laptop AI lokal' tidak boleh memuat pola internal."""
    pipe = SessionPipeline()
    state = {
        "kategori": "laptop",
        "kebutuhan_teks": "bikin model bisnis pakai AI lokal"
    }
    res, state_after = pipe.process_turn("Budget saya maksimal 15 juta untuk laptop AI lokal", state)
    teks_balasan = res.teks_jawaban

    for pat in LEAK_PATTERNS:
        assert pat not in teks_balasan, f"Pola internal '{pat}' bocor ke pelanggan: {teks_balasan}"


def test_butir2_action_engine_minta_rekomendasi_budget_15jt():
    """Butir 2: ActionEngine dengan budget 15 juta harus mengembalikan produk terdekat dalam budget (<= 15 jt)."""
    engine = ActionEngine()
    state = {
        "kategori": "laptop",
        "budget": 15000000,
        "kebutuhan_teks": "bikin model bisnis pakai AI lokal"
    }
    args = ActionArguments(
        kategori="laptop",
        max_harga=15000000,
        kebutuhan_teks="bikin model bisnis pakai AI lokal"
    )
    res = engine._handle_minta_rekomendasi(args, state)
    assert res.fakta["status"] == "belum_ada_yang_memenuhi"
    assert len(res.produk_list) > 0, "Harus mengembalikan produk terdekat dalam budget"
    for p in res.produk_list:
        assert p.get("harga") <= 15000000, f"Produk {p.get('nama')} melebihi batas budget: {p.get('harga')}"
        assert p["catatan_minimum"]["memenuhi"] is False, "Harus mencatat jujur bahwa spesifikasi belum memenuhi"


def test_butir2_session_pipeline_budget_15jt_tidak_menampilkan_di_atas_15jt():
    """Butir 2: Begitu pelanggan menyebut budget 15 juta, tidak ada produk > 15 juta di produk_tampil, kartu, maupun balasan."""
    pipe = SessionPipeline()
    # State awal memuat produk mahal (> 15 juta) dari giliran sebelumnya
    state = {
        "kategori": "laptop",
        "kebutuhan_teks": "bikin model bisnis pakai AI lokal",
        "produk_tampil": [
            {"kode": "KB-L09", "nama": "ASUS TUF Gaming A15", "harga": 16999000, "kategori": "laptop"},
            {"kode": "KB-L10", "nama": "Lenovo Legion Pro 5 16", "harga": 23999000, "kategori": "laptop"}
        ]
    }
    res, state_after = pipe.process_turn("Tapi dananya cuma maksimal 15 juta", state)

    # 1. Pastikan produk_tampil setelah giliran ini tidak memuat produk di atas 15 juta
    prods_tampil = state_after.get("produk_tampil", [])
    for p in prods_tampil:
        p_price = p.get("harga") if isinstance(p, dict) else 0
        assert p_price <= 15000000, f"Produk {p.get('nama')} dengan harga {p_price} ada di produk_tampil"

    # 2. Pastikan kartu_isi tidak memuat produk di atas 15 juta
    if res.kartu_isi:
        for card_item in res.kartu_isi:
            c_price = card_item.get("harga") or 0
            assert c_price <= 15000000, f"Kartu memuat produk {card_item.get('nama')} dengan harga {c_price}"

    # 3. Pastikan balasan tidak menyebut nominal harga di atas 15 juta sebagai pilihan
    prices_in_reply = GroundingChecker.extract_prices_from_text(res.teks_jawaban)
    for pr in prices_in_reply:
        assert pr <= 15000000, f"Balasan menyebut harga Rp{pr:,} yang di atas budget 15 juta: {res.teks_jawaban}"


def test_butir2_budget_rendah_tidak_ada_dalam_anggaran():
    """Butir 2: Jika budget benar-benar tidak ada yang memenuhi di katalog, kembalikan tidak_ada_dalam_anggaran."""
    engine = ActionEngine()
    state = {
        "kategori": "laptop",
        "budget": 2000000,
        "kebutuhan_teks": "bikin model bisnis pakai AI lokal"
    }
    args = ActionArguments(
        kategori="laptop",
        max_harga=2000000,
        kebutuhan_teks="bikin model bisnis pakai AI lokal"
    )
    res = engine._handle_minta_rekomendasi(args, state)
    assert res.fakta["status"] == "tidak_ada_dalam_anggaran"
    assert len(res.produk_list) == 0
    assert res.fakta["harga_termurah_kategori"] > 2000000
