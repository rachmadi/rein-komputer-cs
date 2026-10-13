import sys

with open("d:/RAG/tests/conftest.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('os.environ["DB_PATH"] = "data/test_catalog.db"', 'os.environ["DB_PATH"] = "data/test_catalog.db"\nimport shutil\nif os.path.exists("data/catalog.db"):\n    shutil.copy("data/catalog.db", "data/test_catalog.db")')

with open("d:/RAG/tests/conftest.py", "w", encoding="utf-8") as f:
    f.write(text)
