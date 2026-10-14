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
    """Menguji penyusunan pesan ringkasan riwayat alat (Putaran 19 Butir 3b)."""
    from services.agentic_tool_engine import format_tool_history_message
    sample_turns = [
        {
            "tool_calls": [
                {
                    "nama": "katalog",
                    "argumen": {"kata_kunci": "mini desktop"},
                    "total_cocok": 3,
                    "produk": [
                        {
                            "kode": "KB-D12",
                            "nama": "Intel NUC 11 Essential",
                            "harga": "Rp3.199.000",
                            "spek": "Celeron N5105 | RAM 4GB",
                            "ada_foto": True
                        },
                        {
                            "kode": "KB-D11",
                            "nama": "Apple Mac mini M2",
                            "harga": "Rp11.499.000",
                            "spek": "Apple M2 | RAM 8GB",
                            "ada_foto": False
                        }
                    ]
                },
                {
                    "nama": "pengetahuan",
                    "argumen": {"pertanyaan": "garansi toko"},
                    "total_cocok": 1,
                    "pengetahuan": [
                        {
                            "id": "K01",
                            "judul": "Kebijakan Garansi Toko",
                            "cuplikan": "Garansi toko berlaku 7 hari ganti baru untuk cacat pabrik."
                        }
                    ]
                }
            ]
        }
    ]
    msg = format_tool_history_message(sample_turns)
    assert msg is not None
    assert "KB-D12 Intel NUC 11 Essential (Rp3.199.000; Celeron N5105 | RAM 4GB, ada foto)" in msg
    assert "Apple Mac mini M2 (Rp11.499.000; Apple M2 | RAM 8GB)" in msg
    assert "ada foto" not in "Apple Mac mini M2 (Rp11.499.000; Apple M2 | RAM 8GB)"
    assert "(total 3 produk cocok)" in msg
    assert "Kebijakan Garansi Toko: Garansi toko berlaku 7 hari ganti baru untuk cacat pabrik." in msg


def test_prompt_v6_components():
    """Menguji penyusunan prompt varian V6 (Putaran 20 Butir 5)."""
    from services.agentic_tool_engine import build_agent_system_prompt, KOMPONEN_V6_TAMBAHAN
    prompt_v6 = build_agent_system_prompt("V6")
    prompt_v4 = build_agent_system_prompt("V4")
    assert KOMPONEN_V6_TAMBAHAN in prompt_v6
    assert KOMPONEN_V6_TAMBAHAN not in prompt_v4
    assert "Tulis hanya kalimat untuk pelanggan" in prompt_v6
    assert "Bila pelanggan menanyakan foto, lihat ada_foto" in prompt_v6



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


def test_product_cards_render_up_to_5_and_ordered_by_mention():
    """Menguji bahwa kartu produk merender hingga 5 produk (Putaran 18e Butir 2)
    dan berurutan sesuai kemunculan di balasan.
    """
    from services.product_card import format_product_cards_message
    from services.agentic_tool_engine import get_product_mention_position

    prods = [
        {"kode": f"KB-L{i:02d}", "nama": f"Laptop Model {i}", "harga": i * 1_000_000, "spesifikasi": f"Spek {i}"}
        for i in range(1, 7)
    ]

    # Uji batas aman maksimal 5 kartu di format_product_cards_message
    msg_all = format_product_cards_message(prods)
    assert "1. Laptop Model 1" in msg_all
    assert "5. Laptop Model 5" in msg_all
    assert "6. Laptop Model 6" not in msg_all

    # Uji urutan kemunculan di teks balasan
    reply_text = (
        "Kami menyarankan KB-L04 terlebih dahulu, lalu KB-L02, disusul KB-L05, "
        "KB-L01, dan terakhir KB-L03."
    )
    # Temukan posisi masing-masing produk
    pos_items = []
    for p in prods[:5]:
        pos = get_product_mention_position(p, reply_text)
        assert pos >= 0
        pos_items.append((pos, p))

    pos_items.sort(key=lambda x: x[0])
    ordered_prods = [item[1] for item in pos_items]
    ordered_codes = [p["kode"] for p in ordered_prods]
    assert ordered_codes == ["KB-L04", "KB-L02", "KB-L05", "KB-L01", "KB-L03"]


def test_property_katalog_ada_foto(catalog):
    """Properti: untuk setiap produk di katalog, ada_foto == berkas image_file-nya ada
    (Putaran 18e Butir 3), baik pada hasil ringkas maupun detail.
    """
    from pathlib import Path
    assert len(catalog.by_code) > 0

    for p in catalog.by_code.values():
        img_f = (p.get("image_file") or "").strip()
        expected_ada_foto = bool(img_f and Path(img_f).is_file())

        # 1. Uji Cabang Detail
        res_detail = katalog(kode_atau_nama=p["kode"], catalog=catalog)
        assert res_detail["status"] == "sukses"
        assert len(res_detail["detail"]) == 1
        d = res_detail["detail"][0]
        assert d["ada_foto"] == expected_ada_foto, (
            f"Detail {p['kode']}: diharapkan ada_foto={expected_ada_foto}, dapat {d['ada_foto']}"
        )

        # 2. Uji Cabang Ringkas
        res_ringkas = katalog(kode_atau_nama=None, kata_kunci=p["nama"], catalog=catalog)
        assert res_ringkas["status"] == "sukses"
        matched = next((item for item in res_ringkas.get("produk", []) if item["kode"] == p["kode"]), None)
        if matched:
            assert matched["ada_foto"] == expected_ada_foto, (
                f"Ringkas {p['kode']}: diharapkan ada_foto={expected_ada_foto}, dapat {matched['ada_foto']}"
            )


def test_grounding_checker_usage_text_exemption():
    """Putaran 18e Butir 6: Aturan klaim peruntukan di GroundingChecker tidak menandai
    frasa kegunaan yang memang tertulis di usage_text produk giliran itu.
    """
    from services.grounding_checker import GroundingChecker

    checker = GroundingChecker()

    # 1. Kasus kebutuhan kosong, klaim peruntukan sesuai dengan usage_text produk
    fakta_sesuai = {
        "status": "sukses",
        "produk": [{
            "nama": "ASUS Vivobook Go 14",
            "harga": 6299000,
            "kategori": "laptop",
            "usage_text": "Cocok untuk kerja kantor dan penggunaan harian."
        }]
    }
    state_empty_keb = {"kategori": "laptop", "kebutuhan_teks": ""}
    teks_sesuai = "ASUS Vivobook Go 14 cocok untuk kerja kantor dan penggunaan harian."
    is_valid, violations = checker.check(teks_sesuai, fakta=fakta_sesuai, state=state_empty_keb)
    assert not any("peruntukan" in v.lower() for v in violations), (
        f"Klaim peruntukan yang ada di usage_text tidak boleh ditandai pelanggaran: {violations}"
    )

    # 2. Kasus kebutuhan kosong, klaim peruntukan TIDAK ADA di usage_text produk (misal klaim gaming)
    teks_tidak_sesuai = "ASUS Vivobook Go 14 sangat cocok untuk gaming kompetitif."
    is_valid_fail, violations_fail = checker.check(teks_tidak_sesuai, fakta=fakta_sesuai, state=state_empty_keb)
    assert any("peruntukan" in v.lower() for v in violations_fail), (
        f"Klaim peruntukan di luar usage_text harus ditandai pelanggaran: {violations_fail}"
    )

    # 3. Kasus kebutuhan ada ('kerja kantor'), tapi bot juga menyebut 'kuliah' yang ada di usage_text
    fakta_kuliah = {
        "status": "sukses",
        "kebutuhan_teks": "kerja kantor",
        "produk": [{
            "nama": "Lenovo IdeaPad Slim 3",
            "harga": 7000000,
            "kategori": "laptop",
            "usage_text": "Cocok untuk kerja kantor dan kuliah."
        }]
    }
    state_ada_keb = {"kategori": "laptop", "kebutuhan_teks": "kerja kantor"}
    teks_kuliah = "Lenovo IdeaPad Slim 3 cocok untuk kuliah dan kerja kantor."
    is_valid_k, violations_k = checker.check(teks_kuliah, fakta=fakta_kuliah, state=state_ada_keb)
    assert not any("kuliah" in v.lower() for v in violations_k), (
        f"Peruntukan 'kuliah' ada di usage_text produk sehingga tidak boleh ditandai: {violations_k}"
    )


def test_property_product_mention_keys(catalog):
    """Putaran 19 Butir 4: Tes berbasis properti untuk pencocok kartu produk."""
    from services.agentic_tool_engine import (
        build_product_key_index,
        get_product_mention_position,
        is_product_mentioned_in_reply,
    )
    from core.catalog import Catalog

    # Ambil 40 produk resmi katalog aktif (mengabaikan produk fixture warisan KB-L01..10, KB-D01..05, KB-P01..05)
    legacy_codes = {f"KB-L{i:02d}" for i in range(1, 11)} | {f"KB-D{i:02d}" for i in range(1, 6)} | {f"KB-P{i:02d}" for i in range(1, 6)}
    active_records = [p for p in catalog.products if p["kode"] not in legacy_codes]
    assert len(active_records) == 40
    active_catalog = Catalog(active_records)

    index = build_product_key_index(active_catalog)
    assert len(index) == len(active_catalog.by_code)

    # 1. Properti: untuk setiap produk di katalog, setiap kunci di indeksnya tidak pernah cocok dengan produk lain
    for code, keys in index.items():
        prod = active_catalog.by_code[code]
        for key in keys:
            assert is_product_mentioned_in_reply(prod, key, catalog=active_catalog), (
                f"Kunci '{key}' tidak cocok dengan produk asalnya {code}"
            )
            for other_code, other_prod in active_catalog.by_code.items():
                if other_code == code:
                    continue
                assert not is_product_mentioned_in_reply(other_prod, key, catalog=active_catalog), (
                    f"Kolisi kunci! Kunci '{key}' milik {code} ({prod.get('nama')}) "
                    f"juga cocok dengan {other_code} ({other_prod.get('nama')})"
                )

    # 2. Contoh nyata
    cases = [
        ("Mac mini M2", "KB-D11"),
        ("VG27AQ", "KB-M05"),
        ("T82X", "KB-P09"),
        ("24MP400", "KB-M01"),
        ("MacBook Pro", "KB-L30"),
    ]
    for text, expected_code in cases:
        expected_prod = active_catalog.by_code[expected_code]
        pos = get_product_mention_position(expected_prod, text, catalog=active_catalog)
        assert pos >= 0, f"'{text}' diharapkan cocok dengan {expected_code}, tapi pos={pos}"
        for other_code, other_prod in active_catalog.by_code.items():
            if other_code != expected_code:
                assert not is_product_mentioned_in_reply(other_prod, text, catalog=active_catalog), (
                    f"'{text}' diharapkan hanya milik {expected_code}, tapi juga cocok dengan {other_code}"
                )

    # 3. Kalimat generik tidak mencocokkan produk mana pun
    generic_text = "cocok untuk gaming, slim, modern, dan layar oled"
    for code, prod in active_catalog.by_code.items():
        pos = get_product_mention_position(prod, generic_text, catalog=active_catalog)
        assert pos == -1, (
            f"Kalimat generik mencocokkan {code} ({prod.get('nama')}) pada pos {pos}"
        )


def test_prompt_variants_v0_v3_match_baselines():
    """Putaran 19b Butir 2: V0 harus sama persis dengan prompt sebelum-putaran19,
    dan V3 harus sama persis dengan prompt sebelum-putaran19b.
    """
    import subprocess
    from services.agentic_tool_engine import build_agent_system_prompt

    # 1. Baseline sebelum-putaran19
    src_19 = subprocess.check_output(
        ["git", "show", "sebelum-putaran19:services/agentic_tool_engine.py"],
        encoding="utf-8"
    )
    loc_19 = {}
    exec(compile(src_19, "<string>", "exec"), loc_19)
    baseline_19 = loc_19["build_agent_system_prompt"]()

    # 2. Baseline sebelum-putaran19b
    src_19b = subprocess.check_output(
        ["git", "show", "sebelum-putaran19b:services/agentic_tool_engine.py"],
        encoding="utf-8"
    )
    loc_19b = {}
    exec(compile(src_19b, "<string>", "exec"), loc_19b)
    baseline_19b = loc_19b["build_agent_system_prompt"]("C")

    # Uji kesamaan persis
    v0_prompt = build_agent_system_prompt("V0")
    v3_prompt = build_agent_system_prompt("V3")

    assert v0_prompt == baseline_19, "V0 tidak sama persis dengan prompt sebelum-putaran19"
    assert v3_prompt == baseline_19b, "V3 tidak sama persis dengan prompt sebelum-putaran19b"


def test_katalog_kata_kunci_tidak_cocok_kembalikan_catatan():
    """Menguji monitor + 'perbandingan' -> total 0, catatan menyebut kategori dan menyertakan produk_di_kategori (Putaran 20 Butir 4 / Putaran 28 Butir 4)."""
    res = katalog(kategori="monitor", kata_kunci="perbandingan")
    assert res["total_cocok"] == 0
    assert "catatan" in res
    assert "perbandingan" in res["catatan"]
    assert "produk_di_kategori" in res
    assert len(res["produk_di_kategori"]) == 5
    assert res.get("produk") == []


def test_putaran28_butir4_pencarian_kategori_fallback():
    """Menguji ekstraksi kategori otomatis dan fallback produk_di_kategori (Putaran 28 Butir 4 & Butir 7a)."""
    # 1. 'printer irit volume tinggi' tanpa kategori -> kategori terisi printer, 0 hasil cocok, produk_di_kategori berisi 5 printer asli
    res = katalog(kata_kunci="printer irit volume tinggi")
    assert res["status"] == "sukses"
    assert res["total_cocok"] == 0
    assert "produk_di_kategori" in res
    assert len(res["produk_di_kategori"]) in (5, 10)
    assert all(p["kode"].startswith("KB-P") for p in res["produk_di_kategori"])
    assert "printer" in res["catatan"].lower()
    assert "Jangan sebut produk atau harga di luar daftar ini" in res["catatan"]

    # 2. Urutan termahal dihormati pada fallback
    res_mahal = katalog(kata_kunci="printer irit volume tinggi", urutan="termahal")
    assert res_mahal["produk_di_kategori"][0]["harga_idr"] >= res_mahal["produk_di_kategori"][-1]["harga_idr"]
    assert res_mahal["produk_di_kategori"][0]["kode"] in ("KB-P05", "KB-P10")

    # 3. Urutan termurah bawaan
    res_murah = katalog(kata_kunci="printer irit volume tinggi")
    assert res_murah["produk_di_kategori"][0]["harga_idr"] <= res_murah["produk_di_kategori"][-1]["harga_idr"]
    assert res_murah["produk_di_kategori"][0]["kode"] == "KB-P07"


def test_putaran28_butir1_katalog_segar_tanpa_restart():
    """Menguji bahwa perubahan data produk di SQLite langsung terdeteksi tanpa restart (Putaran 28 Butir 1 & 7a)."""
    import sqlite3
    from services.catalog_service import (
        get_active_catalog,
        _get_catalog_db_path,
        set_catalog_turn_id,
        get_last_check_duration_ms,
        get_last_reload_duration_ms
    )

    set_catalog_turn_id(None)
    cat_awal = get_active_catalog(force_check=True)
    db_path = _get_catalog_db_path()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT kode, nama FROM products WHERE kode='KB-P07'")
    row = cur.fetchone()
    assert row is not None
    kode, nama_asli = row

    try:
        cur.execute("UPDATE products SET nama = ? WHERE kode = ?", (nama_asli + " EDISI KHUSUS P28", kode))
        conn.commit()

        # Panggil get_active_catalog, harus memuat ulang dan nama baru terbaca
        cat_baru = get_active_catalog(force_check=True)
        prod = cat_baru.by_code.get(kode)
        assert prod is not None
        assert "EDISI KHUSUS P28" in prod["nama"]

        check_ms = get_last_check_duration_ms()
        reload_ms = get_last_reload_duration_ms()
        assert check_ms >= 0.0
        assert reload_ms >= 0.0
    finally:
        cur.execute("UPDATE products SET nama = ? WHERE kode = ?", (nama_asli, kode))
        conn.commit()
        conn.close()
        get_active_catalog(force_check=True)



def test_pesan_tertunda_sisipan_catatan():
    """Menguji penyisipan catatan pesan tertunda pada 5 menit dan tidak pada 4 menit (Putaran 20 Butir 7)."""
    from unittest.mock import patch
    from services.agentic_tool_engine import run_agentic_tool

    captured_messages_5 = []
    captured_messages_4 = []

    def mock_ollama_5(messages, **kwargs):
        captured_messages_5.extend(messages)
        return {"message": {"role": "assistant", "content": "Halo Kak!"}}

    def mock_ollama_4(messages, **kwargs):
        captured_messages_4.extend(messages)
        return {"message": {"role": "assistant", "content": "Halo Kak!"}}

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama_5):
        run_agentic_tool(
            user_text="Halo apa kabar?",
            history=[],
            menunggu_menit=5
        )

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama_4):
        run_agentic_tool(
            user_text="Halo apa kabar?",
            history=[],
            menunggu_menit=4
        )

    # Pada 5 menit: catatan disisipkan tepat sebelum pesan pelanggan
    assert len(captured_messages_5) >= 2
    expected_note = (
        "Catatan: pesan pelanggan berikut sudah menunggu sekitar 5 menit "
        "karena layanan sempat tidak aktif. Kamu boleh meminta maaf atas keterlambatannya "
        "dengan wajar, lalu layani seperti biasa."
    )
    assert any(m.get("content") == expected_note for m in captured_messages_5)

    # Pada 4 menit: catatan tidak disisipkan
    for m in captured_messages_4:
        assert "layanan sempat tidak aktif" not in m.get("content", "")
        assert "sudah menunggu sekitar" not in m.get("content", "")


def test_search_kb_markdown_all_tidak_pernah_berjudul_komentar():
    """Menguji bahwa hasil pencarian kata kunci KB tidak pernah memuat komentar HTML <!-- (Putaran 21 Butir 1)."""
    from services.agent_tools import _search_kb_markdown_all, pengetahuan
    from unittest.mock import patch

    for q in ["panduan", "komputer", "laptop", "kebijakan", "monitor", "intel", "garansi"]:
        res = _search_kb_markdown_all(q)
        for item in res:
            assert "<!--" not in item.get("judul", ""), f"Judul memuat <!-- pada query '{q}': {item.get('judul')}"
            assert "<!--" not in item.get("id", ""), f"ID memuat <!-- pada query '{q}': {item.get('id')}"

    # Uji field sumber pada pengetahuan() normal (qdrant)
    res_q = pengetahuan("kebijakan garansi")
    assert res_q["sumber"] == "qdrant"

    # Uji field sumber dan alasan_cadangan pada fallback kata_kunci
    with patch("services.catalog_service.get_embedding", return_value=[0.1] * 1024):
        with patch("requests.post", side_effect=Exception("Qdrant down")):
            res_kw = pengetahuan("kebijakan garansi")
            assert res_kw["sumber"] == "kata_kunci"
            assert "Qdrant down" in res_kw.get("alasan_cadangan", "")
            for it in res_kw.get("pengetahuan", []):
                assert "<!--" not in it.get("judul", "")

def test_pemeriksaan_ulang_terpicu_pada_janji_tanpa_alat():
    """Menguji mekanisme A: terpicu pada 'Saya cek dulu ya Kak' tanpa alat (Putaran 21 Butir 2c)."""
    from services.agentic_tool_engine import run_agentic_tool
    from unittest.mock import patch

    calls = []

    def mock_ollama(messages, **kwargs):
        calls.append(list(messages))
        if len(calls) == 1:
            return {
                "message": {"role": "assistant", "content": "Saya cek dulu ya Kak"}
            }
        else:
            return {
                "message": {"role": "assistant", "content": "Stok produk kami saat ini tersedia lengkap Kak."}
            }

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama):
        res = run_agentic_tool(
            user_text="Laptop ready kak?",
            history=[],
            pemeriksaan_ulang_janji=True
        )

    assert res["pemeriksaan_ulang"] is True
    assert res["balasan_sebelum_periksa"] == "Saya cek dulu ya Kak"
    assert res["reply"] == "Stok produk kami saat ini tersedia lengkap Kak."
    assert len(calls) == 2

    # Verifikasi pesan teguran sistem dikirim ke panggilan kedua
    pesan_kedua = calls[1]
    expected_teguran = (
        "Balasanmu menyatakan akan mengecek, tetapi di giliran ini kamu belum memanggil alat. "
        "Panggil alat yang dibutuhkan sekarang, atau tulis ulang balasanmu tanpa janji mengecek "
        "dan tanpa menyuruh pelanggan mengecek sendiri."
    )
    assert any(m.get("role") == "system" and m.get("content") == expected_teguran for m in pesan_kedua)
    assert any(m.get("role") == "assistant" and m.get("content") == "Saya cek dulu ya Kak" for m in pesan_kedua)


def test_pemeriksaan_ulang_tidak_terpicu_bila_alat_sudah_dipanggil():
    """Menguji mekanisme A: tidak terpicu bila alat sudah dipanggil di giliran ini (Putaran 21 Butir 2c)."""
    from services.agentic_tool_engine import run_agentic_tool
    from unittest.mock import patch

    calls = []

    def mock_ollama(messages, **kwargs):
        calls.append(list(messages))
        if len(calls) == 1:
            return {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "katalog",
                                "arguments": {"kata_kunci": "ideapad"}
                            }
                        }
                    ]
                }
            }
        else:
            return {
                "message": {"role": "assistant", "content": "Saya sudah cek, berikut pilihannya..."}
            }

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama):
        res = run_agentic_tool(
            user_text="Cari Lenovo Ideapad",
            history=[],
            pemeriksaan_ulang_janji=True
        )

    assert res["pemeriksaan_ulang"] is False
    assert res["balasan_sebelum_periksa"] is None
    assert len(res["tools_called"]) > 0


def test_pemeriksaan_ulang_tidak_terpicu_pada_balasan_tanpa_pola():
    """Menguji mekanisme A: tidak terpicu pada balasan tanpa kata-kata janji periksa (Putaran 21 Butir 2c)."""
    from services.agentic_tool_engine import run_agentic_tool
    from unittest.mock import patch

    calls = []

    def mock_ollama(messages, **kwargs):
        calls.append(list(messages))
        return {
            "message": {"role": "assistant", "content": "Halo Kak, selamat datang di ReIn Komputer! Ada yang bisa saya bantu?"}
        }

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama):
        res = run_agentic_tool(
            user_text="Halo kak",
            history=[],
            pemeriksaan_ulang_janji=True
        )

    assert res["pemeriksaan_ulang"] is False
    assert res["balasan_sebelum_periksa"] is None
    assert len(calls) == 1


def test_payload_mode_berpikir_berisi_think_true_dan_num_predict_2048():
    """Menguji mekanisme B: payload berisi think true dan num_predict 2048 (Putaran 21 Butir 2c)."""
    from services.agentic_tool_engine import run_agentic_tool
    from unittest.mock import patch

    captured_kwargs = []

    def mock_ollama(*args, **kwargs):
        captured_kwargs.append(dict(kwargs))
        return {
            "message": {
                "role": "assistant",
                "content": "Halo Kak!",
                "thinking": "Sedang berpikir mendalam..."
            }
        }

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama):
        res_b = run_agentic_tool(
            user_text="Halo kak",
            history=[],
            mode_berpikir=True
        )

    assert len(captured_kwargs) == 1
    assert captured_kwargs[0]["think"] is True
    assert captured_kwargs[0]["num_predict"] == 2048
    # Verifikasi isi thinking tidak dikirim ke pelanggan
    assert res_b["reply"] == "Halo Kak!"
    # Verifikasi panjang thinking dicatat di llm_calls
    assert res_b["llm_calls"][0]["thinking_chars"] == len("Sedang berpikir mendalam...")

    # Verifikasi mode berpikir mati (bawaan)
    captured_kwargs.clear()
    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama):
        res_default = run_agentic_tool(
            user_text="Halo kak",
            history=[],
            mode_berpikir=False,
            mode_berpikir_sebagian=False
        )

    assert len(captured_kwargs) == 1
    assert captured_kwargs[0]["think"] is False
    assert captured_kwargs[0]["num_predict"] == 1024


def test_parse_kb_k01_k05_dan_tanpa_id_kosong():
    """Menguji parser KB: K01–K05 punya payload ID yang benar, dan tidak ada potongan tanpa ID (Putaran 22 Butir 2b)."""
    from scripts.ingest_knowledge import parse_kb

    chunks = parse_kb("data/knowledge/panduan_kebutuhan_v2.md")
    assert len(chunks) == 29, f"Harus tepat 29 potongan, didapat {len(chunks)}"

    chunk_ids = [c.get("id") for c in chunks]
    # Memastikan tidak ada potongan tanpa ID
    assert all(bool(cid) for cid in chunk_ids), f"Ditemukan potongan tanpa ID: {chunks}"

    # Memastikan K01–K06 ada dan memiliki payload yang benar
    for k_id in ["K01", "K02", "K03", "K04", "K05", "K06"]:
        assert k_id in chunk_ids, f"ID {k_id} tidak ditemukan di hasil parsing"
        matching = next(c for c in chunks if c.get("id") == k_id)
        assert matching.get("tipe") in ("kebijakan toko", "kebijakan_toko")
        assert "kebijakan toko" in matching.get("judul", "").lower()
        assert len(matching.get("kata_kunci", [])) > 0
        assert len(matching.get("text", "")) > 50

    # Memastikan G05 juga ada
    assert "G05" in chunk_ids


def test_payload_b1_panggilan_pertama_think_true_berikutnya_think_false():
    """Menguji mekanisme B1: panggilan pertama think true num_predict 2048, berikutnya think false num_predict 1024 (Putaran 22 Butir 3c)."""
    from services.agentic_tool_engine import run_agentic_tool
    from unittest.mock import patch

    captured_calls = []

    def mock_ollama(*args, **kwargs):
        captured_calls.append(dict(kwargs))
        if len(captured_calls) == 1:
            return {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "thinking": "Sedang berpikir pada panggilan pertama...",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "katalog",
                                "arguments": {"kata_kunci": "ideapad"}
                            }
                        }
                    ]
                }
            }
        else:
            return {
                "message": {
                    "role": "assistant",
                    "content": "Ini laptop Lenovo Ideapad yang tersedia Kak."
                }
            }

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama):
        res = run_agentic_tool(
            user_text="Cari lenovo ideapad",
            history=[],
            mode_berpikir=False,
            mode_berpikir_sebagian=True
        )

    assert len(captured_calls) == 2
    # Panggilan pertama: think True, num_predict 2048
    assert captured_calls[0]["think"] is True
    assert captured_calls[0]["num_predict"] == 2048

    # Panggilan berikutnya (sesudah hasil alat): think False, num_predict 1024
    assert captured_calls[1]["think"] is False
    assert captured_calls[1]["num_predict"] == 1024

    # Bila B dan B1 sama-sama aktif, B yang berlaku (semua think True, 2048)
    captured_calls.clear()
    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama):
        res_both = run_agentic_tool(
            user_text="Cari lenovo ideapad",
            history=[],
            mode_berpikir=True,
            mode_berpikir_sebagian=True
        )

    assert len(captured_calls) == 2
    assert captured_calls[0]["think"] is True
    assert captured_calls[0]["num_predict"] == 2048
    assert captured_calls[1]["think"] is True
    assert captured_calls[1]["num_predict"] == 2048


def test_pos_hanya_muncul_di_varian_yang_memakainya():
    """Menguji bahwa komponen POS hanya muncul di varian yang memakainya (P, PB1) dan terletak setelah KEPUTUSAN sebelum persona (Putaran 22 Butir 3c)."""
    from services.agentic_tool_engine import (
        build_agent_system_prompt,
        KOMPONEN_POS,
        KOMPONEN_KEPUTUSAN,
        KOMPONEN_R2,
        KOMPONEN_R3,
        PERSONA_NAMA_R3,
    )

    prompt_p = build_agent_system_prompt("P")
    prompt_pb1 = build_agent_system_prompt("PB1")
    prompt_v4 = build_agent_system_prompt("V4")
    prompt_b = build_agent_system_prompt("B")
    prompt_b1 = build_agent_system_prompt("B1")

    # POS muncul di P dan PB1
    assert KOMPONEN_POS in prompt_p
    assert KOMPONEN_POS in prompt_pb1

    # POS TIDAK muncul di V4, B, B1
    assert KOMPONEN_POS not in prompt_v4
    assert KOMPONEN_POS not in prompt_b
    assert KOMPONEN_POS not in prompt_b1

    # Letak POS tepat sesudah KEPUTUSAN, sebelum persona
    pos_idx = prompt_p.find(KOMPONEN_POS)
    kep_idx = prompt_p.find(KOMPONEN_KEPUTUSAN)
    persona_r = KOMPONEN_R3 if PERSONA_NAMA_R3 else KOMPONEN_R2
    persona_idx = prompt_p.find(persona_r)

    assert kep_idx >= 0 and pos_idx >= 0 and persona_idx >= 0
    assert kep_idx < pos_idx < persona_idx


def test_build_agent_system_prompt_bawaan_sama_v4_tanpa_pos():
    """Menguji bahwa prompt bawaan produksi sama dengan V4 dan tidak memuat POS (Putaran 23 Butir 1)."""
    from services.agentic_tool_engine import (
        build_agent_system_prompt,
        KOMPONEN_POS,
        PROMPT_VARIAN,
        MODE_BERPIKIR,
        MODE_BERPIKIR_SEBAGIAN,
        PEMERIKSAAN_ULANG_JANJI,
        PENGURAI_ALAT_MENTAH,
    )

    assert PROMPT_VARIAN == "V4"
    assert MODE_BERPIKIR is False
    assert MODE_BERPIKIR_SEBAGIAN is True
    assert PEMERIKSAAN_ULANG_JANJI is False
    assert PENGURAI_ALAT_MENTAH is True

    prompt_default = build_agent_system_prompt()
    prompt_v4 = build_agent_system_prompt("V4")

    assert prompt_default == prompt_v4
    assert KOMPONEN_POS not in prompt_default


def test_pengurai_alat_mentah_dua_string_p_dan_string_rusak():
    """Menguji pengurai alat mentah pada 2 string dari P22 Varian P dan string rusak (Putaran 23 Butir 2)."""
    from services.agentic_tool_engine import parse_raw_tool_call

    # String dari Giliran 14
    s14 = 'katalog{kategori:<|"|>monitor<|"|>,kata_kunci:<|"|>24 inci<|"|>}<tool_call|><|tool_response>'
    res14 = parse_raw_tool_call(s14)
    assert res14 is not None
    assert res14[0] == "katalog"
    assert res14[1] == {"kategori": "monitor", "kata_kunci": "24 inci"}

    # String dari Giliran 16
    s16 = 'katalog{kategori:<|"|>monitor<|"|>}<tool_call|><|tool_response>'
    res16 = parse_raw_tool_call(s16)
    assert res16 is not None
    assert res16[0] == "katalog"
    assert res16[1] == {"kategori": "monitor"}

    # String tak terurai
    s_rusak = '<tool_call|> pesan rusak tanpa fungsi yang valid <|'
    assert parse_raw_tool_call(s_rusak) is None


def test_pengurai_alat_mentah_terintegrasi_dan_fallback():
    """Menguji eksekusi pengurai alat mentah terintegrasi dan fallback darurat (Putaran 23 Butir 2)."""
    from services.agentic_tool_engine import run_agentic_tool, FALLBACK_EMERGENCY_REPLY
    from unittest.mock import patch

    calls = []

    # Kasus 1: String G14 terurai menjadi katalog dengan argumen yang benar
    s14 = 'katalog{kategori:<|"|>monitor<|"|>,kata_kunci:<|"|>24 inci<|"|>}<tool_call|><|tool_response>'

    def mock_ollama_s14(messages, **kwargs):
        calls.append(list(messages))
        if len(calls) == 1:
            return {"message": {"role": "assistant", "content": s14}}
        else:
            return {"message": {"role": "assistant", "content": "Berikut monitor 24 inci yang tersedia Kak."}}

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama_s14):
        res14 = run_agentic_tool(
            user_text="Ada monitor 24 inci?",
            history=[],
            pengurai_alat_mentah=True
        )

    assert "alat_mentah_diurai" in res14["alat_mentah_events"]
    assert "katalog" in res14["tools_called"]
    assert s14 not in res14["reply"]
    # Pastikan teks mentah tidak masuk ke riwayat obrolan / pesan panggilan kedua
    assert len(calls) == 2
    for m in calls[1]:
        assert s14 not in m.get("content", "")

    # Kasus 2: String tak terurai tidak pernah menjadi balasan (pakai balasan darurat)
    s_rusak = '<tool_call|> rusak <|'
    calls.clear()

    def mock_ollama_rusak(messages, **kwargs):
        calls.append(list(messages))
        # Mengembalikan string rusak baik pada panggilan awal maupun retry
        return {"message": {"role": "assistant", "content": s_rusak}}

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama_rusak):
        res_rusak = run_agentic_tool(
            user_text="Tanya sesuatu",
            history=[],
            pengurai_alat_mentah=True
        )

    assert "alat_mentah_gagal" in res_rusak["alat_mentah_events"]
    assert s_rusak not in res_rusak["reply"]
    assert res_rusak["reply"] == FALLBACK_EMERGENCY_REPLY
    assert res_rusak["is_emergency_fallback"] is True
    assert res_rusak["error_darurat"] == "alat_mentah_gagal"


def test_b1f_memuat_tambahan_pengingat_format():
    """Menguji bahwa varian B1F menyisipkan kalimat format di akhir pengingat P (Putaran 23 Butir 4b)."""
    from services.agentic_tool_engine import run_agentic_tool
    from unittest.mock import patch

    captured_b1f = []
    captured_b1 = []

    def mock_ollama_b1f(messages, **kwargs):
        captured_b1f.append(list(messages))
        return {"message": {"role": "assistant", "content": "Halo Kak!"}}

    def mock_ollama_b1(messages, **kwargs):
        captured_b1.append(list(messages))
        return {"message": {"role": "assistant", "content": "Halo Kak!"}}

    kalimat_tambahan = "Tulis balasan dalam satu paragraf, maksimal 4 kalimat, tanpa daftar dan tanpa baris baru."

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama_b1f):
        run_agentic_tool(user_text="Halo", history=[], varian="B1F")

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama_b1):
        run_agentic_tool(user_text="Halo", history=[], varian="B1")

    # B1F harus memuat kalimat_tambahan di pesan sistem pengingat P
    assert any(kalimat_tambahan in m.get("content", "") for m in captured_b1f[0])

    # B1 TIDAK boleh memuat kalimat_tambahan
    assert not any(kalimat_tambahan in m.get("content", "") for m in captured_b1[0])


def test_pengetahuan_topk_configurable():
    """Menguji bahwa PENGETAHUAN_TOPK bawaan adalah 3 dan pengetahuan() mendukung top_k configurable (Putaran 24 Butir 2)."""
    from services.agent_tools import PENGETAHUAN_TOPK, pengetahuan
    assert PENGETAHUAN_TOPK == 3

    # Tes pencarian dengan top_k default (3) vs top_k=5
    res3 = pengetahuan("apakah mini pc bisa dijual paket dengan monitor", top_k=3)
    assert res3["status"] == "sukses"
    assert len(res3["pengetahuan"]) <= 3

    res5 = pengetahuan("apakah mini pc bisa dijual paket dengan monitor", top_k=5)
    assert res5["status"] == "sukses"
    assert len(res5["pengetahuan"]) <= 5
    # Jika Qdrant aktif dan memiliki cukup titik, len(res5["pengetahuan"]) > len(res3["pengetahuan"])


def test_putaran25_butir0_tidak_ada_pesan_ganda_dan_riwayat_kosong():
    """
    Menguji Putaran 25 Butir 0:
    - Pesan yang dikirim ke LLM memuat teks pelanggan terbaru tepat satu kali.
    - Untuk salam pertama di sesi baru, riwayat yang dikirim ke run_agentic_tool kosong.
    """
    from services.chat_service import process_chat_message, get_session_manager
    from unittest.mock import patch

    sm = get_session_manager()
    session_id = "test_p25_b0_sess"
    if session_id in sm._sessions:
        del sm._sessions[session_id]

    captured_calls = []

    def mock_ollama_raw(messages, **kwargs):
        captured_calls.append(list(messages))
        return {
            "message": {"role": "assistant", "content": "Halo Kak, ada yang bisa dibantu?"},
            "prompt_eval_count": 10,
            "eval_count": 10,
            "done_reason": "stop"
        }

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama_raw):
        # Giliran 1: Salam pertama di sesi baru
        res1 = process_chat_message(session_id, "halo")
        assert len(captured_calls) == 1
        msgs_turn1 = captured_calls[0]

        # 1. Pastikan teks pelanggan "halo" muncul tepat 1 kali di seluruh pesan yang dikirim ke LLM
        user_msgs = [m for m in msgs_turn1 if m.get("role") == "user" and m.get("content") == "halo"]
        assert len(user_msgs) == 1, f"Teks pelanggan terbaru harus muncul tepat satu kali, ditemukan: {len(user_msgs)}"

        # 2. Untuk salam pertama di sesi baru, riwayat pesan sebelum prompt/pengingat tidak boleh memuat pesan masa lalu
        # Di msgs_turn1, satu-satunya pesan role user adalah "halo", dan tidak ada pesan role assistant sebelumnya
        assistant_msgs = [m for m in msgs_turn1 if m.get("role") == "assistant"]
        assert len(assistant_msgs) == 0, f"Salam pertama di sesi baru tidak boleh memiliki riwayat assistant, ditemukan: {assistant_msgs}"

        # Giliran 2: Pesan kedua
        captured_calls.clear()
        res2 = process_chat_message(session_id, "Tanya mini pc")
        assert len(captured_calls) == 1
        msgs_turn2 = captured_calls[0]

        # 3. Teks "Tanya mini pc" muncul tepat 1 kali
        user_msgs_t2 = [m for m in msgs_turn2 if m.get("role") == "user" and m.get("content") == "Tanya mini pc"]
        assert len(user_msgs_t2) == 1
        # Riwayat giliran 1 (halo dan jawaban bot) ada di riwayat
        assert any(m.get("content") == "halo" for m in msgs_turn2)
        assert any("Halo Kak, ada yang bisa dibantu?" in m.get("content", "") for m in msgs_turn2)


def test_putaran25_butir1_kirim_ke_pelanggan_retry():
    """
    Menguji Putaran 25 Butir 1c:
    - Gagal 2 kali lalu berhasil menghasilkan 1 pesan terkirim (sukses=True, attempts=3).
    - Gagal 3 kali menghasilkan status gagal tanpa crash (sukses=False, attempts=3).
    """
    import asyncio
    from telegram_bot import kirim_ke_pelanggan
    from telegram.error import TimedOut, NetworkError

    async def _async_test():
        # Skenario 1: gagal 2 kali lalu berhasil
        call_count_1 = 0
        async def mock_sender_gagal_2_lalu_berhasil():
            nonlocal call_count_1
            call_count_1 += 1
            if call_count_1 == 1:
                raise TimedOut("Simulated timeout 1")
            elif call_count_1 == 2:
                raise NetworkError("Simulated network error 2")
            return "Pesan terkirim"

        sukses, err, attempts = await kirim_ke_pelanggan(
            send_fn=mock_sender_gagal_2_lalu_berhasil,
            delays=(0.001, 0.001)
        )
        assert sukses is True
        assert err is None
        assert attempts == 3
        assert call_count_1 == 3

        # Skenario 2: gagal 3 kali menghasilkan status gagal tanpa crash
        call_count_2 = 0
        async def mock_sender_gagal_3_kali():
            nonlocal call_count_2
            call_count_2 += 1
            raise NetworkError(f"Simulated error {call_count_2}")

        sukses_fail, err_fail, attempts_fail = await kirim_ke_pelanggan(
            send_fn=mock_sender_gagal_3_kali,
            delays=(0.001, 0.001)
        )
        assert sukses_fail is False
        assert "Simulated error 3" in str(err_fail)
        assert attempts_fail == 3
        assert call_count_2 == 3

    asyncio.run(_async_test())


def test_putaran25_butir2_riwayat_jujur():
    """Menguji penandaan pesan tidak terkirim dan awalan catatan koneksi pada riwayat LLM (Putaran 25 Butir 2)."""
    from services.chat_service import get_session_manager, tandai_pesan_terakhir_tidak_terkirim
    from services.agentic_tool_engine import run_agentic_tool
    from unittest.mock import patch

    mgr = get_session_manager()
    sid = "test_p25_b2_session"
    mgr._sessions.pop(sid, None)

    # Tambahkan pesan user dan bot
    mgr.add_message(sid, "user", "Ada mini pc?")
    mgr.add_message(sid, "bot", "Ada Kak, kami punya Intel NUC.")

    # Tandai tidak terkirim
    marked = tandai_pesan_terakhir_tidak_terkirim(sid)
    assert marked is True

    sess = mgr.get_session(sid)
    assert sess["messages"][-1]["terkirim"] is False

    # Verifikasi riwayat yang disusun untuk LLM memuat awalan khusus
    captured_messages = []
    def mock_ollama(messages, **kwargs):
        captured_messages.extend(messages)
        return {
            "message": {"role": "assistant", "content": "Iya Kak, tadi ada gangguan koneksi."}
        }

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama):
        run_agentic_tool(
            user_text="Kok gak jawab?",
            history=sess["messages"],
        )

    expected_prefix = "(Balasan ini TIDAK sampai ke pelanggan karena gangguan koneksi.) "
    bot_in_llm = [m for m in captured_messages if m.get("role") == "assistant" and expected_prefix in m.get("content", "")]
    assert len(bot_in_llm) >= 1, "Pesan tidak terkirim harus diawali penanda gangguan koneksi"
    assert bot_in_llm[0]["content"].startswith(expected_prefix)


def test_putaran25_butir3_status_kirim_log_httpx():
    """Menguji pencatatan peristiwa status_kirim dan level logger httpx (Putaran 25 Butir 3)."""
    import logging
    from core.chat_logger import log_status_kirim
    import telegram_bot  # noqa: F401

    # 1. Pastikan logger httpx berada pada tingkat WARNING
    httpx_logger = logging.getLogger("httpx")
    assert httpx_logger.level == logging.WARNING

    # 2. Catat peristiwa sukses
    rec_sukses = log_status_kirim("test_session_kirim_1", "terkirim", 1)
    assert rec_sukses["type"] == "status_kirim"
    assert rec_sukses["status"] == "terkirim"
    assert rec_sukses["jumlah_percobaan"] == 1
    assert rec_sukses["error_teks"] is None

    # 3. Catat peristiwa gagal
    rec_gagal = log_status_kirim("test_session_kirim_2", "gagal", 3, error_teks="TimedOut error simulated")
    assert rec_gagal["type"] == "status_kirim"
    assert rec_gagal["status"] == "gagal"
    assert rec_gagal["jumlah_percobaan"] == 3
    assert rec_gagal["error_teks"] == "TimedOut error simulated"


def test_putaran25_butir4_persona_nama_r3():
    """Menguji aturan nama Reni dan fakta awal percakapan (Putaran 25 Butir 4)."""
    from services.agentic_tool_engine import (
        PERSONA_NAMA_R3,
        KOMPONEN_R2,
        KOMPONEN_R3,
        build_agent_system_prompt,
        run_agentic_tool,
    )
    from unittest.mock import patch

    # 1. Prompt dengan R2 eksplisit memuat R2, bukan R3
    prompt_r2 = build_agent_system_prompt(persona_nama_r3=False)
    assert "Bila pesan pertama pelanggan hanya salam, balas salamnya dan perkenalkan dirimu sebagai Reni." in prompt_r2
    assert "Perkenalkan dirimu sebagai Reni hanya di awal percakapan" not in prompt_r2

    # 2. Prompt dengan R3 aktif memuat R3, bukan R2
    prompt_r3 = build_agent_system_prompt(persona_nama_r3=True)
    assert "Perkenalkan dirimu sebagai Reni hanya di awal percakapan" in prompt_r3
    assert "Bila pesan pertama pelanggan hanya salam" not in prompt_r3

    # 4. Pengujian fakta awal percakapan:
    # Kasus a: riwayat belum berisi pesan bot -> sisipkan 'Ini awal percakapan; kamu belum memperkenalkan diri.'
    captured_messages_a = []
    def mock_ollama_a(messages, **kwargs):
        captured_messages_a.extend(messages)
        return {"message": {"role": "assistant", "content": "Halo Kak, saya Reni."}}

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama_a):
        run_agentic_tool(
            user_text="Halo",
            history=[],
            persona_nama_r3=True,
        )

    expected_fakta_a = "Ini awal percakapan; kamu belum memperkenalkan diri."
    assert any(m.get("role") == "system" and m.get("content") == expected_fakta_a for m in captured_messages_a)

    # Kasus b: riwayat sudah berisi pesan bot -> sisipkan 'Kamu sudah memperkenalkan diri di percakapan ini.'
    captured_messages_b = []
    def mock_ollama_b(messages, **kwargs):
        captured_messages_b.extend(messages)
        return {"message": {"role": "assistant", "content": "Ada Kak, kami punya Intel NUC."}}

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama_b):
        run_agentic_tool(
            user_text="Ada mini pc?",
            history=[
                {"role": "user", "content": "Halo"},
                {"role": "assistant", "content": "Halo Kak, saya Reni dari ReIn Komputer."}
            ],
            persona_nama_r3=True,
        )

    expected_fakta_b = "Kamu sudah memperkenalkan diri di percakapan ini."
    assert any(m.get("role") == "system" and m.get("content") == expected_fakta_b for m in captured_messages_b)


def test_putaran26_butir1_persona_nama_r3_bawaan_true():
    """Menguji nilai bawaan PERSONA_NAMA_R3 adalah True (Putaran 26 Butir 1)."""
    from services.agentic_tool_engine import PERSONA_NAMA_R3, build_agent_system_prompt
    assert PERSONA_NAMA_R3 is True
    prompt = build_agent_system_prompt()
    assert "Perkenalkan dirimu sebagai Reni hanya di awal percakapan" in prompt
    assert "Bila pesan pertama pelanggan hanya salam" not in prompt


def test_putaran26_butir2_aturan_pribadi_atribut():
    """Menguji kalimat aturan data pribadi dan atribut produk (Putaran 26 Butir 2)."""
    from services.agentic_tool_engine import (
        ATURAN_PRIBADI_ATRIBUT,
        KOMPONEN_T,
        build_agent_system_prompt,
    )

    # 1. Nilai bawaan mati
    assert ATURAN_PRIBADI_ATRIBUT is False

    kalimat_1 = "Kamu tidak punya data pribadi seperti alamat rumah, umur, atau kehidupan di luar pekerjaan, jadi jangan mengarangnya; bila pelanggan menanyakan hal pribadi, tolak dengan sopan dan ramah lalu kembali membantu. Jangan menyebut website, alamat, atau kontak toko yang tidak tertulis di hasil alat."
    kalimat_2 = "Atribut satu produk, misalnya barebone, tangki tinta, ukuran, atau port, tidak berlaku untuk produk lain kecuali tertulis di hasil alat untuk produk itu; bila belum ada, panggil katalog untuk produk itu."

    # 2. Saat mati, kalimat tidak ada di prompt
    prompt_mati = build_agent_system_prompt(aturan_pribadi_atribut=False)
    assert kalimat_1 not in prompt_mati
    assert kalimat_2 not in prompt_mati

    # 3. Saat nyala, kedua kalimat ada di prompt dan berada sebelum KOMPONEN_T
    prompt_nyala = build_agent_system_prompt(aturan_pribadi_atribut=True)
    assert kalimat_1 in prompt_nyala
    assert kalimat_2 in prompt_nyala

    pos_k1 = prompt_nyala.find(kalimat_1)
    pos_k2 = prompt_nyala.find(kalimat_2)
    pos_t = prompt_nyala.find(KOMPONEN_T)
    assert pos_k1 < pos_k2 < pos_t, "Kalimat aturan pribadi & atribut harus berada sebelum komponen T"


def test_putaran26_butir3_kirim_foto():
    """Menguji parameter kirim_foto, skema, hasil alat, dan prompt (Putaran 26 Butir 3)."""
    from services.agent_tools import AGENT_TOOLS_SCHEMA, execute_agent_tool, katalog
    from services.agentic_tool_engine import (
        KIRIM_FOTO_OLEH_LLM,
        KOMPONEN_T,
        build_agent_system_prompt,
    )

    # 1. Konstanta bawaan aktif (Putaran 28 Butir 3a: keputusan Rachmadi)
    assert KIRIM_FOTO_OLEH_LLM is True

    # 2. Skema alat katalog memuat kirim_foto
    katalog_schema = next(t for t in AGENT_TOOLS_SCHEMA if t["function"]["name"] == "katalog")
    props = katalog_schema["function"]["parameters"]["properties"]
    assert "kirim_foto" in props
    assert props["kirim_foto"]["type"] == "boolean"
    assert (
        props["kirim_foto"]["description"]
        == "Isi true bila pelanggan ingin melihat foto produk yang dicari, atau bila menurutmu foto membantu pelanggan; foto hanya terkirim untuk produk yang ada_foto-nya true."
    )

    # 3. Saat kirim_foto_oleh_llm True: kirim_foto true untuk produk berfoto (KB-D10) -> foto_tersedia berisi kode itu
    res_with_photo = katalog(kode_atau_nama="KB-D10", kirim_foto=True, kirim_foto_oleh_llm=True)
    assert res_with_photo.get("foto_tersedia") == ["KB-D10"]
    assert res_with_photo.get("foto_tidak_tersedia") == []

    # 4. produk tanpa foto -> masuk foto_tidak_tersedia (uji dengan mock is_file False)
    from unittest.mock import patch
    with patch("pathlib.Path.is_file", return_value=False):
        res_without_photo = katalog(kode_atau_nama="KB-D06", kirim_foto=True, kirim_foto_oleh_llm=True)
        assert res_without_photo.get("foto_tersedia") == []
        assert res_without_photo.get("foto_tidak_tersedia") == ["KB-D06"]

    # 5. kirim_foto tidak diisi menghasilkan tidak ada foto
    res_no_param = katalog(kode_atau_nama="KB-D10", kirim_foto_oleh_llm=True)
    assert "foto_tersedia" not in res_no_param
    assert "foto_tidak_tersedia" not in res_no_param

    # 6. Uji lewat execute_agent_tool
    res_exec = execute_agent_tool("katalog", {"kode_atau_nama": "KB-D10", "kirim_foto": True}, kirim_foto_oleh_llm=True)
    assert res_exec.get("foto_tersedia") == ["KB-D10"]

    # 7. Uji kalimat prompt P29 Butir 1b
    kalimat_foto = (
        "Foto produk terkirim hanya untuk produk di foto_tersedia yang namanya kamu tulis di balasan; "
        "jangan menulis bahwa foto sudah terkirim untuk produk yang tidak kamu sebut namanya. "
        "Bila pelanggan bilang foto belum muncul, panggil katalog lagi dengan kirim_foto untuk produk itu dan sebut namanya; "
        "jangan menyebut kendala teknis."
    )
    prompt_mati = build_agent_system_prompt(kirim_foto_oleh_llm=False)
    assert kalimat_foto not in prompt_mati

    prompt_nyala = build_agent_system_prompt(kirim_foto_oleh_llm=True)
    assert kalimat_foto in prompt_nyala
    pos_foto = prompt_nyala.find(kalimat_foto)
    pos_t = prompt_nyala.find(KOMPONEN_T)
    assert pos_foto < pos_t, "Kalimat aturan kirim foto harus sebelum komponen T"


def test_putaran28_butir3_foto_diputuskan_reni():
    """Menguji pemilihan foto sebagai irisan murni produk disebut dan foto_tersedia (Putaran 28 Butir 3, diperbarui Putaran 29 Butir 1)."""
    from services.agentic_tool_engine import (
        KIRIM_FOTO_OLEH_LLM,
        pilih_foto_yang_akan_dikirim,
        get_active_catalog
    )
    assert KIRIM_FOTO_OLEH_LLM is True, "Bawaan KIRIM_FOTO_OLEH_LLM harus True"

    cat = get_active_catalog()

    # 1. Irisan: hasil pencarian ada 2 foto (KB-D10, KB-D11), tapi balasan hanya menyebut KB-D10
    foto_raw = ["KB-D10", "KB-D11"]
    prods_disebut = [{"kode": "KB-D10", "nama": "HP Slim Desktop S01"}]
    hasil = pilih_foto_yang_akan_dikirim(foto_tersedia=foto_raw, produk_disebut=prods_disebut)
    assert hasil == ["KB-D10"], "Produk yang tidak disebut di balasan akhir tidak boleh dikirim fotonya"

    # 2. Irisan berbasis reply_text jika produk_disebut kosong
    reply_teks = "Kami menyarankan Lenovo ThinkCentre Neo 50s (KB-D10) untuk kebutuhan Anda."
    hasil_teks = pilih_foto_yang_akan_dikirim(
        foto_tersedia=foto_raw,
        produk_disebut=[],
        reply_text=reply_teks,
        catalog_by_code=cat.by_code
    )
    assert hasil_teks == ["KB-D10"]

    # 3. Produk hasil pencarian tidak disebut sama sekali -> 0 foto dikirim
    reply_kosong = "Maaf stok untuk spesifikasi tersebut saat ini sedang habis."
    hasil_nol = pilih_foto_yang_akan_dikirim(
        foto_tersedia=foto_raw,
        produk_disebut=[],
        reply_text=reply_kosong,
        catalog_by_code=cat.by_code
    )
    assert hasil_nol == []

    # 4. foto_tersedia kosong -> 0 foto dikirim
    assert pilih_foto_yang_akan_dikirim(foto_tersedia=[], produk_disebut=prods_disebut) == []


def test_putaran27_butir2_sembunyikan_kirim_foto():
    """Menguji penyembunyian kirim_foto saat KIRIM_FOTO_OLEH_LLM False (Putaran 27 Butir 2)."""
    from services.agent_tools import get_agent_tools_schema, katalog, execute_agent_tool

    # 1. Saat False (bawaan): parameter kirim_foto tidak ada di skema yang dikirim ke model
    schema_false = get_agent_tools_schema(kirim_foto_oleh_llm=False)
    katalog_schema_false = next(t for t in schema_false if t["function"]["name"] == "katalog")
    assert "kirim_foto" not in katalog_schema_false["function"]["parameters"]["properties"]

    # 2. Saat False: hasil katalog tidak memuat foto_tersedia / foto_tidak_tersedia meski kirim_foto=True
    res_false = katalog(kode_atau_nama="KB-D10", kirim_foto=True, kirim_foto_oleh_llm=False)
    assert "foto_tersedia" not in res_false
    assert "foto_tidak_tersedia" not in res_false

    res_search_false = katalog(kategori="laptop", kirim_foto=True, kirim_foto_oleh_llm=False)
    assert "foto_tersedia" not in res_search_false
    assert "foto_tidak_tersedia" not in res_search_false

    # 3. Saat True: skema memuat kirim_foto dan hasil memuat foto_tersedia (perilaku P26 tetap)
    schema_true = get_agent_tools_schema(kirim_foto_oleh_llm=True)
    katalog_schema_true = next(t for t in schema_true if t["function"]["name"] == "katalog")
    assert "kirim_foto" in katalog_schema_true["function"]["parameters"]["properties"]

    res_true = katalog(kode_atau_nama="KB-D10", kirim_foto=True, kirim_foto_oleh_llm=True)
    assert res_true.get("foto_tersedia") == ["KB-D10"]
    assert res_true.get("foto_tidak_tersedia") == []



def test_putaran27_butir1_katalog_sql():
    """Unit test SQL langsung untuk pencarian katalog berbasis query SQL (Putaran 27 Butir 1)."""
    import sqlite3
    from services.agent_tools import KATALOG_SQL, _get_catalog_db_path, katalog, execute_agent_tool

    # 1. Flag KATALOG_SQL bernilai True secara bawaan
    assert KATALOG_SQL is True

    # 2. Path database aktif sama dengan yang dipakai db/catalog_service
    db_path = _get_catalog_db_path()
    assert "catalog.db" in db_path
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 3. Termurah & Termahal per Kategori
    for cat in ["laptop", "desktop", "monitor", "printer"]:
        cur.execute("SELECT kode, CAST(harga_idr AS INTEGER) FROM products WHERE LOWER(kategori) = ? ORDER BY CAST(harga_idr AS INTEGER) ASC LIMIT 1", (cat,))
        expected_min = cur.fetchone()[0]
        cur.execute("SELECT kode, CAST(harga_idr AS INTEGER) FROM products WHERE LOWER(kategori) = ? ORDER BY CAST(harga_idr AS INTEGER) DESC LIMIT 1", (cat,))
        expected_max = cur.fetchone()[0]

        res_min = katalog(kategori=cat, urutan="termurah")
        assert res_min["status"] == "sukses"
        assert res_min["urutan"] == "termurah"
        assert res_min["produk"][0]["kode"] == expected_min

        res_max = katalog(kategori=cat, urutan="termahal")
        assert res_max["status"] == "sukses"
        assert res_max["urutan"] == "termahal"
        assert res_max["produk"][0]["kode"] == expected_max

    # 4. Termurah & Termahal per Merek
    test_brands = ["ASUS", "Acer", "Apple", "Lenovo", "HP", "MSI", "Epson"]
    for b in test_brands:
        cur.execute("SELECT kode FROM products WHERE LOWER(brand) = ? ORDER BY CAST(harga_idr AS INTEGER) ASC LIMIT 1", (b.lower(),))
        expected_min = cur.fetchone()[0]
        cur.execute("SELECT kode FROM products WHERE LOWER(brand) = ? ORDER BY CAST(harga_idr AS INTEGER) DESC LIMIT 1", (b.lower(),))
        expected_max = cur.fetchone()[0]

        res_min = katalog(merek=b, urutan="termurah")
        assert res_min["produk"][0]["kode"] == expected_min

        res_max = katalog(merek=b, urutan="termahal")
        assert res_max["produk"][0]["kode"] == expected_max

    # 5. Laptop gpu_dedicated termurah -> KB-L26 (HP Victus 15-fb0009AX, Rp10.299.000)
    cur.execute("""
        SELECT kode FROM products 
        WHERE LOWER(kategori) = 'laptop' AND gpu_dedicated = 1 
        ORDER BY CAST(harga_idr AS INTEGER) ASC LIMIT 1
    """)
    expected_gpu_min = cur.fetchone()[0]
    assert expected_gpu_min == "KB-L26"

    res_gpu = katalog(kategori="laptop", gpu_dedicated=True, urutan="termurah")
    assert res_gpu["status"] == "sukses"
    assert res_gpu["produk"][0]["kode"] == "KB-L26"
    assert res_gpu["produk"][0]["harga_idr"] == 10299000

    # 6. Laptop ram_min_gb=16 termurah -> KB-L21 (MSI Modern 14 C12M, Rp8.499.000)
    cur.execute("""
        SELECT kode FROM products 
        WHERE LOWER(kategori) = 'laptop' AND CAST(ram_gb AS INTEGER) >= 16 
        ORDER BY CAST(harga_idr AS INTEGER) ASC LIMIT 1
    """)
    expected_ram_min = cur.fetchone()[0]
    assert expected_ram_min == "KB-L21"

    res_ram = katalog(kategori="laptop", ram_min_gb=16, urutan="termurah")
    assert res_ram["status"] == "sukses"
    assert res_ram["produk"][0]["kode"] == "KB-L21"
    assert res_ram["produk"][0]["harga_idr"] == 8499000

    # 7. Gabungan Merek + Urutan
    cur.execute("SELECT kode FROM products WHERE LOWER(brand) = 'acer' ORDER BY CAST(harga_idr AS INTEGER) ASC LIMIT 1")
    exp_acer_min = cur.fetchone()[0]
    res_acer_min = katalog(merek="Acer", urutan="termurah")
    assert res_acer_min["produk"][0]["kode"] == exp_acer_min

    cur.execute("SELECT kode FROM products WHERE LOWER(brand) = 'acer' ORDER BY CAST(harga_idr AS INTEGER) DESC LIMIT 1")
    exp_acer_max = cur.fetchone()[0]
    res_acer_max = katalog(merek="Acer", urutan="termahal")
    assert res_acer_max["produk"][0]["kode"] == exp_acer_max

    cur.execute("SELECT kode FROM products WHERE LOWER(kategori) = 'laptop' AND (LOWER(brand) LIKE '%asus%' OR LOWER(nama) LIKE '%asus%') ORDER BY CAST(harga_idr AS INTEGER) ASC LIMIT 1")
    exp_asus_lap = cur.fetchone()[0]
    res_asus_lap = katalog(kategori="laptop", merek="Asus", urutan="termurah")
    assert res_asus_lap["produk"][0]["kode"] == exp_asus_lap

    # 8. Urutan kosong = keluaran sama persis dengan jalur lama
    for cat in ["laptop", "desktop", "monitor", "printer"]:
        res_sql = katalog(kategori=cat, katalog_sql=True)
        res_old = katalog(kategori=cat, katalog_sql=False)
        assert res_sql["total_cocok"] == res_old["total_cocok"]
        assert [p["kode"] for p in res_sql["produk"]] == [p["kode"] for p in res_old["produk"]]

    # Periksa kasus pencarian kata kunci dengan urutan kosong
    res_kw_sql = katalog(kata_kunci="oled", katalog_sql=True)
    res_kw_old = katalog(kata_kunci="oled", katalog_sql=False)
    assert res_kw_sql["total_cocok"] == res_kw_old["total_cocok"]
    assert [p["kode"] for p in res_kw_sql["produk"]] == [p["kode"] for p in res_kw_old["produk"]]

    # Periksa kasus budget_max dengan urutan kosong
    res_b_sql = katalog(kategori="laptop", budget_max=7000000, katalog_sql=True)
    res_b_old = katalog(kategori="laptop", budget_max=7000000, katalog_sql=False)
    assert res_b_sql["total_cocok"] == res_b_old["total_cocok"]
    assert [p["kode"] for p in res_b_sql["produk"]] == [p["kode"] for p in res_b_old["produk"]]

    # 9. Uji lewat execute_agent_tool
    res_exec = execute_agent_tool("katalog", {
        "kategori": "laptop",
        "gpu_dedicated": True,
        "urutan": "termurah"
    })
    assert res_exec["produk"][0]["kode"] == "KB-L26"

    conn.close()


def test_putaran27_butir4a_unit_sql():
    """Unit test SQL lengkap sesuai spesifikasi Butir 4a (Putaran 27)."""
    import sqlite3
    from services.agent_tools import _get_catalog_db_path, katalog

    db_path = _get_catalog_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. Urutan termurah/termahal untuk 4 kategori (laptop, desktop, monitor, printer)
    categories = ["laptop", "desktop", "monitor", "printer"]
    for cat in categories:
        cur.execute("SELECT kode, CAST(harga_idr AS INTEGER) FROM products WHERE LOWER(kategori) = ? ORDER BY CAST(harga_idr AS INTEGER) ASC LIMIT 1", (cat,))
        exp_min_code, exp_min_price = cur.fetchone()
        cur.execute("SELECT kode, CAST(harga_idr AS INTEGER) FROM products WHERE LOWER(kategori) = ? ORDER BY CAST(harga_idr AS INTEGER) DESC LIMIT 1", (cat,))
        exp_max_code, exp_max_price = cur.fetchone()

        res_min = katalog(kategori=cat, urutan="termurah")
        assert res_min["status"] == "sukses"
        assert res_min["urutan"] == "termurah"
        assert res_min["produk"][0]["kode"] == exp_min_code
        assert res_min["produk"][0]["harga_idr"] == exp_min_price

        res_max = katalog(kategori=cat, urutan="termahal")
        assert res_max["status"] == "sukses"
        assert res_max["urutan"] == "termahal"
        assert res_max["produk"][0]["kode"] == exp_max_code
        assert res_max["produk"][0]["harga_idr"] == exp_max_price

    # 2. Filter gabungan: laptop ram>=16 + gpu_dedicated=true + ssd>=512 + urutan termurah
    cur.execute("""
        SELECT kode, CAST(harga_idr AS INTEGER) FROM products 
        WHERE LOWER(kategori) = 'laptop' 
          AND CAST(ram_gb AS INTEGER) >= 16 
          AND gpu_dedicated = 1 
          AND CAST(storage_ssd_gb AS INTEGER) >= 512 
        ORDER BY CAST(harga_idr AS INTEGER) ASC
    """)
    rows_combo = cur.fetchall()
    exp_combo_codes = [r[0] for r in rows_combo]
    assert len(exp_combo_codes) >= 6
    assert exp_combo_codes[0] == "KB-L26"

    res_combo = katalog(
        kategori="laptop",
        ram_min_gb=16,
        gpu_dedicated=True,
        ssd_min_gb=512,
        urutan="termurah"
    )
    assert res_combo["status"] == "sukses"
    assert res_combo["urutan"] == "termurah"
    assert res_combo["total_cocok"] == len(exp_combo_codes)
    assert [p["kode"] for p in res_combo["produk"]] == exp_combo_codes[:10]

    # 3. Filter layar: monitor layar_min 27 + refresh_min 144
    cur.execute("""
        SELECT kode, CAST(harga_idr AS INTEGER) FROM products 
        WHERE LOWER(kategori) = 'monitor' 
          AND CAST(screen_inch AS REAL) >= 27 
          AND CAST(refresh_hz AS INTEGER) >= 144 
        ORDER BY CAST(harga_idr AS INTEGER) ASC
    """)
    rows_monitor = cur.fetchall()
    exp_mon_codes = [r[0] for r in rows_monitor]
    assert len(exp_mon_codes) >= 2
    assert "KB-M02" in exp_mon_codes

    res_monitor = katalog(
        kategori="monitor",
        layar_min_inci=27.0,
        refresh_min_hz=144,
        urutan="termurah"
    )
    assert res_monitor["status"] == "sukses"
    assert res_monitor["total_cocok"] == len(exp_mon_codes)
    assert [p["kode"] for p in res_monitor["produk"]] == exp_mon_codes[:10]

    # 4. budget_max tetap menghasilkan "melebihi_budget" bila tidak ada yang cocok
    res_over = katalog(kategori="laptop", budget_max=2000000)
    assert res_over["status"] == "melebihi_budget"
    assert res_over["total_cocok"] == 0
    assert len(res_over["produk_termurah"]) > 0
    assert res_over["produk_termurah"][0]["harga_idr"] > 2000000


    # 5. Verifikasi hasil urutan SQL sama dengan ground truth manual dari database aktif
    for cat in ["laptop", "desktop", "monitor", "printer"]:
        cur.execute("SELECT kode FROM products WHERE LOWER(kategori) = ? ORDER BY CAST(harga_idr AS INTEGER) ASC LIMIT 1", (cat,))
        expected_min_code = cur.fetchone()[0]
        cur.execute("SELECT kode FROM products WHERE LOWER(kategori) = ? ORDER BY CAST(harga_idr AS INTEGER) DESC LIMIT 1", (cat,))
        expected_max_code = cur.fetchone()[0]

        res_min = katalog(kategori=cat, urutan="termurah")
        assert res_min["produk"][0]["kode"] == expected_min_code

        res_max = katalog(kategori=cat, urutan="termahal")
        assert res_max["produk"][0]["kode"] == expected_max_code

    conn.close()


def test_putaran28_butir6_aturan_layanan_p28():
    """Menguji flag ATURAN_LAYANAN_P28 default False, dan injeksi 5 kalimat jika True (Putaran 28 Butir 6)."""
    from services.agentic_tool_engine import (
        ATURAN_LAYANAN_P28,
        build_agent_system_prompt,
        KOMPONEN_T
    )

    # 1. Bawaan harus False
    assert ATURAN_LAYANAN_P28 is False

    # 2. Bila False (default), 5 kalimat tidak ada di prompt
    prompt_default = build_agent_system_prompt()
    lima_kalimat = [
        "Bila pelanggan bertanya apakah toko menjual sesuatu atau meminta rekomendasi, panggil katalog dan sebut produknya; panduan boleh ditambahkan singkat.",
        "Bila hasil alat tidak memuat informasi yang ditanyakan, katakan terus terang bahwa datanya belum tersedia; jangan menyuruh pelanggan melihat dokumen, tautan, atau tampilan lain.",
        "Bila pernyataan pelanggan benar, akui; bila kamu salah paham, minta maaf singkat lalu jawab pertanyaannya.",
        "Jangan menyarankan menaikkan budget bila pelanggan tidak menyebut budget.",
        "Sebut dirimu chatbot hanya bila pelanggan bertanya apakah sedang berbicara dengan manusia atau bot."
    ]
    for k in lima_kalimat:
        assert k not in prompt_default

    # 3. Bila True, seluruh 5 kalimat ada apa adanya dan terletak sebelum KOMPONEN_T
    prompt_p28 = build_agent_system_prompt(aturan_layanan_p28=True)
    for k in lima_kalimat:
        assert k in prompt_p28

    # Pastikan letaknya di akhir SISA sebelum KOMPONEN_T
    idx_kalimat5 = prompt_p28.index(lima_kalimat[-1])
    idx_t = prompt_p28.index(KOMPONEN_T)
    assert idx_kalimat5 < idx_t


def test_putaran29_butir3_catatan_pengetahuan():
    """Menguji flag CATATAN_PENGETAHUAN_KATALOG dan catatan hasil alat pengetahuan (Putaran 29 Butir 3 & Putaran 30 Butir 2)."""
    from services.agent_tools import CATATAN_PENGETAHUAN_KATALOG, pengetahuan, execute_agent_tool

    # 1. Bawaan flag (sejak Putaran 30 adalah True)
    assert CATATAN_PENGETAHUAN_KATALOG is True

    teks_catatan = "Ini panduan, bukan daftar produk. Bila pelanggan bertanya apakah toko menjual sesuatu atau meminta rekomendasi, panggil katalog juga sebelum menjawab."

    # 2. Bila False secara eksplisit, catatan TIDAK muncul di hasil pengetahuan
    res_false = pengetahuan("rekomendasi laptop desain", catatan_pengetahuan_katalog=False)
    assert "catatan" not in res_false

    # 3. Bila True atau default (Putaran 30), catatan muncul apa adanya di hasil pengetahuan
    res_default = pengetahuan("rekomendasi laptop desain")
    assert res_default.get("catatan") == teks_catatan

    res_true = pengetahuan("rekomendasi laptop desain", catatan_pengetahuan_katalog=True)
    assert res_true.get("catatan") == teks_catatan

    # 4. Uji via execute_agent_tool
    res_exec_false = execute_agent_tool("pengetahuan", {"pertanyaan": "laptop desain"}, catatan_pengetahuan_katalog=False)
    assert "catatan" not in res_exec_false

    res_exec_true = execute_agent_tool("pengetahuan", {"pertanyaan": "laptop desain"}, catatan_pengetahuan_katalog=True)
    assert res_exec_true.get("catatan") == teks_catatan


def test_putaran29_butir4_produk_terdekat():
    """Menguji fallback produk_terdekat saat filter spek menghasilkan 0 hasil (Putaran 29 Butir 4 & Putaran 30 Butir 1)."""
    from services.agent_tools import PRODUK_TERDEKAT, katalog, execute_agent_tool

    # 1. Bawaan flag (sejak Putaran 30 adalah True)
    assert PRODUK_TERDEKAT is True

    teks_catatan = (
        "Tidak ada produk yang memenuhi filter ini. Sampaikan apa adanya; "
        "bila relevan, tawarkan produk_terdekat dan sebut perbedaannya. "
        "Jangan menyarankan menaikkan budget bila pelanggan tidak menyebut budget."
    )

    # 2. Saat False secara eksplisit: katalog(kategori="desktop", ram_min_gb=32) memberi 0 hasil tanpa produk_terdekat
    res_false = katalog(kategori="desktop", ram_min_gb=32, produk_terdekat=False)
    assert res_false.get("total_cocok") == 0
    assert "produk_terdekat" not in res_false
    assert "catatan" not in res_false

    # 3. Saat True atau default: katalog(kategori="desktop", ram_min_gb=32) memberi 0 hasil + produk_terdekat desktop RAM tertinggi
    res_true = katalog(kategori="desktop", ram_min_gb=32, produk_terdekat=True)
    assert res_true.get("total_cocok") == 0
    assert "produk_terdekat" in res_true
    assert len(res_true["produk_terdekat"]) <= 3
    assert res_true.get("catatan") == teks_catatan

    res_default = katalog(kategori="desktop", ram_min_gb=32)
    assert res_default.get("total_cocok") == 0
    assert "produk_terdekat" in res_default

    # Verifikasi produk terdekat adalah desktop dengan RAM tertinggi di katalog (16 GB)
    codes_terdekat = [p["kode"] for p in res_true["produk_terdekat"]]
    assert codes_terdekat == ["KB-D15", "KB-D13", "KB-D08"]

    # 4. Uji via execute_agent_tool
    res_exec = execute_agent_tool("katalog", {"kategori": "desktop", "ram_min_gb": 32}, produk_terdekat=True)
    assert res_exec.get("total_cocok") == 0
    assert "produk_terdekat" in res_exec
    assert [p["kode"] for p in res_exec["produk_terdekat"]] == ["KB-D15", "KB-D13", "KB-D08"]


def test_putaran30_default_flags():
    """Menguji bahwa default produksi kedua flag adalah True (Putaran 30 Butir 1 & 2)."""
    from services.agent_tools import PRODUK_TERDEKAT, CATATAN_PENGETAHUAN_KATALOG, pengetahuan, katalog
    from services.agentic_tool_engine import (
        PRODUK_TERDEKAT as ENGINE_PRODUK_TERDEKAT,
        CATATAN_PENGETAHUAN_KATALOG as ENGINE_CATATAN_PENGETAHUAN_KATALOG,
        build_agent_system_prompt,
    )

    assert PRODUK_TERDEKAT is True
    assert CATATAN_PENGETAHUAN_KATALOG is True
    assert ENGINE_PRODUK_TERDEKAT is True
    assert ENGINE_CATATAN_PENGETAHUAN_KATALOG is True

    # Panggilan default tanpa argumen flag
    res_p = pengetahuan("rekomendasi laptop desain")
    assert "catatan" in res_p
    assert res_p["catatan"] == (
        "Ini panduan, bukan daftar produk. Bila pelanggan bertanya apakah toko menjual sesuatu atau meminta rekomendasi, "
        "panggil katalog juga sebelum menjawab."
    )

    res_k = katalog(kategori="desktop", ram_min_gb=32)
    assert res_k.get("total_cocok") == 0
    assert "produk_terdekat" in res_k
    assert [p["kode"] for p in res_k["produk_terdekat"]] == ["KB-D15", "KB-D13", "KB-D08"]

    # Verifikasi kalimat tegas di sistem prompt
    prompt = build_agent_system_prompt()
    aturan_tegas = (
        "Bila jawabanmu menyebut kategori atau profil kebutuhan produk, kamu wajib memanggil katalog pada giliran "
        "yang sama sebelum menjawab, memakai kata kunci atau tag kategori dari profil yang cocok. "
        "Jangan menjawab rekomendasi produk hanya dari panduan tanpa memeriksa katalog."
    )
    assert aturan_tegas in prompt


def test_putaran30_pengaman_katalog_otomatis():
    """Menguji pengaman pemanggilan katalog otomatis jika pengetahuan dipanggil tapi katalog tidak dipanggil (Putaran 30 Butir 2)."""
    from unittest.mock import patch
    from services.agentic_tool_engine import run_agentic_tool

    # 1. Kasus A: Model memanggil pengetahuan (dengan catatan), tapi TIDAK memanggil katalog.
    # Pengaman harus otomatis memanggil katalog satu kali, dan model merevisi balasan.
    llm_call_count = 0
    def mock_ollama_tanpa_katalog(messages, **kwargs):
        nonlocal llm_call_count
        llm_call_count += 1
        tools = kwargs.get("tools")
        if tools and llm_call_count == 1:
            # Round 1: Model hanya memanggil pengetahuan
            return {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "pengetahuan",
                                "arguments": {"pertanyaan": "desain 3D"}
                            }
                        }
                    ]
                }
            }
        elif tools and llm_call_count == 2:
            # Round 2: Model menjawab tanpa memanggil katalog sama sekali
            return {
                "message": {
                    "role": "assistant",
                    "content": "Untuk kebutuhan desain 3D, disarankan PC desktop dengan CPU Core i7/Ryzen 7 dan RAM minimal 16GB."
                }
            }
        else:
            # Panggilan revisi pengaman (tools=None)
            return {
                "message": {
                    "role": "assistant",
                    "content": "Untuk desain 3D, kami punya PC Gaming ROG Strix G15CF (Core i7, RAM 16GB) seharga Rp 22.000.000."
                }
            }

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama_tanpa_katalog):
        res_a = run_agentic_tool(
            user_text="Kalo desktop untuk desain 3D, apa rekomendasimu?",
            history=[],
        )

    # Verifikasi pengaman otomatis berjalan
    tool_calls_a = res_a.get("tool_calls", [])
    auto_guard_calls = [tc for tc in tool_calls_a if tc.get("pengaman_otomatis") is True]
    assert len(auto_guard_calls) == 1, f"Harus ada tepat 1 panggilan katalog dari pengaman otomatis: {tool_calls_a}"
    assert auto_guard_calls[0]["nama"] == "katalog"
    assert auto_guard_calls[0]["argumen"].get("kategori") == "desktop"
    assert "ROG Strix" in res_a["reply"]

    # 2. Kasus B: Model SUDAH memanggil katalog secara manual.
    # Pengaman TIDAK BOLEH memanggil katalog untuk kedua kalinya.
    llm_call_count_b = 0
    def mock_ollama_dengan_katalog(messages, **kwargs):
        nonlocal llm_call_count_b
        llm_call_count_b += 1
        tools = kwargs.get("tools")
        if tools and llm_call_count_b == 1:
            # Round 1: Model memanggil pengetahuan dan katalog
            return {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "pengetahuan",
                                "arguments": {"pertanyaan": "desain 3D"}
                            }
                        },
                        {
                            "function": {
                                "name": "katalog",
                                "arguments": {"kata_kunci": "desain 3D", "kategori": "desktop"}
                            }
                        }
                    ]
                }
            }
        elif tools and llm_call_count_b == 2:
            # Round 2: Model menjawab akhir
            return {
                "message": {
                    "role": "assistant",
                    "content": "Rekomendasi desktop untuk desain 3D adalah PC Gaming ROG Strix G15CF."
                }
            }
        else:
            return {
                "message": {
                    "role": "assistant",
                    "content": "Revisi tidak diharapkan terjadi."
                }
            }

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama_dengan_katalog):
        res_b = run_agentic_tool(
            user_text="Kalo desktop untuk desain 3D, apa rekomendasimu?",
            history=[],
        )

    tool_calls_b = res_b.get("tool_calls", [])
    auto_guard_calls_b = [tc for tc in tool_calls_b if tc.get("pengaman_otomatis") is True]
    assert len(auto_guard_calls_b) == 0, "Pengaman tidak boleh memanggil katalog jika katalog sudah dipanggil oleh model!"
    katalog_calls_b = [tc for tc in tool_calls_b if tc.get("nama") == "katalog"]
    assert len(katalog_calls_b) == 1, "Harus hanya ada 1 panggilan katalog (dari LLM)"

    # 3. Kasus C: User query tidak memuat kata kategori ('Kan buat AI lokal?'),
    # tetapi session_state memiliki kategori='laptop'.
    # Pengaman harus mewarisi kategori='laptop' dari sesi agar tidak terjadi fallback lintas kategori (anomali Intel NUC).
    llm_call_count_c = 0
    def mock_ollama_waris_kategori(messages, **kwargs):
        nonlocal llm_call_count_c
        llm_call_count_c += 1
        tools = kwargs.get("tools")
        if tools and llm_call_count_c == 1:
            return {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "pengetahuan",
                                "arguments": {"pertanyaan": "persyaratan hardware untuk AI lokal"}
                            }
                        }
                    ]
                }
            }
        elif tools and llm_call_count_c == 2:
            return {
                "message": {
                    "role": "assistant",
                    "content": "Untuk AI lokal disarankan GPU Nvidia dengan VRAM besar."
                }
            }
        else:
            return {
                "message": {
                    "role": "assistant",
                    "content": "Rekomendasi laptop untuk AI lokal adalah Acer Nitro V 15."
                }
            }

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama_waris_kategori):
        res_c = run_agentic_tool(
            user_text="Kan buat AI lokal?",
            history=[],
            session_state={"category": "laptop"},
        )

    tool_calls_c = res_c.get("tool_calls", [])
    auto_guard_calls_c = [tc for tc in tool_calls_c if tc.get("pengaman_otomatis") is True]
    assert len(auto_guard_calls_c) == 1
    assert auto_guard_calls_c[0]["argumen"].get("kategori") == "laptop", "Pengaman wajib mewarisi kategori='laptop' dari session_state!"

    # 4. Kasus D: Pertanyaan komplain / klarifikasi ('Kenapa juga ditawari intel NUC?')
    # Pengaman TIDAK BOLEH memicu katalog otomatis baru.
    llm_call_count_d = 0
    def mock_ollama_komplain(messages, **kwargs):
        nonlocal llm_call_count_d
        llm_call_count_d += 1
        tools = kwargs.get("tools")
        if tools and llm_call_count_d == 1:
            return {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "pengetahuan",
                                "arguments": {"pertanyaan": "perbedaan mini pc dan laptop"}
                            }
                        }
                    ]
                }
            }
        else:
            return {
                "message": {
                    "role": "assistant",
                    "content": "Mohon maaf atas kekeliruan tadi, saya akan fokus hanya pada laptop."
                }
            }

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama_komplain):
        res_d = run_agentic_tool(
            user_text="Kenapa juga ditawari intel NUC?",
            history=[],
            session_state={"category": "laptop"},
        )

    tool_calls_d = res_d.get("tool_calls", [])
    auto_guard_calls_d = [tc for tc in tool_calls_d if tc.get("pengaman_otomatis") is True]
    assert len(auto_guard_calls_d) == 0, "Pengaman tidak boleh terpicu pada pertanyaan komplain/klarifikasi!"

    # 5. Kasus E: Pertanyaan kelengkapan / isi paket (misal: "Mac mini sudah termasuk monitor?")
    # Pengaman TIDAK BOLEH memanggil katalog otomatis
    llm_call_count_e = 0
    def mock_ollama_kelengkapan(messages, **kwargs):
        nonlocal llm_call_count_e
        llm_call_count_e += 1
        tools = kwargs.get("tools")
        if tools and llm_call_count_e == 1:
            return {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "pengetahuan",
                                "arguments": {"pertanyaan": "apakah mac mini sudah termasuk monitor"}
                            }
                        }
                    ]
                }
            }
        else:
            return {
                "message": {
                    "role": "assistant",
                    "content": "Berdasarkan kebijakan toko, paket Mac mini belum termasuk monitor Kak."
                }
            }

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama_kelengkapan):
        res_e = run_agentic_tool(
            user_text="Mac mini sudah termasuk monitor?",
            history=[],
            session_state={"category": "desktop"},
        )

    tool_calls_e = res_e.get("tool_calls", [])
    auto_guard_calls_e = [tc for tc in tool_calls_e if tc.get("pengaman_otomatis") is True]
    assert len(auto_guard_calls_e) == 0, "Pengaman tidak boleh terpicu pada pertanyaan kelengkapan/isi paket!"

    # 6. Kasus F: Evaluasi fitur/kecocokan produk yang sedang aktif dibahas (misal: "Bisa untuk coding gak?")
    # Pengaman TIDAK BOLEH memanggil katalog otomatis
    llm_call_count_f = 0
    def mock_ollama_evaluasi(messages, **kwargs):
        nonlocal llm_call_count_f
        llm_call_count_f += 1
        tools = kwargs.get("tools")
        if tools and llm_call_count_f == 1:
            return {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "pengetahuan",
                                "arguments": {"pertanyaan": "kebutuhan coding"}
                            }
                        }
                    ]
                }
            }
        else:
            return {
                "message": {
                    "role": "assistant",
                    "content": "Untuk coding ringan sampai menengah, laptop MSI Modern 14 C12M dengan RAM 16GB ini sudah sangat memadai Kak."
                }
            }

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama_evaluasi):
        res_f = run_agentic_tool(
            user_text="Bisa untuk coding gak?",
            history=[{"role": "user", "content": "Minta spek MSI"}, {"role": "assistant", "content": "MSI Modern 14 C12M RAM 16GB"}],
            session_state={
                "category": "laptop",
                "mentioned_products": [{"kode": "KB-L21", "nama": "MSI Modern 14 C12M"}]
            },
        )

    tool_calls_f = res_f.get("tool_calls", [])
    auto_guard_calls_f = [tc for tc in tool_calls_f if tc.get("pengaman_otomatis") is True]
    assert len(auto_guard_calls_f) == 0, "Pengaman tidak boleh terpicu pada evaluasi fitur produk yang sedang dibahas!"




def test_putaran29_butir2_gambar_kandidat_terpasang():
    """Menguji bahwa keempat image_file baru menunjuk berkas png yang ada dan berkas jpg lama telah dihapus (Putaran 29 Butir 2 & 5a)."""
    import os
    import sqlite3
    from services.agent_tools import _get_catalog_db_path

    db_path = _get_catalog_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    new_items = ["KB-L12", "KB-D15", "KB-L23", "KB-L29"]
    for code in new_items:
        cur.execute("SELECT image_file FROM products WHERE kode = ?", (code,))
        row = cur.fetchone()
        assert row is not None, f"Produk {code} harus ada di DB"
        img_f = row[0]
        assert img_f == f"data/images/{code}.png", f"image_file {code} harus .png, bukan {img_f}"
        assert os.path.isfile(img_f), f"Berkas gambar {img_f} harus ada di disk"

        # Berkas lama .jpg harus sudah terhapus
        old_jpg = f"data/images/{code}.jpg"
        assert not os.path.exists(old_jpg), f"Berkas lama {old_jpg} harus sudah dihapus dari data/images/"

    # KB-P10 tetap memakai gambar yang terpasang sekarang (.png)
    cur.execute("SELECT image_file FROM products WHERE kode = 'KB-P10'")
    row_p10 = cur.fetchone()
    assert row_p10 is not None
    assert row_p10[0] == "data/images/KB-P10.png"
    assert os.path.isfile(row_p10[0])
    conn.close()


def test_putaran29_butir1_nama_field_foto_tersedia():
    """Menguji bahwa nama field baru 'foto_tersedia' dipakai di semua modul (Putaran 29 Butir 1 & 5a)."""
    import inspect
    from services.agent_tools import katalog, execute_agent_tool
    from services.agentic_tool_engine import pilih_foto_yang_akan_dikirim, run_agentic_tool

    # 1. Output katalog memuat foto_tersedia saat kirim_foto=True
    res = katalog(kode_atau_nama="KB-D10", kirim_foto=True, kirim_foto_oleh_llm=True)
    assert "foto_tersedia" in res
    assert "foto_akan_dikirim" not in res
    assert res["foto_tersedia"] == ["KB-D10"]

    # 2. Output execute_agent_tool memuat foto_tersedia
    res_exec = execute_agent_tool("katalog", {"kode_atau_nama": "KB-D10", "kirim_foto": True}, kirim_foto_oleh_llm=True)
    assert "foto_tersedia" in res_exec
    assert "foto_akan_dikirim" not in res_exec
    assert res_exec["foto_tersedia"] == ["KB-D10"]

    # 3. Signature pilih_foto_yang_akan_dikirim memiliki parameter foto_tersedia
    sig = inspect.signature(pilih_foto_yang_akan_dikirim)
    assert "foto_tersedia" in sig.parameters

    # 4. telegram_bot membaca foto_tersedia
    with open("telegram_bot.py", "r", encoding="utf-8") as f:
        tg_code = f.read()
    assert 'res.get("foto_tersedia"' in tg_code


def test_katalog_tag_expansion_ai_ml():
    """Menguji bahwa kata kunci tag ai_ml/programming pada laptop mencocokkan laptop dengan GPU RTX / RAM tinggi."""
    from services.agent_tools import katalog

    res = katalog(kategori="laptop", kata_kunci="ai_ml, programming")
    assert res.get("status") == "sukses"
    assert res.get("total_cocok", 0) > 0
    top_codes = [p["kode"] for p in res.get("produk", [])[:3]]
    # Laptop yang cocok harus laptop performa tinggi/RTX, bukan Celeron KB-L14 atau N100 KB-L11
    assert "KB-L14" not in top_codes
    assert "KB-L11" not in top_codes
    assert any(c in top_codes for c in ["KB-L24", "KB-L25", "KB-L27", "KB-L28", "KB-L29"])


def test_katalog_fallback_tanpa_kategori_tidak_dump_produk():
    """Menguji bahwa jika kata kunci tidak cocok dan kategori None, katalog tidak membuang 10 produk acak seluruh toko."""
    from services.agent_tools import katalog

    res = katalog(kata_kunci="kata_kunci_acak_yang_pasti_tidak_ada")
    assert res.get("status") == "sukses"
    assert res.get("total_cocok") == 0
    assert len(res.get("produk", [])) == 0
    assert len(res.get("produk_di_kategori", [])) == 0


def test_auto_inject_kirim_foto_pada_spek_produk():
    """Menguji bahwa permintaan spek produk spesifik secara otomatis menyertakan kirim_foto=True dan foto_tersedia."""
    from unittest.mock import patch
    from services.agentic_tool_engine import run_agentic_tool

    # 1. Kasus A: Pelanggan meminta spek produk spesifik ("Spek lengkapnya dong")
    # LLM hanya memanggil katalog({'kode_atau_nama': 'LG 24MP400-B'}) tanpa kirim_foto
    call_a = 0
    def mock_ollama_spek(messages, tools=None, **kwargs):
        nonlocal call_a
        call_a += 1
        if call_a == 1:
            return {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "function": {
                            "name": "katalog",
                            "arguments": {"kode_atau_nama": "LG 24MP400-B"}
                        }
                    }]
                }
            }
        return {
            "message": {
                "role": "assistant",
                "content": "Ini spek lengkap LG 24MP400-B ya Kak: Layar 23.8 inch IPS 75Hz, port HDMI/D-Sub, harga Rp1.250.000."
            }
        }

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama_spek):
        res = run_agentic_tool(
            user_text="Spek lengkapnya dong",
            history=[{"role": "user", "content": "Ada monitor LG?"}, {"role": "assistant", "content": "Ada LG 24MP400-B Kak."}],
            kirim_foto_oleh_llm=True
        )

    # Argumen alat yang dieksekusi harus otomatis memiliki kirim_foto=True
    assert len(res["tool_calls"]) == 1
    assert res["tool_calls"][0]["argumen"].get("kirim_foto") is True
    # foto_tersedia harus berisi kode produk KB-M01
    assert "KB-M01" in res["foto_tersedia"]
    # Produk yang disebut harus mencakup KB-M01
    assert any(p.get("kode") == "KB-M01" for p in res["products"])

    # 2. Kasus B: Pencarian umum katalog (bukan produk spesifik) TIDAK menginjeksi kirim_foto
    call_b = 0
    def mock_ollama_umum(messages, tools=None, **kwargs):
        nonlocal call_b
        call_b += 1
        if call_b == 1:
            return {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "function": {
                            "name": "katalog",
                            "arguments": {"kategori": "monitor", "kata_kunci": "daily"}
                        }
                    }]
                }
            }
        return {
            "message": {
                "role": "assistant",
                "content": "Kami punya monitor LG 24MP400-B seharga Rp1.250.000."
            }
        }

    with patch("services.agentic_tool_engine.call_ollama_chat_raw", side_effect=mock_ollama_umum):
        res_umum = run_agentic_tool(
            user_text="Rekomendasi monitor untuk kantor",
            history=[],
            kirim_foto_oleh_llm=True
        )

    assert len(res_umum["tool_calls"]) == 1
    assert res_umum["tool_calls"][0]["argumen"].get("kirim_foto") is not True
    assert res_umum["foto_tersedia"] == []


def test_aturan_fokus_produk_dan_cegah_foto_duplikat():
    """Menguji aturan prompt untuk tidak mengulang spek produk yang sudah dibahas dan penyaringan foto terkirim di bot."""
    from services.agentic_tool_engine import build_agent_system_prompt, pilih_foto_yang_akan_dikirim

    # 1. Prompt memuat instruksi fokus komponen dan tidak mengulang daftar spek utama
    prompt = build_agent_system_prompt()
    kalimat_fokus = (
        "Bila membahas produk yang sudah disebutkan di pesan-pesan sebelumnya, "
        "jawablah langsung dan fokus hanya pada hal atau komponen yang sedang ditanyakan pelanggan secara ringkas; "
        "jangan mengulang kembali daftar spesifikasi utama (seperti prosesor, RAM, storage, atau harga) "
        "yang sudah kamu sampaikan sebelumnya kecuali pelanggan memintanya."
    )
    assert kalimat_fokus in prompt, "Prompt harus memuat aturan agar tidak mengulang spek produk yang sudah dibahas"

    # 2. telegram_bot.py memuat logika pencegahan foto duplikat
    with open("telegram_bot.py", "r", encoding="utf-8") as f:
        tg_code = f.read()
    assert "final_photo_codes = [c for c in final_photo_codes if c not in sent_photos]" in tg_code
    assert "fotonya lagi" in tg_code

    # 3. Logika filter: bila sudah ada di sent_photos dan user tidak minta foto eksplisit -> foto tidak dikirim ulang
    raw_photos = ["KB-L24"]
    prods = [{"kode": "KB-L24", "nama": "Acer Nitro V 15"}]
    codes = pilih_foto_yang_akan_dikirim(foto_tersedia=raw_photos, produk_disebut=prods)
    assert codes == ["KB-L24"]

    sent_photos = {"KB-L24"}
    user_text_tanya_layar = "Layar ukuran berapa itu?"
    photo_phrases = ("kirim foto", "minta foto", "tampilkan foto", "lihat foto", "fotonya lagi")
    is_explicit = any(p in user_text_tanya_layar.lower() for p in photo_phrases)
    filtered_codes = [c for c in codes if c not in sent_photos] if not is_explicit else codes
    assert filtered_codes == [], "Foto KB-L24 tidak boleh dikirim ulang saat user hanya tanya ukuran layar"

    # 4. Bila user minta foto eksplisit ("Kirim fotonya lagi dong") -> foto tetap dikirim walau sudah di sent_photos
    user_text_minta_foto = "Kirim fotonya lagi dong"
    is_explicit_req = any(p in user_text_minta_foto.lower() for p in photo_phrases)
    filtered_explicit = [c for c in codes if c not in sent_photos] if not is_explicit_req else codes
    assert filtered_explicit == ["KB-L24"], "Foto KB-L24 harus dikirim jika user minta eksplisit"


def test_katalog_query_intel_processor_dan_gpu_dedicated():
    """Menguji bahwa query laptop Intel atau prosesor Intel dengan dedicated GPU menemukan produk laptop yang tepat."""
    from services.agent_tools import katalog

    # 1. katalog(kategori='laptop', kata_kunci='Intel', gpu_dedicated=True)
    res_kw = katalog(kategori="laptop", kata_kunci="Intel", gpu_dedicated=True)
    assert res_kw.get("status") == "sukses"
    assert res_kw.get("total_cocok") == 5
    codes_kw = [p["kode"] for p in res_kw.get("produk", [])]
    assert set(codes_kw) == {"KB-L23", "KB-L24", "KB-L27", "KB-L28", "KB-L29"}

    # 2. katalog(kategori='laptop', merek='Intel', gpu_dedicated=True)
    res_merek = katalog(kategori="laptop", merek="Intel", gpu_dedicated=True)
    assert res_merek.get("status") == "sukses"
    assert res_merek.get("total_cocok") == 5

    # 3. katalog(kata_kunci='laptop intel')
    res_lap_intel = katalog(kata_kunci="laptop intel")
    assert res_lap_intel.get("status") == "sukses"
    assert res_lap_intel.get("total_cocok") == 13


def test_katalog_kode_atau_nama_ekstraksi_kode_dan_ecotank():
    """Menguji bahwa kode_atau_nama berhasil mengekstrak kode produk saat digabung dengan nama produk."""
    from services.agent_tools import katalog

    # 1. Kasus gabungan kode dan nama (kasus live EcoTank)
    res_combo = katalog(kode_atau_nama="KB-P06 Epson EcoTank L3210")
    assert res_combo.get("status") == "sukses"
    assert res_combo.get("total_cocok") == 1
    assert res_combo.get("detail")[0]["kode"] == "KB-P06"

    # 2. Kasus nama lengkap
    res_nama = katalog(kode_atau_nama="Epson EcoTank L3210")
    assert res_nama.get("status") == "sukses"
    assert res_nama.get("total_cocok") == 1
    assert res_nama.get("detail")[0]["kode"] == "KB-P06"

    # 3. Kasus multi kode
    res_multi = katalog(kode_atau_nama="KB-L14, KB-P06")
    assert res_multi.get("status") == "sukses"
    assert res_multi.get("total_cocok") == 2


def test_katalog_pencarian_printer_warna():
    """Menguji bahwa pencarian printer warna menyaring tepat printer warna (HP, Epson EcoTank, Canon) dan mengecualikan printer mono/thermal."""
    from services.agent_tools import katalog

    res = katalog(kategori="printer", kata_kunci="warna")
    assert res.get("status") == "sukses"
    assert res.get("total_cocok") == 3
    codes = [p["kode"] for p in res.get("produk", [])]
    assert set(codes) == {"KB-P06", "KB-P07", "KB-P10"}
    # Pastikan laser mono (KB-P08) dan thermal (KB-P09) tidak masuk
    assert "KB-P08" not in codes
    assert "KB-P09" not in codes




