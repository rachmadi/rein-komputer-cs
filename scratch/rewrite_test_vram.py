import sys

with open("d:/RAG/tests/test_vram_admin.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('def test_vram_null_dedicated_fallback():\n    # Rule (2)', 'def test_vram_null_dedicated_fallback():\n    # Rule (2)')
# Let's just rewrite the whole test_vram_admin.py to be safe

new_content = """from fastapi.testclient import TestClient
from app.main import app
from services.agentic_tool_engine import apply_filters
from core.catalog import Catalog

client = TestClient(app)

def test_admin_vram_validation():
    response = client.post(
        "/api/admin/products",
        json={
            "kode": "TEST-GPU-NULL",
            "nama": "Test Product GPU",
            "kategori": "laptop", "brand": "asus",
            "harga_idr": 10000000,
            "gpu_dedicated": 1,
            "vram_gb": None
        }
    )
    assert response.status_code == 400
    assert "vram" in response.json()["detail"].lower()

def test_igpu_null_vram_fails_hard():
    catalog = Catalog.from_dummy()
    p = {
        "kode": "TEST-IGPU",
        "nama": "Test iGPU",
        "gpu_dedicated": 0,
        "vram_gb": None
    }
    filters = [{"field": "vram_gb", "op": ">=", "value": 4, "strength": "hard"}]
    passed, reason, penalty, report = apply_filters(p, filters)
    assert report["tidak_terpenuhi"]

def test_vram_null_dedicated_fallback():
    catalog = Catalog.from_dummy()
    p = {
        "kode": "TEST-DED-NULL",
        "nama": "Test Ded GPU",
        "gpu_dedicated": 1,
        "vram_gb": None
    }
    filters = [{"field": "vram_gb", "op": ">=", "value": 4, "strength": "hard"}]
    passed, reason, penalty, report = apply_filters(p, filters)
    assert report["tidak_diketahui"]
"""

with open("d:/RAG/tests/test_vram_admin.py", "w", encoding="utf-8") as f:
    f.write(new_content)
