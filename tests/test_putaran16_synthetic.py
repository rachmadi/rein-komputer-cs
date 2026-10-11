# -*- coding: utf-8 -*-
"""
tests/test_putaran16_synthetic.py
Pengujian Putaran 16 — Kontrak Umum & Berbasis Properti dari Katalog.
"""
import pytest
from core.db import get_catalog_inventory, format_daftar_kategori, extract_kategori_from_products
from services.action_engine import ActionEngine
from services.schema_actions import ParserOutput, ActionArguments, ActionEnum
from services.llm_generator import build_deterministic_fallback_text

def test_butir1_properti_kategori_fallback():
    """Butir 1c Putaran 16: Untuk SETIAP kategori di katalog,
    cari_produk kategori itu -> teks fallback deterministik menyebut kategori itu dan tidak menyebut kategori lain.
    """
    engine = ActionEngine()
    inventory = get_catalog_inventory()
    categories = inventory["kategori"]
    assert len(categories) >= 3, "Katalog harus memiliki minimal 3 kategori"

    for cat in categories:
        raw_p = ParserOutput(
            aksi=ActionEnum.CARI_PRODUK,
            argumen=ActionArguments(kategori=cat)
        )
        res = engine.execute(raw_p)
        assert res.fakta.get("status") == "sukses", f"Pencarian kategori {cat} harus sukses"
        assert res.fakta.get("produk"), f"Harus ada produk untuk kategori {cat}"

        # Butir 1a: Setiap fakta yang membawa produk wajib punya "kategori" level atas dari produk aktual
        assert "kategori" in res.fakta, f"Fakta harus punya key 'kategori' level atas untuk kategori {cat}"
        assert res.fakta["kategori"] == cat, f"Fakta kategori harus '{cat}', bukan '{res.fakta.get('kategori')}'"

        # Butir 1c: Teks fallback deterministik menyebut kategori itu dan tidak menyebut kategori lain
        fallback_text = build_deterministic_fallback_text(res.aksi, res.fakta)
        assert cat in fallback_text.lower(), f"Fallback text harus menyebut '{cat}': {fallback_text}"

        other_cats = [c for c in categories if c != cat]
        for other in other_cats:
            assert other not in fallback_text.lower(), (
                f"Fallback text untuk {cat} tidak boleh menyebut {other}: {fallback_text}"
            )

def test_butir1_produk_campuran_kategori():
    """Butir 1a Putaran 16: Jika produk campuran kategori, sebut sesuai isinya."""
    prods_mixed = [
        {"kode": "KB-L01", "nama": "Laptop Alpha", "kategori": "laptop"},
        {"kode": "KB-M01", "nama": "Monitor Beta", "kategori": "monitor"}
    ]
    kat_mixed = extract_kategori_from_products(prods_mixed)
    assert kat_mixed == "laptop dan monitor"

    prods_3_mixed = [
        {"kode": "KB-D01", "nama": "Desktop A", "kategori": "desktop"},
        {"kode": "KB-L01", "nama": "Laptop B", "kategori": "laptop"},
        {"kode": "KB-P01", "nama": "Printer C", "kategori": "printer"}
    ]
    kat_3_mixed = extract_kategori_from_products(prods_3_mixed)
    assert kat_3_mixed == "desktop, laptop, dan printer"

def test_butir1_sapaan_tanpa_hardcode():
    """Butir 1b Putaran 16: Teks sapaan deterministik menggunakan kategori dari get_catalog_inventory()."""
    from services.session_pipeline import match_rule_greeting
    sapaan_res = match_rule_greeting("Halo", history=[])
    assert sapaan_res is not None
    reply = sapaan_res[1]
    assert "laptop atau komputer" not in reply.lower()
    assert "komputer atau laptop" not in reply.lower()
    # Harus memuat kategori dari inventaris
    for cat in get_catalog_inventory()["kategori"]:
        assert cat in reply.lower()


# =========================================================================
# BUTIR 2 — Dilarang Mengatribusikan Kebutuhan Yang Tidak Dinyatakan
# =========================================================================

def test_butir2_fakta_tanpa_kebutuhan_teks_klaim_peruntukan_ditolak():
    """Butir 2c Putaran 16: Fakta tanpa kebutuhan_teks + teks yang menyebut peruntukan -> ditandai pelanggaran."""
    from services.grounding_checker import GroundingChecker

    checker = GroundingChecker()
    fakta = {
        "status": "sukses",
        "produk": [{"nama": "Acer Swift Go 14", "harga": 14000000, "kategori": "laptop"}]
    }
    state = {
        "kategori": "laptop",
        "kebutuhan_teks": "",  # kosong!
        "_pesan_pelanggan": "Aku tanya laptop",
        "produk_tampil": [{"nama": "Acer Swift Go 14", "harga": 14000000, "kategori": "laptop"}]
    }

    # Kasus 1: Klaim kebutuhan eksplisit
    teks_klaim_1 = "Berdasarkan kebutuhan Anda untuk kerja kantor dan kuliah, kami sarankan unit ini."
    is_valid, violations = checker.check(teks_klaim_1, fakta, state)
    assert not is_valid, f"Harus ditolak: {violations}"
    assert any("kebutuhan" in v.lower() or "peruntukan" in v.lower() for v in violations)

    # Kasus 2: Klaim peruntukan / penggunaan spesifik
    teks_klaim_2 = "Unit ini sangat pas untuk penggunaan harian dan office."
    is_valid, violations = checker.check(teks_klaim_2, fakta, state)
    assert not is_valid, f"Harus ditolak: {violations}"
    assert any("peruntukan" in v.lower() for v in violations)

    # Kasus 3: Klaim kriteria minimum yang dicari
    teks_klaim_3 = "Berikut kriteria minimum yang Anda cari (RAM 16GB, SSD 512GB) di katalog kami."
    is_valid, violations = checker.check(teks_klaim_3, fakta, state)
    assert not is_valid, f"Harus ditolak: {violations}"
    assert any("kriteria" in v.lower() for v in violations)


def test_butir2_fakta_tanpa_kebutuhan_teks_teks_netral_lolos():
    """Butir 2c Putaran 16: Fakta tanpa kebutuhan_teks + teks netral -> lolos."""
    from services.grounding_checker import GroundingChecker

    checker = GroundingChecker()
    fakta = {
        "status": "sukses",
        "produk": [{"nama": "LG 24MP400-B", "harga": 1250000, "kategori": "monitor"}]
    }
    state = {
        "kategori": "monitor",
        "kebutuhan_teks": "",
        "_pesan_pelanggan": "Jual monitor?",
        "produk_tampil": [{"nama": "LG 24MP400-B", "harga": 1250000, "kategori": "monitor"}]
    }

    # Teks rekomendasi objektif netral
    teks_netral = "Berikut rekomendasi monitor di katalog kami: LG 24MP400-B seharga Rp1.250.000. Apakah ada model yang ingin Kakak ketahui lebih detail?"
    is_valid, violations = checker.check(teks_netral, fakta, state)
    assert is_valid, f"Teks netral harus lolos, tapi dapat violations: {violations}"

    # Teks spesifikasi netral
    teks_spek = "Monitor LG 24MP400-B memiliki bentang layar 23.8 inci IPS dengan resolusi Full HD."
    is_valid, violations = checker.check(teks_spek, fakta, state)
    assert is_valid, f"Teks spesifikasi netral harus lolos: {violations}"

    # Teks bertanya kebutuhan balik (bukan mengklaim)
    teks_tanya = "Ada yang bisa kami bantu carikan hari ini? Boleh diceritakan kebutuhan perangkat yang sedang dicari?"
    is_valid, violations = checker.check(teks_tanya, fakta, state)
    assert is_valid, f"Teks bertanya kebutuhan harus lolos: {violations}"


def test_butir2_kebutuhan_ada_peruntukan_sesuai_vs_tidak_sesuai():
    """Butir 2a Putaran 16: Jika kebutuhan_teks ada, peruntukan yang disebut harus sesuai isinya."""
    from services.grounding_checker import GroundingChecker

    checker = GroundingChecker()
    fakta = {
        "status": "sukses",
        "kebutuhan_teks": "desain grafis",
        "produk": [{"nama": "Creator 15", "harga": 15000000, "kategori": "laptop"}]
    }
    state = {
        "kategori": "laptop",
        "kebutuhan_teks": "desain grafis",
        "_pesan_pelanggan": "butuh buat desain grafis",
        "produk_tampil": [{"nama": "Creator 15", "harga": 15000000, "kategori": "laptop"}]
    }

    # Sesuai kebutuhan_teks -> lolos
    teks_cocok = "Laptop ini cocok untuk aktivitas desain grafis Kakak dengan layar warna akurat."
    is_valid, violations = checker.check(teks_cocok, fakta, state)
    assert is_valid, f"Peruntukan yang sesuai harus lolos: {violations}"

    # Tidak sesuai kebutuhan_teks -> ditolak
    teks_beda = "Laptop ini sangat cocok untuk aktivitas gaming berat Kakak."
    is_valid, violations = checker.check(teks_beda, fakta, state)
    assert not is_valid, f"Peruntukan yang bertentangan harus ditolak: {violations}"
    assert any("gaming" in v.lower() for v in violations)

