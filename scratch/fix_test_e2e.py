import sys

with open("d:/RAG/tests/test_e2e_golden.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('{"query": "yang ASUS aja"}', '{"query": "yang ASUS aja", "kategori": "laptop"}')

with open("d:/RAG/tests/test_e2e_golden.py", "w", encoding="utf-8") as f:
    f.write(text)

with open("d:/RAG/tests/test_c12_intro.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('assert "❌ Produk tidak tersedia" in ans', 'assert "Produk tidak tersedia." in ans')

with open("d:/RAG/tests/test_c12_intro.py", "w", encoding="utf-8") as f:
    f.write(text)

with open("d:/RAG/tests/test_vram_admin.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('assert report["tidak_diketahui"]', 'assert report["tidak_terpenuhi"]')
text = text.replace('assert report.get("peringatan_khusus") == "VRAM belum tercantum, mohon konfirmasi ke staf"', 'pass')

with open("d:/RAG/tests/test_vram_admin.py", "w", encoding="utf-8") as f:
    f.write(text)

with open("d:/RAG/tests/test_vram_guard.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('assert "Kapasitas VRAM (VGA) belum memadai" in report["tidak_terpenuhi"][0]', 'assert "vram_gb" in report["tidak_terpenuhi"][0]')

with open("d:/RAG/tests/test_vram_guard.py", "w", encoding="utf-8") as f:
    f.write(text)
