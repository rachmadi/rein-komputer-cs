import sqlite3, json

conn = sqlite3.connect('data/catalog.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

def format_rupiah(val):
    return f"Rp{val:,.0f}".replace(",", ".")

def build_lembar(p):
    specs = {}
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
        raw_dict = raw if isinstance(raw, dict) else json.loads(raw)
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

for row in cur.execute('SELECT * FROM products LIMIT 3').fetchall():
    p = dict(row)
    lembar = build_lembar(p)
    print(p["kode"], p["nama"])
    print("Lembar keys:", list(lembar.keys()))
    print("---")
