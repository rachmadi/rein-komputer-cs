import os
import json
from services.knowledge_service import get_usage_requirements
from services.agentic_tool_engine import execute_tool
from services.catalog_service import get_active_catalog

reqs = get_usage_requirements("laptop buat edit video 4k")
print("Retrieved profiles:", reqs)
pls = reqs.get("profil", [])
p_ids = [p["profil_id"] for p in pls]
print("Profile IDs:", p_ids)

cat = get_active_catalog()
print("Total products in active catalog:", len(cat.products))

res_str, prods, cat_out, prof_out = execute_tool(
    "search_catalog",
    {"profil_id": ",".join(p_ids), "kategori": "laptop"},
    cat,
    [],
    "laptop buat edit video 4k"
)
print("Execute tool result:\n", res_str)
print("Prods:", [p["kode"] for p in prods])
