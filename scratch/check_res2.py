# -*- coding: utf-8 -*-
import urllib.request
import json

history_sim = [
    {"role": "user", "content": "Ada asus?"},
    {"role": "assistant", "content": "Ada Asus ExpertCenter, ROG Strix, dan Vivobook 14."},
    {"role": "user", "content": "Laptop"},
    {"role": "assistant", "content": "", "tool_calls": [{"id": "call_1", "function": {"name": "search_catalog", "arguments": {"query": "laptop"}}}]},
    {"role": "tool", "content": json.dumps({"status": "success", "products": [{"nama": "ASUS Vivobook 14 A1405", "harga": "Rp8.799.000", "prosesor": "Intel Core i5-1235U"}]})}
]

payload = {
    "model": "gemma4:e4b",
    "messages": history_sim,
    "stream": False
}

req = urllib.request.Request(
    "http://localhost:11434/api/chat",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(req, timeout=30) as resp:
    res = json.loads(resp.read().decode("utf-8"))

msg = res.get("message", {})
print("CONTENT REPR:", repr(msg.get("content")))
print("TOOL CALLS:", msg.get("tool_calls"))
print("THINKING REPR:", repr(msg.get("thinking")[:100] if msg.get("thinking") else None))
