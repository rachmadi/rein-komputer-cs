import sys
sys.path.append("d:/RAG")

from services.knowledge_service import get_embedding, QDRANT_URL, KNOWLEDGE_COLLECTION, RAG_SCORE_THRESHOLD
import requests
from core.normalizer import normalize

negative_sentences = [
    "cara masak nasi goreng enak",
    "jadwal bola liga inggris malam ini",
    "berapa harga tiket pesawat ke bali",
    "rekomendasi wisata di jogja",
    "tutorial makeup natural untuk pemula",
    "review film horror terbaru",
    "cara menanam cabe di pot",
    "berita politik hari ini",
    "cara memperbaiki genteng bocor",
    "resep kue bolu kukus",
    "tips diet sehat menurunkan berat badan",
    "hasil pertandingan bulutangkis",
    "cara membuat kerajinan dari botol bekas",
    "sejarah kemerdekaan indonesia",
    "lirik lagu pop populer",
    "cara investasi saham pemula",
    "daftar harga mobil bekas",
    "tips merawat kulit wajah",
    "cara daftar bpjs online",
    "ramalan zodiak minggu ini"
]

false_positives = 0
for s in negative_sentences:
    vec = get_embedding(normalize(s))
    url = f"{QDRANT_URL}/collections/{KNOWLEDGE_COLLECTION}/points/search"
    payload = {
        "vector": vec,
        "limit": 1,
        "with_payload": True
    }
    resp = requests.post(url, json=payload, timeout=10)
    points = resp.json().get("result", [])
    if points:
        score = points[0].get("score", 0)
        if score >= RAG_SCORE_THRESHOLD:
            false_positives += 1
            print(f"FP: '{s}' -> score {score:.4f} (Profile: {points[0]['payload']['judul']})")

print(f"Total Sentences: {len(negative_sentences)}")
print(f"False Positives: {false_positives}")
fp_rate = (false_positives / len(negative_sentences)) * 100
print(f"False Positive Rate: {fp_rate:.1f}%")
