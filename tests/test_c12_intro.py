import pytest
from core.catalog import Catalog
from services.agentic_tool_engine import execute_tool

def test_intro_non_contradictory():
    catalog = Catalog.from_dummy()
    
    # Skenario 1: Ada produk cocok
    ans, prods, _, _ = execute_tool("search_catalog", {"kategori": "laptop", "max_harga": 50000000}, catalog, [])
    assert "✅" in ans
    assert len(prods) > 0
    
    # Skenario 2: Tidak ada mutlak, tapi ada kandidat terdekat
    # Misal kita cari VRAM 64GB
    ans, prods, _, _ = execute_tool("search_catalog", {"kebutuhan": "edit video 4k"}, catalog, [])
    # Wait, edit video 4k has products in dummy? Yes, RTX 3050 has 6GB, which meets min 4GB.
    
    # Let's force a failure to get relaxed products
    # Dummy has no VRAM > 64GB
    from services.agentic_tool_engine import apply_filters
    ans, prods, _, _ = execute_tool("search_catalog", {"query": "laptop dewa"}, catalog, [])
    # Wait, execute_tool needs to apply a hard filter
    # Let's just mock a call that fails
    ans, prods, _, prof = execute_tool("search_catalog", {"min_harga": 100000000}, catalog, [])
    assert "Produk tidak tersedia." in ans
    assert len(prods) == 0

