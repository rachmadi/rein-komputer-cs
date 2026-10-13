# -*- coding: utf-8 -*-
"""
scripts/unduh_gambar_produk.py
Mengunduh gambar produk dari image_url, memvalidasi (HTTP 200, Content-Type image/*, Pillow),
mendeteksi dan menolak gambar duplikat/generik via perceptual hash (dHash) dan MD5,
menyimpan ke data/images/<kode>.<ekstensi>, dan memperbarui kolom image_file di SQLite.
"""
import argparse
import hashlib
import io
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "catalog.db"
TEST_DB_PATH = ROOT / "data" / "test_catalog.db"
IMAGES_DIR = ROOT / "data" / "images"

# Hash berkas placeholder / logo generik yang diketahui bukan foto produk asli
KNOWN_GENERIC_HASHES = {
    "b40b0e9f492cd26f41701c923b11ca98",  # Logo naga MSI generik 13.854 bytes
}

# Fallback kandidat per kode produk jika primary image_url gagal / duplikat
FALLBACK_CANDIDATES = {
    # Dapat diisi URL alternatif per kode produk
}


def compute_dhash(image: Image.Image, hash_size: int = 8) -> str:
    """Menghitung perceptual difference hash (dHash) 64-bit menggunakan Pillow."""
    try:
        resized = image.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
        if hasattr(resized, "get_flattened_data"):
            pixels = list(resized.get_flattened_data())
        else:
            pixels = list(resized.getdata())
        diff = []
        for row in range(hash_size):
            for col in range(hash_size):
                pixel_left = pixels[row * (hash_size + 1) + col]
                pixel_right = pixels[row * (hash_size + 1) + col + 1]
                diff.append(pixel_left > pixel_right)
        decimal_val = 0
        hex_str = []
        for index, value in enumerate(diff):
            if value:
                decimal_val += 2 ** (index % 4)
            if (index % 4) == 3:
                hex_str.append(hex(decimal_val)[2:])
                decimal_val = 0
        return "".join(hex_str)
    except Exception:
        return ""


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


def download_and_validate_images(
    db_path: Path = DB_PATH,
    candidates_file: str | None = None
) -> list[dict]:
    ensure_image_column(db_path)
    if TEST_DB_PATH.exists():
        ensure_image_column(TEST_DB_PATH)

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    extra_candidates = dict(FALLBACK_CANDIDATES)
    if candidates_file and os.path.exists(candidates_file):
        try:
            with open(candidates_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    extra_candidates.update(loaded)
        except Exception as e:
            print(f"[WARN] Gagal membaca kandidat dari {candidates_file}: {e}")

    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("SELECT kode, nama, image_url FROM products ORDER BY kode")
    products = c.fetchall()

    results = []
    seen_md5: dict[str, str] = {}  # md5 -> kode
    seen_dhash: dict[str, str] = {}  # dhash -> kode

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for kode, nama, primary_url in products:
        item = {
            "kode": kode,
            "nama": nama,
            "status": "gagal",
            "ukuran": 0,
            "hash": "-",
            "dhash": "-",
            "alasan": "",
            "file": None
        }

        # Kumpulkan kandidat URL untuk produk ini
        candidate_urls = []
        if primary_url and primary_url.strip():
            candidate_urls.append(primary_url.strip())
        if kode in extra_candidates:
            for u in extra_candidates[kode]:
                if u and u.strip() not in candidate_urls:
                    candidate_urls.append(u.strip())

        if not candidate_urls:
            item["alasan"] = "image_url kosong"
            results.append(item)
            # Pastikan di database tidak ada file stale
            c.execute("UPDATE products SET image_file = NULL WHERE kode = ?", (kode,))
            conn.commit()
            continue

        item_saved = False
        duplicate_detected = False

        for url in candidate_urls:
            if not url.startswith("http://") and not url.startswith("https://"):
                item["alasan"] = f"Skema URL tidak valid: {url}"
                continue

            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=20) as resp:
                    status_code = resp.status if hasattr(resp, "status") else 200
                    if status_code != 200:
                        item["alasan"] = f"HTTP {status_code}"
                        continue

                    content_type = resp.headers.get("Content-Type", "").lower()
                    if not content_type.startswith("image/") and "image" not in content_type and "octet-stream" not in content_type:
                        item["alasan"] = f"Tipe konten bukan gambar ({content_type})"
                        continue

                    img_bytes = resp.read()

            except urllib.error.HTTPError as e:
                item["alasan"] = f"HTTP Error {e.code}"
                continue
            except urllib.error.URLError as e:
                item["alasan"] = f"Koneksi gagal ({e.reason})"
                continue
            except Exception as e:
                item["alasan"] = f"Gagal mengunduh: {e}"
                continue

            # Validasi format dengan Pillow
            try:
                pil_img = Image.open(io.BytesIO(img_bytes))
                pil_img.verify()
                pil_img = Image.open(io.BytesIO(img_bytes))
                fmt = (pil_img.format or "").lower()
            except Exception as e:
                item["alasan"] = f"Pillow gagal memvalidasi berkas: {e}"
                continue

            # Pengecekan Hash (MD5 dan perceptual dHash)
            md5_str = hashlib.md5(img_bytes).hexdigest()
            dhash_str = compute_dhash(pil_img)
            item["ukuran"] = len(img_bytes)
            item["hash"] = md5_str
            item["dhash"] = dhash_str

            # Deteksi duplikat terhadap logo generik yang diketahui atau produk lain
            is_generic = md5_str in KNOWN_GENERIC_HASHES
            is_seen_md5 = md5_str in seen_md5
            is_seen_dhash = bool(dhash_str and dhash_str in seen_dhash)

            if is_generic or is_seen_md5 or is_seen_dhash:
                prev_kode = seen_md5.get(md5_str) or seen_dhash.get(dhash_str) or "logo_generik"
                item["status"] = "duplikat_dicurigai"
                item["alasan"] = f"Hash terdeteksi duplikat dengan {prev_kode} (MD5: {md5_str[:8]}...)"
                duplicate_detected = True
                continue  # Coba kandidat berikutnya jika ada

            # Gambar valid dan unik! Simpan berkas
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

            if TEST_DB_PATH.exists():
                tconn = sqlite3.connect(str(TEST_DB_PATH))
                tc = tconn.cursor()
                tc.execute("UPDATE products SET image_file = ? WHERE kode = ?", (rel_file_path, kode))
                tconn.commit()
                tconn.close()

            seen_md5[md5_str] = kode
            if dhash_str:
                seen_dhash[dhash_str] = kode

            item["status"] = "berhasil"
            item["alasan"] = f"Tervalidasi Pillow ({fmt.upper()}, {pil_img.size[0]}x{pil_img.size[1]})"
            item["file"] = rel_file_path
            item_saved = True
            break

        if not item_saved:
            if duplicate_detected:
                item["status"] = "duplikat_dicurigai"
            else:
                item["status"] = "gagal"
            # Bersihkan record di database dan hapus file disk lama jika ada
            c.execute("UPDATE products SET image_file = NULL WHERE kode = ?", (kode,))
            conn.commit()
            if TEST_DB_PATH.exists():
                tconn = sqlite3.connect(str(TEST_DB_PATH))
                tc = tconn.cursor()
                tc.execute("UPDATE products SET image_file = NULL WHERE kode = ?", (kode,))
                tconn.commit()
                tconn.close()

            # Hapus berkas lama jika berstatus duplikat/gagal
            for old_file in IMAGES_DIR.glob(f"{kode}.*"):
                try:
                    old_file.unlink()
                except Exception:
                    pass

        results.append(item)

    conn.close()
    return results


def main():
    parser = argparse.ArgumentParser(description="Unduh dan validasi foto produk.")
    parser.add_argument("--kandidat", default=None, help="Path ke berkas JSON multi-kandidat URL")
    args = parser.parse_args()

    print("=" * 80)
    print("MEMULAI PENGUNDUHAN DAN VALIDASI FOTO PRODUK REIN KOMPUTER (DENGAN DETEKSI HASH)")
    print("=" * 80)
    results = download_and_validate_images(candidates_file=args.kandidat)

    berhasil = sum(1 for r in results if r["status"] == "berhasil")
    duplikat = sum(1 for r in results if r["status"] == "duplikat_dicurigai")
    gagal = sum(1 for r in results if r["status"] == "gagal")

    print("\nLAPORAN HASIL PER PRODUK (40 PRODUK):")
    print(f"{'Kode':<8} | {'Status':<18} | {'Ukuran':<10} | {'Hash MD5':<32} | {'Keterangan'}")
    print("-" * 105)
    for r in results:
        uk_str = f"{r['ukuran']} B" if r["ukuran"] else "-"
        desc = r["file"] if r["status"] == "berhasil" else r["alasan"]
        print(f"{r['kode']:<8} | {r['status']:<18} | {uk_str:<10} | {r['hash']:<32} | {desc}")

    print("-" * 105)
    print(f"Total: {len(results)} produk | Berhasil: {berhasil} | Duplikat: {duplikat} | Gagal: {gagal}")
    print("=" * 80)


if __name__ == "__main__":
    main()
