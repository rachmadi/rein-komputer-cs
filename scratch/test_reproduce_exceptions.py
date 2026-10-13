import json
import sys
import os

sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding="utf-8")

from services.llm_generator import generate_response

with open("logs/chat_history.jsonl", "r", encoding="utf-8") as f:
    lines = [json.loads(l) for l in f if "2026-10-11T15:" in json.loads(l).get("timestamp", "")]

print(f"Total turns loaded: {len(lines)}")

for idx in [5, 7, 8]:  # 0-indexed: 5 is Turn 6, 7 is Turn 8, 8 is Turn 9
    turn = lines[idx]
    user_text = turn.get("user_text")
    aksi = turn.get("aksi_parser")
    fakta = turn.get("fakta_lengkap") or {}
    state = turn.get("state_setelah") or {}
    
    hist = []
    for prev in lines[max(0, idx-4):idx]:
        hist.append({"role": "user", "content": prev.get("user_text")})
        hist.append({"role": "assistant", "content": prev.get("bot_reply")})

    print(f"\n=======================================================")
    print(f"Turn {idx+1}: '{user_text}' (Aksi: {aksi})")
    print(f"=======================================================")

    out, metrics = generate_response(
        aksi=aksi,
        fakta=fakta,
        state=state,
        history=hist,
        pesan_pelanggan=user_text
    )

    print("Error:", metrics.get("error"))
    print("Latency ms:", metrics.get("latency_ms"))
    print("Raw Content:", repr(metrics.get("raw_content")))
    print("Output text:", out.teks)
