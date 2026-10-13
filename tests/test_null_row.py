import pytest
from core.db import row_to_dict

class DummyRow:
    def __init__(self, data):
        self.data = data
    def keys(self):
        return self.data.keys()
    def __getitem__(self, key):
        return self.data[key]
    def __iter__(self):
        return iter(self.data)

def test_null_normalization():
    # Simulate DB row with NULL tags and NULL vram_gb
    raw = {
        "kode": "NULL-01",
        "nama": "Test Product",
        "tags": None,
        "vram_gb": None,
        "gpu_dedicated": 1,
        "kategori": "laptop"
    }
    
    row = DummyRow(raw)
    d = row_to_dict(row)
    
    assert d["tags"] == [], "Tags should be normalized to empty list"
    assert d["vram_gb"] is None, "vram_gb should remain None"
