# -*- coding: utf-8 -*-
import sys
import io
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')

from services.catalog_service import reload_catalog
from services.agentic_tool_engine import run_agentic_tool

cat = reload_catalog()

print("=== TEST 1: KONSULTAN IT & MAIN LLM LOKAL ===")
h1 = [
    {"role": "user", "content": "Papaku konsultan IT"},
    {"role": "assistant", "content": "Wah, untuk konsultan IT kita sarankan laptop performa tinggi."},
    {"role": "user", "content": "Kadang main LLM lokal juga"}
]
res1 = run_agentic_tool("Kadang main LLM lokal juga", h1[:-1], cat, current_category="laptop")
print("Reply 1:", res1["reply"])
print("Route 1:", res1["route"])
print("Products 1:", [p["nama"] for p in res1["products"]])
print("-" * 50)

print("\n=== TEST 2: SPEKNYA DONG ===")
h2 = h1 + [{"role": "assistant", "content": res1["reply"]}]
res2 = run_agentic_tool("Speknya dong", h2, cat, current_category="laptop", current_offered_products=[p["kode"] for p in res1["products"]])
print("Reply 2:", res2["reply"])
print("Route 2:", res2["route"])
print("Products 2:", [p["nama"] for p in res2["products"]])
print("-" * 50)
