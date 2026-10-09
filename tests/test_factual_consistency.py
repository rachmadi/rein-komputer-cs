# -*- coding: utf-8 -*-
"""
tests/test_factual_consistency.py
Uji pemeriksa konsistensi fakta (Poin 7):
- total_ditemukan = 0 atau status tidak_ditemukan tidak boleh disertai klaim produk tersedia.
- Kartu produk harus cocok dengan produk yang disebut di teks (tidak halusinasi model lain).
- Jika aksi cari_produk dengan merek_kecuali, tidak boleh ada produk merek itu baik di fakta maupun teks.
"""
import pytest
from services.grounding_checker import GroundingChecker


def test_fact_consistency_zero_results_forbids_availability_claim():
    checker = GroundingChecker()
    fakta = {
        "status": "tidak_ditemukan",
        "total_ditemukan": 0,
        "produk": []
    }

    # 1. Teks klaim palsu produk tersedia
    false_claim_text = "Kami ada beberapa pilihan unit laptop yang cocok untuk Kakak."
    is_ok, viols = checker.check(false_claim_text, fakta=fakta)
    assert is_ok is False
    assert any("total_ditemukan = 0" in v for v in viols)

    # 2. Teks jujur mengakui tidak ada produk
    honest_text = "Maaf Kak, saat ini belum ada unit laptop yang sesuai dengan kriteria tersebut."
    is_ok2, viols2 = checker.check(honest_text, fakta=fakta)
    assert is_ok2 is True
    assert len(viols2) == 0


def test_fact_consistency_cards_must_match_text_models():
    checker = GroundingChecker()
    fakta = {
        "status": "sukses",
        "total_ditemukan": 2,
        "produk": [
            {"nama": "ASUS Vivobook 14 A1405", "brand": "asus"},
            {"nama": "Lenovo IdeaPad Slim 3", "brand": "lenovo"}
        ]
    }

    # 1. Teks menyebut model yang tidak ada di kartu (MacBook)
    hallucinated_text = "Kakak bisa mempertimbangkan MacBook atau ASUS Vivobook untuk kebutuhan tersebut."
    is_ok, viols = checker.check(hallucinated_text, fakta=fakta)
    assert is_ok is False
    assert any("macbook" in v.lower() for v in viols)

    # 2. Teks menyebut model yang sesuai dengan kartu (Vivobook)
    valid_text = "Untuk kebutuhan tersebut, ASUS Vivobook 14 bisa menjadi pilihan yang tepat."
    is_ok2, viols2 = checker.check(valid_text, fakta=fakta)
    assert is_ok2 is True
    assert len(viols2) == 0


def test_fact_consistency_merek_kecuali_enforced():
    checker = GroundingChecker()

    # Kasus A: Fakta produk melanggar (memuat Asus padahal merek_kecuali=asus)
    fakta_viol = {
        "status": "sukses",
        "merek_kecuali": "asus",
        "total_ditemukan": 1,
        "produk": [
            {"nama": "ASUS Vivobook 14", "brand": "asus"}
        ]
    }
    is_ok_a, viols_a = checker.check("Berikut rekomendasi laptop untuk Kakak.", fakta=fakta_viol)
    assert is_ok_a is False
    assert any("memuat merek 'asus'" in v for v in viols_a)

    # Kasus B: Teks merekomendasikan merek yang dikecualikan
    fakta_clean = {
        "status": "sukses",
        "merek_kecuali": "asus",
        "total_ditemukan": 1,
        "produk": [
            {"nama": "Lenovo IdeaPad Slim 3", "brand": "lenovo", "harga": 7299000}
        ]
    }
    text_viol = "Selain Lenovo, kami ada opsi laptop Asus Vivobook yang bagus."
    is_ok_b, viols_b = checker.check(text_viol, fakta=fakta_clean)
    assert is_ok_b is False
    assert any("merekomendasikan merek 'asus'" in v for v in viols_b)

    # Kasus C: Teks dan fakta bersih dari merek yang dikecualikan
    text_clean = "Untuk merek selain Asus, Lenovo IdeaPad Slim 3 seharga Rp7.299.000 bisa jadi pertimbangan."
    is_ok_c, viols_c = checker.check(text_clean, fakta=fakta_clean)
    assert is_ok_c is True
    assert len(viols_c) == 0


def test_fact_consistency_evaluasi_kecocokan_structured_penilaian():
    """Poin 10: Pemeriksa memverifikasi secara deterministik kesesuaian penilaian terstruktur dengan tanda selisih."""
    checker = GroundingChecker()

    fakta_eval = {
        "status": "sukses",
        "evaluasi_produk": [
            {
                "kode": "KB-L01",
                "nama": "Acer Aspire Lite 14",
                "status_kecocokan": "di_bawah_minimum",
                "selisih_terhadap_minimum": {"cpu_tier": -1, "ram_gb": -8, "ssd_gb": 0, "gpu_vram_gb": 0},
                "selisih_terhadap_rekomendasi": {"cpu_tier": -2, "ram_gb": -8, "ssd_gb": 0, "gpu_vram_gb": 0}
            },
            {
                "kode": "KB-L06",
                "nama": "Acer Nitro V 15",
                "status_kecocokan": "memenuhi_minimum",
                "selisih_terhadap_minimum": {"cpu_tier": 0, "ram_gb": 0, "ssd_gb": 0, "gpu_vram_gb": 4},
                "selisih_terhadap_rekomendasi": {"cpu_tier": -1, "ram_gb": 0, "ssd_gb": 0, "gpu_vram_gb": 4}
            },
            {
                "kode": "KB-L09",
                "nama": "ASUS TUF Gaming A15",
                "status_kecocokan": "memenuhi_rekomendasi",
                "selisih_terhadap_minimum": {"cpu_tier": 1, "ram_gb": 0, "ssd_gb": 488, "gpu_vram_gb": 8},
                "selisih_terhadap_rekomendasi": {"cpu_tier": 0, "ram_gb": 0, "ssd_gb": 488, "gpu_vram_gb": 8}
            }
        ]
    }

    # 1. Penilaian konsisten (semua cocok dengan tanda selisih)
    penilaian_valid = {
        "KB-L01": "di_bawah_minimum",
        "KB-L06": "memenuhi_minimum",
        "KB-L09": "memenuhi_rekomendasi"
    }
    is_ok, viols = checker.check("Berikut evaluasi spesifikasi laptop untuk kebutuhan Kakak.", fakta=fakta_eval, penilaian=penilaian_valid)
    assert is_ok is True
    assert len(viols) == 0

    # 2. Penilaian inkonsisten: KB-L01 (selisih negatif) diklaim memenuhi_rekomendasi
    penilaian_invalid = {
        "KB-L01": "memenuhi_rekomendasi",
        "KB-L06": "memenuhi_minimum",
        "KB-L09": "memenuhi_rekomendasi"
    }
    is_ok2, viols2 = checker.check("Berikut evaluasi spesifikasi laptop untuk kebutuhan Kakak.", fakta=fakta_eval, penilaian=penilaian_invalid)
    assert is_ok2 is False
    assert any("KB-L01" in v and "bertentangan dengan tanda selisih" in v for v in viols2)


def test_fact_consistency_string_budget_handling():
    checker = GroundingChecker()
    fakta = {"status": "sukses", "produk": []}
    prices = checker.extract_prices_from_facts(fakta, state={"budget": "lebih mahal"})
    assert isinstance(prices, set)
    prices2 = checker.extract_prices_from_facts(fakta, state={"budget": "10 juta"})
    assert 10_000_000 in prices2

