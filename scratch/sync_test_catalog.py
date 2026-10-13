import sqlite3

src = sqlite3.connect("data/catalog.db")
dst = sqlite3.connect("data/test_catalog.db")
c_src = src.cursor()
c_dst = dst.cursor()

cols = [r[1] for r in c_src.execute("PRAGMA table_info(products)").fetchall()]
col_str = ", ".join([f'"{col}"' for col in cols])
placeholders = ", ".join(["?"] * len(cols))
rows = c_src.execute(f"SELECT {col_str} FROM products").fetchall()

for r in rows:
    c_dst.execute("DELETE FROM products WHERE kode = ?", (r[0],))
c_dst.executemany(f"INSERT INTO products ({col_str}) VALUES ({placeholders})", rows)
dst.commit()
print(f"Synced {len(rows)} products into test_catalog.db")
src.close()
dst.close()
