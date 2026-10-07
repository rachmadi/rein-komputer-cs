import pytest
from services.catalog_service import upsert_product

def test_upsert_product_null_vram_dedicated():
    data = {
        "kode": "TEST-DIRECT",
        "nama": "Test Product Direct",
        "kategori": "laptop",
        "harga_idr": 5000000,
        "gpu": "RTX 3050"  # This implies dedicated, but vram is missing
    }
    with pytest.raises(ValueError) as exc:
        upsert_product(data, sync_qdrant=False)
    assert "GPU Dedicated wajib mencantumkan kapasitas VRAM" in str(exc.value)
