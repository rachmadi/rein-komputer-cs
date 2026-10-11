# -*- coding: utf-8 -*-
"""
Property-based and Unit Tests for ReIn Komputer Agent Tools (Putaran 18 Butir 2).
Memverifikasi:
- Pencarian kata kunci khas untuk setiap produk mengembalikan produk tersebut.
- budget_max adalah filter keras (tidak pernah ada produk di atas budget_max).
- Kategori dan merek terfilter secara tepat dan dinamis.
- detail_produk mengembalikan lembar spesifikasi lengkap dan raw_data.
- Istilah karakteristik (ecotank, printer struk, tangki tinta) berhasil ditemukan.
- pengetahuan_kebutuhan dan info_toko mengembalikan data otoritatif dari KB.
"""
import pytest
from core.db import get_catalog_inventory
from services.catalog_service import get_active_catalog
from services.agent_tools import (
    cari_produk,
    detail_produk,
    pengetahuan_kebutuhan,
    info_toko,
    execute_agent_tool,
)


@pytest.fixture
def catalog():
    return get_active_catalog()


def test_property_distinct_word_retrieves_product(catalog):
    """Properti: untuk setiap produk di katalog, satu kata khas dari namanya mengembalikan produk itu."""
    all_products = list(catalog.by_code.values())
    assert len(all_products) >= 40

    brands = {"lenovo", "asus", "acer", "hp", "msi", "brother", "epson", "canon", "apple", "samsung", "lg", "dell"}
    stop_words = brands | {
        "intel", "amd", "core", "ryzen", "gen", "pro", "plus", "dan", "untuk", "with",
        "inch", "inci", "series", "the", "all", "in", "one", "mini", "tower", "pc",
        "laptop", "desktop", "printer", "monitor"
    }

    for p in all_products:
        nama = p["nama"]
        words = [w for w in nama.split() if len(w) >= 3 and w.lower() not in stop_words]
        distinct_word = words[0] if words else nama.split()[0]

        res = cari_produk(kata_kunci=distinct_word, catalog=catalog)
        assert res["status"] in ("sukses", "melebihi_budget")
        returned_codes = [x["kode"] for x in res.get("produk", [])] or [x["kode"] for x in res.get("produk_termurah", [])]
        assert p["kode"] in returned_codes, (
            f"Produk {p['kode']} ({nama}) tidak ditemukan saat dicari dengan kata khas '{distinct_word}'. Hasil: {returned_codes}"
        )


def test_property_budget_max_never_exceeded(catalog):
    """Properti: budget_max adalah filter keras, produk yang dikembalikan tidak pernah melampaui budget_max."""
    all_products = list(catalog.by_code.values())
    prices = [p.get("harga") or p.get("harga_idr") for p in all_products if (p.get("harga") or p.get("harga_idr"))]
    min_price = min(prices)
    max_price = max(prices)

    test_budgets = [
        min_price - 100_000,   # Pasti tidak ada yang muat
        min_price,             # Produk termurah
        min_price + 2_000_000,
        10_000_000,
        max_price
    ]

    for b in test_budgets:
        res = cari_produk(budget_max=b, catalog=catalog)
        if res["status"] == "sukses":
            assert len(res["produk"]) > 0
            for item in res["produk"]:
                assert item["harga_idr"] <= b, f"Produk {item['kode']} harga {item['harga_idr']} melampaui budget_max {b}!"
        elif res["status"] == "melebihi_budget":
            assert len(res["produk"]) == 0
            assert len(res["produk_termurah"]) > 0
            assert res["produk_termurah"][0]["harga_idr"] >= b


def test_property_kategori_filter_integrity(catalog):
    """Properti: pencarian per kategori dinamis tidak pernah mengembalikan kategori lain."""
    inv = get_catalog_inventory()
    categories = inv.get("kategori", [])
    assert len(categories) >= 4

    for cat in categories:
        res = cari_produk(kategori=cat, catalog=catalog)
        assert res["status"] == "sukses"
        for item in res["produk"]:
            assert item["kategori"].lower() == cat.lower(), f"Produk {item['kode']} bukan kategori {cat}!"


def test_cari_produk_karakteristik_spesifik(catalog):
    """Menguji kecocokan karakteristik umum: ecotank, printer struk, tangki tinta."""
    # 1. ecotank
    res_ecotank = cari_produk(kata_kunci="ecotank", catalog=catalog)
    codes_ecotank = [p["kode"] for p in res_ecotank.get("produk", [])]
    assert "KB-P06" in codes_ecotank  # Epson EcoTank L3210

    # 2. printer struk
    res_struk = cari_produk(kata_kunci="printer struk", catalog=catalog)
    codes_struk = [p["kode"] for p in res_struk.get("produk", [])]
    assert "KB-P09" in codes_struk  # Epson TM-T82X thermal

    # 3. tangki tinta
    res_tangki = cari_produk(kata_kunci="tangki tinta", catalog=catalog)
    codes_tangki = [p["kode"] for p in res_tangki.get("produk", [])]
    assert any(c in codes_tangki for c in ["KB-P06", "KB-P10"])


def test_detail_produk_single_and_multiple(catalog):
    """Menguji detail_produk mengembalikan lembar_spesifikasi lengkap dan raw_data."""
    # Single
    res_single = detail_produk("KB-L14", catalog=catalog)
    assert res_single["status"] == "sukses"
    assert len(res_single["detail"]) == 1
    d0 = res_single["detail"][0]
    assert d0["kode"] == "KB-L14"
    assert "prosesor" in d0["lembar_spesifikasi"]
    assert "raw_data" in d0

    # Multiple
    res_multi = detail_produk("KB-L14, KB-P06", catalog=catalog)
    assert res_multi["status"] == "sukses"
    assert len(res_multi["detail"]) == 2
    codes = [d["kode"] for d in res_multi["detail"]]
    assert "KB-L14" in codes and "KB-P06" in codes


def test_pengetahuan_kebutuhan():
    """Menguji pengetahuan_kebutuhan mengembalikan panduan profil dari KB."""
    res = pengetahuan_kebutuhan("kuliah informatika programming")
    assert res["status"] == "sukses"
    assert len(res["profil_rekomendasi"]) > 0
    p0 = res["profil_rekomendasi"][0]
    assert "profil_id" in p0
    assert "judul" in p0


def test_info_toko():
    """Menguji info_toko mengembalikan kebijakan resmi ReIn Komputer."""
    res = info_toko("desktop")
    assert res["status"] == "sukses"
    info = res["info"]
    assert info["nama_toko"] == "ReIn Komputer"
    assert "Paket desktop tidak termasuk monitor" in info["kebijakan_desktop"]
    assert "laptop" in info["kategori_produk"]
    assert "@" in info["kontak_staf"]


def test_execute_agent_tool_wrapper():
    """Menguji dispatcher execute_agent_tool."""
    res = execute_agent_tool("cari_produk", {"kategori": "monitor"})
    assert res["status"] == "sukses"
    assert len(res["produk"]) > 0

    res_err = execute_agent_tool("alat_ngawur", {})
    assert res_err["status"] == "error"
