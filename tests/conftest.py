import os
import sqlite3 as _sqlite3_module
import pytest
from core import db

os.environ["DB_PATH"] = "data/test_catalog.db"

# Simpan referensi sqlite3.connect asli sebelum di-patch, untuk uji baca-saja
_real_connect = _sqlite3_module.connect

@pytest.fixture(autouse=True)
def mock_db_path(monkeypatch):
    test_db = "data/test_catalog.db"
    monkeypatch.setattr(db, "DB_PATH", test_db)
    monkeypatch.setenv("DB_PATH", test_db)
    monkeypatch.setenv("QDRANT_PRODUCTS_COLLECTION", "test_computer_products")
    
    original_connect = db.sqlite3.connect
    def safe_connect(db_path, *args, **kwargs):
        if "catalog.db" in db_path and "test_catalog.db" not in db_path:
            raise RuntimeError(f"TEST FAILED: Attempted to touch live DB: {db_path}")
        return original_connect(db_path, *args, **kwargs)
        
    monkeypatch.setattr(db.sqlite3, "connect", safe_connect)
    yield

