# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, ".")
import time
from services.agentic_tool_engine import run_agentic_tool
from core.catalog import Catalog

cat = Catalog.from_dummy()

unseen_queries = [
    "PC untuk simulasi kasir minimarket sekaligus render model 3D blender di malam hari",
    "komputer gaming berat Black Myth Wukong tapi juga dipakai kasir kasbon",
    "laptop untuk rendering 3D Maya studio sekalian main game berat",
    "PC desktop kasir toko grosir merangkap render animasi 3D",
    "butuh laptop yang kuat game triple A dan juga buat render 3D arsitektur",
    "komputer untuk admin kasir barcode dan render video 3D produk",
    "laptop buat main game berat rata kanan sambil render 3D",
    "PC untuk kasir ritel harian tapi sorenya buat gaming berat",
    "perangkat render 3D modeling berat dan sesekali game berat",
    "PC buat program kasir toko kelontong tanpa butuh spek berat"
]

print("=== PENGUJIAN 10 KALIMAT BARU BELUM PERNAH DILIHAT ===")
results = []
for idx, q in enumerate(unseen_queries, 1):
    t0 = time.time()
    res = run_agentic_tool(q, [], cat)
    dt_ms = (time.time() - t0) * 1000
    route = res.get("route")
    prof = res.get("active_profile_id")
    prods = [p["kode"] for p in res.get("products", [])]
    reply = res.get("reply", "")
    
    status = "SUCCESS" if prods else "EMPTY/CLARIFY"
    print(f"[{idx:02d}] Query: {q}")
    print(f"     Profile: {prof} | Route: {route} | Prods: {prods} | Time: {dt_ms:.1f}ms")
    first_line = reply.strip().split("\n")[0]
    print(f"     Reply Header: {first_line[:90]}")
    print("-" * 60)
    results.append({
        "no": idx,
        "query": q,
        "profile": prof,
        "route": route,
        "products": prods,
        "time_ms": dt_ms
    })
