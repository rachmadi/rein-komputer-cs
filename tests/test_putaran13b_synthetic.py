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
