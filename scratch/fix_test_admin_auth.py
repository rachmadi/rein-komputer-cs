import sys

with open("d:/RAG/tests/test_vram_admin.py", "r", encoding="utf-8") as f:
    text = f.read()

override = """from app.main import app
from app.auth import get_current_admin

app.dependency_overrides[get_current_admin] = lambda: "admin"
"""

text = text.replace('from app.main import app', override)

with open("d:/RAG/tests/test_vram_admin.py", "w", encoding="utf-8") as f:
    f.write(text)
