# Laporan Insiden Live Test: Anomali Penawaran Intel NUC pada Sesi AI Lokal

**Tanggal Kejadian:** 13 Oktober 2026, 19:07 – 19:11 WIB  
**Lingkungan:** Live Telegram Bot (`telegram_bot.py`), Cabang `llm-parser`, Putaran 30  
**Penguji:** Rachmadi  
**Status:** Teridentifikasi Penuh, Siap Diperbaiki  

---

## 1. Ringkasan Insiden
Pada sesi uji coba interaktif melalui Telegram, pengguna mencari laptop untuk kebutuhan *AI lokal* dengan anggaran maksimal Rp15.000.000. Namun, bot secara aneh dan tidak relevan justru menawarkan **Intel NUC 11 Essential NUC11ATKC4** (mini PC desktop *barebone* prosesor Celeron tanpa RAM/SSD seharga Rp3.199.000). Ketika pengguna mengeluhkan mengapa ditawari Intel NUC, bot kembali memicu pemanggilan katalog yang tidak sinkron dan menyodorkan laptop kantor umum (ASUS Zenbook OLED dan MSI Modern 14) tanpa GPU yang memadai untuk AI.

---

## 2. Transkrip Percakapan dan Bukti Log

### Giliran 1 (19:07:39 WIB)
* **Pengguna:** `"Duitnya cuma 15 juta"`
* **Alat LLM:** `katalog({"budget_max": 15000000, "gpu_dedicated": true, "kategori": "laptop", "ram_min_gb": 16})` (dipanggil mandiri oleh LLM)
* **Produk Tampil:** `KB-L26` (HP Victus 15), `KB-L24` (Acer Nitro V 15)
* **Balasan Bot (Verbatim):**
  > *"Wah, kalau budgetnya maksimal 15 juta, Kakak masih ada dua pilihan bagus yang speknya oke buat AI dan coding. Ada HP Victus 15-fb0009AX seharga Rp10.299.000, ini bagus buat gaming dan editing. Atau, kalau mau yang lebih bertenaga, Acer Nitro V 15 ANV15-51 harganya Rp14.999.000, ini cocok banget buat gaming dan rendering 3D."*

---

### Giliran 2 (19:09:34 WIB) — Titik Awal Anomali
* **Pengguna:** `"Kan buat AI lokal?"`
* **Alat LLM:** `pengetahuan({"pertanyaan": "persyaratan hardware untuk AI lokal"})`
* **Intervensi Pengaman P30:**
  * Log Terminal: `2026-10-13 19:09:25,725 - agentic_tool_engine - INFO - Pengaman P30 Butir 2 terpicu: memanggil katalog otomatis {'kata_kunci': 'ai_ml, programming'}`
  * Argumen Eksekusi: `katalog({"kata_kunci": "ai_ml, programming"})` **(tanpa filter `kategori: "laptop"`)**
* **Produk Tampil yang Masuk Balasan:** `KB-D12` (Intel NUC 11 Essential NUC11ATKC4)
* **Balasan Bot (Verbatim):**
  > *"Kak, berdasarkan panduan untuk AI lokal, yang paling penting itu adalah GPU Nvidia karena dukungannya lebih baik untuk deep learning dan machine learning. Dari pilihan yang budget-nya di bawah 15 juta, Acer Nitro V 15 ANV15-51 dengan RTX 4060 8GB itu paling ideal. **Selain itu, kalau Kakak mau yang lebih kecil, ada Intel NUC 11 Essential NUC11ATKC4 seharga Rp3.199.000, tapi perlu diingat ini barebone dan harus beli RAM/SSD terpisah.**"*

---

### Giliran 3 (19:10:23 WIB)
* **Pengguna:** `"Waduh. Aku maunya laptop kan"`
* **Alat:** Tidak ada pemanggilan alat
* **Balasan Bot (Verbatim):**
  > *"Betul Kak, fokusnya memang laptop yang speknya mumpuni buat AI lokal. Dari budget 15 juta, dua pilihan terbaik yang ada GPU dedicated-nya adalah Acer Nitro V 15 ANV15-51 seharga Rp14.999.000 dengan RTX 4060 8GB. Atau, kalau mau yang lebih hemat tapi tetap oke, ada HP Victus 15-fb0009AX seharga Rp10.299.000."*

---

### Giliran 4 (19:11:17 WIB) — Anomali Lanjutan pada Komplain
* **Pengguna:** `"Kenapa juga ditawari intel NUC?"`
* **Alat LLM:** `pengetahuan({"pertanyaan": "perbedaan mini pc dan laptop untuk kebutuhan AI lokal"})`
* **Intervensi Pengaman P30:**
  * Log Terminal: `2026-10-13 19:11:08,663 - agentic_tool_engine - INFO - Pengaman P30 Butir 2 terpicu: memanggil katalog otomatis {'kata_kunci': 'office, daily'}`
* **Produk Tampil yang Masuk Balasan:** `KB-L22` (ASUS Zenbook 14 OLED UX3402ZA), `KB-L21` (MSI Modern 14 C12M)
* **Balasan Bot (Verbatim):**
  > *"Kak, saya minta maaf sekali lagi atas kebingungan tadi. Saya akan fokus hanya pada laptop ya. Untuk kebutuhan AI lokal dengan budget maksimal 15 juta, saya sarankan Kakak lihat Acer Nitro V 15 ANV15-51 seharga Rp14.999.000 karena sudah ada RTX 4060 8GB. Alternatif lain yang bagus adalah ASUS Zenbook 14 OLED UX3402ZA seharga Rp13.999.000, ini layarnya OLED bagus banget buat visual. Kalau mau yang lebih irit tapi masih oke, ada MSI Modern 14 C12M seharga Rp8.499.000 dengan RAM 16 GB."*

---

## 3. Analisis Akar Masalah (Root Cause Analysis)

### 1. Kehilangan Konteks Kategori pada Pengaman Otomatis (`session_state` Diabaikan)
Pada implementasi awal Putaran 30, pendeteksian kategori di pengaman kode (`services/agentic_tool_engine.py`) hanya memeriksa `user_text` pada giliran itu saja:
```python
u_tokens = [w for w in re.findall(r"\w+", user_text.lower())]
for tok in u_tokens:
    if tok in cat_synonyms_map:
        detected_cat = cat_synonyms_map[tok]
        break
```
Saat pengguna mengetik `"Kan buat AI lokal?"`, kata `"laptop"` tidak ada dalam kalimat tersebut. Pengaman tidak membaca `session_state.get("category")` atau `session_state.get("kategori")` dari giliran sebelumnya. Akibatnya, pemanggilan katalog otomatis dijalankan dengan `kategori = None`.

### 2. Inkonsistensi Kata Kunci Tag KB vs Database Produk
Di basis pengetahuan (`panduan_kebutuhan_v2.md`), profil P04 memiliki header:
`- **ID:** P04 | **Tag katalog:** ai_ml, programming | ...`
String `"ai_ml, programming"` diekstrak mentah-mentah dan dioper ke parameter `kata_kunci` fungsi `katalog`. Di database SQLite (`catalog.db`), tidak ada produk yang cocok dengan string `"ai_ml, programming"`, sehingga hasil pencarian adalah `total_cocok = 0`.

### 3. Logika Fallback Katalog Mengembalikan Produk Termurah Seluruh Toko
Ketika `total_cocok = 0` dan parameter `kategori` bernilai `None`, fungsi katalog mengeksekusi fallback bawaan: mengembalikan 10 produk termurah dari seluruh toko (`ORDER BY harga ASC LIMIT 10`). Daftar fallback tersebut berisi printer, monitor kasir, dan unit desktop barebone mini PC: **Intel NUC 11 Essential NUC11ATKC4** (Rp3.199.000).

### 4. Prompt Revisi Pengaman Terlalu Mengikat
Prompt revisi pengaman menginstruksikan:
> *"Revisi balasanmu sebelumnya dengan menyertakan rekomendasi produk nyata dari hasil katalog di atas (sebutkan nama produk, spesifikasi ringkas, dan harganya)."*
LLM yang patuh melihat ada produk komputer dalam daftar fallback (Intel NUC), lalu memaksakan produk tersebut masuk ke dalam jawaban dengan narasi *"kalau Kakak mau yang lebih kecil..."*, meskipun spesifikasinya (Celeron N5105 tanpa RAM/SSD) sama sekali tidak masuk akal untuk komputasi AI lokal.

### 5. Komplain Meta Pertanyaan Diperlakukan Sebagai Permintaan Rekomendasi
Pada Giliran 4, pertanyaan `"Kenapa juga ditawari intel NUC?"` adalah pertanyaan evaluasi/komplain. LLM memanggil `pengetahuan` untuk membandingkan form factor, dan pengaman otomatis kembali terpicu karena LLM tidak memanggil katalog. Akibatnya, pengaman memanggil katalog dengan tag `'office, daily'`, memaksa bot kembali merekomendasikan Zenbook dan MSI Modern yang tidak relevan.

---

## 4. Rencana Perbaikan Teknis

1. **Memori Kategori Multigiliran**:
   Pengaman wajib memeriksa `session_state.get("category")` atau `session_state.get("kategori")` jika `user_text` tidak memuat kata kunci kategori secara eksplisit. Kategori aktif tidak boleh hilang antar giliran.
2. **Sanitasi Kata Kunci Tag**:
   Jika kata kunci tag katalog komposit menghasilkan `0 cocok`, jangan lakukan fallback lintas kategori. Tetap kunci filter `kategori` sesuai sesi pelanggan.
3. **Penyaringan Relevansi pada Revisi LLM**:
   Instruksi revisi harus menegaskan: *"Sertakan produk dari katalog HANYA jika benar-benar memenuhi kategori dan spesifikasi yang dicari pelanggan. Jangan menawarkan produk di luar kategori yang dibahas atau yang spesifikasinya tidak memadai."*
4. **Pencegahan Pengaman pada Giliran Komplain / Klarifikasi**:
   Bila pesan pengguna terdeteksi sebagai pertanyaan alasan/komplain (misal pola `"kenapa..."`, `"kok..."`, `"mengapa..."`), pengaman katalog otomatis tidak boleh dipicu.
