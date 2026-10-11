# -*- coding: utf-8 -*-
"""
tests/test_putaran15_synthetic.py
Pengujian sintetis Putaran 15: Impor katalog v2, CPU Apple, data kosong, lepas ketergantungan dummy, pilihan dalam budget, dan kesetaraan kategori.
"""
import pytest
from scripts.migrate_derived_fields import cpu_tier


# =============================================================================
# BUTIR 2 — Tingkat CPU Apple (KB G01)
# =============================================================================
@pytest.mark.parametrize("cpu_str,expected_tier", [
    # Apple M dasar -> Tier 2
    ("Apple M1 8-core", 2),
    ("Apple M2 8-core", 2),
    ("Apple M3", 2),
    ("Apple M4 10-core", 2),
    # Apple M Pro -> Tier 3
    ("Apple M1 Pro", 3),
    ("Apple M2 Pro 10-core", 3),
    ("Apple M3 Pro 11-core", 3),
    # Apple M Max -> Tier 4
    ("Apple M1 Max", 4),
    ("Apple M2 Max 12-core", 4),
    ("Apple M3 Max 14-core", 4),
    # Varian lain (mis. Ultra) -> None (NULL)
    ("Apple M1 Ultra", None),
    ("Apple M2 Ultra", None),
    # Intel & AMD tetap sesuai aturan
    ("Intel Core Ultra 7 155H", 3),
    ("Intel Core i5-12400", 2),
    ("AMD Ryzen 7 7735HS", 3),
    ("Intel Celeron N4500", 1),
    ("Intel Processor N100", 1),
    ("", None),
    (None, None),
])
def test_butir2_cpu_tier_apple_dan_pc(cpu_str, expected_tier):
    assert cpu_tier(cpu_str) == expected_tier


# =============================================================================
# BUTIR 3 — Data Kosong dan Keterangan Produk
# =============================================================================
def test_butir3_data_kosong_tidak_dianggap_memenuhi_syarat():
    """Kolom spesifikasi kosong berarti tidak diketahui/tidak termasuk. Jangan dianggap 0 dan jangan dianggap memenuhi syarat."""
    from services.catalog_search import apply_filters
    
    # Produk barebone (SSD None, RAM None)
    prod_barebone = {
        "kode": "SYN-D01",
        "nama": "Mini PC Barebone",
        "kategori": "desktop",
        "cpu_tier": 2,
        "ram_gb": None,
        "storage_ssd_gb": None,
        "gpu_dedicated": 0,
        "raw_data": '{"barebone": true, "catatan": "Belum termasuk RAM dan SSD"}'
    }
    
    # Filter butuh SSD >= 256
    filters = [{"field": "storage_ssd_gb", "op": ">=", "value": 256, "strength": "soft"}]
    passed, reason, penalty, report = apply_filters(prod_barebone, filters)
    assert passed is False
    assert "storage_ssd_gb" in reason
    assert "storage_ssd_gb (tidak tersedia/tidak termasuk)" in report["tidak_terpenuhi"]


def test_butir3_raw_data_keterangan_masuk_lembar_spesifikasi():
    """Keterangan di raw_data (barebone, paket, catatan) wajib masuk lembar spesifikasi."""
    from services.action_engine import build_lembar_spesifikasi
    
    p = {
        "kode": "SYN-D02",
        "nama": "Komputer Bundling",
        "kategori": "desktop",
        "harga_idr": 10000000,
        "raw_data": '{"barebone": false, "paket": "Termasuk monitor 24 inci", "catatan": "Garansi resmi 3 tahun", "bonus": "Keyboard & Mouse"}'
    }
    
    specs = build_lembar_spesifikasi(p)
    assert specs.get("paket") == "Termasuk monitor 24 inci"
    assert specs.get("catatan") == "Garansi resmi 3 tahun"
    assert specs.get("bonus") == "Keyboard & Mouse"
    assert specs.get("barebone") is False


# =============================================================================
# BUTIR 4 — Lepas Ketergantungan Dummy & Inferensi Data
# =============================================================================
def test_butir4_infer_category_from_data_kb_and_catalog():
    """Pemetaan kebutuhan ke kategori diturunkan dari data KB dan katalog, bukan daftar manual."""
    from services.knowledge_service import infer_category_from_data

    assert infer_category_from_data("butuh komputer kasir toko") == "desktop"
    assert infer_category_from_data("cari printer cetak dokumen kantor") == "printer"
    assert infer_category_from_data("laptop buat kuliah dan tugas skripsi") == "laptop"
    assert infer_category_from_data("monitor layar lebar untuk multitasking") == "monitor"
    assert infer_category_from_data("butuh laptop baterai awet") == "laptop"


def test_butir4_grounding_checker_tidak_ada_known_outside():
    """GroundingChecker tidak boleh memiliki daftar manual known_outside."""
    from services.grounding_checker import GroundingChecker
    import inspect

    src = inspect.getsource(GroundingChecker.check)
    assert "known_outside" not in src, "known_outside dilarang ada di GroundingChecker!"


def test_butir4_dynamic_item_luar_katalog_ditolak():
    """Item luar katalog ditentukan dinamis saat runtime dengan mengecek ketiadaannya di katalog."""
    from core.db import get_catalog_inventory
    from services.action_engine import ActionEngine
    from services.validator import validate_parser_output

    inv = get_catalog_inventory()
    # Pilih kategori dan merek yang benar-benar tidak ada di inventory saat ini
    kandidat_kat = ["tablet", "kamera", "smartwatch", "drone", "proyektor"]
    kandidat_merek = ["sony", "samsung", "toshiba", "logitech", "huawei"]

    item_kat = next(k for k in kandidat_kat if k not in inv["kategori"])
    item_merek = next(m for m in kandidat_merek if m not in inv["merek"])

    engine = ActionEngine()
    raw = {
        "aksi": "cari_produk",
        "argumen": {"kategori": item_kat, "merek": item_merek},
        "pembaruan_state": {"kategori": item_kat, "merek": item_merek}
    }
    validated, is_valid = validate_parser_output(raw)
    res = engine.execute(validated, session_state={})
    assert res.fakta["status"] == "tidak_dijual"
    assert res.produk_list == []


# =============================================================================
# BUTIR 5 — Pilihan Terdekat dalam Budget
# =============================================================================
def test_butir5_pilihan_terdekat_dalam_budget_render_3d():
    """
    Skenario: 'budget 10 juta untuk render 3D'.
    Karena tidak ada laptop render 3D (P03) dalam budget 10 juta,
    sistem HARUS menampilkan produk <= 10 juta terdekat (urut harga menurun)
    beserta catatan jujur mengenai kekurangannya, bukan status kosong atau produk di luar budget.
    """
    from services.action_engine import ActionEngine
    from services.validator import validate_parser_output

    engine = ActionEngine()
    raw = {
        "aksi": "minta_rekomendasi",
        "argumen": {
            "kategori": "laptop",
            "budget_max": 10000000,
            "kebutuhan_teks": "render 3D"
        },
        "pembaruan_state": {
            "kategori": "laptop",
            "budget": 10000000,
            "kebutuhan_teks": "render 3D"
        }
    }
    validated, is_valid = validate_parser_output(raw)
    assert is_valid is True

    res = engine.execute(validated, session_state={})
    assert res.fakta.get("status") == "belum_ada_yang_memenuhi"
    assert len(res.produk_list) > 0
    assert len(res.produk_list) <= 3

    # Semua produk HARUS <= budget 10 juta
    for p in res.produk_list:
        harga = p.get("harga") or p.get("harga_idr")
        assert harga <= 10000000, f"Produk {p.get('nama')} seharga {harga} melebihi budget!"
        # Catatan jujur mengenai kekurangan
        cat_min = p.get("catatan_minimum", {})
        assert cat_min.get("memenuhi") is False
        assert "Belum memenuhi" in cat_min.get("alasan", "")

    # Urutan harga menurun (harga tertinggi yang masih <= budget di peringkat pertama)
    prices = [p.get("harga") or p.get("harga_idr") for p in res.produk_list]
    assert prices == sorted(prices, reverse=True), f"Produk harus diurutkan menurun: {prices}"

