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
