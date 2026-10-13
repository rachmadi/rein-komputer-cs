#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ganti alamat 'localhost' ke 127.0.0.1 untuk Ollama dan Qdrant di tiga berkas layanan.

Alasan: di Windows, 'localhost' memicu penundaan ~2 detik per panggilan (IPv6 dicoba dulu).
Pemakaian (dari D:\\RAG):
    .\\.venv\\Scripts\\python.exe scratch\\fix_loopback.py
Cadangan berkas asli disimpan di scratch\\backup_loopback\\. Hanya string URL yang diganti;
akhir baris dan pengodean berkas dipertahankan. Skrip tidak menyentuh .env.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
TARGETS = ["services/catalog_service.py", "services/llm_parser.py", "services/llm_generator.py"]
REPL = [(b"http://localhost:11434", b"http://127.0.0.1:11434"),
        (b"http://localhost:6333", b"http://127.0.0.1:6333")]
backup = ROOT / "scratch" / "backup_loopback"
backup.mkdir(parents=True, exist_ok=True)

total = 0
for rel in TARGETS:
    p = ROOT / rel
    if not p.exists():
        print(f"LEWATI (tidak ada): {rel}")
        continue
    data = p.read_bytes()
    new = data
    n = 0
    for old, repl in REPL:
        n += new.count(old)
        new = new.replace(old, repl)
    if n == 0:
        print(f"Tidak ada yang diganti: {rel}")
        continue
    shutil.copy2(p, backup / (rel.replace("/", "__")))
    p.write_bytes(new)
    total += n
    print(f"Diganti {n}x di {rel}")
print(f"Selesai. Total {total} penggantian. Cek dengan: git diff --stat")
