import pytest
import os
import json
from core.catalog import Catalog
from core import db
import sqlite3
from services.agentic_tool_engine import execute_tool

def load_fixture_catalog():
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "catalog_snapshot.json")
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Catalog(data)


def test_e2e_golden_static():
    """Golden E2E matrix terhadap snapshot statis. KB tidak diubah, parser sesuai migrate_derived_fields."""
    cat = load_fixture_catalog()

    # (a) "laptop buat edit video 4k" -> P03, hanya KB-L10 (Legion Pro 5) ✅
    ans_a, prods_a, c_a, p_a = execute_tool(
        "search_catalog", {"profil_id": "P03", "kategori": "laptop"},
        cat, [], "laptop buat edit video 4k"
    )
    assert p_a == "P03"
    assert c_a == "laptop"
    assert "✅" in ans_a, f"Tidak ada ✅ dalam jawaban: {ans_a}"
    kb_l10 = next((p for p in prods_a if p["kode"] == "KB-L10"), None)
    assert kb_l10 is not None, "KB-L10 (Legion Pro 5) tidak ada di hasil"
    # Pastikan TUF, Vivobook, Nitro tidak ✅
    for p in prods_a:
        if p["kode"] in ("KB-L09", "KB-L07", "KB-L06"):
            assert "✅" not in ans_a.split(p["nama"])[0].split("\n")[-1], \
                f"{p['nama']} tidak boleh ✅"

    # (b) lanjutan "yang ASUS aja" – mewarisi P03 + laptop, tidak ada ✅
    ans_b, prods_b, c_b, p_b = execute_tool(
        "search_catalog", {"query": "asus"}, cat, [], "yang ASUS aja", "P03", "laptop"
    )
    assert p_b == "P03", f"Profil tidak dipertahankan: {p_b}"
    assert c_b == "laptop", f"Kategori tidak dipertahankan: {c_b}"
    assert "✅" not in ans_b, f"Tidak boleh ada ✅ saat ASUS tidak memenuhi P03: {ans_b}"
    assert "Kandidat terdekat" in ans_b
    kodes_b = [p["kode"] for p in prods_b]
    assert "KB-L09" in kodes_b, "TUF (KB-L09) harus ada di kandidat"
    assert "KB-L07" in kodes_b, "Vivobook (KB-L07) harus ada di kandidat"
    assert "KB-D05" not in kodes_b, "ROG Strix (desktop) tidak boleh muncul di laptop query"
    # Urutan: TUF (1 kegagalan) sebelum Vivobook (2 kegagalan)
    idx_tuf = kodes_b.index("KB-L09")
    idx_vivob = kodes_b.index("KB-L07")
    assert idx_tuf < idx_vivob, "TUF (1 gagal) harus urutan sebelum Vivobook (2 gagal)"
    # Validasi kegagalan per produk
    tuf = next(p for p in prods_b if p["kode"] == "KB-L09")
    vivob = next(p for p in prods_b if p["kode"] == "KB-L07")
    assert tuf["match_report"]["tidak_terpenuhi"] == ["ram_gb >= 32 (got 16)"], \
        f"TUF hanya boleh gagal RAM, actual: {tuf['match_report']['tidak_terpenuhi']}"
    assert set(vivob["match_report"]["tidak_terpenuhi"]) == {"ram_gb >= 32 (got 16)", "vram_gb >= 8 (got 6)"}, \
        f"Vivobook harus gagal RAM+VRAM, actual: {vivob['match_report']['tidak_terpenuhi']}"

    # (c) lanjutan "ada yang lebih murah?" – patokan = harga ✅ terakhir = Rp23.999.000 (Legion)
    # batas atas eksklusif: max_harga = 23_999_000 - 1 = 23_998_999
    ans_c, prods_c, c_c, p_c = execute_tool(
        "search_catalog", {"max_harga": 23_998_999}, cat,
        [], "ada yang lebih murah?", "P03", "laptop"
    )
    assert p_c == "P03"
    assert c_c == "laptop"
    assert "lebih murah" in ans_c.lower(), f"Jawaban harus menyebut 'lebih murah': {ans_c}"
    assert "✅" not in ans_c
    # Kandidat terdekat diurutkan naik jumlah kegagalan: TUF dulu lalu Vivobook
    kodes_c = [p["kode"] for p in prods_c]
    if "KB-L09" in kodes_c and "KB-L07" in kodes_c:
        assert kodes_c.index("KB-L09") < kodes_c.index("KB-L07")

    # (d) "laptop RAM 128GB" -> tidak tersedia
    ans_d, prods_d, _, _ = execute_tool(
        "search_catalog", {"query": "laptop RAM 128GB", "kategori": "laptop"},
        cat, [], "laptop RAM 128GB"
    )
    assert "tidak tersedia" in ans_d.lower()
    assert len(prods_d) == 0

    # (e) "game berat tapi kasir" -> P05+P15, desktop, KB-D05 ✅
    ans_e, prods_e, c_e, p_e = execute_tool(
        "search_catalog", {"profil_id": "P05,P15", "kategori": "desktop"},
        cat, [], "komputer buat game berat tapi kasir"
    )
    assert "P05" in p_e and "P15" in p_e
    assert "✅" in ans_e
    kodes_e = [p["kode"] for p in prods_e]
    assert "KB-D05" in kodes_e, "ROG Strix (KB-D05) harus ✅ untuk P05"
    # HP Pavilion KB-D01 VRAM 6GB harus tidak ✅
    if "KB-D01" in kodes_e:
        hp = next(p for p in prods_e if p["kode"] == "KB-D01")
        assert hp["match_report"]["tidak_terpenuhi"], "KB-D01 tidak boleh ✅ (VRAM kurang)"

    # (f) invariant: tidak ada produk ✅ dengan tidak_terpenuhi tidak kosong
    for ans, prods in [(ans_a, prods_a), (ans_b, prods_b), (ans_c, prods_c), (ans_e, prods_e)]:
        for p in prods:
            fails = p.get("match_report", {}).get("tidak_terpenuhi", [])
            if fails:
                assert "✅" not in ans.split(p["nama"])[0][-20:] \
                    if p["nama"] in ans else True, \
                    f"Produk {p['kode']} dengan kegagalan {fails} berlabel ✅"


def test_snapshot_integrity():
    """Verifikasi snapshot fixture: lengkap, semua kode unik, field wajib ada."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "catalog_snapshot.json")
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 20, f"Snapshot harus 20 produk, got {len(data)}"
    kodes = [p["kode"] for p in data]
    assert len(kodes) == len(set(kodes)), "Kode produk harus unik"

    required = {"kode", "nama", "harga_idr", "kategori"}
    for p in data:
        missing = required - set(k for k, v in p.items() if v is not None)
        assert not missing, f"{p['kode']} kekurangan field: {missing}"

    # Konfirmasi kode produksi yang diharapkan ada
    expected_kodes = {"KB-L07", "KB-L09", "KB-L10", "KB-D05"}
    for k in expected_kodes:
        assert k in kodes, f"{k} tidak ada di snapshot"
