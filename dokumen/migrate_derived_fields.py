"""
Menambah kolom turunan (numerik/terstruktur) ke tabel `products` dengan mem-parsing
kolom teks cpu, gpu, storage, display, dan raw_data. Aman dijalankan berulang kali.

Pakai:  python migrate_derived_fields.py data/catalog.db [--dry-run]

Kolom baru:
  cpu_tier        1-4 (lihat G01), NULL jika tidak dikenali / Apple M-series (varian beragam)
  storage_ssd_gb  total kapasitas SSD/NVMe dalam GB (1 TB = 1000 GB)
  has_hdd         1 jika ada HDD
  gpu_dedicated   1 = GPU dedicated, 0 = integrated
  gpu_class       none | igpu | entry | mid | high
  vram_gb         diambil dari teks gpu (mis. "RTX 4060 8GB"); NULL jika tidak tertulis
  screen_inch     ukuran layar
  refresh_hz      refresh rate
  panel           IPS | OLED | VA | TN
  srgb_pct        cakupan sRGB (%), jika tertulis
  tags            dari raw_data["tags"] jika ada (dipisah koma)

PENTING: vram_gb sengaja TIDAK ditebak dari nama GPU (VRAM laptop dan desktop berbeda).
Isi VRAM langsung di data produk, mis. "NVIDIA GeForce RTX 4060 8GB".
"""
import json
import re
import sqlite3
import sys

NEW_COLUMNS = {
    "cpu_tier": "INTEGER",
    "storage_ssd_gb": "INTEGER",
    "has_hdd": "INTEGER",
    "gpu_dedicated": "INTEGER",
    "gpu_class": "TEXT",
    "vram_gb": "INTEGER",
    "screen_inch": "REAL",
    "refresh_hz": "INTEGER",
    "panel": "TEXT",
    "srgb_pct": "INTEGER",
    "tags": "TEXT",
}


def cpu_tier(cpu: str):
    s = (cpu or "").lower()
    if not s:
        return None
    m = re.search(r"core\s+ultra\s+([579])", s)
    if m:
        return {"5": 2, "7": 3, "9": 4}[m.group(1)]
    m = re.search(r"core\s+i([3579])", s)
    if m:
        return {"3": 1, "5": 2, "7": 3, "9": 4}[m.group(1)]
    m = re.search(r"core\s+([579])\s+\d", s)  # penamaan baru: "Core 5 120U"
    if m:
        return {"5": 2, "7": 3, "9": 4}[m.group(1)]
    m = re.search(r"ryzen\s+(?:ai\s+)?([3579])", s)
    if m:
        return {"3": 1, "5": 2, "7": 3, "9": 4}[m.group(1)]
    if re.search(r"\bn\d{2,3}\b|celeron|pentium|athlon", s):
        return 1
    return None  # termasuk Apple M-series


def storage_info(storage: str):
    s = (storage or "")
    ssd_gb, has_hdd = 0, 0
    for part in re.split(r"\+|,|&|\bdan\b", s, flags=re.I):
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*(TB|GB)", part, flags=re.I)
        if not m:
            continue
        size = float(m.group(1).replace(",", "."))
        gb = size * 1000 if m.group(2).upper() == "TB" else size
        if re.search(r"ssd|nvme", part, flags=re.I):
            ssd_gb += gb
        elif re.search(r"hdd|harddisk|hard disk", part, flags=re.I):
            has_hdd = 1
    return (int(ssd_gb) if ssd_gb else None), has_hdd


def gpu_info(gpu: str):
    s = (gpu or "")
    low = s.lower()
    if not low:
        return None, None, None
    dedicated = bool(re.search(
        r"\brtx\b|\bgtx\b|geforce\s+mx|\bmx\s?\d{3}\b|radeon\s+rx|\brx\s?\d{4}|arc\s+a\d{3}|quadro", low))
    vram = None
    m = re.search(r"(\d{1,2})\s*gb", low)
    if dedicated and m:
        vram = int(m.group(1))
    if not dedicated:
        return 0, "igpu", None
    cls = "entry"
    m = re.search(r"rtx\s*(\d)0(\d)0", low)  # RTX 3050/4060/5070 ...
    if m:
        d = int(m.group(2))
        cls = "entry" if d <= 5 else "mid" if d == 6 else "high"
    else:
        m = re.search(r"rx\s*(\d)(\d)00", low)  # RX 6500M / 7600M ...
        if m:
            d = int(m.group(2))
            cls = "entry" if d <= 5 else "mid" if d == 6 else "high"
    return 1, cls, vram


def display_info(display: str):
    s = (display or "")
    inch = None
    m = re.search(r"(\d{2}(?:[.,]\d)?)\s*(?:inch|inci|in\b|\"|”|″)", s, flags=re.I)
    if m:
        inch = float(m.group(1).replace(",", "."))
    hz = None
    m = re.search(r"(\d{2,3})\s*hz", s, flags=re.I)
    if m:
        hz = int(m.group(1))
    panel = None
    for p in ("OLED", "IPS", "VA", "TN"):
        if re.search(rf"\b{p}\b", s, flags=re.I):
            panel = p
            break
    srgb = None
    m = re.search(r"(\d{2,3})\s*%\s*s?rgb", s, flags=re.I)
    if m:
        srgb = int(m.group(1))
    return inch, hz, panel, srgb


def tags_from_raw(raw: str):
    try:
        data = json.loads(raw) if raw else {}
    except (ValueError, TypeError):
        return None
    t = data.get("tags") if isinstance(data, dict) else None
    if isinstance(t, list):
        return ",".join(str(x).strip().lower() for x in t if str(x).strip()) or None
    if isinstance(t, str):
        return t.strip().lower() or None
    return None


def main(path: str, dry: bool):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    existing = {r["name"] for r in con.execute("PRAGMA table_info(products)")}
    for col, typ in NEW_COLUMNS.items():
        if col not in existing and not dry:
            con.execute(f"ALTER TABLE products ADD COLUMN {col} {typ}")
    rows = con.execute("SELECT * FROM products").fetchall()
    for r in rows:
        ssd, hdd = storage_info(r["storage"])
        ded, cls, vram = gpu_info(r["gpu"])
        inch, hz, panel, srgb = display_info(r["display"])
        vals = (cpu_tier(r["cpu"]), ssd, hdd, ded, cls, vram, inch, hz, panel, srgb,
                tags_from_raw(r["raw_data"]), r["kode"])
        print(r["kode"], vals[:-1])
        if not dry:
            con.execute(
                "UPDATE products SET cpu_tier=?, storage_ssd_gb=?, has_hdd=?, gpu_dedicated=?, "
                "gpu_class=?, vram_gb=?, screen_inch=?, refresh_hz=?, panel=?, srgb_pct=?, tags=? "
                "WHERE kode=?", vals)
    if not dry:
        con.commit()
    con.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], "--dry-run" in sys.argv)
