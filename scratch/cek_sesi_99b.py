import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

lines = open("logs/chat_history.jsonl", "r", encoding="utf-8").readlines()
sess_turns = [
    json.loads(l) for l in lines 
    if json.loads(l).get("session_id") == "99b9b3f6adc7" 
    and json.loads(l).get("user_text") is not None
]
print(f"Total turns in session 99b9b3f6adc7: {len(sess_turns)}")
for i, t in enumerate(sess_turns, 1):
    ts = t.get("timestamp")
    u = t.get("user_text")
    tools = [tc.get("nama") for tc in t.get("tool_calls", [])]
    args = [tc.get("argumen") for tc in t.get("tool_calls", [])]
    reply = t.get("bot_reply")
    lat = round(t.get("latency_ms", 0)/1000, 2)
    print(f"\n--- [T{i:02d}] ({lat}s) {ts} ---")
    print(f"User : {u}")
    print(f"Tools: {tools} -> Args: {args}")
    print(f"Bot  : {reply}")
