import pytest
from core.catalog import Catalog
from services.agentic_tool_engine import apply_filters

def test_vram_6gb_fails_8gb():
    catalog = Catalog.from_dummy()
    # Dummy product with RTX 3050 6GB
    p = {
        "kode": "TEST-GPU",
        "nama": "Test Laptop RTX 3050",
        "gpu_dedicated": 1,
        "vram_gb": 6
    }
    
    # Needs P03 with 8GB VRAM
    filters = [
        {"field": "vram_gb", "op": ">=", "value": 8, "strength": "hard"}
    ]
    
    passed, reason, penalty, report = apply_filters(p, filters)
    assert not passed
    assert "vram_gb" in reason.lower()
    assert len(report["tidak_terpenuhi"]) == 1
    assert "vram_gb" in report["tidak_terpenuhi"][0]
