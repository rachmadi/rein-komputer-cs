# -*- coding: utf-8 -*-
import os
import sys
sys.path.insert(0, ".")
import json
import csv
import time
import requests
import uuid

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "knowledge_test"

from services.catalog_service import get_embedding
from core.catalog import Catalog
from scripts.ingest_knowledge import parse_kb, KNOWLEDGE_FILE
from services.agentic_tool_engine import should_skip_rag
from services.intent_router import classify_intent

# Set pengembangan penuh (20 Positif, 25 Negatif Sulit)
DEV_SET_POSITIVE = [
    ("laptop buat edit video 4k", "P03"),
    ("komputer untuk game AAA berat", "P05"),
    ("laptop kuliah sehari-hari untuk mahasiswa", "P01"),
    ("laptop baterai awet untuk kerja kantoran", "P01"),
    ("ada laptop gaming terjangkau untuk main valorant", "P04"),
    ("laptop buat koding python dan docker", "P06"),
    ("laptop desain grafis dan edit foto photoshop", "P02"),
    ("komputer kasir toko ritel", "P15"),
    ("laptop streaming youtube dan obs studio", "P08"),
    ("laptop data science AI machine learning", "P13"),
    ("komputer buat trading saham 4 monitor", "P10"),
    ("laptop untuk akuntan kerja excel formula berat", "P14"),
    ("laptop buat arsitek render autocad sketchup", "P07"),
    ("komputer untuk bikin musik studio rekaman", "P09"),
    ("laptop sederhana untuk orang tua browsing berita", "P11"),
    ("laptop buat content creator video pendek tiktok", "P12"),
    ("laptop buat kerja kantoran administrasi surat", "P01"),
    ("komputer pc desktop untuk render animasi blender", "P03"),
    ("komputer kasir pos barcode minimarket", "P15"),
    ("laptop serbaguna buat kuliah dan game santai", "P16"),
]

DEV_SET_NEGATIVE = [
    ("berapa jam buka toko Bobby Computer hari ini", None),
    ("cara bayar cicilan atau kredit apakah ada paylater", None),
    ("garansi laptop resmi di toko berapa tahun", None),
    ("ongkos kirim ke Surabaya atau luar pulau berapa", None),
    ("apakah hari minggu toko buka dan ada teknisi", None),
    ("alamat toko fisik Bobby Computer di jalan mana", None),
    ("bisa minta nomor whatsapp customer service toko", None),
    ("apakah menerima tukar tambah laptop bekas", None),
    ("cara klaim garansi jika layar bergaris atau rusak", None),
    ("apakah ada jasa servis ganti pasta termal laptop", None),
    ("metode pembayaran apa saja yang diterima di kasir", None),
    ("apakah melayani pengiriman instant gojek grab", None),
    ("syarat kredit laptop tanpa kartu kredit apa saja", None),
    ("apakah ada promo diskon ulang tahun toko bulan ini", None),
    ("apakah barang yang dibeli bisa dikembalikan jika tidak cocok", None),
    ("bisa minta pricelist brosur lengkap format pdf", None),
    ("apakah toko menjual makanan atau minuman ringan", None),
    ("dimana lokasi parkir mobil untuk pengunjung toko", None),
    ("apakah teknisi toko bisa datang ke rumah atau kantor", None),
    ("apakah melayani instalasi software bajakan atau crack", None),
    ("resep membuat kopi espresso yang enak bagaimana", None),
    ("jadwal pertandingan sepak bola piala dunia malam ini", None),
    ("cuaca di Jakarta besok diperkirakan hujan atau panas", None),
    ("siapa penemu komputer pertama di dunia", None),
    ("kurs dollar amerika ke rupiah hari ini berapa", None),
]

FULL_DEV_SET = [(q, exp, True) for q, exp in DEV_SET_POSITIVE] + [(q, exp, False) for q, exp in DEV_SET_NEGATIVE]

def recreate_test_collection():
    requests.delete(f"{QDRANT_URL}/collections/{COLLECTION_NAME}")
    requests.put(f"{QDRANT_URL}/collections/{COLLECTION_NAME}", json={"vectors": {"size": 1024, "distance": "Cosine"}})

def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    resp = requests.post(
        "http://localhost:11434/api/embed",
        json={"model": "bge-m3", "input": texts, "keep_alive": "5m"},
        timeout=120
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]

def ingest_chunks_to_test(chunks):
    texts = [f"Judul: {c['judul']}. Kata Kunci: {', '.join(c.get('kata_kunci', []))}. Perangkat: {c.get('perangkat', '')}." for c in chunks]
    vecs = get_embeddings_batch(texts)
    points = []
    for i, (c, vec) in enumerate(zip(chunks, vecs)):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, c["id"] or str(i)))
        points.append({
            "id": point_id,
            "vector": vec,
            "payload": {
                "id": c["id"],
                "profil_id": c["id"],
                "tipe": c["tipe"],
                "judul": c["judul"],
                "kategori": c.get("kategori"),
                "filter": c.get("filter", []),
                "catatan": c.get("catatan", "")
            }
        })
    requests.put(f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points?wait=true", json={"points": points})

def query_retrieval(query_text: str):
    vec = get_embeddings_batch([query_text])[0]
    url = f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/search"
    # Filter: G dan M dilarang keras (hanya tipe profil)
    resp = requests.post(url, json={
        "vector": vec,
        "limit": 5,
        "filter": {
            "must": [{"key": "tipe", "match": {"value": "profil"}}]
        },
        "with_payload": True
    }, timeout=10)
    hits = resp.json().get("result", [])
    # Post-filter in Python: reject G and M
    valid_hits = [
        h for h in hits
        if h.get("payload", {}).get("tipe") == "profil" and not str(h.get("payload", {}).get("id", "")).startswith(("G", "M"))
    ]
    return valid_hits

def run_evaluation(phase_name: str):
    print(f"\n--- Menjalankan Evaluasi OOD: {phase_name} ---")
    ret_tp = ret_fp = ret_fn = ret_tn = 0
    guard_tp = guard_fp = guard_fn = guard_tn = 0
    records = []

    for query, expected_id, is_pos in FULL_DEV_SET:
        t0 = time.time()
        hits = query_retrieval(query)
        dt = time.time() - t0

        top_hit = hits[0] if hits else None
        top_score = top_hit.get("score", 0.0) if top_hit else 0.0
        top_id = top_hit.get("payload", {}).get("id") if top_hit else None

        # Evaluasi Retrieval murni (ambang 0.40)
        ret_qualifies = (top_score >= 0.40 and top_id is not None)
        if is_pos:
            if ret_qualifies: ret_tp += 1
            else: ret_fn += 1
        else:
            if ret_qualifies: ret_fp += 1
            else: ret_tn += 1

        # Evaluasi Retrieval + Guard
        intent = classify_intent(query)
        cat_dummy = Catalog.from_dummy()
        is_ood = (intent == "di-luar-topik" or should_skip_rag(query, cat_dummy))
        guard_passes = ret_qualifies and not is_ood

        if is_pos:
            if guard_passes: guard_tp += 1
            else: guard_fn += 1
        else:
            if guard_passes: guard_fp += 1
            else: guard_tn += 1

        records.append({
            "phase": phase_name,
            "query": query,
            "is_positive": is_pos,
            "expected_id": expected_id,
            "top_id": top_id,
            "top_score": round(top_score, 4),
            "ret_qualifies": ret_qualifies,
            "intent": intent,
            "guard_blocked": is_ood,
            "guard_passes": guard_passes,
            "latency_ms": round(dt * 1000, 2)
        })

    pos_total = len(DEV_SET_POSITIVE)
    neg_total = len(DEV_SET_NEGATIVE)

    ret_recall = ret_tp / pos_total if pos_total else 0.0
    ret_fp_rate = ret_fp / neg_total if neg_total else 0.0

    guard_recall = guard_tp / pos_total if pos_total else 0.0
    guard_fp_rate = guard_fp / neg_total if neg_total else 0.0

    print(f"Hasil {phase_name}:")
    print(f"  Positif ({pos_total} kueri):")
    print(f"    Retrieval-only Recall : {ret_recall * 100:.1f}% ({ret_tp}/{pos_total})")
    print(f"    Retrieval+Guard Recall: {guard_recall * 100:.1f}% ({guard_tp}/{pos_total})")
    print(f"  Negatif Sulit ({neg_total} kueri):")
    print(f"    Retrieval-only FP     : {ret_fp}/{neg_total} ({ret_fp_rate * 100:.1f}%)")
    print(f"    Retrieval+Guard FP    : {guard_fp}/{neg_total} ({guard_fp_rate * 100:.1f}%)")

    return {
        "phase": phase_name,
        "ret_tp": ret_tp, "ret_fn": ret_fn, "ret_fp": ret_fp, "ret_tn": ret_tn,
        "ret_recall": ret_recall, "ret_fp_rate": ret_fp_rate,
        "guard_tp": guard_tp, "guard_fn": guard_fn, "guard_fp": guard_fp, "guard_tn": guard_tn,
        "guard_recall": guard_recall, "guard_fp_rate": guard_fp_rate,
        "records": records
    }

if __name__ == "__main__":
    print("Memulai Pengujian OOD pada Koleksi Uji (Koleksi Produksi DILINDUNGI)...")
    recreate_test_collection()
    
    # 1. Sebelum Ingest (koleksi uji kosong)
    res_before = run_evaluation("SEBELUM_INGEST")

    # 2. Ingest seluruh chunk ke koleksi uji
    chunks = parse_kb(KNOWLEDGE_FILE)
    print(f"\nMelakukan Ingest {len(chunks)} chunk ke koleksi uji '{COLLECTION_NAME}'...")
    ingest_chunks_to_test(chunks)
    print("Ingest ke koleksi uji selesai.")

    # 3. Sesudah Ingest
    res_after = run_evaluation("SESUDAH_INGEST")

    # Simpan ke CSV
    all_records = res_before["records"] + res_after["records"]
    with open("docs/ood_full_eval_v2.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_records[0].keys()))
        writer.writeheader()
        writer.writerows(all_records)

    with open("docs/ood_summary_v2.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Fase", "Recall Positif Retrieval", "Recall Positif Guard", "FP Negatif Retrieval", "FP Negatif Guard"])
        writer.writerow([
            "SEBELUM_INGEST",
            f"{res_before['ret_recall']*100:.1f}%", f"{res_before['guard_recall']*100:.1f}%",
            f"{res_before['ret_fp_rate']*100:.1f}%", f"{res_before['guard_fp_rate']*100:.1f}%"
        ])
        writer.writerow([
            "SESUDAH_INGEST",
            f"{res_after['ret_recall']*100:.1f}%", f"{res_after['guard_recall']*100:.1f}%",
            f"{res_after['ret_fp_rate']*100:.1f}%", f"{res_after['guard_fp_rate']*100:.1f}%"
        ])

    print("\nFile CSV evaluasi OOD berhasil disimpan di docs/ood_full_eval_v2.csv dan docs/ood_summary_v2.csv")
