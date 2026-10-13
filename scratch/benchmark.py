import requests
import time
import json
from services.agentic_tool_engine import run_agentic_tool
from core.catalog import Catalog
import os
import subprocess

cat = Catalog.from_dummy()

def measure_e2e(name):
    t0 = time.time()
    res = run_agentic_tool("laptop buat edit video 4k", [], cat, model="gemma4:e4b")
    dt = time.time() - t0
    
    ps = requests.get("http://localhost:11434/api/ps").json()
    size = size_vram = 0
    for p in ps.get("models", []):
        if p["name"] == "gemma4:e4b":
            size = p["size"]
            size_vram = p["size_vram"]
            
    print(f"{name} -> E2E: {dt:.2f}s | Size: {size/1024/1024:.1f}MB | VRAM: {size_vram/1024/1024:.1f}MB")

measure_e2e("Baseline")

# Modify num_ctx in intent_classifier and agentic_tool_engine?
# Actually, I can just modify OLLAMA_FLASH_ATTENTION and OLLAMA_KV_CACHE_TYPE by restarting Ollama!
