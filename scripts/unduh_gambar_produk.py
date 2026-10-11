# -*- coding: utf-8 -*-
"""
scripts/unduh_gambar_produk.py
Mengunduh gambar produk dari image_url, memvalidasi (HTTP 200, Content-Type image/*, Pillow),
menyimpan ke data/images/<kode>.<ekstensi>, dan memperbarui kolom image_file di database SQLite.
"""
import io
import os
import sys
import sqlite3
import urllib.request
import urllib.error
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "catalog.db"
TEST_DB_PATH = ROOT / "data" / "test_catalog.db"
IMAGES_DIR = ROOT / "data" / "images"


def ensure_image_column(db_path: Path):
    if not db_path.exists():
        return
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    cols = [r[1] for r in c.execute("PRAGMA table_info(products)").fetchall()]
    if "image_file" not in cols:
        c.execute("ALTER TABLE products ADD COLUMN image_file TEXT")
        conn.commit()
    conn.close()


def download_and_validate_images(db_path: Path = DB_PATH) -> list[dict]:
    ensure_image_column(db_path)
    if TEST_DB_PATH.exists():
        ensure_image_column(TEST_DB_PATH)

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("SELECT kode, nama, image_url FROM products ORDER BY kode")
    products = c.fetchall()

    results = []

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for kode, nama, img_url in products:
        item = {
            "kode": kode,
            "nama": nama,
            "status": "GAGAL",
            "alasan": "",
            "file": None
        }

        url = (img_url or "").strip()
        if not url:
            item["alasan"] = "image_url kosong"
            results.append(item)
            continue

        if not url.startswith("http://") and not url.startswith("https://"):
            item["alasan"] = f"Skema URL tidak valid: {url}"
            results.append(item)
            continue

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as resp:
                status_code = resp.status if hasattr(resp, "status") else 200
                if status_code != 200:
                    item["alasan"] = f"HTTP {status_code}"
                    results.append(item)
                    continue

                content_type = resp.headers.get("Content-Type", "").lower()
                # Beberapa CDN mengembalikan octet-stream atau image/jpeg;charset=utf-8
                if not content_type.startswith("image/") and "image" not in content_type and "octet-stream" not in content_type:
                    item["alasan"] = f"Tipe konten bukan gambar ({content_type})"
                    results.append(item)
                    continue

                img_bytes = resp.read()

        except urllib.error.HTTPError as e:
            item["alasan"] = f"HTTP Error {e.code}"
            results.append(item)
            continue
        except urllib.error.URLError as e:
            item["alasan"] = f"Koneksi gagal ({e.reason})"
            results.append(item)
            continue
        except Exception as e:
            item["alasan"] = f"Gagal mengunduh: {e}"
            results.append(item)
            continue

        # Validasi dengan Pillow
        try:
            pil_img = Image.open(io.BytesIO(img_bytes))
            pil_img.verify()

            # Buka kembali untuk mengekstrak format
            pil_img = Image.open(io.BytesIO(img_bytes))
            fmt = (pil_img.format or "").lower()
            if fmt in ("jpeg", "jpg"):
                ext = "jpg"
            elif fmt == "png":
                ext = "png"
            elif fmt == "webp":
                ext = "webp"
            elif fmt == "gif":
                ext = "gif"
            else:
                ext = fmt or "png"

            target_filename = f"{kode}.{ext}"
            target_path = IMAGES_DIR / target_filename
            with open(target_path, "wb") as f_out:
                f_out.write(img_bytes)

            rel_file_path = f"data/images/{target_filename}"
            c.execute("UPDATE products SET image_file = ? WHERE kode = ?", (rel_file_path, kode))
            conn.commit()

            # Update juga test_catalog jika ada
            if TEST_DB_PATH.exists():
                tconn = sqlite3.connect(str(TEST_DB_PATH))
                tc = tconn.cursor()
                tc.execute("UPDATE products SET image_file = ? WHERE kode = ?", (rel_file_path, kode))
                tconn.commit()
                tconn.close()

            item["status"] = "BERHASIL"
            item["alasan"] = f"Tervalidasi Pillow ({fmt.upper()}, {pil_img.size[0]}x{pil_img.size[1]})"
            item["file"] = rel_file_path

        except Exception as e:
            item["alasan"] = f"Pillow gagal memvalidasi berkas: {e}"

        results.append(item)

    conn.close()
    return results


def main():
    print("=" * 70)
    print("MEMULAI PENGUNDUHAN DAN VALIDASI FOTO PRODUK REIN KOMPUTER")
    print("=" * 70)
    results = download_and_validate_images()

    berhasil = sum(1 for r in results if r["status"] == "BERHASIL")
    gagal = sum(1 for r in results if r["status"] == "GAGAL")

    print("\nLAPORAN HASIL PER PRODUK:")
    print(f"{'Kode':<8} | {'Status':<10} | {'File / Alasan'}")
    print("-" * 70)
    for r in results:
        desc = r["file"] if r["status"] == "BERHASIL" else r["alasan"]
        print(f"{r['kode']:<8} | {r['status']:<10} | {desc}")

    print("-" * 70)
    print(f"Total: {len(results)} produk | Berhasil: {berhasil} | Gagal: {gagal}")
    print("=" * 70)


if __name__ == "__main__":
    main()
