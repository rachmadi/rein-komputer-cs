# -*- coding: utf-8 -*-
import json
import os
import dotenv

dotenv.load_dotenv()

# Pastikan tidak dalam test mode agar menulis ke logs/chat_history.jsonl
os.environ.pop("CHAT_LOG_TARGET", None)
os.environ.pop("PYTEST_CURRENT_TEST", None)
os.environ.pop("TESTING", None)

import sys
sys.path.insert(0, os.path.abspath("."))

from services.chat_service import process_chat_message

session_id = "test_live_audit_turn_17a"
user_text = "Rekomendasi laptop untuk mahasiswa budget 8 juta"

print(f"Mengirim pesan: '{user_text}' untuk sesi '{session_id}'...")
result = process_chat_message(session_id=session_id, user_text=user_text)

print(f"Reply: {result.get('reply')}")
print(f"Route: {result.get('route')}")

log_path = os.path.join("logs", "chat_history.jsonl")
with open(log_path, "r", encoding="utf-8") as f:
    lines = [l.strip() for l in f if l.strip()]

last_line = lines[-1]
last_entry = json.loads(last_line)

print("\n--- BARIS TERAKHIR logs/chat_history.jsonl ---")
print(json.dumps(last_entry, ensure_ascii=False, indent=2))

print("\n--- FIELD generator_calls ---")
print(json.dumps(last_entry.get("generator_calls"), ensure_ascii=False, indent=2))
