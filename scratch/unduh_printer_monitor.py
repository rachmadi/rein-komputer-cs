# -*- coding: utf-8 -*-
"""
scratch/unduh_printer_monitor.py
Mengunduh dan menyimpan foto produk untuk kategori Printer (5 produk) dan Monitor (4 produk).
"""
import io
import os
import sqlite3
import urllib.request
from pathlib import Path
from PIL import Image

TARGETS = [
    # PRINTER (5 Produk)
    {
        "kode": "KB-P06",
        "nama": "Epson EcoTank L3210",
        "kategori": "printer",
        "url": "https://mediaserver.goepson.com/adaptivemedia/rendition?id=d60560b00fe766443f873ee2fdc6da1b9be04f59&vid=d60560b00fe766443f873ee2fdc6da1b9be04f59&prid=1200Wx1200H&clid=SAPDAM&prclid=banner&assetDescr=L3210-%281%29",
        "preferred_ext": "jpg"
    },
    {
        "kode": "KB-P07",
        "nama": "HP DeskJet Ink Advantage 2336",
        "kategori": "printer",
        "url": "https://hp.widen.net/content/cklpdca3hv/png/cklpdca3hv.png?w=400&h=400&dpi=72&color=ffffff00",
        "preferred_ext": "png"
    },
    {
        "kode": "KB-P08",
        "nama": "Brother HL-L2365DW",
        "kategori": "printer",
        "url": "https://www.brother.co.id/-/media/ap2/indonesia/products/hl-l2365dw/20240605103922_hl_l2365dw.png?rev=00c324c3d2594656a5c5f3ada791e536&hash=3E6BFA8C8C19CA42E65883E761D440AB",
        "preferred_ext": "png"
    },
    {
        "kode": "KB-P09",
        "nama": "Epson TM-T82X",
        "kategori": "printer",
        "url": "https://mediaserver.goepson.com/adaptivemedia/rendition?id=08fdcae58ca810dce94b4f968084c4bba2f404cd&vid=08fdcae58ca810dce94b4f968084c4bba2f404cd&prid=1200Wx1200H&clid=SAPDAM&prclid=banner&assetDescr=FY18_SIL_Left_EBCK",
        "preferred_ext": "jpg"
    },
    {
        "kode": "KB-P10",
        "nama": "Canon PIXMA G3020",
        "kategori": "printer",
        "url": "https://d2po8s8685fal.cloudfront.net/ecommerce/storage/27164/conversions/slide1_5-converted.webp",
        "preferred_ext": "png"
    },

    # MONITOR (4 Produk)
    {
        "kode": "KB-M01",
        "nama": "LG 24MP400-B",
        "kategori": "monitor",
        "url": "https://media.us.lg.com/transform/ecomm-PDPGallery-1100x730/49b51724-8dd2-4c56-87b5-95dd810d907d/md08000731-Z1-jpg",
        "preferred_ext": "jpg"
    },
    {
        "kode": "KB-M02",
        "nama": "MSI G274F",
        "kategori": "monitor",
        "url": "https://storage-asset.msi.com/global/picture/product/product_16914612277028ab9822d510d295e742ec2d26f46b.webp",
        "preferred_ext": "png"
    },
    {
        "kode": "KB-M03",
        "nama": "LG 34WP500-B",
        "kategori": "monitor",
        "url": "https://media.us.lg.com/transform/ecomm-PDPGallery-1100x730/35d63e53-b562-4434-82a9-295884de147e/md07523757-zoom-01-jpg?io=transform:fill,width:1536",
        "preferred_ext": "jpg"
    },
    {
        "kode": "KB-M05",
        "nama": "ASUS TUF Gaming VG27AQ",
        "kategori": "monitor",
        "url": "https://www.asus.com/media/global/gallery/ddcqh7fg9nnzj1y1_setting_xxx_0_90_end_2000.png",
        "preferred_ext": "png"
    }
]

def main():
    images_dir = Path("data/images")
    images_dir.mkdir(parents=True, exist_ok=True)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    results = []
    for item in TARGETS:
        kode = item["kode"]
        nama = item["nama"]
        url = item["url"]
        pref_ext = item["preferred_ext"]
        out_filename = f"{kode}.{pref_ext}"
        out_path = images_dir / out_filename
        rel_path = f"data/images/{out_filename}"

        print(f"\n[UNDUH] {kode} - {nama}...")
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()

            img = Image.open(io.BytesIO(data))
            img.verify()
            img = Image.open(io.BytesIO(data))

            # Konversi format jika perlu
            if pref_ext == "png":
                if img.mode not in ("RGBA", "RGB"):
                    img = img.convert("RGBA")
                img.save(out_path, format="PNG", optimize=True)
            elif pref_ext in ("jpg", "jpeg"):
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(out_path, format="JPEG", quality=90, optimize=True)

            file_size = out_path.stat().st_size
            dim = img.size
            print(f"  -> Sukses! Tersimpan di {out_path} ({dim[0]}x{dim[1]}, {file_size:,} bytes)")

            results.append({
                "kode": kode,
                "nama": nama,
                "kategori": item["kategori"],
                "file": rel_path,
                "dimensi": f"{dim[0]}x{dim[1]}",
                "ukuran_bytes": file_size,
                "status": "berhasil"
            })

        except Exception as e:
            print(f"  -> GAGAL {kode}: {e}")
            results.append({
                "kode": kode,
                "nama": nama,
                "kategori": item["kategori"],
                "file": None,
                "dimensi": "-",
                "ukuran_bytes": 0,
                "status": f"gagal ({e})"
            })

    # Update database
    success_count = sum(1 for r in results if r["status"] == "berhasil")
    print(f"\n=== MENGUPDATE DATABASE ({success_count}/{len(results)} BERHASIL) ===")
    
    for db_file in ["data/catalog.db", "data/test_catalog.db"]:
        if not os.path.exists(db_file):
            continue
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        for r in results:
            if r["status"] == "berhasil":
                c.execute("UPDATE products SET image_file = ? WHERE kode = ?", (r["file"], r["kode"]))
        conn.commit()
        conn.close()
        print(f"  -> Updated {db_file}")

    print("\n=== RINGKASAN HASIL ===")
    print(f"{'Kode':<8} | {'Kategori':<8} | {'Dimensi':<10} | {'Ukuran':<12} | {'Nama'}")
    print("-" * 65)
    for r in results:
        uk_str = f"{r['ukuran_bytes']:,} B" if r["ukuran_bytes"] else "-"
        print(f"{r['kode']:<8} | {r['kategori']:<8} | {r['dimensi']:<10} | {uk_str:<12} | {r['nama']}")

if __name__ == "__main__":
    main()
