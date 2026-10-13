import sqlite3
import json
import re
from typing import Any, Tuple

conn = sqlite3.connect('data/test_catalog.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

def format_rupiah(val: int | float) -> str:
    return f"Rp{int(val):,}".replace(",", ".")

def clean_specs(p: dict) -> str:
    parts = []
    if p.get("cpu"): parts.append(str(p["cpu"]))
    if p.get("ram"): parts.append(str(p["ram"]))
    if p.get("storage"): parts.append(str(p["storage"]))
    if p.get("display"): parts.append(str(p["display"]))
    return " | ".join(parts)

def build_lembar_spesifikasi(p: dict) -> dict[str, Any]:
    if not isinstance(p, dict):
        return {}
    specs: dict[str, Any] = {}

    field_labels = {
        "nama": "nama",
        "kategori": "kategori",
        "brand": "merek",
        "cpu": "prosesor",
        "ram": "ram",
        "storage": "penyimpanan",
        "gpu": "grafis",
        "display": "layar",
        "panel": "panel",
        "refresh_hz": "refresh_rate",
        "srgb_pct": "akurasi_warna_srgb",
        "screen_inch": "ukuran_layar",
        "os": "sistem_operasi",
        "ram_gb": "ram_gb",
        "storage_ssd_gb": "storage_ssd_gb",
        "vram_gb": "vram_gb",
        "cpu_tier": "cpu_tier",
        "gpu_class": "gpu_class",
        "gpu_dedicated": "gpu_dedicated",
    }
    for k, label in field_labels.items():
        v = p.get(k)
        if v not in (None, "", [], {}):
            if label == "refresh_rate" and isinstance(v, (int, float)):
                specs[label] = f"{int(v)} Hz"
            elif label == "akurasi_warna_srgb" and isinstance(v, (int, float)):
                specs[label] = f"{int(v)}% sRGB"
            elif label == "ukuran_layar" and isinstance(v, (int, float)):
                specs[label] = f"{v} inci"
            elif label == "gpu_dedicated" and isinstance(v, (int, bool)):
                specs[label] = "Ya" if v else "Tidak"
            else:
                specs[label] = v

    p_price = p.get("harga") or p.get("harga_idr")
    if p_price not in (None, "", 0):
        specs["harga"] = format_rupiah(int(p_price))

    raw = p.get("raw_data")
    if raw:
        raw_dict = raw if isinstance(raw, dict) else {}
        if isinstance(raw, str):
            try:
                raw_dict = json.loads(raw)
            except Exception:
                pass
        for rk, rv in raw_dict.items():
            if rv not in (None, "", [], {}):
                lbl = "kecepatan_cetak" if rk == "kecepatan" else rk
                if isinstance(rv, list):
                    specs[lbl] = ", ".join(str(x) for x in rv)
                elif isinstance(rv, bool):
                    specs[lbl] = "Ya" if rv else "Tidak"
                else:
                    specs[lbl] = rv

    skip_cols = {"raw_data", "image_url", "sumber_url", "image_file", "tanggal_harga", "is_accessory"}
    for col, val in p.items():
        if col not in skip_cols and col not in field_labels and col not in specs:
            if val not in (None, "", [], {}):
                if isinstance(val, list):
                    specs[col] = ", ".join(str(x) for x in val)
                elif isinstance(val, bool):
                    specs[col] = "Ya" if val else "Tidak"
                else:
                    specs[col] = val
    return specs

SYNONYMS = {
    "harga": ["harga", "harga_idr", "price", "banderol", "biaya"],
    "ram": ["ram", "ram_gb", "ram_type", "memori", "memory"],
    "storage": ["storage", "storage_ssd_gb", "penyimpanan", "ssd", "hdd", "rom", "kapasitas"],
    "cpu": ["cpu", "prosesor", "processor", "cpu_vendor", "cpu_tier"],
    "gpu": ["gpu", "grafis", "vga", "gpu_class", "gpu_dedicated", "vram_gb", "kartu_grafis"],
    "layar": ["display", "layar", "screen", "monitor", "screen_inch", "panel", "refresh_hz", "srgb_pct"],
    "baterai": ["baterai", "battery", "daya"],
    "port": ["port", "ports", "colokan", "konektivitas", "koneksi", "io"],
    "bobot": ["bobot", "berat", "weight"],
    "keyboard": ["keyboard", "papan_ketik"],
    "kamera": ["webcam", "kamera", "camera"],
    "os": ["os", "sistem_operasi", "operating_system"],
    "cetak_foto": ["cetak_foto", "cetak foto", "foto", "borderless", "cetak tanpa tepi"],
    "tipe_printer": ["tipe_printer", "tipe printer", "tangki tinta", "tabung tinta", "ink tank", "tinta"],
    "kecepatan_cetak": ["kecepatan_cetak", "kecepatan cetak", "kecepatan", "ipm", "ppm"],
    "hasil_cetak_tinta": ["hasil_cetak_tinta", "hasil cetak tinta", "kapasitas cetak", "kapasitas tinta"],
    "fungsi": ["fungsi", "scan", "copy", "fitur"],
    "wifi": ["wifi", "nirkabel", "wireless"],
    "duplex": ["duplex", "bolak balik", "cetak bolak-balik"],
}

def lookup_attribute_in_product(p: dict, attr_query: str, lembar: dict[str, Any]) -> Tuple[bool, Any, str]:
    if not attr_query:
        return False, None, ""
    q = str(attr_query).lower().strip()
    q_clean = re.sub(r"[^a-z0-9]", "", q)

    raw = p.get("raw_data")
    raw_dict = {}
    if isinstance(raw, dict): raw_dict = raw
    elif isinstance(raw, str):
        try: raw_dict = json.loads(raw)
        except Exception: pass

    # 1. Exact match di lembar
    if q in lembar and lembar[q] not in (None, "", [], {}):
        return True, lembar[q], q
    for k, v in lembar.items():
        if q_clean == re.sub(r"[^a-z0-9]", "", k.lower()) and v not in (None, "", [], {}):
            return True, v, k

    # 2. Match di p langsung
    if q in p:
        val = p[q]
        if val not in (None, "", [], {}):
            return True, str(val), q
        else:
            return False, None, q

    # 3. Match di raw_dict langsung
    if q in raw_dict:
        val = raw_dict[q]
        if val not in (None, "", [], {}):
            return True, str(val), q
        else:
            return False, None, q

    # 4. Synonym match
    matched_target = None
    for syn_key, syn_list in SYNONYMS.items():
        if q == syn_key or q_clean == re.sub(r"[^a-z0-9]", "", syn_key) or any(q == s or q_clean == re.sub(r"[^a-z0-9]", "", s) for s in syn_list):
            matched_target = syn_list
            break
    if matched_target:
        for cand in matched_target:
            if cand in lembar and lembar[cand] not in (None, "", [], {}):
                return True, lembar[cand], cand
            if cand in raw_dict and raw_dict[cand] not in (None, "", [], {}):
                return True, raw_dict[cand], cand
            if cand in p and p[cand] not in (None, "", [], {}):
                return True, p[cand], cand

    # 5. Substring / fuzzy match di lembar dan raw_dict
    if len(q_clean) >= 3:
        for k, v in lembar.items():
            k_clean = re.sub(r"[^a-z0-9]", "", k.lower())
            if (q_clean in k_clean or k_clean in q_clean) and v not in (None, "", [], {}):
                return True, v, k

    # 6. Kata kunci khusus domain
    if "tinta" in q or "tabung" in q:
        for k in ("tipe_printer", "hasil_cetak_tinta"):
            if k in raw_dict and raw_dict[k]:
                return True, raw_dict[k], k
            if k in lembar and lembar[k]:
                return True, lembar[k], k
    if "foto" in q:
        if "cetak_foto" in raw_dict and raw_dict["cetak_foto"]:
            return True, raw_dict["cetak_foto"], "cetak_foto"

    return False, None, q

# Tes Canon G3020
row = cur.execute('SELECT * FROM products WHERE kode = "KB-P10"').fetchone()
p = dict(row)
lembar = build_lembar_spesifikasi(p)
print("Produk:", p["nama"])
print("\n=== Test Laptop KB-L11 ===")
p_lap = dict(cur.execute('SELECT * FROM products WHERE kode = "KB-L11"').fetchone())
l_lap = build_lembar_spesifikasi(p_lap)
print("RAM:", lookup_attribute_in_product(p_lap, "ram", l_lap))
print("Layar:", lookup_attribute_in_product(p_lap, "layar", l_lap))
print("Baterai:", lookup_attribute_in_product(p_lap, "baterai", l_lap))
print("Cetak foto:", lookup_attribute_in_product(p_lap, "cetak foto", l_lap))

print("\n=== Property-based test check across fixture products ===")
cols_to_test = ["ram", "storage", "cpu", "gpu", "display", "baterai", "port", "refresh_hz", "screen_inch", "panel", "vram_gb", "gpu_dedicated"]
skip_meta = {"raw_data", "image_url", "sumber_url", "image_file", "tanggal_harga", "is_accessory", "tags", "usage_text"}

all_prods = [dict(r) for r in cur.execute('SELECT * FROM products').fetchall()]
passed_filled = 0
passed_empty = 0
failed = 0

for p in all_prods:
    lembar = build_lembar_spesifikasi(p)
    # 1. Test standard columns
    for col in cols_to_test:
        val = p.get(col)
        found, res_val, k = lookup_attribute_in_product(p, col, lembar)
        if val not in (None, "", [], {}):
            if found:
                passed_filled += 1
            else:
                # If column has value but not found
                print(f"FAILED filled: {p['kode']} {col} = {val}")
                failed += 1
        else:
            # Column is empty in p
            # Check if raw_data or lembar has it under another name or value
            if not found:
                passed_empty += 1
            else:
                # Found something even though p[col] was None - check if raw_dict has it
                pass

    # 2. Test raw_data keys
    raw = p.get("raw_data")
    if raw:
        rdict = raw if isinstance(raw, dict) else json.loads(raw)
        for rk, rv in rdict.items():
            if rk in ("sumber_spek", "catatan_sumber"): continue
            found, res_val, k = lookup_attribute_in_product(p, rk, lembar)
            if rv not in (None, "", [], {}):
                if found:
                    passed_filled += 1
                else:
                    print(f"FAILED raw filled: {p['kode']} {rk} = {rv}")
                    failed += 1

print(f"Passed filled: {passed_filled}, Passed empty: {passed_empty}, Failed: {failed}")
