import sqlite3
import os
from pathlib import Path

def main():
    conn = sqlite3.connect("data/catalog.db")
    cur = conn.cursor()
    cur.execute("SELECT kode, nama, kategori, image_url, image_file FROM products ORDER BY kategori, kode")
    rows = cur.fetchall()

    ada_gambar = []
    tidak_ada_gambar = []

    for kode, nama, kategori, img_url, img_file in rows:
        file_exists = False
        if img_file:
            p = Path(img_file)
            file_exists = p.is_file()
        
        status = {
            "kode": kode,
            "nama": nama,
            "kategori": kategori,
            "image_url": img_url,
            "image_file": img_file,
            "file_exists": file_exists
        }
        if file_exists:
            ada_gambar.append(status)
        else:
            tidak_ada_gambar.append(status)

    print(f"Total produk: {len(rows)}")
    print(f"Ada gambar (berkas ada): {len(ada_gambar)}")
    print(f"Tidak ada gambar: {len(tidak_ada_gambar)}")
    print()
    print("=== RINCIAN PER KATEGORI ===")
    cats = sorted(list(set(r[2] for r in rows)))
    for c in cats:
        c_ada = [x for x in ada_gambar if x["kategori"] == c]
        c_tidak = [x for x in tidak_ada_gambar if x["kategori"] == c]
        print(f"[{c.upper()}] Total: {len(c_ada) + len(c_tidak)} | Ada gambar: {len(c_ada)} | Tanpa gambar: {len(c_tidak)}")

    print()
    print("=== DAFTAR PRODUK YANG TIDAK MEMILIKI GAMBAR ===")
    for item in tidak_ada_gambar:
        print(f"{item['kode']:<8} | {item['kategori']:<8} | {item['nama']:<35} | image_file: {item['image_file']} | file_exists: {item['file_exists']}")

    print()
    print("=== APAKAH ADA IMAGE_FILE YANG TERCATAT TAPI BERKASNYA TIDAK ADA? ===")
    hilang = [x for x in rows if x[4] and not Path(x[4]).is_file()]
    if hilang:
        for x in hilang:
            print(f"Hilang: {x[0]} - {x[4]}")
    else:
        print("Tidak ada berkas yang hilang (semua image_file yang tercatat benar-benar ada di disk).")

    print()
    print("=== PRODUK DENGAN GAMBAR ===")
    for item in ada_gambar:
        print(f"{item['kode']:<8} | {item['kategori']:<8} | {item['nama']:<35} | {item['image_file']}")

if __name__ == "__main__":
    main()
