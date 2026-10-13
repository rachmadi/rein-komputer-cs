# -*- coding: utf-8 -*-
"""
scratch/unduh_desktop_laptop.py
Mengunduh dan menyimpan foto produk untuk 8 Desktop dan 14 Laptop (22 produk).
"""
import io
import os
import sqlite3
import urllib.request
from pathlib import Path
from PIL import Image

TARGETS = [
    # DESKTOP (8 Produk)
    {
        "kode": "KB-D06",
        "nama": "Lenovo ThinkCentre M70s Gen 3",
        "kategori": "desktop",
        "url": "https://p1-ofp.static.pub/medias/bWFzdGVyfHJvb3R8MTY3NDIyfGltYWdlL3BuZ3xoYWQvaGJjLzEzNzAzMTcwNDU3NjMwLnBuZ3xiMmU4NDkzNjg5NTdlMDVjYmJlMDFhOGZlNmY2YmUxMjg3MDIwYjllMWE5OTVhN2Y0MDAwZjNlODkyMDU0MjI1/lenovo-desktops-thinkcentre-m70s-gen-3-hero.png",
        "preferred_ext": "png"
    },
    {
        "kode": "KB-D07",
        "nama": "HP Pro Tower 280 G9 + Monitor 23.8 inch",
        "kategori": "desktop",
        "url": "https://hp.widen.net/content/itkfa16kou/png/itkfa16kou.png?w=800&h=600&dpi=72&color=ffffff00",
        "preferred_ext": "png"
    },
    {
        "kode": "KB-D08",
        "nama": "ASUS ROG Strix G10CE",
        "kategori": "desktop",
        "url": "https://dlcdnwebimgs.asus.com/gain/4AE1EB77-C820-444A-B0A5-49912F3C1412/w1000/h732",
        "preferred_ext": "png"
    },
    {
        "kode": "KB-D09",
        "nama": "MSI MAG Infinite S3",
        "kategori": "desktop",
        "url": "https://storage-asset.msi.com/global/picture/product/product_1709268962d13167eb01b5512bea0228baab607995.webp",
        "preferred_ext": "png"
    },
    {
        "kode": "KB-D12",
        "nama": "Intel NUC 11 Essential NUC11ATKC4",
        "kategori": "desktop",
        "url": "https://c1.neweggimages.com/productimage/nb640/56-102-370-01.png",
        "preferred_ext": "png"
    },
    {
        "kode": "KB-D13",
        "nama": "Acer Aspire TC-1760",
        "kategori": "desktop",
        "url": "https://images.tokopedia.net/img/cache/700/aphluv/1997/1/1/65aad65ae3a24c9190a31bcd89d64605~.image",
        "preferred_ext": "jpg"
    },
    {
        "kode": "KB-D14",
        "nama": "ASUS ROG Desktop G700 GM700TZ",
        "kategori": "desktop",
        "url": "https://id.store.asus.com/media/catalog/product/g/m/gm700__05_2_1_1.jpg",
        "preferred_ext": "jpg"
    },
    {
        "kode": "KB-D15",
        "nama": "Lenovo IdeaCentre Tower 14IRR9",
        "kategori": "desktop",
        "url": "https://psrefstuff.lenovo.com/syspool/Sys/PDF/IdeaCentre/IdeaCentre_Tower_14IRR9/IdeaCentre_Tower_14IRR9_OverViewPic.jpg",
        "preferred_ext": "jpg"
    },

    # LAPTOP (14 Produk)
    {
        "kode": "KB-L11",
        "nama": "Acer Aspire 3 A314-36P-C14Z",
        "kategori": "laptop",
        "url": "https://els.id/wp-content/uploads/2023/09/A314-36P-Silver-5.png",
        "preferred_ext": "png"
    },
    {
        "kode": "KB-L12",
        "nama": "Lenovo IdeaPad Slim 1 14AMN7",
        "kategori": "laptop",
        "url": "https://psrefstuff.lenovo.com/syspool//Sys/Image/IdeaPad/IdeaPad_1_14AMN7/Compressedimage/IdeaPad_1_14AMN7_CT3_02.png",
        "preferred_ext": "jpg"
    },
    {
        "kode": "KB-L13",
        "nama": "ASUS Vivobook Go 14 E1404FA",
        "kategori": "laptop",
        "url": "https://id.store.asus.com/media/catalog/product/v/i/vivobook_go_14_e1404f_e1404g_product_photo_1k_mixed_black_05_fingerprint_backlit_2.png",
        "preferred_ext": "png"
    },
    {
        "kode": "KB-L14",
        "nama": "HP 14s-dq3111TU",
        "kategori": "laptop",
        "url": "https://static.retailworldvn.com/Products/Images/12217/309097/laptop-hp-14s-dq3111tu-celeron-n4500-8gb-512gb-win11-7z952pa-silver-1.jpg",
        "preferred_ext": "png"
    },
    {
        "kode": "KB-L15",
        "nama": "Axioo MyBook Hype 5",
        "kategori": "laptop",
        "url": "https://els.id/wp-content/uploads/2024/12/Mybook-Hype-5.png",
        "preferred_ext": "png"
    },
    {
        "kode": "KB-L17",
        "nama": "ASUS Vivobook 14 A1404VAP",
        "kategori": "laptop",
        "url": "https://id.store.asus.com/media/catalog/product/v/i/vivobook_14_x1404vap_product_photo_1s_cool_silver_05_fingerprint_backlit_3.png",
        "preferred_ext": "png"
    },
    {
        "kode": "KB-L20",
        "nama": "HP Pavilion Aero 13 be0003AU",
        "kategori": "laptop",
        "url": "https://els.id/wp-content/uploads/2023/09/Aero-13-Silver.png",
        "preferred_ext": "png"
    },
    {
        "kode": "KB-L22",
        "nama": "ASUS Zenbook 14 OLED UX3402ZA",
        "kategori": "laptop",
        "url": "https://els.id/wp-content/uploads/2023/11/Asus-Zenbook-UX3402.jpg",
        "preferred_ext": "jpg"
    },
    {
        "kode": "KB-L23",
        "nama": "Lenovo LOQ 15IRX9 AAID",
        "kategori": "laptop",
        "url": "https://psrefstuff.lenovo.com/syspool/Sys/PDF/LOQ/LOQ_15IRX9/LOQ_15IRX9_OverViewPic.jpg",
        "preferred_ext": "jpg"
    },
    {
        "kode": "KB-L24",
        "nama": "Acer Nitro V 15 ANV15-51",
        "kategori": "laptop",
        "url": "https://els.id/wp-content/uploads/2023/10/Nitro-V-ANV15-51-2.png",
        "preferred_ext": "png"
    },
    {
        "kode": "KB-L25",
        "nama": "ASUS TUF Gaming A15 FA507NU",
        "kategori": "laptop",
        "url": "https://els.id/wp-content/uploads/2023/10/FA507.png",
        "preferred_ext": "png"
    },
    {
        "kode": "KB-L28",
        "nama": "ASUS ROG Strix G16 G614JI",
        "kategori": "laptop",
        "url": "https://id.store.asus.com/media/catalog/product/s/t/strix_g16_g614__03_gray_4zone_1.jpg",
        "preferred_ext": "jpg"
    },
    {
        "kode": "KB-L29",
        "nama": "Lenovo Legion Pro 5i 16IRX8",
        "kategori": "laptop",
        "url": "https://psrefstuff.lenovo.com/syspool/Sys/PDF/Legion/Legion_Pro_5_16IRX8/Legion_Pro_5_16IRX8_OverViewPic.jpg",
        "preferred_ext": "jpg"
    },
    {
        "kode": "KB-L30",
        "nama": "Apple MacBook Pro 14 M3 Pro",
        "kategori": "laptop",
        "url": "https://store.storeimages.cdn-apple.com/1/as-images.apple.com/is/refurb-mbp14-m3-max-pro-spaceblack-202402?wid=1144&hei=1144&fmt=jpeg&qlt=90",
        "preferred_ext": "jpg"
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
            print(f"  -> Sukses! {dim[0]}x{dim[1]}, {file_size:,} bytes")

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
