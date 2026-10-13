# -*- coding: utf-8 -*-
import json
import sqlite3
import sys
import io
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')

from services.catalog_service import reload_catalog
from services.agentic_tool_engine import execute_tool

cat = reload_catalog()

# Ambil history sebelum ID 153
conn = sqlite3.connect('data/catalog.db')
cur = conn.cursor()
cur.execute('SELECT user_text, bot_reply FROM chat_logs WHERE session_id=\'tg_1095607605\' AND id <= 152 ORDER BY id ASC')
rows = cur.fetchall()

history = []
for u, b in rows[-6:]:
    history.append({'role': 'user', 'content': u})
    if b:
        history.append({'role': 'assistant', 'content': b})

tool_out_str, matched, _ = execute_tool("search_catalog", {"query": "laptop"}, cat)

msg1_sim = {
    "role": "assistant",
    "content": "",
    "tool_calls": [
        {"id": "call_laptop", "function": {"name": "search_catalog", "arguments": {"query": "laptop"}}}
    ]
}

messages = history[-8:] + [
    {"role": "user", "content": "Laptop"},
    msg1_sim,
    {"role": "tool", "content": tool_out_str}
]

payload2 = {
    "model": "gemma4:e4b",
    "messages": messages,
    "stream": False,
    "think": False,
    "options": {"temperature": 0.2, "num_predict": 300}
}

req2 = urllib.request.Request("http://localhost:11434/api/chat", data=json.dumps(payload2).encode("utf-8"), headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req2) as resp2:
    res2 = json.loads(resp2.read().decode("utf-8"))

msg2 = res2.get("message", {})
print("\n--- PUTARAN 2 HASIL RES2 ---")
print("content:", repr(msg2.get("content")))
print("tool_calls:", msg2.get("tool_calls"))
print("thinking:", repr(msg2.get("thinking")[:150] if msg2.get("thinking") else None))
