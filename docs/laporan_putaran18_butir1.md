# Laporan Putaran 18 — Butir 1: Telusuri Agent Lama dan Uji Ulang Kemampuan Dasar

## 1. Penelusuran Mesin Agent Lama dari Riwayat Git
Berdasarkan riwayat git log repositori:
- **Periode Default**: `agentic_tool` (dan sebelumnya `dynamic_rag`) aktif sebagai default sejak commit `bbe8141` ("Implementasi lapisan percakapan Customer Care", 2026-10-08) dan snapshot awal `47d5a69` ("Pre-Phase 7 Refactor Snapshot", 2026-10-07) hingga digantikan ke `antigravity_v2` pada commit `ec9b037` ("feat(pipeline): default to antigravity_v2", 2026-10-09).
- **Prompt Sistem Saat Itu**:
```text
Anda asisten AI Bobby Computer.
TUGAS ANDA: Panggil tool `search_catalog` atau jawab sapaan.
JANGAN RAKIT ULANG HASIL TOOL KE DALAM TEKS!
Sistem akan melampirkan daftar produk secara otomatis.
Jika tool dipanggil, TULIS HANYA 1 KALIMAT PENGANTAR. (Misal: "Berikut rekomendasi yang cocok:")
JANGAN halusinasi harga/spek.
```
- **Definisi Alat Saat Itu (`TOOLS_DEFINITION`)**:
```json
[
  {
    "type": "function",
    "function": {
      "name": "search_catalog",
      "description": "Cari produk dari katalog Bobby Computer.",
      "parameters": {
        "type": "object",
        "properties": {
          "kategori": {"type": "string", "enum": ["laptop", "desktop", "printer", "monitor", "all"]},
          "kebutuhan": {"type": "string", "description": "HANYA isi dengan peruntukan/kegiatan. Contoh: 'edit video', 'gaming', 'kasir', 'anak sekolah'."},
          "query": {"type": "string", "description": "HANYA isi dengan nama merek, model, atau kata kunci eksplisit (misal: 'asus', '128gb', 'RTX')."},
          "profil_id": {"type": "string", "description": "Isi jika user meminta opsi 'lain' atau 'lebih murah'."},
          "min_harga": {"type": "integer"},
          "max_harga": {"type": "integer"}
        }
      }
    }
  }
]
```

## 2. Contoh Balasan Verbatim dari logs/chat_history.jsonl Periode Tersebut

### Contoh 1 (Sapaan/Klarifikasi Kebutuhan)
- **Timestamp**: `2026-10-07T00:01:23.972363`
- **Route**: `DIRECT_AGENT`
- **User Text**: `Cuma jual laptop?`
- **Bot Reply (Verbatim)**:
```text
Tidak sama sekali, Kak! Di Bobby Computer kami jual lengkap, mulai dari laptop, desktop PC, printer, sampai monitor juga tersedia.

Kakak lagi cari kebutuhan komputasi untuk apa nih? Biar saya bantu cek katalognya ya. 😊
```

### Contoh 2 (Pencarian Katalog Merek Tertentu)
- **Timestamp**: `2026-10-07T00:02:01.339191`
- **Route**: `TOOL_SEARCH_CATALOG`
- **User Text**: `Ada laptop acer?`
- **Bot Reply (Verbatim)**:
```text
Wah, Kak, di katalog kami ada beberapa pilihan laptop Acer nih.

Ada **Acer Aspire Lite 14** dengan harga Rp5.199.000, ini udah pakai Intel Processor N100, RAM 8 GB, dan layar 14 inci WUXGA IPS, cocok buat kebutuhan harian.

Kalau Kakak cari yang lebih bertenaga, ada **Acer Nitro V 15** seharga Rp12.999.000. Speknya udah pakai Intel Core i5-13420H, RAM 16 GB, dan yang paling oke, ada GPU NVIDIA GeForce RTX 2050 4 GB dengan layar 15,6 inci FHD 144 Hz.

Ada juga pilihan lain yang mungkin menarik, Kak. Kira-kira Kakak lebih tertarik untuk kebutuhan apa nih? Biar saya bantu filter yang paling pas ya. 😊
```

### Contoh 3 (Rekomendasi Persona/Kebutuhan Mahasiswa)
- **Timestamp**: `2026-10-07T00:02:49.308433`
- **Route**: `TOOL_SEARCH_CATALOG`
- **User Text**: `Aku mahasiswa komputer`
- **Bot Reply (Verbatim)**:
```text
Berikut rekomendasi produk dari katalog Bobby Computer yang sesuai kebutuhan Kakak:

• **ASUS Vivobook 14 A1405**: Rp8.799.000
  Spek: Intel Core i5-1235U, RAM 16 GB DDR4, Intel Iris Xe

• **HP 14s-fq1036AU**: Rp9.499.000
  Spek: AMD Ryzen 5 7530U, RAM 16 GB DDR4, AMD Radeon Graphics

• **Acer Nitro V 15**: Rp12.999.000
  Spek: Intel Core i5-13420H, RAM 16 GB DDR5, NVIDIA GeForce RTX 2050 4 GB

Ada tipe tertentu yang ingin Kakak tanyakan lebih detail?
```

### Contoh 4 (Diskusi Kebutuhan AI Lokal & GPU)
- **Timestamp**: `2026-10-07T00:04:28.796360`
- **Route**: `DIRECT_AGENT`
- **User Text**: `Tapi aku juga lagi eksplorasi LLM lokal`
- **Bot Reply (Verbatim)**:
```text
Wah, kalau sudah masuk ke eksplorasi LLM lokal, Kak, ini berarti kebutuhan komputasinya cukup tinggi, terutama di bagian GPU dan RAM.

Saya cek katalognya lagi ya, Kak, untuk kebutuhan LLM lokal, GPU yang kuat itu sangat membantu.

Saya sarankan kita lihat lagi **Acer Nitro V 15** yang speknya sudah dilengkapi **NVIDIA GeForce RTX 2050 4 GB** dengan harga Rp12.999.000. Keberadaan GPU NVIDIA ini sangat membantu proses *inference* model lokal.

Selain itu, pastikan RAM-nya minimal 16 GB seperti yang ada di beberapa rekomendasi tadi.

Apakah Kakak ingin saya cek apakah ada model lain dengan GPU yang lebih tinggi, atau apakah spesifikasi yang ada ini sudah cukup untuk eksplorasi awal LLM lokal, Kak?
```

### Contoh 5 (Evaluasi Komparasi Spesifikasi)
- **Timestamp**: `2026-10-07T00:06:16.547041`
- **Route**: `DIRECT_AGENT`
- **User Text**: `Yang ketiga gak punya gpu?`
- **Bot Reply (Verbatim)**:
```text
Betul Kak, yang ketiga, yaitu **HP 14s-fq1036AU**, memang tidak dilengkapi dengan kartu grafis khusus (dedicated GPU) seperti dua tipe sebelumnya.

Spek utamanya adalah menggunakan grafis terintegrasi dari prosesor AMD Ryzen 5 7530U. Jadi, performanya lebih fokus untuk tugas sehari-hari, *coding* ringan, atau pekerjaan yang tidak terlalu menuntut grafis berat.

Kalau Kakak memang fokus ke LLM lokal, GPU khusus seperti yang ada di dua tipe atas akan sangat membantu akselerasi modelnya, Kak.

Apakah Kakak ingin saya bandingkan lagi antara tipe yang ada GPU (Nitro V atau Vivobook Pro) dengan tipe yang lebih hemat daya tapi tanpa GPU khusus?
```

---

## 3. Hasil Uji Tool Calling gemma4:e4b via Ollama /api/chat
Pengujian tool calling via parameter `tools` pada `http://localhost:11434/api/chat`:

### Request Mentah:
```json
{
  "model": "gemma4:e4b",
  "messages": [
    {
      "role": "system",
      "content": "Kamu staf toko ReIn Komputer. Gunakan alat bila perlu mencari produk."
    },
    {
      "role": "user",
      "content": "Ada laptop acer budget 10 juta?"
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "cari_produk",
        "description": "Mencari produk di katalog komputer berdasarkan kata kunci, kategori, merek, dan budget.",
        "parameters": {
          "type": "object",
          "properties": {
            "kata_kunci": {
              "type": "string",
              "description": "Kata kunci pencarian atau model spesifik"
            },
            "kategori": {
              "type": "string",
              "description": "Kategori produk: laptop, desktop, printer, monitor"
            },
            "merek": {
              "type": "string",
              "description": "Merek produk"
            },
            "budget_max": {
              "type": "integer",
              "description": "Batas budget maksimal dalam rupiah"
            }
          }
        }
      }
    }
  ],
  "stream": false,
  "options": {
    "temperature": 0.1,
    "num_predict": 512
  }
}
```

### Response Mentah (HTTP 200):
```json
{
  "role": "assistant",
  "content": "",
  "thinking": "The user is asking for an Acer laptop with a budget of 10 million IDR. I should use the `cari_produk` tool to search for this specific product.\n\n1.  **Tool:** `cari_produk`\n2.  **Parameters:**\n    *   `kategori`: \"laptop\"\n    *   `merek`: \"Acer\"\n    *   `budget_max`: 10,000,000 (10 juta)\n\nI will call the tool with these parameters.",
  "tool_calls": [
    {
      "id": "call_u50492cl",
      "function": {
        "index": 0,
        "name": "cari_produk",
        "arguments": {
          "budget_max": 10000000,
          "kategori": "laptop",
          "merek": "Acer"
        }
      }
    }
  ]
}
```

---

## 4. Hasil Uji num_ctx 8192 & Status VRAM (`ollama ps`)
Uji parameter `num_ctx: 8192` pada `gemma4:e4b`:
Output dari `ollama ps`:
```text
NAME          ID              SIZE      PROCESSOR    CONTEXT    RUNNER      UNTIL              
gemma4:e4b    c6eb396dbd59    3.2 GB    100% GPU     8192       llamacpp    4 minutes from now
```
**Temuan**:
Model berukuran 3.2 GB dan tetap **100% di GPU** pada context window 8192 (tidak ada offload ke CPU pada VRAM 6 GB).
Sehingga `num_ctx: 8192` aman digunakan untuk mesin agent baru dengan parameter:
- `num_ctx: 8192`
- `num_predict: 1024`
- `timeout: 120` detik.
