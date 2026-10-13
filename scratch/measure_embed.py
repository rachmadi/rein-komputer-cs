import time
import requests
import json
import csv

sentences = [
    "halo selamat pagi",
    "berapa harga laptop ini",
    "mau cari komputer gaming",
    "bisa cicilan pakai kartu kredit",
    "alamat toko dimana",
    "kapan toko buka",
    "layar laptop rusak",
    "laptop asus rog",
    "saya butuh laptop untuk kuliah",
    "ada diskon hari ini?"
]

times = []
for s in sentences:
    t0 = time.time()
    resp = requests.post("http://localhost:11434/api/embeddings", json={
        "model": "bge-m3",
        "prompt": s,
        "keep_alive": "60m"
    })
    resp.raise_for_status()
    dt = time.time() - t0
    times.append(dt)

avg_time = sum(times) / len(times)

with open("d:/RAG/docs/embedding_latency.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["sentence", "latency_s"])
    for s, t in zip(sentences, times):
        writer.writerow([s, f"{t:.4f}"])
    writer.writerow(["AVERAGE", f"{avg_time:.4f}"])

print(f"Average Embedding Time: {avg_time:.4f}s")
