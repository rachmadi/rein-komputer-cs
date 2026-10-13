import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from services.catalog_service import get_active_catalog
from services.product_card import format_product_card

cat = get_active_catalog()
prods_by_cat = {}
for p in cat.by_code.values():
    k = p.get("kategori", "").lower()
    if k not in prods_by_cat:
        prods_by_cat[k] = p

for k in ["laptop", "desktop", "monitor", "printer"]:
    p = prods_by_cat.get(k)
    print(f"=== KATEGORI: {k.upper()} ({p.get('kode')}) ===")
    print(format_product_card(p))
    print()
