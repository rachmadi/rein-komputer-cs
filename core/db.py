import sqlite3
import json
import re
from typing import Any
from core.catalog import Catalog, infer_tags_from_specs, derive_tags, normalize

import os
DB_PATH = os.getenv("DB_PATH", "data/catalog.db")

def init_db(db_path: str = DB_PATH):
    import os
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS products (
        kode TEXT PRIMARY KEY,
        nama TEXT NOT NULL,
        kategori TEXT NOT NULL,
        harga_idr INTEGER NOT NULL,
        is_accessory INTEGER DEFAULT 0,
        cpu TEXT,
        cpu_vendor TEXT,
        cpu_tier INTEGER,
        ram TEXT,
        ram_gb INTEGER,
        ram_type TEXT,
        storage TEXT,
        storage_ssd_gb INTEGER,
        gpu TEXT,
        gpu_type TEXT,
        gpu_class INTEGER,
        gpu_dedicated INTEGER,
        vram_gb INTEGER,
        display TEXT,
        screen_inch REAL,
        refresh_hz INTEGER,
        panel TEXT,
        srgb_pct INTEGER,
        sistem_operasi TEXT,
        fungsi TEXT,
        teknologi TEXT,
        kecepatan TEXT,
        resolusi TEXT,
        konektivitas TEXT,
        usage_text TEXT,
        raw_data TEXT,
        tags TEXT
    )
    ''')
    conn.commit()
    conn.close()

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    if d.get("tags") is None:
        d["tags"] = []
    elif isinstance(d["tags"], str):
        try:
            d["tags"] = json.loads(d["tags"])
        except:
            d["tags"] = []

    d["is_accessory"] = bool(d.get("is_accessory", 0))
    if d.get("kategori") == "desktop":
        d["includes_monitor"] = False

    if not d.get("brand") or d.get("brand") == "other":
        nama_low = d.get("nama", "").lower()
        for b in ("acer", "asus", "lenovo", "hp", "canon", "epson", "brother", "dell", "apple"):
            if b in nama_low:
                d["brand"] = b
                break

    cpu = d.get("cpu", "")
    if not d.get("cpu_vendor") and cpu:
        low_cpu = cpu.lower()
        d["cpu_vendor"] = "intel" if ("intel" in low_cpu or "n100" in low_cpu) else "amd" if ("amd" in low_cpu or "ryzen" in low_cpu) else None

    ram = d.get("ram", "")
    if not ram and d.get("ram_gb"):
        ram = f"{d['ram_gb']} GB {d.get('ram_type', '')}".strip()
        d["ram"] = ram
    if ram:
        if not d.get("ram_gb"):
            rm = re.search(r"(\d+)\s*GB", ram, re.I)
            if rm:
                d["ram_gb"] = int(rm.group(1))
        if not d.get("ram_type"):
            rt = re.search(r"(DDR\d|LPDDR\d)", ram, re.I)
            if rt:
                d["ram_type"] = rt.group(1).upper()

    gpu = d.get("gpu")
    if gpu:
        if not d.get("gpu_vram"):
            vm = re.search(r"(\d+)\s*GB", gpu, re.I)
            if vm:
                d["gpu_vram"] = int(vm.group(1))
        if not d.get("gpu_type"):
            low_g = gpu.lower()
            if any(x in low_g for x in ("geforce", "rtx", "gtx", "radeon rx", "arc")):
                d["gpu_type"] = "discrete"
            elif any(x in low_g for x in ("intel uhd", "iris xe", "radeon graphics", "integrated", "intel graphics")):
                d["gpu_type"] = "integrated"
            else:
                d["gpu_type"] = "discrete" if "gb" in low_g else "integrated"

    usage = d.get("usage_text", "")
    tags = derive_tags(usage) if usage else []
    if not tags:
        tags = infer_tags_from_specs(d)
    d["need_tags"] = tags

    if d.get("raw_data"):
        try:
            extra = json.loads(d["raw_data"])
            for k, v in extra.items():
                if k not in d or d[k] is None:
                    d[k] = v
        except:
            pass

    return d

def get_all_products(category: str | None = None, db_path: str = DB_PATH) -> list[dict]:
    init_db(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    if category:
        cur.execute("SELECT * FROM products WHERE kategori = ? ORDER BY kode", (category,))
    else:
        cur.execute("SELECT * FROM products ORDER BY kode")
    rows = cur.fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]

def get_product(kode: str, db_path: str = DB_PATH) -> dict | None:
    init_db(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE kode = ?", (kode,))
    row = cur.fetchone()
    conn.close()
    return row_to_dict(row) if row else None

def seed_db_from_catalog(products: list[dict], db_path: str = DB_PATH):
    init_db(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    for p in products:
        d = p.copy()
        if "need_tags" in d:
            del d["need_tags"]
        for k in list(d.keys()):
            if k not in ["kode", "nama", "kategori", "harga_idr", "is_accessory",
                         "cpu", "cpu_vendor", "cpu_tier", "ram", "ram_gb", "ram_type",
                         "storage", "storage_ssd_gb", "gpu", "gpu_type", "gpu_class",
                         "gpu_dedicated", "vram_gb", "display", "screen_inch", "refresh_hz",
                         "panel", "srgb_pct", "sistem_operasi", "fungsi", "teknologi",
                         "kecepatan", "resolusi", "konektivitas", "usage_text", "raw_data", "tags"]:
                del d[k]
        cols = ", ".join(d.keys())
        qms = ", ".join("?" for _ in d)
        vals = tuple(d.values())
        cur.execute(f"INSERT OR REPLACE INTO products ({cols}) VALUES ({qms})", vals)
    conn.commit()
    conn.close()

def save_product(kode: str, data: dict, db_path: str = DB_PATH):
    init_db(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cols = ', '.join(data.keys())
    qms = ', '.join('?' for _ in data)
    vals = tuple(data.values())
    cur.execute(f'INSERT OR REPLACE INTO products ({cols}) VALUES ({qms})', vals)
    conn.commit()
    conn.close()

def delete_product(kode: str, db_path: str = DB_PATH):
    init_db(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute('DELETE FROM products WHERE kode = ?', (kode,))
    conn.commit()
    conn.close()

