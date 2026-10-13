# -*- coding: utf-8 -*-
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')

from services.catalog_service import reload_catalog
from services.dynamic_rag_engine import run_dynamic_rag

cat = reload_catalog()

print("=== TEST 1: GAMBAR TEKNIK & INTERIOR DESIGNER ===")
res1 = run_dynamic_rag(
    user_text="Aku lupa. Mamaku interior designer, butuh gambar teknik",
    history=[],
    catalog=cat,
    current_category="laptop"
)
print("Reply 1:", res1["reply"])
print("Products 1:", [p["nama"] for p in res1["products"]])

print("\n=== TEST 2: KONFIRMASI GEFORCE ===")
history2 = [
    {"role": "user", "content": "Aku lupa. Mamaku interior designer, butuh gambar teknik"},
    {"role": "assistant", "content": res1["reply"]}
]
res2 = run_dynamic_rag(
    user_text="Itu ada yang pake geforce?",
    history=history2,
    catalog=cat,
    current_category="laptop",
    current_offered_products=[p["kode"] for p in res1["products"]]
)
print("Reply 2:", res2["reply"])
print("Products 2:", [p["nama"] for p in res2["products"]])

print("\n=== TEST 3: MINTA SPEK LENGKAP & GAMBAR ===")
history3 = history2 + [
    {"role": "user", "content": "Itu ada yang pake geforce?"},
    {"role": "assistant", "content": res2["reply"]}
]
res3 = run_dynamic_rag(
    user_text="Spek lengkap sama gambarnya dong",
    history=history3,
    catalog=cat,
    current_category="laptop",
    current_offered_products=[p["kode"] for p in res2["products"]]
)
print("Reply 3:", res3["reply"])
print("Products 3:", [p["nama"] for p in res3["products"]])
print("Image URLs 3:", [p.get("image_url") for p in res3["products"]])
