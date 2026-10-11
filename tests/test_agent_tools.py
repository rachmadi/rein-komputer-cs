# -*- coding: utf-8 -*-
"""
Property-based and Unit Tests for ReIn Komputer Agent Tools (Putaran 18b).
Memverifikasi:
- Properti 1: Setiap produk ditemukan lewat kata khas namanya di katalog().
- Properti 2: budget_max tidak pernah mengembalikan produk di atasnya.
- Properti 3: katalog(kategori=X) tanpa kata kunci memberi total_cocok = jumlah produk kategori X.
- Properti 4: pengetahuan() mengembalikan teks dari tipe G, P, M, dan kebijakan untuk pertanyaan relevan.
- Pencarian khusus: 'mini desktop' mengembalikan Mac mini & Intel NUC tanpa tower desktop.
- Lembar spesifikasi: katalog(kode_atau_nama=...) mengembalikan spek lengkap dan raw_data.
- Skema alat: tepat dua alat yaitu katalog dan pengetahuan.
"""
import json
import re
import pytest
from core.db import get_catalog_inventory
from services.catalog_service import get_active_catalog
from services.agent_tools import (
    katalog,
    pengetahuan,
    cari_produk,
    detail_produk,
    pengetahuan_kebutuhan,
    info_toko,
    execute_agent_tool,
    AGENT_TOOLS_SCHEMA,
)


@pytest.fixture
def catalog():
    return get_active_catalog()


def test_property_distinct_word_retrieves_product(catalog):
    """Properti: untuk setiap produk di katalog, satu kata khas dari namanya mengembalikan produk itu di katalog()."""
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

        res = katalog(kata_kunci=distinct_word, catalog=catalog)
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
        res = katalog(budget_max=b, catalog=catalog)
        if res["status"] == "sukses":
            assert len(res["produk"]) > 0
            for item in res["produk"]:
                assert item["harga_idr"] <= b, f"Produk {item['kode']} harga {item['harga_idr']} melampaui budget_max {b}!"
        elif res["status"] == "melebihi_budget":
            assert len(res["produk"]) == 0
            assert len(res["produk_termurah"]) > 0
            assert res["produk_termurah"][0]["harga_idr"] >= b


def test_property_kategori_without_keyword_matches_total(catalog):
    """Properti: katalog(kategori=X) tanpa kata kunci memberi total_cocok = jumlah produk kategori X."""
    all_products = list(catalog.by_code.values())
    inv = get_catalog_inventory()
    categories = inv.get("kategori", [])
    assert len(categories) >= 4

    for cat in categories:
        expected_count = len([p for p in all_products if str(p.get("kategori", "")).lower() == cat.lower()])
        res = katalog(kategori=cat, catalog=catalog)
        assert res["status"] == "sukses"
        assert res["total_cocok"] == expected_count, (
            f"Kategori {cat}: total_cocok={res['total_cocok']}, diharapkan {expected_count}"
        )
        assert len(res["produk"]) == min(10, expected_count)
        for item in res["produk"]:
            assert item["kategori"].lower() == cat.lower()


def test_property_pengetahuan_types_coverage():
    """Properti: pengetahuan() mengembalikan teks dari tipe G, P, M, dan kebijakan untuk kueri yang relevan."""
    test_cases = [
        ("G", "panduan tingkatan prosesor cpu", "G01"),
        ("P", "kebutuhan render 3d dan arsitek", "P07"),
        ("M", "panduan memilih monitor gaming", "M01"),
        ("K", "apakah paket desktop sudah dapat monitor?", "K01"),
    ]

    for expected_type, query, expected_id in test_cases:
        res = pengetahuan(query)
        assert res["status"] == "sukses"
        assert len(res["pengetahuan"]) > 0
        top_item = res["pengetahuan"][0]
        assert top_item["id"].startswith(expected_type), (
            f"Kueri '{query}': diharapkan tipe {expected_type} (id {expected_id}), dapat {top_item['id']} ({top_item['judul']})"
        )
        # Pastikan tidak ada kode internal P01/G01/M01/K01 di judul yang dikirim ke LLM
        assert not top_item["judul"].startswith(("P0", "P1", "G0", "M0", "K0")), (
            f"Judul masih memuat kode internal: {top_item['judul']}"
        )
        # Pastikan ada teks panduan/kebijakan
        assert len(top_item["teks"]) > 20


def test_property_katalog_form_factor_search(catalog):
    """Tes properti dari data: untuk SETIAP produk yang raw_data-nya punya form_factor,
    katalog(kata_kunci=<salah satu kata form_factor-nya>, kategori=<kategorinya>)
    memuat produk itu. Tanpa kode produk hardcode.
    """
    products_with_ff = []
    for p in catalog.by_code.values():
        raw_val = p.get("raw_data")
        if not raw_val:
            continue
        raw_dict = raw_val if isinstance(raw_val, dict) else json.loads(raw_val)
        ff = raw_dict.get("form_factor")
        if ff:
            products_with_ff.append((p, ff))

    assert len(products_with_ff) > 0, "Harus ada produk dengan form_factor di katalog"

    for product, ff in products_with_ff:
        # Ekstrak kata-kata form_factor bermakna (panjang >= 3)
        words = [
            w.lower() for w in re.findall(r"[a-zA-Z]+", ff)
            if len(w) >= 3 and w.lower() not in ("dan", "atau", "dengan", "yang", "dari")
        ]
        assert len(words) > 0, f"Produk {product.get('kode')} tidak memiliki kata form_factor yang valid"

        # Cari salah satu kata form_factor yang memuat produk tersebut
        matched = False
        kategori_prod = product.get("kategori")
        for w in words:
            res = katalog(kata_kunci=w, kategori=kategori_prod, catalog=catalog)
            if res.get("status") == "sukses":
                found_codes = [item.get("kode") for item in res.get("produk", [])]
                if product.get("kode") in found_codes:
                    matched = True
                    break

        assert matched, (
            f"Produk {product.get('kode')} (kategori={kategori_prod}, form_factor='{ff}') "
            f"tidak ditemukan di katalog dengan kata_kunci dari form_factor-nya: {words}"
        )


def test_katalog_detail_produk(catalog):
    """Menguji bahwa katalog dengan kode_atau_nama mengembalikan lembar spesifikasi dan raw_data."""
    # Single
    res_single = katalog(kode_atau_nama="KB-L19", catalog=catalog)
    assert res_single["status"] == "sukses"
    assert res_single["total_cocok"] == 1
    d0 = res_single["detail"][0]
    assert d0["kode"] == "KB-L19"
    assert "Swift Go 14 SFG14-73" in d0["nama"]
    assert "prosesor" in d0["lembar_spesifikasi"]
    assert "raw_data" in d0

    # Multiple
    res_multi = katalog(kode_atau_nama="KB-L14, KB-P06", catalog=catalog)
    assert res_multi["status"] == "sukses"
    assert res_multi["total_cocok"] == 2
    codes = [d["kode"] for d in res_multi["detail"]]
    assert "KB-L14" in codes and "KB-P06" in codes


def test_schema_has_two_tools():
    """Menguji skema alat yang diekspos ke LLM hanya memiliki 2 fungsi: katalog dan pengetahuan."""
    tool_names = [t["function"]["name"] for t in AGENT_TOOLS_SCHEMA]
    assert tool_names == ["katalog", "pengetahuan"]


def test_execute_agent_tool_dispatcher(catalog):
    """Menguji eksekusi alat lewat execute_agent_tool."""
    res_kat = execute_agent_tool("katalog", {"kategori": "monitor"}, catalog=catalog)
    assert res_kat["status"] == "sukses"
    assert len(res_kat["produk"]) > 0

    res_pen = execute_agent_tool("pengetahuan", {"pertanyaan": "apakah desktop dapat monitor"})
    assert res_pen["status"] == "sukses"
    assert len(res_pen["pengetahuan"]) > 0

    # Backward compatibility
    res_leg = execute_agent_tool("cari_produk", {"kategori": "printer"}, catalog=catalog)
    assert res_leg["status"] == "sukses"
    assert len(res_leg["produk"]) > 0


def test_format_tool_history_message():
    """Menguji penyusunan pesan ringkasan riwayat alat 3 giliran terakhir (Butir 4)."""
    from services.agentic_tool_engine import format_tool_history_message
    sample_turns = [
        {
            "tool_calls": [
                {
                    "nama": "katalog",
                    "argumen": {"kata_kunci": "mini desktop"},
                    "total_cocok": 2,
                    "produk": [
                        {"kode": "KB-D12", "nama": "Intel NUC 11 Essential", "harga": "Rp3.199.000"},
                        {"kode": "KB-D11", "nama": "Apple Mac mini M2", "harga": "Rp11.499.000"}
                    ]
                }
            ]
        }
    ]
    msg = format_tool_history_message(sample_turns)
    assert msg is not None
    assert "katalog" in msg
    assert "KB-D12" in msg
    assert "KB-D11" in msg


def test_property_product_card_spek_not_empty(catalog):
    """Properti: untuk SETIAP produk di katalog, kartu yang dirender dari data
    katalog mentahnya memiliki baris Spek yang tidak kosong (Putaran 18e Butir 1).
    """
    from services.product_card import format_product_card

    assert len(catalog.by_code) > 0
    for p in catalog.by_code.values():
        card = format_product_card(p)
        spek_lines = [line for line in card.split("\n") if "Spek:" in line]
        assert len(spek_lines) == 1, f"Produk {p.get('kode')} tidak memiliki baris Spek di kartu"
        spek_text = spek_lines[0].replace("⚙️ Spek:", "").strip()
        assert len(spek_text) > 0 and spek_text != "-", (
            f"Baris Spek kosong pada produk {p.get('kode')} ({p.get('nama')})"
        )
