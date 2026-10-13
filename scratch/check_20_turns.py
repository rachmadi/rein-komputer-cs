import json

with open("logs/chat_history.jsonl", "r", encoding="utf-8") as f:
    lines = [json.loads(line) for line in f if line.strip()]

print(f"Total lines: {len(lines)}")
for i, l in enumerate(lines[-20:], 1):
    usr = l.get("pesan_user") or l.get("user_text") or l.get("pesan") or l.get("text")
    print(f"{i}: {usr}")
