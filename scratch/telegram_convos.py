import sys
sys.path.append("d:/RAG")
from dotenv import load_dotenv
load_dotenv()
from services.chat_service import process_chat_message
import services.chat_service
services.chat_service.CHAT_ENGINE_MODE = "agentic_tool"
import time

scenarios = [
    ("S1", "kebutuhan jelas: laptop buat edit video 4k"),
    ("S1", "yang ASUS aja"),
    ("S1", "ada yang lebih murah?"),
    ("S2", "komputer buat game berat tapi juga buat kasir toko"),
    ("S3", "laptop RAM 128GB")
]

for sid, q in scenarios:
    print(f"\n======================================")
    print(f"USER ({sid}): {q}")
    t0 = time.time()
    res = process_chat_message(sid, q)
    dt = time.time() - t0
    
    print(f"BOT ({dt:.2f}s):\n{res.get('reply')}")
    print(f"\n[DEBUG] Profile Aktif: {res.get('active_profile_id')}")
    tools = res.get("tool_calls", [])
    if tools:
        print(f"[DEBUG] Tool yang dipanggil: {tools[0]['name']} with args {tools[0]['args']}")
    else:
        print(f"[DEBUG] Tool yang dipanggil: None (atau bypass/fast_path)")
