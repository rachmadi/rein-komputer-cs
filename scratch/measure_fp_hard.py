import sys
sys.path.append("d:/RAG")
from core.normalizer import normalize
from services.knowledge_service import get_embedding, QDRANT_URL, KNOWLEDGE_COLLECTION
import requests

hard_negatives = [
    "gimana cara klaim garansi laptop asus?",
    "apakah service center buka hari minggu?",
    "bisa cicilan 12 bulan pakai kartu kredit bca?",
    "alamat toko bobby computer dimana ya?",
    "jam operasional toko dari jam berapa sampai jam berapa?",
    "laptop saya tiba-tiba mati total, bisa servis?",
    "layar laptop bergaris, kira-kira biaya perbaikannya berapa?",
    "keyboard macbook pro saya rusak, ada sparepartnya?",
    "berapa harga lenovo legion 5 pro sekarang?",
    "mending asus rog atau acer predator?",
    "apa bedanya prosesor intel core i5 dan i7?",
    "bagaimana cara install ulang windows 11?",
    "toko ini jual sparepart RAM ddr4 laptop nggak?",
    "apakah ada promo diskon akhir tahun?",
    "bisa tukar tambah laptop bekas nggak?",
    "baterai laptop cepet habis, itu kenapa ya?",
    "berapa biaya ganti pasta termal laptop?",
    "jual charger laptop hp pavilion?",
    "laptop asus vivobook saya lemot banget",
    "ada nomor wa teknisi yang bisa dihubungi?",
    "lebih bagus mana layar oled atau ips?",
    "cara masuk bios lenovo ideapad gimana?",
    "apakah gratis ongkir kalau beli lewat tokopedia?",
    "bisa upgrade ssd dari 512gb ke 1tb?",
    "saya butuh install aplikasi adobe premiere, bisa dibantu?"
]

fp_retrieval_only = 0
fp_retrieval_and_guard = 0
THRESHOLD = 0.45

for s in hard_negatives:
    vec = get_embedding(normalize(s))
    url = f"{QDRANT_URL}/collections/{KNOWLEDGE_COLLECTION}/points/search"
    resp = requests.post(url, json={"vector": vec, "limit": 1, "with_payload": True}, timeout=10)
    points = resp.json().get("result", [])
    if points:
        score = points[0].get("score", 0)
        if score >= THRESHOLD:
            fp_retrieval_only += 1
            
            # Guard check
            # if should_skip_rag is True, then guard successfully skips RAG (not a FP)
            from services.agentic_tool_engine import should_skip_rag
            from core.catalog import Catalog
            cat = Catalog.from_dummy()
            if not should_skip_rag(s, cat):
                fp_retrieval_and_guard += 1

print(f"FP Retrieval Only: {fp_retrieval_only}")
print(f"FP Retrieval + Guard: {fp_retrieval_and_guard}")
