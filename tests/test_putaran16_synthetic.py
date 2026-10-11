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
