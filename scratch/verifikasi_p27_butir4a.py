import sqlite3
import json
from services.agent_tools import katalog

def run_4a_verification():
    db_path = "data/catalog.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    print("=== VERIFIKASI BUTIR 4a: TES UNIT SQL & GROUND TRUTH data/catalog.db ===")
    
    # 1. 4 Kategori: Termurah & Termahal
    categories = ["laptop", "desktop", "monitor", "printer"]
    print("\n--- 1. Urutan Termurah & Termahal (4 Kategori) ---")
    for cat in categories:
        cur.execute("SELECT kode, nama, CAST(harga_idr AS INTEGER) FROM products WHERE LOWER(kategori) = ? ORDER BY CAST(harga_idr AS INTEGER) ASC LIMIT 1", (cat,))
        gt_min = cur.fetchone()
        cur.execute("SELECT kode, nama, CAST(harga_idr AS INTEGER) FROM products WHERE LOWER(kategori) = ? ORDER BY CAST(harga_idr AS INTEGER) DESC LIMIT 1", (cat,))
        gt_max = cur.fetchone()

        res_min = katalog(kategori=cat, urutan="termurah", katalog_sql=True)
        res_max = katalog(kategori=cat, urutan="termahal", katalog_sql=True)

        katalog_min = res_min["produk"][0]
        katalog_max = res_max["produk"][0]

        match_min = (katalog_min["kode"] == gt_min[0] and katalog_min["harga_idr"] == gt_min[2])
        match_max = (katalog_max["kode"] == gt_max[0] and katalog_max["harga_idr"] == gt_max[2])

        print(f"[{cat.upper()}]")
        print(f"  Termurah: GT={gt_min[0]} ({gt_min[1]}, Rp{gt_min[2]:,}) | Tool={katalog_min['kode']} ({katalog_min['nama']}, Rp{katalog_min['harga_idr']:,}) | Cocok={match_min}")
        print(f"  Termahal: GT={gt_max[0]} ({gt_max[1]}, Rp{gt_max[2]:,}) | Tool={katalog_max['kode']} ({katalog_max['nama']}, Rp{katalog_max['harga_idr']:,}) | Cocok={match_max}")
        assert match_min and match_max

    # 2. Filter Gabungan: laptop ram>=16 + gpu_dedicated=true + ssd>=512 + urutan termurah
    print("\n--- 2. Filter Gabungan Laptop ---")
    cur.execute("""
        SELECT kode, nama, CAST(harga_idr AS INTEGER), ram_gb, gpu_dedicated, storage_ssd_gb
        FROM products 
        WHERE LOWER(kategori) = 'laptop' 
          AND CAST(ram_gb AS INTEGER) >= 16 
          AND gpu_dedicated = 1 
          AND CAST(storage_ssd_gb AS INTEGER) >= 512 
        ORDER BY CAST(harga_idr AS INTEGER) ASC
    """)
    gt_combo = cur.fetchall()
    res_combo = katalog(
        kategori="laptop",
        ram_min_gb=16,
        gpu_dedicated=True,
        ssd_min_gb=512,
        urutan="termurah",
        katalog_sql=True
    )
    print(f"GT total cocok: {len(gt_combo)}, kode urut: {[r[0] for r in gt_combo]}")
    print(f"Tool total cocok: {res_combo['total_cocok']}, kode urut: {[p['kode'] for p in res_combo['produk']]}")
    assert res_combo["total_cocok"] == len(gt_combo)
    assert [p["kode"] for p in res_combo["produk"]] == [r[0] for r in gt_combo]
    print(f"Produk pertama termurah: {res_combo['produk'][0]['kode']} ({res_combo['produk'][0]['nama']}) - Rp{res_combo['produk'][0]['harga_idr']:,}")

    # 3. Filter Layar: monitor layar_min 27 + refresh_min 144
    print("\n--- 3. Filter Layar Monitor ---")
    cur.execute("""
        SELECT kode, nama, CAST(harga_idr AS INTEGER), screen_inch, refresh_hz 
        FROM products 
        WHERE LOWER(kategori) = 'monitor' 
          AND CAST(screen_inch AS REAL) >= 27 
          AND CAST(refresh_hz AS INTEGER) >= 144 
        ORDER BY CAST(harga_idr AS INTEGER) ASC
    """)
    gt_monitor = cur.fetchall()
    res_monitor = katalog(
        kategori="monitor",
        layar_min_inci=27.0,
        refresh_min_hz=144,
        urutan="termurah",
        katalog_sql=True
    )
    print(f"GT total cocok: {len(gt_monitor)}, kode urut: {[r[0] for r in gt_monitor]}")
    print(f"Tool total cocok: {res_monitor['total_cocok']}, kode urut: {[p['kode'] for p in res_monitor['produk']]}")
    assert res_monitor["total_cocok"] == len(gt_monitor)
    assert [p["kode"] for p in res_monitor["produk"]] == [r[0] for r in gt_monitor]

    # 4. budget_max menghasilkan melebihi_budget
    print("\n--- 4. Budget Max Melebihi Budget ---")
    res_over = katalog(kategori="laptop", budget_max=2000000, katalog_sql=True)
    print(f"Status: {res_over['status']}, Total cocok: {res_over['total_cocok']}")
    print(f"Pesan: {res_over.get('pesan')}")
    print(f"Produk termurah alternatif: {res_over['produk_termurah'][0]['kode']} - Rp{res_over['produk_termurah'][0]['harga_idr']:,}")
    assert res_over["status"] == "melebihi_budget"
    assert res_over["total_cocok"] == 0
    assert res_over["produk_termurah"][0]["harga_idr"] > 2000000

    conn.close()
    print("\n=== SEMUA TES UNIT BUTIR 4a SUKSES & TERVERIFIKASI ===")

if __name__ == "__main__":
    run_4a_verification()
