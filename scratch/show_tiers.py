import sqlite3
conn = sqlite3.connect('data/catalog.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute('SELECT kode, nama, cpu, cpu_tier FROM products ORDER BY cpu_tier DESC')
for r in cur.fetchall():
    kode = r["kode"]
    tier = r["cpu_tier"]
    cpu = str(r["cpu"])[:45] if r["cpu"] else "None"
    print(f"{kode:8} tier={tier} cpu={cpu}")
conn.close()
