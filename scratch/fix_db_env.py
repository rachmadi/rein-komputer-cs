import sys

with open("d:/RAG/core/db.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('DB_PATH = "data/catalog.db"', 'import os\nDB_PATH = os.getenv("DB_PATH", "data/catalog.db")')

with open("d:/RAG/core/db.py", "w", encoding="utf-8") as f:
    f.write(text)

with open("d:/RAG/core/catalog.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('def from_db(cls, db_path: str = "data/catalog.db") -> Catalog:', 'def from_db(cls, db_path: str | None = None) -> Catalog:\n        if db_path is None:\n            import os\n            db_path = os.getenv("DB_PATH", "data/catalog.db")')

with open("d:/RAG/core/catalog.py", "w", encoding="utf-8") as f:
    f.write(text)

with open("d:/RAG/tests/conftest.py", "r", encoding="utf-8") as f:
    text = f.read()

if "os.environ['DB_PATH'] =" not in text:
    text = 'import os\nos.environ["DB_PATH"] = "data/test_catalog.db"\n' + text

with open("d:/RAG/tests/conftest.py", "w", encoding="utf-8") as f:
    f.write(text)
