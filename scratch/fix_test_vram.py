import sys

with open("d:/RAG/tests/test_vram_admin.py", "r", encoding="utf-8") as f:
    text = f.read()

# Fix igpu
text = text.replace('def test_igpu_null_vram_fails_hard():', 'def test_igpu_null_vram_fails_hard():')

text = text.replace('assert report["tidak_diketahui"]', 'assert report["tidak_terpenuhi"]') # oops I replaced both before

with open("d:/RAG/tests/test_vram_admin.py", "w", encoding="utf-8") as f:
    f.write(text)
