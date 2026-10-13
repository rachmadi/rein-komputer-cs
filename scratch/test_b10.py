import os
import sys
sys.path.append("d:/RAG")
from core.catalog import Catalog
from services.agentic_tool_engine import check_fast_path

catalog = Catalog.from_dummy()
queries = [
    "ASUS buat edit video",
    "laptop RAM 16GB buat kuliah",
    "yang lebih murah",
    "yang ASUS aja"
]

for q in queries:
    fast, reply, tool = check_fast_path(q, catalog)
    print(f"Query: {q}")
    print(f"Fast Path: {fast}")
    print(f"Tool: {tool}")
    print("---")
