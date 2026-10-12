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
    """Menguji monitor + 'perbandingan' -> total 0, catatan menyebut 5 produk (Putaran 20 Butir 4)."""
    res = katalog(kategori="monitor", kata_kunci="perbandingan")
    assert res["total_cocok"] == 0
    assert "catatan" in res
    assert "perbandingan" in res["catatan"]
    assert "Ada 5 produk di monitor ini" in res["catatan"]
    assert res.get("produk") == []


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
    assert captured_messages_5[-1] == {"role": "user", "content": "Halo apa kabar?"}
    expected_note = (
        "Catatan: pesan pelanggan berikut sudah menunggu sekitar 5 menit "
        "karena layanan sempat tidak aktif. Kamu boleh meminta maaf atas keterlambatannya "
        "dengan wajar, lalu layani seperti biasa."
    )
    assert captured_messages_5[-2] == {"role": "system", "content": expected_note}

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
    assert len(chunks) == 28, f"Harus tepat 28 potongan, didapat {len(chunks)}"

    chunk_ids = [c.get("id") for c in chunks]
    # Memastikan tidak ada potongan tanpa ID
    assert all(bool(cid) for cid in chunk_ids), f"Ditemukan potongan tanpa ID: {chunks}"

    # Memastikan K01–K05 ada dan memiliki payload yang benar
    for k_id in ["K01", "K02", "K03", "K04", "K05"]:
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
    from services.agentic_tool_engine import build_agent_system_prompt, KOMPONEN_POS, KOMPONEN_KEPUTUSAN, KOMPONEN_R2

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
    persona_idx = prompt_p.find(KOMPONEN_R2)

    assert kep_idx >= 0 and pos_idx >= 0 and persona_idx >= 0
    assert kep_idx < pos_idx < persona_idx
