# Instruksi untuk Antigravity: Menambahkan Fitur RAG "Kecocokan Spek vs Kebutuhan" pada Chatbot Bobby Computer

Dokumen ini adalah spesifikasi tugas untuk agen coding. Baca seluruhnya sebelum menulis kode. Bekerja per fase, dan **berhenti untuk meminta persetujuan setelah Fase 0** (berikan rencana implementasi terlebih dahulu).

---

## 1. Tujuan

Chatbot saat ini hanya menjawab pertanyaan harga dan katalog lewat *Agentic Tool Calling* (tool `search_catalog` + SQLite). Tambahkan kemampuan menjawab pertanyaan **kecocokan spesifikasi dengan peruntukan** ("laptop buat edit video 4K", "PC untuk kasir toko", "laptop buat mama nonton YouTube") dengan RAG, sehingga:

1. Pengetahuan spesifikasi **hanya** bersumber dari basis pengetahuan (KB) di Qdrant.
2. Produk yang direkomendasikan **hanya** berasal dari katalog SQLite.
3. LLM (gemma4:e4b, model kecil) tidak diminta menalar spesifikasi dari nol atau menyalin angka secara manual. Mesin yang menerapkan filter secara deterministik.

## 2. Konteks Sistem yang Sudah Ada (jangan dirusak)

Rujuk `arsitektur_sistem_bobby_computer.md` di repo. Ringkasnya:

- Backend FastAPI (`app/main.py`), endpoint `/api/chat` dipakai Telegram (`telegram_bot.py`) dan Flutter web.
- `services/chat_service.py`: SessionManager (history 8 pesan terakhir, `category`, `offered_products`).
- `services/agentic_tool_engine.py`: alur 2 putaran dengan tool `search_catalog` dan fungsi `execute_tool()` (deteksi kategori terawal, sticky category, tag matching, price proximity scoring, safe empty return `[]`). Aktif saat `CHAT_ENGINE_MODE=agentic_tool`.
- `services/dynamic_rag_engine.py`: mode RAG alternatif yang sudah ada. **Periksa isinya dan gunakan ulang kode embedding/Qdrant yang sudah ada jika layak**, jangan menulis ulang tanpa alasan.
- `services/catalog_service.py`, `core/catalog.py`: CRUD dan sinkronisasi katalog. Database: `data/catalog.db`, tabel `products`.
- Lingkungan: Windows, venv di `d:\RAG\.venv`. LLM via Ollama (`gemma4:e4b`), embedding `bge-m3` (1024 dimensi), Qdrant, collection `computer_knowledge`, jarak cosine. Konfigurasi di `.env`.

**Perilaku yang harus tetap berfungsi (regresi):** Ghost Reply (`tool_call_id` pada `role: "tool"`), lintas kategori (hasil kosong `[]`, bukan produk acak), spam foto pada keluhan (phrase matching), konteks harga (Price Anchor), dan pembatasan 2 foto per respons.

### Skema tabel `products` (sudah ada)
`kode, nama, kategori, brand, harga_idr, cpu, cpu_vendor, ram, ram_gb, ram_type, storage, gpu, display, os, is_accessory, usage_text, image_url, raw_data, created_at, updated_at`

Kolom turunan baru (ditambahkan oleh `migrate_derived_fields.py` di Fase 1): `cpu_tier, storage_ssd_gb, has_hdd, gpu_dedicated, gpu_class, vram_gb, screen_inch, refresh_hz, panel, srgb_pct, tags`.

## 3. Berkas Input yang Disediakan

Salin ke repo (minta konfirmasi jika path sudah dipakai):

| Berkas | Lokasi tujuan | Fungsi |
|---|---|---|
| `Panduan_Kebutuhan_vs_Komponen_Komputer_v2.md` | `data/knowledge/panduan_kebutuhan_v2.md` | Sumber KB (22 chunk: 4 panduan umum G01–G04, 16 profil P01–P16, 2 kategori M01–M02) |
| `migrate_derived_fields.py` | `scripts/migrate_derived_fields.py` | Menambah dan mengisi kolom turunan |

**Jangan mengubah isi KB.** Jika menemukan kesalahan atau ketidakkonsistenan, laporkan ke pengguna, jangan diperbaiki diam-diam.

Format KB: dokumen dipecah per heading `## `. Setiap blok punya ID (`G01`, `P06`, `M01`), baris metadata (`ID`, `Tag katalog`, `Perangkat`, `Kata kunci pelanggan`), tabel Minimum/Direkomendasikan, dan baris `**Filter minimum:**` berformat mis. `ram_gb ≥ 16; storage_ssd_gb ≥ 512; cpu_tier ≥ 2; gpu_dedicated = 1; vram_gb ≥ 8`. Komentar HTML `<!-- ... -->` di bagian atas **tidak boleh di-embed**.

## 4. Desain Target (ikuti, kecuali ada alasan kuat; jelaskan di rencana)

```
Pelanggan: "laptop buat ngoding Flutter, budget 12 juta"
  Putaran 1: LLM -> get_usage_requirements(kebutuhan="ngoding Flutter")
             engine: embed -> Qdrant -> profil P06 -> {profil_id:"P06", ringkasan, catatan}
  Putaran 2: LLM -> search_catalog(kategori="laptop", profil_id="P06", max_harga=12000000)
             engine: ambil filter P06 dari payload (BUKAN dari LLM) -> SQL berparameter -> hasil + match_report
  Putaran 3: LLM merangkum produk dari hasil tool
```

Prinsip kunci: **LLM hanya mengirim `profil_id` dan budget; angka filter dibaca engine dari payload Qdrant.** Ini mengurangi kesalahan transkripsi oleh model kecil.

Konsekuensi: alur "2 putaran" harus menjadi **loop tool-calling dengan batas maksimum 3 iterasi** (mendukung tool berantai maupun beberapa tool call dalam satu respons). Pertahankan format pesan `role: "tool"` dengan `tool_call_id` yang benar di setiap iterasi dan pertahankan fallback deterministik jika teks akhir kosong.

---

## 5. Fase Pekerjaan

### Fase 0: Eksplorasi (hanya baca, belum ubah kode)
1. Baca semua berkas pada bagian 2, `.env`, `requirements.txt`, dan skrip lama yang memakai Qdrant/Ollama (mis. `chatbot.py`).
2. Periksa isi collection `computer_knowledge` yang sekarang (jumlah titik, dimensi, jarak). Collection ini kemungkinan berisi data uji lama.
3. Lihat skema dan 5 contoh baris `products` dari `data/catalog.db`. Cek apakah tag (`office`, `daily`, `gaming`, `rendering_3d`) tersimpan di `raw_data`, `usage_text`, atau kode.
4. Tulis **rencana implementasi**: berkas yang akan dibuat/diubah, keputusan desain, risiko, dan pertanyaan terbuka. **Tunggu persetujuan pengguna.**

### Fase 1: Kolom turunan di database
1. **Backup** `data/catalog.db` ke `data/catalog.db.bak-<tanggal>` sebelum perubahan apa pun.
2. Jalankan `scripts/migrate_derived_fields.py data/catalog.db --dry-run`, tinjau hasilnya, lalu jalankan sungguhan.
3. Integrasikan logika turunan ke `catalog_service.py` (CRUD dan sync) agar produk baru atau yang diedit otomatis menghitung ulang kolom turunan. Hindari duplikasi kode: impor fungsi dari satu modul bersama.
4. Buat laporan singkat: jumlah produk per kolom yang bernilai NULL (terutama `vram_gb`, `cpu_tier`, `tags`) dan daftar kode produk yang terdampak. **Jangan menebak VRAM dari nama GPU.** VRAM laptop dan desktop berbeda untuk nama GPU yang sama.

### Fase 2: Ingestion KB ke Qdrant (`scripts/ingest_knowledge.py`)
1. Parser: pecah per `## `, buang komentar HTML di awal dan pemisah `---`. Hasilkan chunk dengan field: `id`, `judul`, `tipe` (`profil` untuk P*, `panduan_umum` untuk G*, `panduan_kategori` untuk M*), `tag_katalog` (list), `perangkat`, `kata_kunci` (list), `text` (isi chunk penuh termasuk heading), dan `filter` (lihat butir 3).
2. Teks yang di-embed: heading + seluruh isi blok (agar kata kunci pelanggan ikut terwakili).
3. Parser baris `**Filter minimum:**` menjadi daftar kendala terstruktur, mis. `{"field":"ram_gb","op":">=","value":16,"strength":"hard"}`.
   - Operator yang dikenali: `≥` (>=), `=`.
   - Frasa "tidak disyaratkan" berarti tidak ada kendala untuk field itu.
   - "(disarankan)" berarti `strength: "soft"`.
   - Catatan seperti "(Nvidia, cek kolom gpu)" disimpan sebagai `hint` (`gpu_vendor_hint: "nvidia"`, soft); jangan dijadikan kendala keras.
   - Whitelist field yang valid: `ram_gb, storage_ssd_gb, cpu_tier, gpu_dedicated, vram_gb, panel, srgb_pct, refresh_hz, screen_inch`. Field di luar daftar harus memunculkan error saat ingestion.
4. Embedding via Ollama (`bge-m3`) mengikuti cara yang sudah dipakai di repo. Titik Qdrant memakai **ID deterministik** (`uuid5` dari `id` chunk) sehingga ingestion idempoten.
5. Opsi CLI: `--recreate` (drop dan buat ulang collection). **Tanpa `--recreate`, skrip menolak menimpa collection yang berisi data non-KB**, dan harus memberi tahu pengguna terlebih dahulu sebelum menghapus collection `computer_knowledge` yang lama.
6. Validasi akhir: harus ada tepat **22 titik** (4 G, 16 P, 2 M), vektor berdimensi 1024, dan setiap P* punya minimal 1 kendala hard. Cetak ringkasan. Jika tidak sesuai, skrip gagal dengan pesan jelas.

### Fase 3: Layanan pengetahuan (`services/knowledge_service.py`)
- `retrieve(kebutuhan: str, top_k: int = 2, tipe: list[str] | None = None)` mengembalikan daftar `{id, judul, score, tipe, filter, tag_katalog, catatan_ringkas}`.
- Default `tipe=["profil"]`. Chunk panduan umum (G*) dan kategori (M*) hanya diambil jika pertanyaan bersifat edukasi ("apa bedanya SSD dan HDD?", "printer tinta atau laser?", "monitor buat desain") atau saat tool diminta eksplisit.
- Ambang skor (`RAG_SCORE_THRESHOLD`) dikalibrasi memakai set uji di Fase 7 dan dibuat bisa diatur lewat `.env`. Jika semua hasil di bawah ambang, kembalikan daftar kosong dengan `alasan: "tidak_ada_profil_cocok"` agar LLM mengajukan pertanyaan klarifikasi (lihat G04 pada KB).
- Cache payload profil di memori (ID menjadi filter) supaya `search_catalog` bisa mengambil filter berdasarkan `profil_id` tanpa embedding ulang. Pembacaan ulang dari Qdrant boleh dilakukan jika cache kosong.
- Qdrant atau Ollama tidak tersedia berarti kembalikan hasil kosong dengan `alasan: "layanan_pengetahuan_error"` dan catat log. **Jangan crash dan jangan mengarang profil.**

### Fase 4: Tool baru `get_usage_requirements` (`agentic_tool_engine.py`)
- Definisi tool: parameter `kebutuhan` (string, wajib; tuliskan peruntukan pelanggan dengan kata-katanya sendiri).
- Mengembalikan JSON ringkas untuk LLM, misalnya `{"profil":[{"profil_id":"P06","nama":"Programmer dan Software Developer","ringkasan":"...","catatan":"..."}], "alasan": null}`. Sertakan hanya ringkasan teks (Minimum/Direkomendasikan/Catatan) dan ID; tidak perlu seluruh payload.
- Maksimal 2 profil dikembalikan, diurutkan skor.

### Fase 5: Perluas `search_catalog` / `execute_tool`
1. Tambah parameter opsional: `profil_id`, `min_harga`, `max_harga`, `kategori`. Pertahankan parameter dan perilaku lama (`query`, deteksi kategori terawal, sticky category, price anchor).
2. Jika `profil_id` diberikan: ambil kendala dari payload profil, lalu bangun klausa `WHERE` **berparameter** (tanpa string interpolation). Whitelist nama kolom. Kolom `is_accessory = 0` untuk perangkat utama.
3. **Penanganan NULL:** nilai NULL pada kolom yang disyaratkan berarti *tidak diketahui*. Produk tetap boleh muncul tetapi ditandai (mis. `vram_tidak_diketahui: true`) dan diberi peringkat lebih rendah dibanding yang terverifikasi memenuhi syarat.
4. Setiap produk dalam hasil membawa `match_report`: daftar kendala yang terpenuhi, tidak terpenuhi, atau tidak diketahui. Hanya produk dengan semua kendala hard terpenuhi (atau tidak diketahui) yang dikembalikan sebagai rekomendasi utama.
5. **Tangga pelonggaran** bila hasil kosong, dari yang paling aman: abaikan kendala soft, lalu kembalikan kandidat terdekat dengan label `belum_memenuhi_minimum` beserta alasan. **Jangan melonggarkan budget atau kendala hard diam-diam**; sertakan `dilonggarkan: [...]` di hasil sehingga LLM bisa mengatakannya dengan jujur. Jika benar-benar tidak ada produk, kembalikan `[]` (perilaku "Safe Empty Returns" tetap).
6. Validasi argumen dari LLM (tipe, rentang, ID profil harus ada) sebelum eksekusi; argumen tidak valid mengembalikan pesan error terstruktur, bukan exception.
7. Skor peringkat: kombinasikan kecocokan kendala, kedekatan harga dengan budget, dan tag, tanpa menghilangkan scoring lama. Dokumentasikan bobotnya di kode.

### Fase 6: Prompt sistem, sesi, dan alur loop
1. Ubah alur menjadi loop tool-calling (maks 3 iterasi) seperti pada bagian 4. Pertahankan fallback deterministik jika LLM menghasilkan teks kosong.
2. Tambahkan aturan pada prompt sistem (bahasa Indonesia):
   - Pertanyaan **kecocokan/peruntukan** ("cocok buat…", "laptop untuk…") memanggil `get_usage_requirements` terlebih dahulu, lalu `search_catalog` dengan `profil_id`.
   - Pertanyaan harga atau produk spesifik ("harga Acer Nitro V 15") memakai `search_catalog` langsung, tanpa RAG.
   - **Hanya** merekomendasikan produk yang muncul pada hasil tool. Jangan mengarang produk, harga, atau spesifikasi.
   - Jelaskan alasan rekomendasi dalam 1 sampai 2 kalimat berdasarkan ringkasan profil. Jika ada produk yang `belum_memenuhi_minimum`, atau VRAM/komponen tidak diketahui, katakan terus terang.
   - Jangan menampilkan istilah internal kepada pelanggan (ID profil, `cpu_tier`, nama kolom).
   - Jika tidak ada profil yang cocok, ajukan **satu** pertanyaan klarifikasi (kebutuhan, aplikasi/game, atau budget).
   - Gaya tetap ramah dan berorientasi penjualan seperti sebelumnya.
3. Simpan `active_profile_id` di SessionManager sehingga pertanyaan lanjutan ("yang lebih murah dong", "yang ada SSD 1TB?") tetap memakai profil yang sama tanpa retrieval ulang. Reset bila pelanggan berganti topik.
4. Jangan mengubah logika foto Telegram.

### Fase 7: Pengujian
Buat `tests/` (pytest) dengan DB katalog dummy dan, bila memungkinkan, Qdrant/embedding yang dapat dijalankan lokal.

**a. Unit test parser ingestion:** 22 chunk; `P06` menghasilkan kendala `ram_gb >= 16`, `storage_ssd_gb >= 512`, `cpu_tier >= 2`, dan tidak ada kendala GPU; `P03` menghasilkan `gpu_dedicated = 1` dan `vram_gb >= 8`; komentar HTML tidak ikut di-embed; field di luar whitelist memunculkan error.

**b. Uji retrieval (top-1 harus sesuai):**

| Kalimat pelanggan | Harus mengembalikan |
|---|---|
| laptop buat kuliah yang murah | P01 |
| laptop buat mama nonton YouTube dan video call | P11 |
| laptop buat edit foto Photoshop dan CorelDraw | P02 |
| edit video 4K dan render Blender | P03 |
| PC buat main Valorant dan Dota 2 | P04 |
| mau main Cyberpunk setting ultra | P05 |
| laptop buat ngoding Flutter, Docker, emulator Android | P06 |
| laptop buat arsitek, AutoCAD dan SketchUp | P07 |
| mau live streaming pakai OBS | P08 |
| buat bikin musik pakai FL Studio | P09 |
| buat trading saham pakai 4 monitor | P10 |
| mau jalanin Ollama dan LLM lokal | P13 |
| Excel berat, pivot, Power BI | P14 |
| komputer buat kasir di toko | P15 |
| CapCut buat konten TikTok | P12 |
| laptop buat kerja tapi sesekali main game | P16 |
| bedanya inkjet tangki tinta sama laser? | M02 |
| monitor yang bagus buat desain | M01 |
| "halo, apa kabar?" | tidak ada profil (di bawah ambang) |

Target: akurasi top-1 ≥ 90% pada daftar ini. Jika tidak tercapai, laporkan kegagalan per kalimat beserta skor, lalu usulkan perbaikan (mis. kata kunci tambahan pada KB atau menyesuaikan ambang). **Jangan menyesuaikan tes agar lolos.**

**c. Uji filter katalog:** produk tanpa VRAM tidak lolos diam-diam sebagai "terverifikasi"; budget tidak dilonggarkan diam-diam; kategori tidak tertukar; hasil kosong tetap `[]`.

**d. Regresi:** keempat kasus pada bagian 4 dokumen arsitektur (Ghost Reply, lintas kategori, spam foto, konteks harga) tetap lolos.

**e. Uji end-to-end manual (jalankan dan laporkan hasilnya)** untuk minimal 5 percakapan melalui `/api/chat`, termasuk satu pertanyaan lanjutan dan satu kasus produk tidak tersedia.

### Fase 8: Konfigurasi dan dokumentasi
- Tambahkan ke `.env` dan `.env.example`: `QDRANT_URL`, `QDRANT_COLLECTION=computer_knowledge`, `EMBED_MODEL=bge-m3`, `RAG_TOP_K=2`, `RAG_SCORE_THRESHOLD`, `KNOWLEDGE_FILE=data/knowledge/panduan_kebutuhan_v2.md`. Sesuaikan nama variabel dengan yang sudah ada di repo.
- Perbarui `requirements.txt` hanya jika perlu (mis. `qdrant-client`).
- Perbarui `arsitektur_sistem_bobby_computer.md`: tambahkan komponen Knowledge Service, tool `get_usage_requirements`, diagram sekuens baru (loop tool-calling), perintah menjalankan migrasi dan ingestion, dan revisi bagian 6.2 (Qdrant kini dipakai aktif untuk pengetahuan kebutuhan, bukan sekadar *future-proofing*; SQLite tetap untuk filter produk).
- Tulis `README` singkat untuk cara memperbarui KB: edit file KB, jalankan ulang `ingest_knowledge.py`.

## 6. Aturan Kerja

- Perubahan **inkremental dan terkontrol versi**; satu commit per fase dengan pesan jelas. Jangan mengubah file di luar cakupan tanpa alasan.
- Jangan menghapus data (database atau collection Qdrant) tanpa backup dan konfirmasi pengguna.
- Semua query SQL berparameter. Nama kolom dari whitelist.
- Jangan menambahkan dependensi berat tanpa alasan. Utamakan yang sudah ada di repo.
- Ikuti gaya kode, penamaan, dan logging yang sudah ada. Komentar dan pesan pengguna dalam bahasa Indonesia, identifier kode mengikuti konvensi repo.
- Bila ada hal yang ambigu atau bertentangan dengan dokumen ini, **tanyakan kepada pengguna**; jangan berasumsi diam-diam.
- Di akhir tiap fase, laporkan: apa yang dikerjakan, cara memverifikasi, hasil tes, dan masalah yang tersisa.

## 7. Definisi Selesai

1. Pertanyaan peruntukan menghasilkan rekomendasi produk dari katalog yang konsisten dengan profil KB, dengan alasan singkat dan jujur soal data yang tidak diketahui.
2. Tidak ada produk, harga, atau spesifikasi yang muncul di jawaban selain dari hasil tool.
3. Tes pada Fase 7 lolos (retrieval top-1 ≥ 90%) dan regresi tidak ada.
4. Ingestion idempoten dan mudah diulang; dokumentasi diperbarui.
5. Telegram dan Flutter web tetap bekerja tanpa perubahan pada kontrak `/api/chat`.
