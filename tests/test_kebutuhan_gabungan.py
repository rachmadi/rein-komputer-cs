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

    # Harus ada kalimat pembuka gabungan
    assert "Kebutuhan gabungan" in ans, f"Teks 'Kebutuhan gabungan' harus ada dalam jawaban:\n{ans}"
    assert "P05" in ans and "P15" in ans

    # Harus ada ✅
    assert "✅" in ans, f"Harus ada produk ✅:\n{ans}"

    # KB-D05 (ROG Strix, VRAM 12GB, ram 32GB, cpu_tier 3) memenuhi P05
    kodes = [p["kode"] for p in prods]
    assert "KB-D05" in kodes, "ROG Strix (KB-D05) harus muncul"

    # HP Pavilion KB-D01 (VRAM 6GB) tidak boleh ✅ untuk P05 (syarat vram >= 8)
    if "KB-D01" in kodes:
        hp = next(p for p in prods if p["kode"] == "KB-D01")
        assert hp["match_report"]["tidak_terpenuhi"], \
            "KB-D01 VRAM=6GB tidak boleh ✅ jika syarat P05 vram>=8"
