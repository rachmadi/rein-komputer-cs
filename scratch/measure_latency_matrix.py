import time
import requests
import json
from services.agentic_tool_engine import run_agentic_tool
from core.catalog import Catalog

cat = Catalog.from_dummy()

def measure_runs(cond_name, num_runs=5):
    print(f"\n--- Measuring {cond_name} ---")
    times = []
    embed_times = []
    
    for i in range(num_runs):
        t0 = time.time()
        # Measure embedding isolated
        te0 = time.time()
        from services.catalog_service import get_embedding
        vec = get_embedding("laptop buat edit video 4k")
        te = time.time() - te0
        embed_times.append(te)
        
        # Measure full E2E
        res_dict = run_agentic_tool("laptop buat edit video 4k", [], cat)
        dt = time.time() - t0
        times.append(dt)
        print(f"  Run {i+1}: E2E={dt:.2f}s, Embed={te:.3f}s, Route={res_dict.get('route')}")
    
    # Get ps info
    ps = requests.get("http://localhost:11434/api/ps").json().get("models", [])
    m_info = next((m for m in ps if "gemma4" in m["name"]), {})
    size_mb = round(m_info.get("size", 9608350718) / (1024*1024), 1)
    vram_mb = round(m_info.get("size_vram", 0) / (1024*1024), 1)
    
    cold = times[0]
    warm = times[1:]
    avg_warm = sum(warm) / len(warm) if warm else cold
    max_warm = max(times)
    avg_embed = sum(embed_times) / len(embed_times)
    
    return {
        "kondisi": cond_name,
        "size_mb": size_mb,
        "vram_mb": vram_mb,
        "dingin_s": round(cold, 2),
        "hangat_avg_s": round(avg_warm, 2),
        "terlama_s": round(max_warm, 2),
        "embed_avg_s": round(avg_embed, 3)
    }

# Run benchmark for active configuration
res = measure_runs("Final (Config Aktif: Flash Attn + KV Cache Optim)")
print(json.dumps(res, indent=2))
