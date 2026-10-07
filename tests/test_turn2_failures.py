import pytest
from core.catalog import Catalog
from services.agentic_tool_engine import apply_filters, execute_tool

def test_turn_2_all_hard_failures():
    catalog = Catalog.from_dummy()
    
    # Let's say user wants P03 (game berat, edit video 4k)
    # But product is very basic
    p = {
        "kode": "TEST-01",
        "nama": "Basic Laptop",
        "ram_gb": 4,
        "vram_gb": 0,
        "gpu_dedicated": 0,
        "cpu_tier": 0
    }
    filters = [
        {"field": "ram_gb", "op": ">=", "value": 16, "strength": "hard"},
        {"field": "vram_gb", "op": ">=", "value": 4, "strength": "hard"},
        {"field": "cpu_tier", "op": ">=", "value": 2, "strength": "hard"}
    ]
    
    passed, reason, penalty, report = apply_filters(p, filters)
    assert not passed
    assert "ram_gb" in reason, f"Expected failures, got {len(report['tidak_terpenuhi'])}"
    assert "ram_gb" in report["tidak_terpenuhi"][0].lower() or "vram_gb" in report["tidak_terpenuhi"][0].lower() or "cpu_tier" in report["tidak_terpenuhi"][0].lower()

    # Now let's test via execute_tool where NO products match P03
    import services.agentic_tool_engine; services.agentic_tool_engine.get_profile_by_id = lambda x: {"filter": filters}; args = {"profil_id": "P03", "max_harga": 10000000}
    ans_str, p_list, cat, prof = execute_tool("search_catalog", args, catalog, [], "")
    
    assert "Kandidat terdekat" in ans_str
    for prod in p_list:
        assert "match_report" in prod
        mr = prod["match_report"]
        assert len(mr["tidak_terpenuhi"]) > 0 # <--- RESTORED STRICT ASSERTION
