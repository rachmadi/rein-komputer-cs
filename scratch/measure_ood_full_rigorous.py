import os
import sys
import json
import csv
import time
import requests

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "knowledge_test"

from services.catalog_service import get_embedding
from scripts.ingest_knowledge import parse_kb, KNOWLEDGE_FILE
from services.agentic_tool_engine import should_skip_rag

# Set pengembangan penuh (positif dan negatif sulit)
DEV_SET = [
    # Positif (query, expected_profil_id)
    ("laptop buat edit video 4k", "P03", True),
    ("komputer untuk game AAA berat", "P05", True),
    ("laptop kuliah sehari-hari", "P06", True),
    ("laptop baterai awet", "P16", True),
    ("ada diskon laptop gaming", "P04", True),
    ("install apa saja untuk laptop kuliah", "P06", True),
    ("laptop desain grafis dan edit foto", "P02", True),
    ("komputer kasir toko", "P15", True),
    ("laptop streaming youtube", "P08", True),
    ("laptop data science AI machine learning", "P13", True),
    # Negatif sulit (OOD - tidak boleh dipetakan ke profil spek rekomendasi)
    ("berapa jam buka toko Bobby Computer", None, False),
    ("cara bayar cicilan atau kredit", None, False),
    ("garansi laptop resmi berapa tahun", None, False),
    ("ongkos kirim ke Surabaya berapa ya", None, False),
    ("apakah hari minggu toko buka", None, False),
]

def recreate_collection():
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

def ingest_chunks(chunks):
    texts = [f"Judul: {c['judul']}. Kata Kunci: {', '.join(c.get('kata_kunci', []))}. Perangkat: {c.get('perangkat', '')}." for c in chunks]
    vecs = get_embeddings_batch(texts)
    points = []
    import uuid
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
    resp = requests.post(url, json={
        "vector": vec,
        "limit": 3,
        "with_payload": True
    }, timeout=10)
    hits = resp.json().get("result", [])
    return hits

def evaluate(label: str):
    results = []
    # Metrics
    # Retrieval-only
    ret_tp = ret_fp = ret_fn = ret_tn = 0
    # Retrieval + Guard (di_luar_topik or guard check)
    guard_tp = guard_fp = guard_fn = guard_tn = 0

    for query, expected_id, is_pos in DEV_SET:
        t0 = time.time()
        hits = query_retrieval(query)
        dt = time.time() - t0

        top_hit = hits[0] if hits else None
        top_score = top_hit.get("score", 0.0) if top_hit else 0.0
        top_id = top_hit.get("payload", {}).get("id") if top_hit else None
        top_tipe = top_hit.get("payload", {}).get("tipe") if top_hit else None

        # Retrieval-only judgment
        # In retrieval-only: if positive and top_id == expected -> TP, else FN
        # if negative: if retrieval matched any spec profile with score >= 0.55 -> FP, else TN
        if is_pos:
            ret_matched = (top_id == expected_id)
            if ret_matched: ret_tp += 1
            else: ret_fn += 1
        else:
            ret_is_spec = (top_tipe in ("profil", "panduan umum", "panduan kategori") and top_score >= 0.55)
            if ret_is_spec: ret_fp += 1
            else: ret_tn += 1

        # Retrieval + Guard judgment
        # Guard filters if top_tipe == "di_luar_topik" OR should_skip_rag or threshold rejected
        if is_pos:
            guard_matched = (top_id == expected_id and top_tipe != "di_luar_topik")
            if guard_matched: guard_tp += 1
            else: guard_fn += 1
        else:
            # For negative: if guard marks it as di_luar_topik or rejected -> TN, else FP
            guard_blocked = (top_tipe == "di_luar_topik" or top_score < 0.55 or not top_id)
            if guard_blocked: guard_tn += 1
            else: guard_fp += 1

        results.append({
            "stage": label,
            "query": query,
            "expected": expected_id or "OOD",
            "top_hit_id": top_id,
            "top_tipe": top_tipe,
            "score": round(top_score, 4),
            "is_positive": is_pos,
            "ret_correct": ret_matched if is_pos else not ret_is_spec,
            "guard_correct": guard_matched if is_pos else guard_blocked,
            "latency_s": round(dt, 3)
        })

    ret_recall = ret_tp / (ret_tp + ret_fn) if (ret_tp + ret_fn) > 0 else 0
    ret_fp_rate = ret_fp / (ret_fp + ret_tn) if (ret_fp + ret_tn) > 0 else 0
    guard_recall = guard_tp / (guard_tp + guard_fn) if (guard_tp + guard_fn) > 0 else 0
    guard_fp_rate = guard_fp / (guard_fp + guard_tn) if (guard_fp + guard_tn) > 0 else 0

    summary = {
        "stage": label,
        "pos_count": 10,
        "neg_count": 5,
        "retrieval_tp": ret_tp,
        "retrieval_fp": ret_fp,
        "retrieval_fn": ret_fn,
        "retrieval_tn": ret_tn,
        "retrieval_recall": round(ret_recall, 4),
        "retrieval_fp_rate": round(ret_fp_rate, 4),
        "guard_tp": guard_tp,
        "guard_fp": guard_fp,
        "guard_fn": guard_fn,
        "guard_tn": guard_tn,
        "guard_recall": round(guard_recall, 4),
        "guard_fp_rate": round(guard_fp_rate, 4),
    }
    return results, summary

# 1. SEBELUM INGEST: 22 Chunks Standar
recreate_collection()
base_chunks = parse_kb(KNOWLEDGE_FILE)
ingest_chunks(base_chunks)
res_before, sum_before = evaluate("SEBELUM_INGEST")

# 2. SESUDAH INGEST: Tambah 3 Chunks OOD
ood_chunks = [
    {
        "id": "OOD1",
        "tipe": "di_luar_topik",
        "judul": "Info Toko, Lokasi, dan Jam Operasional",
        "kategori": None,
        "perangkat": "none",
        "kata_kunci": ["jam buka", "alamat", "lokasi", "toko dimana", "hari minggu buka", "tutup jam berapa", "cabang", "parkir", "denah"],
        "filter": [],
        "catatan": "Chunk di luar topik info operasional toko."
    },
    {
        "id": "OOD2",
        "tipe": "di_luar_topik",
        "judul": "Garansi, Servis, dan Purna Jual",
        "kategori": None,
        "perangkat": "none",
        "kata_kunci": ["garansi berapa lama", "servis laptop rusak", "ganti baterai", "klaim garansi", "garansi resmi", "perbaikan", "layanan purna jual", "service center"],
        "filter": [],
        "catatan": "Chunk di luar topik garansi dan purna jual."
    },
    {
        "id": "OOD3",
        "tipe": "di_luar_topik",
        "judul": "Pembayaran, Cicilan, dan Pengiriman",
        "kategori": None,
        "perangkat": "none",
        "kata_kunci": ["bisa cicil", "kredit", "paylater", "tokopedia", "shopee", "ongkir", "gratis ongkir", "bayar pakai kartu", "pengiriman hari ini", "cod", "gosend"],
        "filter": [],
        "catatan": "Chunk di luar topik transaksi dan pembayaran."
    }
]

recreate_collection()
ingest_chunks(base_chunks + ood_chunks)
res_after, sum_after = evaluate("SESUDAH_INGEST")

# Simpan CSV
os.makedirs("docs", exist_ok=True)
with open("docs/ood_full_eval.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(res_before[0].keys()))
    w.writeheader()
    w.writerows(res_before)
    w.writerows(res_after)

with open("docs/ood_summary.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(sum_before.keys()))
    w.writeheader()
    w.writerow(sum_before)
    w.writerow(sum_after)

print("=== OOD EVALUATION SUMMARY ===")
print("SEBELUM INGEST:")
print(f"  Positif Recall (Retrieval): {sum_before['retrieval_recall']*100:.1f}% | FP Rate: {sum_before['retrieval_fp_rate']*100:.1f}% ({sum_before['retrieval_fp']}/5)")
print(f"  Positif Recall (Guard):     {sum_before['guard_recall']*100:.1f}% | FP Rate: {sum_before['guard_fp_rate']*100:.1f}% ({sum_before['guard_fp']}/5)")
print("\nSESUDAH INGEST (dengan OOD chunks pada knowledge_test):")
print(f"  Positif Recall (Retrieval): {sum_after['retrieval_recall']*100:.1f}% | FP Rate: {sum_after['retrieval_fp_rate']*100:.1f}% ({sum_after['retrieval_fp']}/5)")
print(f"  Positif Recall (Guard):     {sum_after['guard_recall']*100:.1f}% | FP Rate: {sum_after['guard_fp_rate']*100:.1f}% ({sum_after['guard_fp']}/5)")
