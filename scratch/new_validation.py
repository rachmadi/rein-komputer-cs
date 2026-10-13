import json
import requests
import os
from services.catalog_service import QDRANT_URL, get_embedding
from services.knowledge_service import normalize_query
from services.agentic_tool_engine import should_skip_rag
from core.catalog import Catalog

catalog = Catalog.load("qdrant")

COLLECTION = "computer_knowledge"

tests_20_validasi_baru = [
    # Gaul/Typo
    "cari lptop buar ngegame berat bang",
    "lepi yg enteng buat ngetik di kafe",
    "kmpter rakttn wat edit pidio tiktok",
    "ada lptp murah gak buat skripsi",
    "bang butuh spek dewa wat main siberpunk",
    "pc buat kasir mureh aja",
    "lptop gaming yg kaga cepet panas",
    # Inggris Campuran
    "looking for laptop buat office work aja",
    "need pc for rendering 3d parah",
    "best lptop for programming front end",
    "budget friendly pc for playing valorant",
    "any recommendation for streaming gear",
    "laptop for my mom buat nonton drakor",
    "mau beli pc for trading crypto",
    "need laptop for machine learning model training",
    # Variasi lain
    "buat desain grafis berat pake ilustrator",
    "butuh pc yg layarnya lega buat kerja",
    "pengen nge-print tugas banyak banget",
    "komputer mini buat di ruang tamu",
    "laptop yg baterainya awet seharian buat nugas"
]

tests_15_negatif_baru = [
    # Produk / Merek / SKU
    "beli asus rog strix",
    "harga lenovo legion pro",
    "spek acer nitro v 15",
    "cari macbook air m2",
    "printer canon pixma",
    # Tanya di luar peruntukan
    "kredit laptop tanpa dp",
    "cara cicilan pake paylater",
    "klaim garansi asus gimana bang",
    "toko buka jam berapa besok",
    "alamat toko offline dimana",
    # Sapaan / Basa-basi
    "halo selamat pagi",
    "makasih bang informasinya",
    "p bang",
    "lagi sibuk ga nih",
    "mantap banget rekomendasinya"
]

def run_tests_with_guard(name, dataset, is_negative=False):
    print(f"\n--- {name} ---")
    pos_retrieved = 0
    pos_total = 0
    neg_fp = 0
    neg_total = 0
    
    for q in dataset:
        skip = should_skip_rag(q, catalog)
        if skip:
            print(f"[GUARD SKIP] Q: {q}")
            if not is_negative:
                pos_total += 1
            else:
                neg_total += 1
            continue
            
        vec = get_embedding(normalize_query(q))
        payload = {"vector": vec, "limit": 1, "with_payload": True}
        r = requests.post(f"{QDRANT_URL}/collections/{COLLECTION}/points/search", json=payload)
        res = r.json().get("result", [])
        
        top1 = res[0] if len(res) > 0 else None
        p1 = top1["payload"].get("id", "??") if top1 else "??"
        s1 = top1["score"] if top1 else 0.0
        
        is_retrieved = s1 >= 0.45
        
        if not is_negative:
            pos_total += 1
            if is_retrieved: pos_retrieved += 1
        else:
            neg_total += 1
            if is_retrieved: neg_fp += 1
            
        print(f"[{'PASS' if is_retrieved else 'FAIL-TH'}] Q: {q} -> {p1} ({s1:.4f})")
        
    if not is_negative:
        print(f"=> Recall Positif di 0.45: {pos_retrieved}/{pos_total} ({(pos_retrieved/pos_total)*100:.1f}%)")
    else:
        print(f"=> False Positive (Negatif Lolos): {neg_fp}/{neg_total}")

run_tests_with_guard("20 Validasi Baru (Positif)", tests_20_validasi_baru, False)
run_tests_with_guard("15 Validasi Baru (Negatif)", tests_15_negatif_baru, True)
