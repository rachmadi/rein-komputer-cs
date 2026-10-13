# ReIn Komputer — RAG & AI Sales Assistant

Sistem Chatbot Rekomendasi Komputer dan Laptop berbasis RAG (Retrieval-Augmented Generation) deterministik dan agentic tool execution.

## Konfigurasi Hardware & Variabel Lingkungan Ollama

Untuk menjaga latensi E2E tetap optimal pada kartu grafis dengan VRAM terbatas (misalnya NVIDIA RTX 3050 Laptop GPU 6GB), model LLM (`gemma4:e4b`) dan embedding (`bge-m3`) dioptimalkan dengan variabel lingkungan berikut:

```bash
# 1. Mengaktifkan Flash Attention untuk pemrosesan konteks dan inferensi efisien
OLLAMA_FLASH_ATTENTION=1

# 2. Mengaktifkan kuantisasi KV Cache ke 8-bit (memangkas pemakaian VRAM hingga 50%)
OLLAMA_KV_CACHE_TYPE=q8_0

# 3. Membatasi model yang dimuat secara bersamaan agar VRAM tidak terfragmentasi
OLLAMA_MAX_LOADED_MODELS=1

# 4. Membatasi paralelisme sesi lokal
OLLAMA_NUM_PARALLEL=1

# 5. Menjaga model tetap hangat di memori selama 5 menit
OLLAMA_KEEP_ALIVE=5m
```

## Spesifikasi Evaluasi Peruntukan (RAG Knowledge Base)

- **KB P03 (Video Editor 4K & 3D Pro):**
  - Syarat Mutlak (Hard Filter): `ram_gb >= 32`, `storage_ssd_gb >= 1000`, `cpu_tier >= 3`, `gpu_dedicated = 1`, `vram_gb >= 8`.
  - Pemetaan CPU: Ryzen 7 dan Core i7 dipetakan ke `cpu_tier = 3` (sesuai spesifikasi `migrate_derived_fields.py` dan database `catalog.db`).
  - Pemetaan Produk:
    - `Lenovo Legion Pro 5 16 (KB-L10)`: Lolos semua syarat (✅).
    - `ASUS TUF Gaming A15 (KB-L09)`: Hanya gagal di RAM (16GB < 32GB). CPU tier (tier 3) dan VRAM (8GB) lolos.
    - `ASUS Vivobook Pro 15 OLED (KB-L07)`: Gagal di RAM (16GB) dan VRAM (6GB < 8GB).
    - `Acer Nitro V 15 (KB-L06)`: Gagal di RAM (16GB), Storage (512GB), CPU tier (tier 2 < 3), dan VRAM (4GB < 8GB).
