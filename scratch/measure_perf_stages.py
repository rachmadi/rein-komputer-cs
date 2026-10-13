import time
import json
import urllib.request
import os
from services.chat_service import process_chat_message, reset_chat_session
from services.agentic_tool_engine import run_agentic_tool
from core.catalog import Catalog

cat = Catalog.from_db("data/catalog.db")

def check_ollama_ps():
    try:
        req = urllib.request.urlopen("http://localhost:11434/api/ps", timeout=5)
        return json.loads(req.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}

print("=== OLLAMA /api/ps STATUS ===")
ps_data = check_ollama_ps()
print(json.dumps(ps_data, indent=2))

queries = [
    ("laptop buat edit video 4k", "laptop"),
    ("komputer buat game berat tapi kasir", "desktop")
]

for query, expected_cat in queries:
    print(f"\n==========================================")
    print(f"PENGUKURAN PER TAHAP: '{query}'")
    print(f"==========================================")
    
    # 1. Jalur Cepat / Templat (Default Produksi)
    for run_type in ["Dingin (Cold)", "Hangat (Warm 1)", "Hangat (Warm 2)"]:
        sid = f"perf_{run_type}_{query[:5]}"
        reset_chat_session(sid)
        t0 = time.perf_counter()
        res = process_chat_message(sid, query)
        total_time = time.perf_counter() - t0
        metrics = res.get("metrics", {})
        tool_time = metrics.get("tool", 0.0)
        frame_time = metrics.get("frame", {}).get("frame_latency", 0.0)
        retrieval_embed_time = max(0.0, total_time - tool_time - frame_time)
        
        print(f"[{run_type}] Mode=TEMPLATE E2E={total_time:.3f}s | Retrieval/Embed={retrieval_embed_time:.3f}s | Tool={tool_time:.4f}s | Frame={frame_time:.5f}s")
        if run_type == "Dingin (Cold)":
            print(f"  Produk: {[p['kode'] for p in res.get('products', [])]}")
            print(f"  Cuplikan Balasan: {res['reply'][:120]}...")

    # 2. Uji LLM Framing (Mengapa memakan waktu ~22-23 detik)
    print(f"\n[Eksperimen LLM Framing untuk '{query}']:")
    t0_llm_run = time.perf_counter()
    res_llm = run_agentic_tool(
        user_text=query,
        history=[],
        catalog=cat,
        use_llm_framing=True
    )
    total_llm = time.perf_counter() - t0_llm_run
    llm_frame_time = res_llm.get("metrics", {}).get("frame", {}).get("frame_latency", 0.0)
    print(f"  Mode=LLM FRAMING E2E={total_llm:.2f}s | Frame LLM Gen={llm_frame_time:.2f}s | Tool={res_llm.get('metrics', {}).get('tool', 0.0):.4f}s")
