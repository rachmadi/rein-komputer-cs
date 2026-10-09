# -*- coding: utf-8 -*-
"""
scripts/build_catalog_db.py
Membangun atau menginisialisasi database SQLite katalog produk (data/catalog.db)
dari data bibit (data/seed/catalog_seed.csv).
Digunakan saat setup awal repositori baru atau untuk me-rebuild database lokal.
"""
import os
import sys
import csv
import sqlite3
import argparse


def build_catalog_db(csv_path: str = "data/seed/catalog_seed.csv", db_path: str = "data/catalog.db", force: bool = False):
    if not os.path.exists(csv_path):
        print(f"[ERROR] Berkas bibit katalog tidak ditemukan di: {csv_path}")
        sys.exit(1)

    if os.path.exists(db_path) and not force:
        print(f"[INFO] Database katalog sudah ada di '{db_path}'. Gunakan flag --force untuk menimpa.")
        return

    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)

    if not fields or not rows:
        print(f"[ERROR] Berkas bibit katalog kosong: {csv_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Buat tabel products
    columns_def = [f'"{col}" TEXT' for col in fields]
    create_sql = f'CREATE TABLE IF NOT EXISTS products (\n  {",\n  ".join(columns_def)},\n  PRIMARY KEY ("kode")\n);'
    cur.execute("DROP TABLE IF EXISTS products;")
    cur.execute(create_sql)

    # Masukkan data baris
    placeholders = ", ".join(["?"] * len(fields))
    col_names = ", ".join([f'"{c}"' for c in fields])
    insert_sql = f'INSERT INTO products ({col_names}) VALUES ({placeholders});'

    row_tuples = [[row[f] for f in fields] for row in rows]
    cur.executemany(insert_sql, row_tuples)
    conn.commit()
    conn.close()

    print(f"[SUKSES] Berhasil memuat {len(rows)} produk dari '{csv_path}' ke database '{db_path}'.")


def main():
    parser = argparse.ArgumentParser(description="Build SQLite catalog database from seed CSV.")
    parser.add_argument("--csv", default="data/seed/catalog_seed.csv", help="Path to seed CSV file")
    parser.add_argument("--db", default="data/catalog.db", help="Path to output SQLite database")
    parser.add_argument("--force", action="store_true", help="Force recreate catalog database")
    args = parser.parse_args()

    build_catalog_db(csv_path=args.csv, db_path=args.db, force=args.force)


if __name__ == "__main__":
    main()
