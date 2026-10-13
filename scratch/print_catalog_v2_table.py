import sqlite3

con = sqlite3.connect("data/catalog.db")
con.row_factory = sqlite3.Row
rows = con.execute("SELECT kode, cpu_tier, storage_ssd_gb, gpu_dedicated, vram_gb, screen_inch FROM products ORDER BY kode").fetchall()

print("| Kode | cpu_tier | storage_ssd_gb | gpu_dedicated | vram_gb | screen_inch |")
print("| :--- | :--- | :--- | :--- | :--- | :--- |")
for r in rows:
    c_tier = r["cpu_tier"] if r["cpu_tier"] is not None else "NULL"
    s_ssd = r["storage_ssd_gb"] if r["storage_ssd_gb"] is not None else "NULL"
    g_ded = r["gpu_dedicated"] if r["gpu_dedicated"] is not None else "NULL"
    v_gb = r["vram_gb"] if r["vram_gb"] is not None else "NULL"
    s_inch = r["screen_inch"] if r["screen_inch"] is not None else "NULL"
    print(f"| {r['kode']} | {c_tier} | {s_ssd} | {g_ded} | {v_gb} | {s_inch} |")
