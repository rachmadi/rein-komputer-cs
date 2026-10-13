import sys
sys.path.insert(0, ".")
import sqlite3, json
from services.action_engine import build_lembar_spesifikasi

con = sqlite3.connect("data/catalog.db")
con.row_factory = sqlite3.Row
p12 = dict(con.execute("SELECT * FROM products WHERE kode = 'KB-D12'").fetchone())
p07 = dict(con.execute("SELECT * FROM products WHERE kode = 'KB-D07'").fetchone())

print("KB-D12 raw_data:", repr(p12.get("raw_data")))
print("KB-D12 lembar_spesifikasi:", json.dumps(build_lembar_spesifikasi(p12), indent=2))
print("KB-D07 raw_data:", repr(p07.get("raw_data")))
print("KB-D07 lembar_spesifikasi:", json.dumps(build_lembar_spesifikasi(p07), indent=2))
