import time
from services.agentic_tool_engine import run_agentic_tool
from core.catalog import Catalog

cat = Catalog.from_dummy()

convos = [
    {
        "id": "Percakapan 1 (Multi-turn P03)",
        "turns": [
            ("laptop buat edit video 4k", None, None),
            ("yang ASUS aja", "laptop", "P03"),
            ("ada yang lebih murah?", "laptop", "P03")
        ]
    },
    {
        "id": "Percakapan 2 (Kebutuhan Gabungan P05+P15)",
        "turns": [
            ("komputer buat game berat tapi kasir", None, None)
        ]
    },
    {
        "id": "Percakapan 3 (Spesifikasi Eksplisit Melebihi Katalog)",
        "turns": [
            ("laptop RAM 128GB", None, None)
        ]
    },
    {
        "id": "Percakapan 4 (OOD Retention - Serbaguna)",
        "turns": [
            ("laptop baterai awet", None, None)
        ]
    },
    {
        "id": "Percakapan 5 (Spesifik Teknik CAD/Revit P07)",
        "turns": [
            ("rekomendasi laptop untuk anak kuliah teknik arsitektur CAD", None, None)
        ]
    }
]

print("=== 5 PERCAKAPAN TELEGRAM LENGKAP ===")
for c in convos:
    print(f"\n=======================================================")
    print(f"[{c['id']}]")
    history = []
    active_cat = None
    active_prof = None
    offered = []
    for text, force_cat, force_prof in c["turns"]:
        cat_in = force_cat or active_cat
        prof_in = force_prof or active_prof
        t0 = time.time()
        res = run_agentic_tool(text, history, cat, current_category=cat_in, current_offered_products=offered, active_profile_id=prof_in)
        dt = time.time() - t0
        
        reply = res.get("reply", "")
        prods = res.get("products", [])
        active_cat = res.get("category") or active_cat
        active_prof = res.get("active_profile_id") or active_prof
        if prods:
            offered.extend([p["kode"] for p in prods])
            
        print(f"\nUSER: {text}")
        print(f"BOT ({dt:.2f}s | Route: {res.get('route')} | Active Profile: {active_prof}):\n{reply}")
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": reply})
