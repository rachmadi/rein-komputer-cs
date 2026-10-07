from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_admin_vram_validation():
    # Attempt to save a dedicated GPU product with NULL VRAM
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
    # Note: If admin endpoint requires auth, this will return 401. 
    # But wait, does it require auth in testing? Let's check.
