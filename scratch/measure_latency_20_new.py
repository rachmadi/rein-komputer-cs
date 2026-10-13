# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, ".")
import time
import statistics
import csv
from services.agentic_tool_engine import run_agentic_tool
from core.catalog import Catalog
import services.knowledge_service

cat = Catalog.from_dummy()

queries_20 = [
    "laptop buat mahasiswa teknik sipil hitung SAP2000",
    "komputer meja untuk studio rekaman musik podcast",
    "laptop tipis layar bagus untuk nonton netflix dan drakor",
    "PC desktop mini untuk laboratorium bahasa sekolah",
    "laptop untuk desainer UI UX pakai figma lancar",
    "laptop buat guru bikin modul ajar dan presentasi canva",
    "komputer render animasi 3D blender dan after effects",
    "laptop buat anak SMA belajar coding python pemula",
    "komputer gaming e-sports main valorant 144hz lancar",
    "laptop kerja kantoran excel vlookup dan data entry",
    "komputer kasir resto touch screen cetak struk",
    "laptop bisnis ringan buat sering dinas luar kota",
    "PC gaming cyberpunk 2077 ray tracing settingan rata kanan",
    "laptop mahasiswa kedokteran buka jurnal dan anatomi 3D",
    "komputer buat kantor notaris ketik akta dan scan dokumen",
    "laptop buat fotografer edit ratusan foto raw lightroom",
    "PC server mini buat database toko kelontong kasir",
    "laptop buat arsitek render lumion dan rancang autocad",
    "laptop multimedia layar jernih baterai irit buat santai",
    "komputer editing video vlog 4k youtube premiere pro"
]

print("=== PENGUKURAN LATENSI 20 KALIMAT BARU (CACHE MATI) ===")
latencies_ms = []
rows = []

for idx, q in enumerate(queries_20, 1):
    # Matikan / bersihkan cache profil memori sebelum setiap iterasi
    services.knowledge_service._PROFILE_CACHE.clear()

    t0 = time.perf_counter()
    res = run_agentic_tool(q, [], cat)
    dt_ms = (time.perf_counter() - t0) * 1000.0
    latencies_ms.append(dt_ms)

    route = res.get("route")
    prof = res.get("active_profile_id")
    prods = [p["kode"] for p in res.get("products", [])]
    
    print(f"[{idx:02d}] {dt_ms:7.2f} ms | Route: {route:<13} | Profile: {str(prof):<10} | '{q}'")
    rows.append({
        "no": idx,
        "query": q,
        "route": route,
        "profile": prof,
        "latency_ms": round(dt_ms, 2)
    })

sorted_lats = sorted(latencies_ms)
min_lat = sorted_lats[0]
max_lat = sorted_lats[-1]
mean_lat = sum(latencies_ms) / len(latencies_ms)
p50 = statistics.median(latencies_ms)
# P95 pada 20 sampel: index int(0.95 * 20) - 1 = 18 (elemen ke-19)
p95 = sorted_lats[int(0.95 * len(sorted_lats)) - 1]

print("\n" + "=" * 50)
print(f"Statistik Latensi (20 Kalimat Baru, Cache Mati):")
print(f"  Min : {min_lat:.2f} ms")
print(f"  Max : {max_lat:.2f} ms")
print(f"  Mean: {mean_lat:.2f} ms")
print(f"  p50 : {p50:.2f} ms")
print(f"  p95 : {p95:.2f} ms")
print("=" * 50)

# Simpan ke CSV
with open("docs/latency_20_new.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["no", "query", "route", "profile", "latency_ms"])
    writer.writeheader()
    writer.writerows(rows)
    f.write(f"\n# Summary: Min={min_lat:.2f}ms, Max={max_lat:.2f}ms, Mean={mean_lat:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms\n")

print("Hasil tersimpan di docs/latency_20_new.csv")
