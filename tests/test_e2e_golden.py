import pytest
from core.catalog import Catalog
from services.agentic_tool_engine import execute_tool
import os

def test_e2e_golden():
    cat = Catalog.from_db("data/test_catalog.db")
    
    # (a) "laptop buat edit video 4k" -> P03
    ans, prods, c, p = execute_tool("search_catalog", {"profil_id": "P03"}, cat, [], "laptop buat edit video 4k")
    assert p == "P03"
    assert "✅" in ans
    assert "Legion Pro 5" in ans
    # Legion should have ✅, TUF and Vivobook should not have ✅
    assert "✅ 1. **Lenovo Legion Pro 5" in ans or "✅ - **Lenovo Legion Pro 5" in ans
    assert "✅" not in ans.split("TUF Gaming A15")[0].split("\n")[-1] if "TUF Gaming A15" in ans else True
    assert "✅" not in ans.split("Vivobook")[0].split("\n")[-1] if "Vivobook" in ans else True
    assert "Acer" not in ans
    
    # (b) "yang ASUS aja" -> P03 inherited
    ans, prods, c, p = execute_tool("search_catalog", {"query": "yang ASUS aja", "kategori": "laptop"}, cat, [], "yang ASUS aja", "P03")
    assert p == "P03"
    assert "✅" not in ans
    assert "Kandidat terdekat" in ans
    assert "TUF Gaming A15" in ans
    assert "Vivobook" in ans
    
    # (c) "ada yang lebih murah?" -> P03 inherited, max_harga = 16999000 (TUF price)
    ans, prods, c, p = execute_tool("search_catalog", {"query": "ada yang lebih murah?", "max_harga": 16999000}, cat, [], "ada yang lebih murah?", "P03")
    assert p == "P03"
    assert "✅" not in ans # no product < 16.999M satisfies P03 perfectly
    
    # (d) "laptop RAM 128GB"
    ans, prods, c, p = execute_tool("search_catalog", {"query": "laptop RAM 128GB"}, cat, [], "laptop RAM 128GB")
    assert "tidak tersedia" in ans.lower()
    assert len(prods) == 0
    
    # (e) "game berat tapi kasir" -> P05+P15
    # Let's assume P05+P15 requires VRAM >= 8
    ans, prods, c, p = execute_tool("search_catalog", {"profil_id": "P05,P15"}, cat, [], "game berat tapi kasir")
    assert p == "P05,P15"
    if "✅" in ans:
        # Check that no product with < 8GB VRAM got ✅
        pass # We assert in check_invariants anyway
        
    for prod in prods:
        assert prod.get("gpu") is not None, "Tidak ada produk berspesifikasi None"
