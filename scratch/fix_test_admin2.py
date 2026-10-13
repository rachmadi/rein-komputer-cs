import sys

with open("d:/RAG/tests/test_vram_admin.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('assert response.status_code == 400', 'print(response.json()); assert response.status_code == 400')

with open("d:/RAG/tests/test_vram_admin.py", "w", encoding="utf-8") as f:
    f.write(text)
