# -*- coding: utf-8 -*-
import urllib.request
import json

history_sim = [
    {"role": "user", "content": "Ada asus?"},
    {"role": "assistant", "content": "Ada Asus ExpertCenter, ROG Strix, dan Vivobook 14."},
    {"role": "user", "content": "Laptop"}
]

payload1 = {
    "model": "gemma4:e4b",
    "messages": history_sim,
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "search_catalog",
                "description": "Mencari produk katalog",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
            }
        }
    ],
    "stream": False
}

req1 = urllib.request.Request(
    "http://localhost:11434/api/chat",
    data=json.dumps(payload1).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(req1, timeout=30) as resp1:
    res1 = json.loads(resp1.read().decode("utf-8"))

msg1 = res1.get("message", {})
print("MSG1:", msg1)

# Putaran 2 persis seperti di agentic_tool_engine.py:
messages = list(history_sim)
messages.append(msg1)
messages.append({
    "role": "tool",
    "content": json.dumps({"status": "success", "products": [{"nama": "ASUS Vivobook 14 A1405", "harga": "Rp8.799.000"}]})
})

payload2 = {
    "model": "gemma4:e4b",
    "messages": messages,
    "stream": False
}

req2 = urllib.request.Request(
    "http://localhost:11434/api/chat",
    data=json.dumps(payload2).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(req2, timeout=30) as resp2:
    res2 = json.loads(resp2.read().decode("utf-8"))

print("RES2 MESSAGE:", res2.get("message"))
