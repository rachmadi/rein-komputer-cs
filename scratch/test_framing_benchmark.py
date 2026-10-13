import urllib.request
import json
import time

user_query = "laptop buat edit video 4k"
facts = "✅ 1. Lenovo Legion Pro 5 16 | Rp23.999.000\n  Spesifikasi: Intel Core i7-14700HX | RTX 4060 8GB | RAM 32 GB DDR5 | 1 TB SSD"

prompt = f"""Kamu adalah staf Customer Care toko Bobby Computer.
Tugasmu: Tulis 1 kalimat pembuka ramah dan 1 kalimat penutup singkat untuk menyapa pelanggan.
JANGAN mengulang spesifikasi atau daftar produk.
Pertanyaan user: "{user_query}"
Fakta produk yang disiapkan sistem:
{facts}

Keluarkan HANYA JSON format berikut:
{{"intro": "<1 kalimat pembuka>", "outro": "<1 kalimat penutup>"}}
"""

payload = {
    "model": "gemma4:e4b",
    "messages": [{"role": "user", "content": prompt}],
    "stream": False,
    "options": {"num_ctx": 1024, "num_predict": 100, "temperature": 0.3}
}

# 1. Benchmark Template
t0_tpl = time.perf_counter()
intro_tpl = "Halo Kak! Untuk kebutuhan edit video 4K, kami sudah pilihkan rekomendasi laptop terbaik dari katalog kami:"
outro_tpl = "Semua unit di atas bergaransi resmi. Kalau Kakak ingin cek opsi cicilan atau spesifikasi lainnya, beri tahu ya!"
t_tpl = (time.perf_counter() - t0_tpl) * 1000

# 2. Benchmark LLM
t0 = time.time()
req = urllib.request.Request("http://localhost:11434/api/chat", data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req) as resp:
    res = json.loads(resp.read().decode("utf-8"))
t_llm = time.time() - t0

content = res.get("message", {}).get("content", "")
print(f"=== LATENCY BENCHMARK ===")
print(f"Template Framing Latency: {t_tpl:.4f} ms ({t_tpl/1000:.6f} s)")
print(f"LLM Framing Latency:      {t_llm*1000:.2f} ms ({t_llm:.2f} s)")
print(f"\nLLM Generated Content:")
print(content)
