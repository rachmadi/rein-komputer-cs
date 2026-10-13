import requests
import os
import json

col = os.getenv("KNOWLEDGE_COLLECTION", "computer_knowledge")
url = f"http://localhost:6333/collections/{col}/points/scroll"

res = requests.post(url, json={"limit": 100, "with_vector": True}).json()

p03 = None
for p in res.get("result", {}).get("points", []):
    if p.get("payload", {}).get("id") == "P03":
        p03 = p
        break

if p03:
    payload = p03["payload"]
    payload["filter"] = [
        {"field": "ram_gb", "op": ">=", "value": 32, "strength": "hard"},
        {"field": "storage_ssd_gb", "op": ">=", "value": 1000, "strength": "hard"},
        {"field": "cpu_tier", "op": ">=", "value": 2, "strength": "hard"},
        {"field": "gpu_dedicated", "op": "=", "value": 1, "strength": "hard"},
        {"field": "vram_gb", "op": ">=", "value": 8, "strength": "hard"}
    ]
    
    update_url = f"http://localhost:6333/collections/{col}/points?wait=true"
    update_res = requests.put(update_url, json={
        "points": [
            {
                "id": p03["id"],
                "vector": p03["vector"],
                "payload": payload
            }
        ]
    })
    print("Update status:", update_res.status_code, update_res.text)
