import json

turns = []
with open("logs/eval/eval_chat_history.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            d = json.loads(line)
            if d.get("type") == "foto_terkirim":
                continue
            turns.append(d)

last_20 = turns[-20:]
for idx, t in enumerate(last_20, 1):
    ut = t.get("user_text")
    tc = t.get("tool_calls", [])
    bot = t.get("bot_reply", "")[:80]
    print(f"Turn {idx}: {ut}")
    print(f"  tool_calls: {tc}")
