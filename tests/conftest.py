import os
os.environ["DB_PATH"] = "data/test_catalog.db"
import shutil
if os.path.exists("data/catalog.db"):
    shutil.copy("data/catalog.db", "data/test_catalog.db")
import os
import pytest
from core import db

@pytest.fixture(autouse=True)
def mock_db_path(monkeypatch):
    test_db = "data/test_catalog.db"
    monkeypatch.setattr(db, "DB_PATH", test_db)
    monkeypatch.setenv("DB_PATH", test_db)
    monkeypatch.setenv("QDRANT_PRODUCTS_COLLECTION", "test_computer_products")
    
    # Also we should patch the actual connection so it fails if it touches live
    original_connect = db.sqlite3.connect
    def safe_connect(db_path, *args, **kwargs):
        if "catalog.db" in db_path and "test_catalog.db" not in db_path:
            raise RuntimeError(f"TEST FAILED: Attempted to touch live DB: {db_path}")
        return original_connect(db_path, *args, **kwargs)
        
    monkeypatch.setattr(db.sqlite3, "connect", safe_connect)
    yield
