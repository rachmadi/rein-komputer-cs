import subprocess
import time
import urllib.request
import json

def get_ps():
    out = subprocess.check_output(["curl", "-s", "http://localhost:11434/api/ps"])
    return json.loads(out).get("models", [])

def print_ps(label):
    print(f"\n--- {label} ---")
    models = get_ps()
    if not models:
        print("No models loaded.")
    for m in models:
        print(f"Model: {m['name']}, Size: {m['size_vram']}, Processor: {m['details']['family']}")

print_ps("BEFORE EMBEDDING")

# 5 Embed calls
t0 = time.time()
for i in range(5):
    req_body = {"model": "bge-m3", "prompt": f"test sentence {i}"}
    req = urllib.request.Request("http://localhost:11434/api/embeddings", data=json.dumps(req_body).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        resp.read()
    print(f"Call {i+1} done")
print(f"Total time for 5 calls: {time.time() - t0:.2f}s")

print_ps("AFTER EMBEDDING")
