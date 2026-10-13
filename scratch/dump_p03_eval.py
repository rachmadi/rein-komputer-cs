from core.catalog import Catalog
from services.agentic_tool_engine import apply_filters, execute_tool
from services.knowledge_service import get_profile_by_id

cat = Catalog.from_dummy()
p03 = get_profile_by_id("P03")
filters = p03["filter"]

print("=== SYARAT P03 ===")
for f in filters:
    print(f"  {f['field']} {f['op']} {f['value']} [{f['strength']}]")

codes = ["KB-L07", "KB-L09", "KB-L01", "KB-L06", "KB-L10", "KB-D05"]
for kode in codes:
    p = next((x for x in cat.products if x["kode"] == kode), None)
    if not p:
        continue
    passed, reason, penalty, report = apply_filters(p, filters)
    print(f"\n--- {p['nama']} ({kode}) ---")
    print(f"  ram_gb={p.get('ram_gb')} cpu_tier={p.get('cpu_tier')} vram_gb={p.get('vram_gb')} gpu_dedicated={p.get('gpu_dedicated')} kategori={p.get('kategori')}")
    print(f"  Lulus: {passed}")
    print(f"  Gagal: {report['tidak_terpenuhi']}")
