# -*- coding: utf-8 -*-
"""
Catalog Management Service
Menangani CRUD produk, caching memory Catalog untuk engine CS, dan sinkronisasi vektor ke Qdrant.
"""
from __future__ import annotations

import re
import requests
from typing import Any
from core.catalog import Catalog, derive_tags
from scripts.migrate_derived_fields import cpu_tier, storage_info, gpu_info, display_info, tags_from_raw
from core.db import get_all_products, get_product, save_product, delete_product as db_delete_product
from core.normalizer import normalize

QDRANT_URL = "http://localhost:6333"
OLLAMA_URL = "http://localhost:11434"
import os
COLLECTION_NAME = os.getenv("QDRANT_PRODUCTS_COLLECTION", "computer_products")
EMBED_MODEL = "bge-m3"

_cached_catalog: Catalog | None = None

def get_active_catalog() -> Catalog:
    global _cached_catalog
    if _cached_catalog is None:
        _cached_catalog = reload_catalog()
    return _cached_catalog

def reload_catalog() -> Catalog:
    global _cached_catalog
    _cached_catalog = Catalog.from_db()
    return _cached_catalog

def format_product_text(p: dict) -> str:
    """Membuat representasi teks chunk produk standar untuk embedding vektor."""
    lines = [
        f"{p['kode']} - {p['nama']}",
        f"Jenis: {p['kategori'].title()}",
        f"Harga: Rp{p['harga_idr']:,}".replace(",", ".")
    ]
    if p.get("cpu"):
        lines.append(f"Prosesor: {p['cpu']}")
    if p.get("ram"):
        lines.append(f"RAM: {p['ram']}")
    if p.get("storage"):
        lines.append(f"Storage: {p['storage']}")
    if p.get("gpu"):
        lines.append(f"GPU: {p['gpu']}")
    if p.get("display"):
        lines.append(f"Display: {p['display']}")
    if p.get("os"):
        lines.append(f"Sistem operasi: {p['os']}")
    if p.get("usage_text"):
        lines.append(f"Penggunaan yang disarankan: {p['usage_text']}")
    return "\n".join(lines)

def build_aliases(record: dict) -> list[str]:
    aliases = [record["nama"].lower(), record["kode"].lower()]
    norm_name = normalize(record["nama"])
    aliases.append(norm_name)
    aliases.append(normalize(record["kode"]))
    aliases.append(record["kode"].lower().replace("-", " "))
    aliases.append(record["kode"].lower().replace("-", ""))
    return list(dict.fromkeys(aliases))

def get_embedding(text: str, ollama_url: str = OLLAMA_URL, model: str = EMBED_MODEL) -> list[float] | None:
    try:
        response = requests.post(
            f"{ollama_url}/api/embed",
            json={
                "model": model,
                "input": text,
                "options": {"num_gpu": 0},
                "keep_alive": "30m"
            },
            timeout=120
        )
        response.raise_for_status()
        return response.json()["embeddings"][0]
    except Exception as e:
        print(f"[Warning] Gagal membuat embedding via Ollama ({model}): {e}")
        return None

def code_to_point_id(kode: str) -> int:
    """Menghasilkan point ID numerik deterministik dari kode produk (misal: KB-L01 -> 101)."""
    m = re.search(r"KB-([A-Z])(\d+)", kode)
    if m:
        cat_char, num_str = m.groups()
        char_val = ord(cat_char)
        return int(f"{char_val}{int(num_str):03d}")
    return abs(hash(kode)) % (10**9)

def sync_product_to_qdrant(record: dict, qdrant_url: str = QDRANT_URL, ollama_url: str = OLLAMA_URL) -> bool:
    chunk_text = format_product_text(record)
    vector = get_embedding(chunk_text, ollama_url=ollama_url)
    if not vector:
        return False
        
    point_id = code_to_point_id(record["kode"])
    record_with_aliases = dict(record)
    record_with_aliases["alias"] = build_aliases(record)
    need_tags = [t["tag"] for t in record.get("need_tags", []) if not t.get("negated")]
    
    payload = {
        "code": record["kode"],
        "kode": record["kode"],
        "product": record["nama"],
        "nama": record["nama"],
        "kategori": record["kategori"],
        "is_accessory": record.get("is_accessory", False),
        "harga_idr": record["harga_idr"],
        "cpu_vendor": record.get("cpu_vendor"),
        "need_tags": need_tags,
        "record": record_with_aliases,
        "text": chunk_text,
        "source": "web_admin"
    }
    
    try:
        body = {
            "points": [
                {
                    "id": point_id,
                    "vector": vector,
                    "payload": payload
                }
            ]
        }
        res = requests.put(
            f"{qdrant_url}/collections/{COLLECTION_NAME}/points?wait=true",
            json=body,
            timeout=15
        )
        res.raise_for_status()
        return True
    except Exception as e:
        print(f"[Warning] Gagal upsert ke Qdrant: {e}")
        return False

def delete_product_from_qdrant(kode: str, qdrant_url: str = QDRANT_URL) -> bool:
    point_id = code_to_point_id(kode)
    try:
        body = {"points": [point_id]}
        res = requests.post(
            f"{qdrant_url}/collections/{COLLECTION_NAME}/points/delete?wait=true",
            json=body,
            timeout=15
        )
        res.raise_for_status()
        return True
    except Exception as e:
        print(f"[Warning] Gagal delete dari Qdrant: {e}")
        return False

def list_products(category: str | None = None) -> list[dict]:
    return get_all_products(category=category)

def get_product_by_code(kode: str) -> dict | None:
    return get_product(kode)

def upsert_product(data: dict, sync_qdrant: bool = True) -> tuple[dict, bool]:
    # Normalisasi fields
    if "harga_idr" in data:
        data["harga_idr"] = int(data["harga_idr"])
    if data.get("ram_gb"):
        data["ram_gb"] = int(data["ram_gb"])
    if data.get("usage_text"):
        data["need_tags"] = derive_tags(data["usage_text"])
        
    # Derived fields
    ssd, hdd = storage_info(data.get("storage", ""))
    ded, cls, vram = gpu_info(data.get("gpu", ""))
    inch, hz, panel, srgb = display_info(data.get("display", ""))
    
    data["cpu_tier"] = cpu_tier(data.get("cpu", ""))
    data["storage_ssd_gb"] = ssd
    data["has_hdd"] = hdd
    data["gpu_dedicated"] = ded
    data["gpu_class"] = cls
    data['vram_gb'] = vram

    if ded == 1 and vram is None:
        raise ValueError('Produk dengan GPU Dedicated wajib mencantumkan kapasitas VRAM')
    data["screen_inch"] = inch
    data["refresh_hz"] = hz
    data["panel"] = panel
    data["srgb_pct"] = srgb
    data["tags"] = tags_from_raw(data.get("raw_data", ""), data.get("usage_text", ""))
    
    save_product(data['kode'], data)
    saved = data
    reload_catalog()
    
    qdrant_synced = False
    if sync_qdrant:
        qdrant_synced = sync_product_to_qdrant(saved)
        
    return saved, qdrant_synced

def delete_product_record(kode: str, sync_qdrant: bool = True) -> bool:
    success = db_delete_product(kode)
    if success:
        reload_catalog()
        if sync_qdrant:
            delete_product_from_qdrant(kode)
    return success

def sync_all_products_to_qdrant() -> dict[str, Any]:
    prods = get_all_products()
    success_count = 0
    failed = []
    for p in prods:
        ok = sync_product_to_qdrant(p)
        if ok:
            success_count += 1
        else:
            failed.append(p["kode"])
    return {
        "total": len(prods),
        "synced": success_count,
        "failed": failed
    }
