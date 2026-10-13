import sqlite3, json
conn = sqlite3.connect('data/catalog.db')
cur = conn.cursor()
for r in cur.execute('SELECT kode, nama, raw_data FROM products WHERE nama LIKE "%G3020%" or nama LIKE "%Canon%"').fetchall():
    print(r[0], r[1])
    raw = json.loads(r[2]) if r[2] else None
    print("RAW:", raw)
