import requests

# Produk yang akan dimasukkan
product_text = """KB-L02 — AstraBook 15 Pro
Jenis: Laptop
Harga: Rp11.999.000
Prosesor: Intel Core i5-13420H
RAM: 16 GB DDR5
Storage: 512 GB NVMe SSD
GPU: NVIDIA GeForce RTX 2050 4 GB
Display: 15,6 inci FHD 144 Hz
Sistem operasi: Windows 11 Home
Penggunaan yang disarankan: Cocok untuk programming, Android Studio, desain ringan, dan gaming menengah."""

# 1. Buat embedding melalui Ollama
response = requests.post(
    "http://localhost:11434/api/embed",
    json={
        "model": "bge-m3",
        "input": product_text
    }
)

response.raise_for_status()

embedding = response.json()["embeddings"][0]

print("Embedding berhasil")
print("Dimensi:", len(embedding))


# 2. Masukkan vector + payload ke Qdrant
point = {
    "id": 1,
    "vector": embedding,
    "payload": {
        "code": "KB-L02",
        "product": "AstraBook 15 Pro",
        "type": "Laptop",
        "text": product_text,
        "source": "Katalog_Komputer_RAG.pdf"
    }
}

response = requests.put(
    "http://localhost:6333/collections/computer_knowledge/points",
    json={
        "points": [point]
    }
)

response.raise_for_status()

print("Berhasil dimasukkan ke Qdrant")
print(response.json())