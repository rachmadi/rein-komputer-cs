import sys
from core.catalog import Catalog
from services.agentic_tool_engine import apply_filters
from services.knowledge_service import get_profile_by_id
import json

cat = Catalog.from_dummy()

def check_prod(kode):
    p = [x for x in cat.products if x["kode"] == kode][0]
    prof = get_profile_by_id("P03")
    filters = prof["filter"]
    passed, reason, penalty, report = apply_filters(p, filters)
    
    print(f"\n--- {p['nama']} ({kode}) ---")
    print(f"ram_gb: {p.get('ram_gb')}")
    print(f"cpu_tier: {p.get('cpu_tier')}")
    print(f"vram_gb: {p.get('vram_gb')}")
    print(f"gpu_dedicated: {p.get('gpu_dedicated')}")
    print(f"kategori: {p.get('kategori')}")
    
    print("\nSyarat P03:")
    for f in filters:
        print(f" - {f['field']} {f['op']} {f['value']}")
        
    print(f"\nGagal: {report['tidak_terpenuhi']}")

check_prod("KB-L09") # TUF
check_prod("KB-L07") # Vivobook
check_prod("KB-D05") # ROG Strix
