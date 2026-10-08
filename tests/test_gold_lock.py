# -*- coding: utf-8 -*-
"""
tests/test_gold_lock.py
Penjaga integritas berkas gold eval/parse_gold.csv.
Gagal jika SHA-256 parse_gold.csv tidak cocok dengan eval/gold.sha256.
Berkas checksum hanya boleh diperbarui atas persetujuan tertulis pemilik data.
"""
import hashlib
from pathlib import Path


def test_gold_dataset_checksum_lock():
    csv_path = Path("eval/parse_gold.csv")
    sha_path = Path("eval/gold.sha256")

    assert csv_path.exists(), f"Berkas {csv_path} tidak ditemukan!"
    assert sha_path.exists(), f"Berkas {sha_path} tidak ditemukan!"

    expected_sha = sha_path.read_text(encoding="utf-8").strip()
    actual_sha = hashlib.sha256(csv_path.read_bytes()).hexdigest()

    assert actual_sha == expected_sha, (
        f"INTEGRITAS GOLD TERLANGGAR: Checksum eval/parse_gold.csv berubah!\n"
        f"Diharapkan (gold.sha256): {expected_sha}\n"
        f"Aktual:                   {actual_sha}\n"
        f"Perubahan pada parse_gold.csv dilarang keras tanpa persetujuan tertulis pemilik data."
    )
