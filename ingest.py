# -*- coding: utf-8 -*-
"""
Ingestion Pipeline: PDF -> Structured Product Records -> Qdrant (§16)
Membaca Katalog_Komputer_RAG.pdf, mengekstrak spesifikasi dan tag kebutuhan terstruktur,
membuat embedding BGE-M3 melalui Ollama, dan menyimpan payload terstruktur ke Qdrant.
"""
from __future__ import annotations

import re
import requests
import pymupdf
from core.catalog import parse_product_text, derive_tags
from core.normalizer import normalize

PDF_PATH = "data/Katalog_Komputer_RAG.pdf"
QDRANT_URL = "http://localhost:6333"
OLLAMA_URL = "http://localhost:11434"
COLLECTION_NAME = "computer_knowledge"
EMBED_MODEL = "bge-m3"

def extract_chunks_from_pdf(pdf_path: str) -> list[str]:
    doc = pymupdf.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text() + "\n"
        
    marker = "Detail Produk dan Product Knowledge"
    if marker not in text:
        raise ValueError(f"Marker '{marker}' tidak ditemukan di PDF.")
        
    detail_text = text.split(marker, 1)[1]
    detail_text = detail_text.split("Kebijakan Knowledge Base", 1)[0]
    
    pattern = r"(?=KB-[A-Z]\d+\b)"
    chunks = re.split(pattern, detail_text)
    return [c.strip() for c in chunks if c.strip()]

def get_embedding(text: str, ollama_url: str = OLLAMA_URL, model: str = EMBED_MODEL) -> list[float]:
    response = requests.post(
        f"{ollama_url}/api/embed",
        json={"model": model, "input": text},
        timeout=60
    )
    response.raise_for_status()
    return response.json()["embeddings"][0]

def build_aliases(record: dict) -> list[str]:
    aliases = [record["nama"].lower(), record["kode"].lower()]
    norm_name = normalize(record["nama"])
    aliases.append(norm_name)
    aliases.append(normalize(record["kode"]))
    aliases.append(record["kode"].lower().replace("-", " "))
    aliases.append(record["kode"].lower().replace("-", ""))
    return list(dict.fromkeys(aliases))

def main():
    print(f"1. Membaca PDF: {PDF_PATH}...")
    chunks = extract_chunks_from_pdf(PDF_PATH)
    print(f"   Ditemukan {len(chunks)} produk.")

    # Siapkan koleksi di Qdrant
    chk = requests.get(f"{QDRANT_URL}/collections/{COLLECTION_NAME}")
    if chk.status_code == 404:
        print(f"   Membuat koleksi baru: '{COLLECTION_NAME}' (1024 dimensi, Cosine)...")
        requests.put(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}",
            json={"vectors": {"size": 1024, "distance": "Cosine"}}
        ).raise_for_status()

    points = []
    print("\n2. Mengekstrak data terstruktur & membuat embedding BGE-M3:")
    for idx, chunk in enumerate(chunks, 1):
        rec = parse_product_text(chunk)
        if not rec:
            print(f"   [Peringatan] Gagal parse chunk #{idx}, lewati.")
            continue
            
        rec["alias"] = build_aliases(rec)
        print(f"   [{idx}/{len(chunks)}] {rec['kode']} — {rec['nama']} ({rec['kategori']}, Rp{rec['harga_idr']:,})")
        
        # Buat embedding vektor
        vector = get_embedding(chunk)
        
        # Susun payload terstruktur (§16)
        payload = {
            "code": rec["kode"],
            "kode": rec["kode"],
            "product": rec["nama"],
            "nama": rec["nama"],
            "kategori": rec["kategori"],
            "is_accessory": rec["is_accessory"],
            "harga_idr": rec["harga_idr"],
            "cpu_vendor": rec["cpu_vendor"],
            "need_tags": [t["tag"] for t in rec["need_tags"] if not t.get("negated")],
            "record": rec,
            "text": chunk,
            "source": "Katalog_Komputer_RAG.pdf"
        }
        
        points.append({
            "id": idx,
            "vector": vector,
            "payload": payload
        })

    print(f"\n3. Menyimpan {len(points)} points terstruktur ke Qdrant...")
    resp = requests.put(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points?wait=true",
        json={"points": points}
    )
    resp.raise_for_status()
    print("   Data berhasil disimpan ke Qdrant!")

    # Buat indeks payload di Qdrant
    print("4. Mengonfigurasi indeks payload Qdrant untuk filter cepat:")
    indexes = [
        ("kategori", "keyword"),
        ("harga_idr", "integer"),
        ("is_accessory", "bool"),
        ("need_tags", "keyword"),
        ("cpu_vendor", "keyword")
    ]
    for field_name, field_schema in indexes:
        try:
            requests.put(
                f"{QDRANT_URL}/collections/{COLLECTION_NAME}/index?wait=true",
                json={"field_name": field_name, "field_schema": field_schema}
            )
            print(f"   - Index '{field_name}' ({field_schema}): OK")
        except Exception as e:
            print(f"   - Index '{field_name}': {e}")

    print("\n============================================================")
    print("INGESTION SELESAI DENGAN SUKSES!")
    print(f"Koleksi: '{COLLECTION_NAME}' di {QDRANT_URL}")
    print("============================================================")

if __name__ == "__main__":
    main()