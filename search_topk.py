import requests

QDRANT_URL = "http://localhost:6333"
OLLAMA_URL = "http://localhost:11434"

COLLECTION = "computer_knowledge"
EMBEDDING_MODEL = "bge-m3"

query = "Berapa kapasitas baterai AstraBook 15 Pro?"

# --------------------------------------------------
# 1. Ubah pertanyaan menjadi embedding
# --------------------------------------------------

response = requests.post(
    f"{OLLAMA_URL}/api/embed",
    json={
        "model": EMBEDDING_MODEL,
        "input": query
    }
)

response.raise_for_status()

embedding = response.json()["embeddings"][0]

print("Query:")
print(query)
print()
print("Dimensi embedding:", len(embedding))


# --------------------------------------------------
# 2. Cari Top-3 di Qdrant
# --------------------------------------------------

response = requests.post(
    f"{QDRANT_URL}/collections/{COLLECTION}/points/query",
    json={
        "query": embedding,
        "limit": 3,
        "with_payload": True
    }
)

response.raise_for_status()

results = response.json()["result"]["points"]


# --------------------------------------------------
# 3. Tampilkan hasil retrieval
# --------------------------------------------------

print()
print("========== HASIL RETRIEVAL ==========")

for i, point in enumerate(results, 1):

    payload = point["payload"]

    print()
    print(f"--- HASIL {i} ---")
    print("ID     :", point["id"])
    print("Score  :", point["score"])
    print("Kode   :", payload.get("kode"))
    print("Produk :", payload.get("produk"))
    print()
    print(payload.get("text"))