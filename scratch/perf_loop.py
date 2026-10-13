import sys
import time
sys.path.append("d:/RAG")

from dotenv import load_dotenv
load_dotenv()

import services.chat_service
services.chat_service.CHAT_ENGINE_MODE = "agentic_tool"
from services.chat_service import process_chat_message

scenarios = [
    ("S1", "laptop buat edit video 4k"),
    ("S2", "ada yang lebih murah?"),
    ("S3", "laptop RAM 128GB"),
    ("S4", "komputer buat game berat tapi juga buat kasir toko"),
    ("S5", "halo"),
    ("S6", "laptop asus tuf")
]

results = {q: {"llm1": [], "tool": [], "llm2": [], "total": []} for sid, q in scenarios}

for i in range(5):
    print(f"--- RUN {i+1} ---")
    for sid, q in scenarios:
        sid_run = f"{sid}_{i}"
        res = process_chat_message(sid_run, q)
        metrics = res.get("metrics", {})
        if metrics:
            results[q]["llm1"].append(metrics.get("llm1", 0))
            results[q]["tool"].append(metrics.get("tool", 0))
            results[q]["llm2"].append(metrics.get("llm2", 0))
            results[q]["total"].append(metrics.get("total", 0))

print("\n\n==== HASIL PERF TEST ====")
for q in results:
    m = results[q]
    if not m["total"]: continue
    avg_llm1 = sum(m["llm1"])/len(m["llm1"])
    avg_tool = sum(m["tool"])/len(m["tool"])
    avg_llm2 = sum(m["llm2"])/len(m["llm2"])
    avg_total = sum(m["total"])/len(m["total"])
    max_total = max(m["total"])
    
    print(f"Query: {q}")
    print(f"  LLM-1 : Avg {avg_llm1:.2f}s | Max {max(m['llm1']):.2f}s")
    print(f"  Tool  : Avg {avg_tool:.2f}s | Max {max(m['tool']):.2f}s")
    print(f"  LLM-2 : Avg {avg_llm2:.2f}s | Max {max(m['llm2']):.2f}s")
    print(f"  Total : Avg {avg_total:.2f}s | Max {max_total:.2f}s\n")
