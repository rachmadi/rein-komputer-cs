import requests
import json

url = "http://localhost:8000/api/chat"
session_id = "test_user_session_99"

queries = [
    "laptop buat edit video 4k",
    "ada yang lebih murah?",
    "yang bisa dipake apa aja",
    "harga Acer Nitro V 15",
    "halo bang"
]

print("==== START API TESTS ====")
for q in queries:
    print(f"\nUser: {q}")
    payload = {
        "session_id": session_id,
        "message": q
    }
    try:
        resp = requests.post(url, json=payload, timeout=50)
        data = resp.json()
        print(f"Assistant: {data.get('reply')}")
        print(f"Route: {data.get('route')}")
        if data.get("products"):
            print(f"Products: {[p['kode'] for p in data['products']]}")
    except Exception as e:
        print(f"Model Gagal (Error): {e}")
