import requests

QDRANT_URL = "http://localhost:6333"
OLLAMA_URL = "http://localhost:11434"

COLLECTION = "computer_knowledge"
EMBEDDING_MODEL = "bge-m3"
LLM_MODEL = "gemma4:e4b"

query = "Apakah AstraBook 15 Pro memiliki baterai 70 Wh dan berapa lama daya tahannya?"

# =========================================================
# 1. Buat embedding untuk pertanyaan
# =========================================================

response = requests.post(
    f"{OLLAMA_URL}/api/embed",
    json={
        "model": EMBEDDING_MODEL,
        "input": query
    }
)

response.raise_for_status()

query_vector = response.json()["embeddings"][0]


# =========================================================
# 2. Cari knowledge yang paling relevan di Qdrant
# =========================================================

response = requests.post(
    f"{QDRANT_URL}/collections/{COLLECTION}/points/query",
    json={
        "query": query_vector,
        "limit": 3,
        "with_payload": True
    }
)

response.raise_for_status()

results = response.json()["result"]["points"]


# =========================================================
# 3. Gabungkan hasil retrieval menjadi context
# =========================================================

context_parts = []

for point in results:
    text = point["payload"]["text"]
    context_parts.append(text)

context = "\n\n".join(context_parts)


# =========================================================
# 4. Buat prompt untuk LLM
# =========================================================

prompt = f"""
Anda adalah chatbot customer care produk komputer.

Tugas Anda adalah menjawab pertanyaan pengguna berdasarkan KNOWLEDGE BASE
yang diberikan.

ATURAN GROUNDING:

1. Gunakan HANYA informasi yang terdapat secara eksplisit dalam
   KNOWLEDGE BASE.

2. Setiap fakta yang Anda sampaikan harus dapat ditemukan secara
   langsung dalam KNOWLEDGE BASE.

3. DILARANG menggunakan pengetahuan umum atau pengetahuan dari luar
   KNOWLEDGE BASE.

4. DILARANG melakukan inferensi teknis yang tidak dinyatakan dalam
   KNOWLEDGE BASE.
   Jangan mengubah spesifikasi menjadi klaim performa seperti:
   "lebih kuat", "lebih cepat", "cukup untuk", "kurang optimal",
   "mampu menjalankan", atau istilah sejenis, kecuali klaim tersebut
   dinyatakan secara eksplisit dalam KNOWLEDGE BASE.

5. Untuk rekomendasi, gunakan hanya kecocokan yang secara eksplisit
   dinyatakan dalam field "Penggunaan yang disarankan" serta
   batasan lain yang dapat diverifikasi dari data.

6. Jika suatu informasi tidak tersedia dalam KNOWLEDGE BASE,
   katakan dengan jelas bahwa informasi tersebut tidak tersedia.

7. Jangan mengarang harga, spesifikasi, performa, stok, baterai,
   kompatibilitas, atau informasi lainnya.

8. Jangan menyatakan bahwa sebuah produk adalah "terbaik".
   Gunakan formulasi seperti "berdasarkan kebutuhan dan informasi
   dalam knowledge base, produk ini sesuai karena ...".

9. Jika beberapa produk memenuhi kebutuhan pengguna, sebutkan
   produk-produk tersebut berdasarkan informasi yang tersedia,
   tanpa membuat ranking berdasarkan penilaian pribadi.

10. Pisahkan antara FAKTA dan ALASAN REKOMENDASI.
    Alasan rekomendasi harus dapat ditelusuri kembali ke informasi
    dalam KNOWLEDGE BASE.

KNOWLEDGE BASE:
----------------
{context}
----------------

PERTANYAAN:
{query}

JAWABAN:
"""


# =========================================================
# 5. Kirim context + pertanyaan ke Qwen
# =========================================================

response = requests.post(
    f"{OLLAMA_URL}/api/generate",
    json={
        "model": LLM_MODEL,
        "prompt": prompt,
        "stream": False
    }
)

response.raise_for_status()

answer = response.json()["response"]


# =========================================================
# 6. Tampilkan hasil
# =========================================================

print()
print("=" * 60)
print("PERTANYAAN")
print("=" * 60)
print(query)

print()
print("=" * 60)
print("CONTEXT DARI QDRANT")
print("=" * 60)
print(context)

print()
print("=" * 60)
print(f"JAWABAN {LLM_MODEL}")
print("=" * 60)
print(answer)