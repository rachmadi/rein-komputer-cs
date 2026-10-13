#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Uji latensi bergantian LLM <-> bge-m3 di Ollama lokal (hanya localhost:11434).

Pemakaian (dari D:\\RAG):
    .\\.venv\\Scripts\\python.exe scratch\\bench_embed.py <label> [model_llm] [model_embed]
Contoh label: sekarang   atau   dua_model
Hasil: scratch\\bench_embed_<label>.json dan ringkasan di layar.
Skrip ini tidak membaca .env, tidak mengubah apa pun, dan hanya memanggil Ollama.
"""
import json
import statistics
import sys
import time
import urllib.request
from pathlib import Path

BASE = "http://localhost:11434"
LABEL = sys.argv[1] if len(sys.argv) > 1 else "sekarang"
LLM = sys.argv[2] if len(sys.argv) > 2 else "gemma4:e4b"
EMB = sys.argv[3] if len(sys.argv) > 3 else "bge-m3"
N = 6
QUERIES = [
    "laptop untuk kuliah desain",
    "berapa harga laptop ini",
    "papaku konsultan IT cari laptop",
    "ada diskon hari ini",
    "komputer untuk kasir toko",
    "alamat toko di mana",
]


def call(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": "application/json"},
        method="POST" if data is not None else "GET")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        body = json.loads(r.read().decode("utf-8"))
    return body, time.time() - t0


def ps():
    body, _ = call("/api/ps")
    return [{"name": m.get("name"),
             "size_gb": round(m.get("size", 0) / 1e9, 2),
             "vram_gb": round(m.get("size_vram", 0) / 1e9, 2)}
            for m in body.get("models", [])]


def unload_all():
    for m in ps():
        name = m["name"]
        try:
            call("/api/generate", {"model": name, "keep_alive": 0})
        except Exception:
            try:
                call("/api/embed", {"model": name, "input": "x", "keep_alive": 0})
            except Exception:
                pass
    time.sleep(2)


def run_mode(nama, opts):
    unload_all()
    rows = []
    for i in range(N):
        try:
            _, t_llm = call("/api/generate", {
                "model": LLM, "prompt": "Jawab satu kata: halo", "stream": False,
                "keep_alive": "10m", "options": {"num_predict": 8}})
            _, t_emb = call("/api/embed", {
                "model": EMB, "input": QUERIES[i % len(QUERIES)],
                "keep_alive": "10m", "options": opts})
            rows.append({"i": i, "llm_s": round(t_llm, 2),
                         "embed_s": round(t_emb, 2), "ps": ps()})
        except Exception as e:  # catat dan lanjut
            rows.append({"i": i, "error": repr(e)})
    return {"mode": nama, "opts": opts, "rows": rows}


def ringkas(hasil):
    ok = [r for r in hasil["rows"] if "error" not in r]
    sisa = ok[1:] if len(ok) > 1 else ok  # buang panggilan pertama (pemuatan awal)
    llm_masih_termuat = [any(m["name"].startswith(LLM.split(":")[0]) for m in r["ps"]) for r in ok]
    return {
        "mode": hasil["mode"],
        "embed_median_s": round(statistics.median([r["embed_s"] for r in sisa]), 2) if sisa else None,
        "llm_median_s": round(statistics.median([r["llm_s"] for r in sisa]), 2) if sisa else None,
        "embed_pertama_s": ok[0]["embed_s"] if ok else None,
        "llm_masih_termuat_setelah_embed": f"{sum(llm_masih_termuat)}/{len(llm_masih_termuat)}",
        "ps_terakhir": ok[-1]["ps"] if ok else None,
        "jumlah_error": len(hasil["rows"]) - len(ok),
    }


def main():
    out = {"label": LABEL, "llm": LLM, "embed": EMB}
    try:
        out["versi"] = call("/api/version")[0]
        tags, _ = call("/api/tags")
        out["ukuran_model_gb"] = {m["name"]: round(m.get("size", 0) / 1e9, 2)
                                  for m in tags.get("models", [])
                                  if m["name"].split(":")[0] in (LLM.split(":")[0], EMB.split(":")[0])}
    except Exception as e:
        print("Ollama tidak terjangkau:", repr(e))
        sys.exit(1)
    hasil = [run_mode("embed_default", {}), run_mode("embed_cpu", {"num_gpu": 0})]
    out["hasil"] = hasil
    out["ringkasan"] = [ringkas(h) for h in hasil]
    path = Path(__file__).resolve().parent / f"bench_embed_{LABEL}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out["ringkasan"], ensure_ascii=False, indent=2))
    print("Disimpan:", path)


if __name__ == "__main__":
    main()
