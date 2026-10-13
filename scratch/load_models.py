import requests
import json
import time

print("Setting keep_alive...")
requests.post("http://localhost:11434/api/generate", json={"model": "gemma4:e4b", "keep_alive": "60m"})
print("Loading gemma4:e4b...")
requests.post("http://localhost:11434/api/generate", json={"model": "gemma4:e4b", "prompt": "Hi", "stream": False})

print("Loading bge-m3...")
requests.post("http://localhost:11434/api/embed", json={"model": "bge-m3:latest", "input": "test", "keep_alive": "60m"})

print("\n--- OLLAMA PS ---")
try:
    res = requests.get("http://localhost:11434/api/ps").json()
    print(json.dumps(res, indent=2))
except Exception as e:
    print(e)
