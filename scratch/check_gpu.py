import threading
import time
import requests
import subprocess
import json

def call_embed():
    print("Sending embed request...")
    try:
        requests.post("http://localhost:11434/api/embed", json={"model": "bge-m3:latest", "input": "This is a test document to check GPU usage."}, timeout=10)
    except Exception as e:
        print("Embed failed:", e)
    print("Embed finished.")

t = threading.Thread(target=call_embed)
t.start()
time.sleep(0.5)

print("\n--- OLLAMA PS ---")
try:
    res = requests.get("http://localhost:11434/api/ps").json()
    print(json.dumps(res, indent=2))
except Exception as e:
    print(e)

print("\n--- NVIDIA SMI ---")
subprocess.run(["nvidia-smi"])

t.join()
