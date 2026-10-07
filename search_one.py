import requests

query = "Laptop untuk programming dan Android Studio dengan budget sekitar 12 juta"

# 1. Ubah pertanyaan menjadi embedding
response = requests.post(
    "http://localhost:11434/api/embed",
    json={
        "model": "bge-m3",
        "input": query
    }
)

response.raise_for_status()

query_vector = response.json()["embeddings"][0]

print("Query berhasil di-embedding")
print("Dimensi:", len(query_vector))


# 2. Cari vector yang paling mirip di Qdrant
response = requests.post(
    "http://localhost:6333/collections/computer_knowledge/points/query",
    json={
        "query": query_vector,
        "limit": 3,
        "with_payload": True
    }
)

response.raise_for_status()

result = response.json()

print()
print("=== HASIL RETRIEVAL ===")

for i, item in enumerate(result["result"]["points"], 1):
    print()
    print(f"--- HASIL {i} ---")
    print("ID:", item["id"])
    print("Score:", item["score"])
    print("Kode:", item["payload"]["code"])
    print("Produk:", item["payload"]["product"])
    print("Teks:")
    print(item["payload"]["text"])