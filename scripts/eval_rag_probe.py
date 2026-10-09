# -*- coding: utf-8 -*-
"""
scripts/eval_rag_probe.py
Evaluasi empiris ambang batas skor RAG Qdrant untuk 20 kueri sintetis (in-domain & OOD)
tanpa kamus heuristik (murni representasi semantik vektor embedding).
Menghasilkan eval/rag_probe.csv.
"""
import os
import csv
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import requests
from services.catalog_service import QDRANT_URL, get_embedding
from services.knowledge_service import KNOWLEDGE_COLLECTION, RAG_SCORE_THRESHOLD

PROBE_QUERIES = [
    # In-Domain (Bahasa santai, ejaan umum, aktivitas komputasi nyata)
    ("kuliah informatika coding python dan web", "in_domain", "P06"),
    ("edit video 4k vlog youtube", "in_domain", "P03"),
    ("kasir toko kelontong minimarket", "in_domain", "P15"),
    ("arsitektur render sketchup 3d autocad", "in_domain", "P07"),
    ("baca berita resep masakan dan youtube pensiunan", "in_domain", "P11"),
    ("main game berat genshin impact dan cyberpunk", "in_domain", "P05"),
    ("desain grafis coreldraw photoshop spanduk percetakan", "in_domain", "P02"),
    ("kantor excel spreadsheet ketik skripsi admin", "in_domain", "P01"),
    ("trading saham pantau chart kripto multi layar", "in_domain", "P10"),
    ("rekaman podcast mixing audio fl studio", "in_domain", "P08"),
    ("data science machine learning deep learning jupyter", "in_domain", "P09"),
    ("live streaming game obs vtuber", "in_domain", "P13"),
    ("belajar anak sd zoom dan canva sekolah", "in_domain", "P10"),
    ("pemrograman mobile android studio flutter emulator", "in_domain", "P06"),
    ("animasi 3d blender render eevee cycles", "in_domain", "P04"),
    ("kerja remote zoom meeting multitasking tab banyak", "in_domain", "P01"),
    # Out of Domain (OOD - Bukan kebutuhan komputasi / non-komputer)
    ("aktivitas antariksa gravitasi nol planet mars", "ood", "NONE"),
    ("memasak kue bolu panggang oven dapur restoran", "ood", "NONE"),
    ("perjalanan wisata hiking gunung pulau terpencil", "ood", "NONE"),
    ("reparasi mesin motor balap bengkel knalpot", "ood", "NONE"),
]

def run_probe():
    os.makedirs("eval", exist_ok=True)
    out_csv = "eval/rag_probe.csv"

    rows = []
    print(f"Menjalankan RAG Probe pada collection '{KNOWLEDGE_COLLECTION}' dengan ambang {RAG_SCORE_THRESHOLD}...")

    for idx, (query, q_type, expected) in enumerate(PROBE_QUERIES, 1):
        vec = get_embedding(query)
        if not vec:
            print(f"[{idx}] Gagal mendapatkan embedding untuk '{query}'")
            continue

        resp = requests.post(
            f"{QDRANT_URL}/collections/{KNOWLEDGE_COLLECTION}/points/search",
            json={"vector": vec, "limit": 1, "with_payload": True},
            timeout=10
        ).json()

        results = resp.get("result", [])
        if results:
            top_hit = results[0]
            pid = top_hit.get("payload", {}).get("id", "UNKNOWN")
            score = round(top_hit.get("score", 0.0), 4)
        else:
            pid = "NONE"
            score = 0.0

        status_ambang = "lolos" if score >= RAG_SCORE_THRESHOLD else "ditolak"
        is_correct_detection = (
            (q_type == "in_domain" and status_ambang == "lolos") or
            (q_type == "ood" and status_ambang == "ditolak")
        )

        rows.append({
            "no": idx,
            "kueri": query,
            "kategori": q_type,
            "profil_teratas": pid,
            "skor_kosinus": score,
            "status_ambang": status_ambang,
            "deteksi_benar": "BENAR" if is_correct_detection else "SALAH"
        })
        print(f"[{idx:02d}] {q_type.upper():10s} | {score:.4f} | {status_ambang:7s} | Top: {pid:4s} | {query}")

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["no", "kueri", "kategori", "profil_teratas", "skor_kosinus", "status_ambang", "deteksi_benar"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nBerhasil menyimpan hasil probe ke {out_csv}")

if __name__ == "__main__":
    run_probe()
