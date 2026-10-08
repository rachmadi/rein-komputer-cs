# -*- coding: utf-8 -*-
"""
tests/test_evaluasi_kecocokan_numbers.py
Uji evaluasi kecocokan mengembalikan fakta angka murni dan selisih (Poin 6):
- Tidak ada kata vonis ("mumpuni", "cocok", "kesimpulan") buatan kode di fakta mesin.
- Memuat angka aktual, standar profil (minimum & rekomendasi), dan selisihnya.
- GroundingChecker memastikan angka spesifikasi yang disebut di teks ada di fakta.
"""
import pytest
from services.schema_actions import ParserOutput, ActionEnum, ActionArguments
from services.action_engine import ActionEngine
from services.grounding_checker import GroundingChecker


def test_evaluasi_kecocokan_returns_pure_numbers_no_verdict():
    engine = ActionEngine()
    # Dummy produk tampil di state
    state = {
        "profil_aktif": "P01",
        "produk_tampil": [
            {"kode": "KB-L01", "nama": "Acer Aspire Lite 14", "harga": 5199000}
        ]
    }
    parsed = ParserOutput(
        aksi=ActionEnum.EVALUASI_KECOCOKAN,
        argumen=ActionArguments(rujukan_produk=[1], produk=["KB-L01"])
    )
    res = engine.execute(parsed, session_state=state)
    assert res.fakta["status"] == "sukses"
    evals = res.fakta.get("evaluasi_produk", [])
    assert len(evals) == 1

    ep = evals[0]
    # 1. Pastikan struktur angka dan selisih ada
    assert "angka_aktual" in ep
    assert "standar_profil" in ep
    assert "selisih_terhadap_minimum" in ep
    assert "selisih_terhadap_rekomendasi" in ep

    # Angka aktual harus berupa angka
    angka = ep["angka_aktual"]
    assert isinstance(angka["cpu_tier"], int)
    assert isinstance(angka["ram_gb"], int)
    assert isinstance(angka["ssd_gb"], int)
    assert isinstance(angka["gpu_vram_gb"], int)

    # 2. Tidak boleh ada kata vonis buatan kode
    assert "kesimpulan" not in ep
    assert "lolos" not in ep
    ep_str = str(ep).lower()
    assert "mumpuni" not in ep_str
    assert "cocok dan mumpuni" not in ep_str


def test_grounding_checker_validates_spec_numbers():
    checker = GroundingChecker()
    fakta = {
        "evaluasi_produk": [
            {
                "kode": "KB-L01",
                "angka_aktual": {"cpu_tier": 1, "ram_gb": 8, "ssd_gb": 512, "gpu_vram_gb": 0},
                "standar_profil": {
                    "minimum": {"cpu_tier": 1, "ram_gb": 8, "ssd_gb": 256, "gpu_vram_gb": 0},
                    "rekomendasi": {"cpu_tier": 2, "ram_gb": 16, "ssd_gb": 512, "gpu_vram_gb": 0}
                },
                "selisih_terhadap_minimum": {"cpu_tier": 0, "ram_gb": 0, "ssd_gb": 256, "gpu_vram_gb": 0},
                "selisih_terhadap_rekomendasi": {"cpu_tier": -1, "ram_gb": -8, "ssd_gb": 0, "gpu_vram_gb": 0}
            }
        ]
    }

    # 1. Teks dengan angka sah (RAM 8 GB, SSD 512 GB)
    text_valid = "Laptop ini memiliki RAM 8 GB dan SSD 512 GB yang memenuhi batas minimum."
    is_ok1, viol1 = checker.check(text_valid, fakta=fakta)
    assert is_ok1 is True
    assert len(viol1) == 0

    # 2. Teks dengan angka halusinasi (RAM 32 GB)
    text_invalid = "Laptop ini dilengkapi RAM 32 GB dan SSD 512 GB."
    is_ok2, viol2 = checker.check(text_invalid, fakta=fakta)
    assert is_ok2 is False
    assert any("32" in v for v in viol2)
