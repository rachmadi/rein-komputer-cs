import os
import sys
import json
import time

sys.path.append("d:/RAG")

from dotenv import load_dotenv
load_dotenv()
import services.chat_service
services.chat_service.CHAT_ENGINE_MODE = "agentic_tool"
from services.chat_service import process_chat_message

import services.agentic_tool_engine
original_execute = services.agentic_tool_engine.execute_tool

def patched_execute(name, args, catalog, session, user_text, prof_id=None):
    print(f"   [Tool Call] {name} -> {json.dumps(args)}")
    return original_execute(name, args, catalog, session, user_text, prof_id)
services.agentic_tool_engine.execute_tool = patched_execute

print("==== START FINAL SCENARIOS ====\n")

scenarios = [
    # 1. Edit video 4K + lebih murah
    ("S1", ["laptop buat edit video 4k", "ada yang lebih murah?"]),
    # 2. Unavailable
    ("S2", ["laptop RAM 128GB"]),
    # 3. Dedicated GPU VRAM NULL
    ("S3", ["laptop Test Laptop Null VRAM"]),
    # 4. Mixed profiles (Game berat + kasir)
    ("S4", ["komputer buat game berat tapi juga buat kasir toko"])
]

for sid, turns in scenarios:
    for q in turns:
        print(f"User: {q}")
        t0 = time.time()
        res = process_chat_message(sid, q)
        t1 = time.time()
        print(f"Assistant: {res['reply']}")
        print(f"Active Profile: {res.get('active_profile_id')}")
        if 'tool_calls' in res:
            for tc in res['tool_calls']:
                print(f"  Match Report: {tc.get('match_report')}")
        print(f"Route: {res.get('route')}")
        if res.get('products'):
            print(f"Products: {[p['kode'] for p in res['products']]}")
        print(f"Time taken: {t1-t0:.2f}s")
        print("-" * 20)
    print("=" * 40)
