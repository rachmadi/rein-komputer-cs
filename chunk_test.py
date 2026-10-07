import fitz
import re

pdf_path = "data/Katalog_Komputer_RAG.pdf"

# Buka PDF
doc = fitz.open(pdf_path)

# Ekstrak seluruh teks
text = ""

for page in doc:
    text += page.get_text() + "\n"


# Ambil bagian detail produk saja
marker = "Detail Produk dan Product Knowledge"

detail_text = text.split(marker, 1)[1]

# Jangan ikutkan bagian Kebijakan Knowledge Base
detail_text = detail_text.split("Kebijakan Knowledge Base", 1)[0]


# Pisahkan berdasarkan kode produk
# Contoh: KB-L01, KB-L02, KB-D01, KB-M01, dst.
pattern = r"(?=KB-[A-Z]\d+\s+[—-])"

chunks = re.split(pattern, detail_text)

# Buang bagian kosong
chunks = [
    chunk.strip()
    for chunk in chunks
    if chunk.strip()
]


# Tampilkan hasil
print("Jumlah chunk produk:", len(chunks))

for i, chunk in enumerate(chunks, 1):
    print()
    print(f"========== CHUNK {i} ==========")
    print(chunk)