#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Uji apakah 'localhost' menambah ~2 detik per panggilan ke Ollama (hanya localhost:11434).

Pemakaian (dari D:\\RAG, setelah benchmark lain selesai dan tidak ada proses lain memakai Ollama):
    .\\.venv\\Scripts\\python.exe scratch\\bench_host.py
Hasil: layar + scratch\\bench_host.json. Tidak membaca .env dan tidak mengubah apa pun.
"""
import json
import statistics
import time
import urllib.request
from pathlib import Path

HOSTS = ["localhost", "127.0.0.1"]
N = 6


def timed(url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"},
                                 method="POST" if data is not None else "GET")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            r.read()
        return round(time.time() - t0, 3), "ok"
    except Exception as e:
        return round(time.time() - t0, 3), type(e).__name__


out = {}
# pemanasan: pastikan bge-m3 termuat agar pengukuran bukan waktu pemuatan
timed("http://127.0.0.1:11434/api/embed", {"model": "bge-m3", "input": "pemanasan", "keep_alive": "10m"})
for host in HOSTS:
    base = f"http://{host}:11434"
    ver = [timed(base + "/api/version") for _ in range(N)]
    emb = [timed(base + "/api/embed", {"model": "bge-m3", "input": "laptop untuk kuliah desain",
                                       "keep_alive": "10m"}) for _ in range(N)]
    out[host] = {
        "version_median_s": round(statistics.median(t for t, _ in ver), 3),
        "embed_median_s": round(statistics.median(t for t, _ in emb), 3),
        "version_s": [t for t, _ in ver],
        "embed_s": [t for t, _ in emb],
        "status": sorted({s for _, s in ver + emb}),
    }
print(json.dumps({h: {k: v for k, v in d.items() if k.endswith("median_s") or k == "status"}
                  for h, d in out.items()}, indent=2))
path = Path(__file__).resolve().parent / "bench_host.json"
path.write_text(json.dumps(out, indent=2), encoding="utf-8")
print("Disimpan:", path)
