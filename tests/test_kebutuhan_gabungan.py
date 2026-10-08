import pytest
from core.catalog import Catalog
from services.agentic_tool_engine import execute_tool
import os, json

def load_fixture_catalog():
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "catalog_snapshot.json")
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Catalog(data)


def test_kebutuhan_gabungan_p05_p15():
    """Kebutuhan gabungan P05+P15: tampilkan label gabungan, profil aktif ganda, syarat terberat."""
    cat = load_fixture_catalog()

    ans, prods, cat_out, prof = execute_tool(
        "search_catalog",
        {"profil_id": "P05,P15", "kategori": "desktop"},
        cat, [], "komputer buat game berat tapi juga buat kasir"
    )

    # Profil ganda harus dikembalikan
    assert "P05" in prof and "P15" in prof, f"Profil gabungan harus P05+P15, got: {prof}"

    # Harus ada kalimat pembuka gabungan natural TANPA kode internal
    assert "Kebutuhan gabungan" in ans, f"Teks 'Kebutuhan gabungan' harus ada dalam jawaban:\n{ans}"
    assert "P05" not in ans and "P15" not in ans, f"Kode internal P05/P15 tidak boleh ada di jawaban:\n{ans}"
    assert ("Game" in ans or "Gamer" in ans) and ("Kasir" in ans or "Toko" in ans), f"Nama natural harus ada:\n{ans}"

    # Harus ada ✅
    assert "✅" in ans, f"Harus ada produk ✅:\n{ans}"

    # KB-D05 (ROG Strix, VRAM 12GB, ram 32GB, cpu_tier 3) memenuhi P05
    kodes = [p["kode"] for p in prods]
    assert "KB-D05" in kodes, "ROG Strix (KB-D05) harus muncul"

    # HP Pavilion KB-D01 (VRAM 6GB) tidak boleh ✅ untuk P05 (syarat vram >= 8)
    if "KB-D01" in kodes:
        hp = next(p for p in prods_e if p["kode"] == "KB-D01") if 'prods_e' in locals() else next(p for p in prods if p["kode"] == "KB-D01")
        assert hp["match_report"]["tidak_terpenuhi"], \
            "KB-D01 VRAM=6GB tidak boleh ✅ jika syarat P05 vram>=8"


def test_profil_hanya_bertipe_profil_bukan_g_atau_m():
    """Chunk G dan M tidak boleh menjadi profil aktif atau 'kebutuhan gabungan'."""
    cat = load_fixture_catalog()
    from services.knowledge_service import get_usage_requirements, get_profile_by_id

    # Chunk G dan M harus ditolak oleh get_profile_by_id
    for invalid_id in ["G01", "G02", "G03", "G04", "M01", "M02"]:
        assert get_profile_by_id(invalid_id) is None, f"{invalid_id} dilarang menjadi data profil"

    # Jika user query menyebut chunk terkait RAM/GPU/Glosarium, chunk G dan M dilarang masuk profil
    reqs = get_usage_requirements("laptop dengan ram besar dan gpu kencang")
    for p in reqs.get("profil", []):
        pid = p.get("profil_id", "")
        assert not pid.startswith(("G", "M")), f"Chunk G/M terdeteksi di hasil retrieval: {pid}"
        assert p.get("tipe") == "profil", f"Tipe bukan profil: {p}"

    # Coba paksa profil_id mengandung G03 atau M01 ke execute_tool
    ans, prods, cat_out, prof = execute_tool(
        "search_catalog",
        {"profil_id": "P05,G03", "kategori": "desktop"},
        cat, [], "komputer buat game berat"
    )
    assert prof == "P05", f"G03 dilarang lolos ke profil aktif: {prof}"
    assert "Panduan Umum" not in ans, "Chunk G03 dilarang digabungkan ke kebutuhan gabungan"


def test_laptop_ram_128gb_tanpa_profil_aktif():
    """'laptop RAM 128GB' tidak boleh memiliki profil aktif (active_profile_id is None)."""
    cat = load_fixture_catalog()
    ans, prods, cat_out, prof = execute_tool(
        "search_catalog",
        {"query": "laptop RAM 128GB", "kategori": "laptop"},
        cat, [], "laptop RAM 128GB"
    )
    assert prof is None, f"laptop RAM 128GB tidak boleh punya profil aktif, got: {prof}"
    assert len(prods) == 0, "Produk harus kosong karena RAM 128GB tidak tersedia di katalog"
    assert "tidak tersedia" in ans.lower()

