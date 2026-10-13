import sqlite3, json

conn = sqlite3.connect('data/catalog.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("""SELECT kode, nama, cpu_tier, ram_gb, vram_gb, gpu_dedicated 
               FROM products WHERE kode IN ('KB-L07', 'KB-L09', 'KB-L01', 'KB-L10')""")
rows = [dict(r) for r in cur.fetchall()]
for r in rows:
    print(r)
conn.close()

# Also check snapshot
with open('tests/fixtures/catalog_snapshot.json', 'r') as f:
    snap = json.load(f)
print("\n--- Snapshot ---")
for p in snap:
    if p['kode'] in ('KB-L07', 'KB-L09', 'KB-L01', 'KB-L10'):
        print({k: p.get(k) for k in ('kode','nama','cpu_tier','ram_gb','vram_gb','gpu_dedicated')})
