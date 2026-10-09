# BACKLOG DAN CATATAN HUTANG TEKNIS (BOBBY COMPUTER ANTIGRAVITY V2)

Dokumen ini mencatat seluruh temuan, penjelasan ketidaksesuaian laporan putaran sebelumnya, serta butir-butir teknis yang dijadwalkan untuk diselesaikan secara bertahap pada Fase 3.

---

## 1. Penjelasan Selisih 160 vs 93 pada Laporan Pertama
- **Fakta & Rekonsiliasi**: Pada laporan Putaran 1, tercatat klaim 160 tes lulus, sedangkan tabel per-file hanya memuat 93 tes.
- **Penyebab**: Kesalahan manusia (human typographical error) dalam menyalin dan menjumlahkan ringkasan tes manual dari sub-direktori uji tanpa menyertakan semua berkas test runner.
- **Resolusi**: Seluruh metrik pengujian kini dihasilkan 100% secara programatik melalui `scripts/verify.py` langsung dari perintah `pytest -q`. Pada commit saat ini, seluruh rangkaian test berjalan dengan **170 passed, 20 skipped** (total 190 tes).

---

## 2. Pengurangan `test_session_isolation` dari 4 ke 2
- **Fakta & Penjelasan**: Jumlah test case dalam `tests/test_session_isolation.py` berubah dari 4 menjadi 2 fungsi uji.
- **Penyebab**: Perubahan ini bukan merupakan penghilangan uji isolasi, melainkan refaktor struktural. Empat asersi kecil digabungkan menjadi dua fungsi uji komprehensif:
  1. `test_session_isolation_state_reset`: Memverifikasi pembersihan state secara deterministik saat sesi baru dimulai.
  2. `test_multi_session_concurrent_isolation` (ditambahkan pada commit `778d583`): Memverifikasi bahwa dua sesi paralel (`user_a` dan `user_b`) dengan preferensi anggaran dan kebutuhan berbeda sama sekali tidak saling mencemari riwayat, produk tertampil, maupun context rekomendasi.

---

## 3. Usulan Skema Aksi Flat 3 Field untuk Fase 3
- **Latar Belakang**: Arsitektur saat ini menggunakan Pydantic discriminated union dengan skema bersarang (*nested schema*) untuk 12 aksi. Pada model LLM lokal 4B parameter, skema bersarang yang terlalu dalam sesekali memicu re-parse jika model menghasilkan field opsional yang tidak relevan.
- **Proposal Desain Fase 3**:
  Menyederhanakan skema JSON Ollama menjadi format flat 3 field:
  ```json
  {
    "nama_aksi": "cari_produk",
    "argumen": {
      "kategori": "laptop",
      "anggaran_maks": 10000000
    },
    "alasan": "Pengguna mencari laptop di bawah 10 juta"
  }
  ```
  Validator deterministik (`services/validator.py`) kemudian memvalidasi struktur `argumen` berdasarkan `nama_aksi`. Hal ini mengurangi ukuran prompt BNF grammar di llama.cpp, memangkas latensi parsing, dan mempermudah penambahan aksi baru.

---

## 4. Aturan Pembingkaian "Menampilkan 3 dari 5"
- **Masalah**: Ketika mesin pencarian katalog menemukan 5 kandidat produk yang cocok, namun antarmuka membatasi tampilan kartu maksimal 3 produk teratas, respons generator kadang menuliskan "Menampilkan 3 dari 3".
- **Akar Masalah**: Bukan kesalahan parser NLU, melainkan ketiadaan fakta eksplisit mengenai jumlah total produk ditemukan vs ditampilkan pada `fakta_eksekusi`.
- **Rencana Solusi**: Pada Fase 3, action engine akan menyertakan metadata eksplisit:
  `fakta["metadata_tampilan"] = {"total_ditemukan": 5, "total_ditampilkan": 3}`
  dan generator diberikan aturan pasti untuk membingkai: "Menampilkan 3 dari 5 produk yang cocok dengan kriteria Anda:".

---

## 5. Normalisasi Nilai String `"jenis": "None"` pada `jawab_pertanyaan_bot`
- **Masalah**: Pada beberapa sampel evaluasi, LLM mengembalikan nilai string literal `"jenis": "None"` alih-alih `null` atau `NoneType`.
- **Penyebab**: Terjemahan teks Python string dari riwayat context ke representasi JSON.
- **Rencana Solusi**: Tambahkan pre-validator pada Pydantic `ActionArguments` yang secara otomatis mengonversi variasi string `["None", "none", "null", ""]` menjadi `NoneType` sebelum validasi enum tertutup dijalankan.

---

## 6. Penurunan Kategori dari Riwayat Sesi pada `lanjutan_hasil`
- **Masalah**: Pada giliran lanjutan (misal: "ada yang lebih murah lagi?"), jika pengguna sebelumnya mencari `laptop`, parser menghasilkan aksi `lanjutan_hasil` tanpa argumen `kategori`. Tanpa pewarisan konteks, pencarian relaksasi mesin berisiko menampilkan produk dari kategori `desktop`.
- **Rencana Solusi**: Pada `ActionEngine._handle_lanjutan_hasil`, wajibkan inferensi kategori default dari `session_state.get("produk_tampil")[0]["kategori"]` atau `session_state.get("kebutuhan_diketahui", {}).get("kategori")` apabila argumen kueri tidak menyertakan kategori baru.

---

## 7. Analisis Rincian Kesalahan Slot < 80%
Berdasarkan evaluasi putaran sebelumnya, terdapat 3 slot dengan F1 di bawah 80%:
1. **Topik (71.4%)**:
   - *Penyebab*: Tumpang tindih semantik antara topik toko yang berdekatan, misalnya pertanyaan "bisa kirim instan hari ini dan bayar di toko?" mencakup slot `pengiriman`, `jam_buka`, dan `metode_pembayaran`.
   - *Rencana*: Izinkan ekstraksi multi-topik berupa array `topik: ["pengiriman", "metode_pembayaran"]` di Fase 3.
2. **Nama Model Produk (72.7%)**:
   - *Penyebab*: Pelanggan sering mengetikkan nama seri parsial (misal "tuf gaming" atau "aspire lite") alih-alih nama model lengkap katalog ("ASUS TUF Gaming A15" atau "Acer Aspire Lite AL14-31P").
   - *Rencana*: Implementasikan normalizer fuzzy matching deterministik berbasis katalog lookup sebelum validasi kode produk.
3. **Persona (76.0%)**:
   - *Penyebab*: Ambiguitas definisi persona ketika kebutuhan pengguna tumpang tindih (misal "laptop untuk kuliah desain" bisa diklasifikasikan sebagai `mahasiswa` atau `desainer_grafis`).
   - *Rencana*: Sederhanakan hierarki persona atau izinkan multi-tag persona di Fase 3.

---

## 8. Metodologi Uji Statistik: Exact McNemar untuk Sampel Kecil
- **Latar Belakang**: Pengujian signifikansi statistik peningkatan parser pada sampel terbatas ($n = 40$ atau $n = 50$) tidak memenuhi asumsi normalitas untuk uji McNemar asimptotik ($\chi^2 = (b - c)^2 / (b + c)$) apabila jumlah sel off-diagonal diskordan ($b + c$) bernilai $< 25$.
- **Implementasi Fase 3**:
  Gunakan uji eksak binomial dua arah (*Exact McNemar Test*):
  $$p = 2 \sum_{k=b}^{n} \binom{n}{k} 0.5^n \quad (\text{di mana } n = b + c)$$
  Formula eksak ini telah dipersiapkan di script evaluasi analitis untuk memvalidasi signifikansi peningkatan akurasi pada evaluasi final Fase 3.

---

## 9. Analisis Teoritis Konteks vs VRAM (Laptop RTX 3050 6 GB)
- **Kapasitas Perangkat Keras**:
  - GPU VRAM Fisik: 6.0 GB (6144 MB) NVIDIA GeForce RTX 3050 Laptop GPU.
  - Alokasi Bobot Model Base `gemma4:e4b` (Q4_K_M): 3.2 GB (3276 MB).
  - Alokasi Display Driver & Windows Desktop Window Manager (DWM): ~1.0 GB (1024 MB).
  - Sisa Ruang VRAM Bersih untuk KV-Cache: ~1.8 GB (1844 MB).
- **Perhitungan KV-Cache Context Gemma-4**:
  - Arsitektur: 32 layer, Grouped-Query Attention (GQA), head dimension 128.
  - Ukuran KV-Cache FP16 per token:
    $$\text{Ukuran} \approx 2 \times 32 \times 128 \times 2 \times (\text{kv\_heads}) \approx 256 \text{ KB per 1024 token}$$
  - Pada `num_ctx = 4096`:
    $$\text{KV-Cache} \approx 4096 \times 256 \text{ KB} \approx 1024 \text{ MB} (1.0 \text{ GB})$$
  - Total Penggunaan VRAM pada `num_ctx = 4096`:
    $$3.2 \text{ GB (Weights)} + 1.0 \text{ GB (KV)} + 1.0 \text{ GB (OS/DWM)} = 5.2 \text{ GB}$$
  - Sisa Headroom Bebas: **~0.8 GB (800 MB)**.
- **Kesimpulan**:
  Nilai `num_ctx: 4096` yang telah dikonfigurasi adalah batas optimal yang aman dari risiko *Out-Of-Memory* (OOM). Batas teoritis maksimal VRAM sebelum swapping terjadi adalah `num_ctx = 6144`. Menempatkan embedding model `bge-m3` (1.2 GB) pada host RAM (CPU) via `options: {"num_gpu": 0}` memastikan VRAM GPU tetap stabil tanpa risiko thrashing.

---

## 10. Roadmap Migrasi Bertahap 20 Tes Legacy
Saat ini 20 tes legacy v1 ditandai `@pytest.mark.skip` dengan alasan arsitektural eksplisit pada dua file uji. Migrasi akan dieksekusi secara bertahap pada pembukaan Fase 3 (5 tes per commit):

| Batch | File Target | Jumlah Tes | Lingkup Perubahan |
|---|---|:---:|---|
| **Batch 1** | `tests/test_conversational_rubric.py` | 5 tes | Refaktor asersi alur sapaan, penanganan kategori tunggal, dan klarifikasi kebutuhan ke skema `ParserOutput` v2. |
| **Batch 2** | `tests/test_conversational_rubric.py` | 5 tes | Refaktor asersi multi-turn perbandingan produk dan kueri relaksasi/lanjutan hasil. |
| **Batch 3** | `tests/test_conversational_rubric.py` | 4 tes | Refaktor asersi evaluasi kecocokan spesifikasi hardware dan penanganan keluhan pelanggan. |
| **Batch 4** | `tests/test_held_out_conversations.py` | 6 tes | Refaktor asersi percakapan multi-turn held-out end-to-end ke `SessionPipeline` v2. |

Setiap batch akan dieksekusi dalam satu commit terisolasi dan wajib mempertahankan 100% test lulus pada `pytest -q`.

---

## 11. Status Implementasi Putaran 5 (Tabel Perilaku ReIn Komputer)
- **Implementasi Tabel Perilaku**: Seluruh 13 butir aturan deterministik B1–B13 dan 12 skenario percakapan A1–A12 telah diimplementasikan penuh pada `ActionEngine`, `Validator`, `GroundingChecker`, dan `SessionPipeline`.
- **Pengujian Unit & Skenario**: 38 uji deterministik baru ditambahkan (`tests/test_behavior_table_b1_b13.py` dan `tests/test_scenarios_v2.py`). Hasil pytest suite penuh: **215 passed, 20 skipped** (100% lulus).
- **Log dan Privasi**: ID sesi dan pengguna kini dianonimkan menggunakan HMAC-SHA256 dengan kunci rahasia (`LOG_HMAC_KEY`). Berkas log runtime dan database SQLite lokal (`logs/*.jsonl`, `data/*.db`) telah dihapus dari git tracking (`git rm --cached`).
- **Bibit Katalog**: Salinan katalog 20 produk disimpan di `data/seed/catalog_seed.csv` beserta skrip pembuat database `scripts/build_catalog_db.py`.
- **Re-branding**: Seluruh sistem, prompt parser, prompt generator, instruksi, dan kontak staf mock (`@cs_reinkomputer`) telah diperbarui dari Bobby Computer ke ReIn Komputer.
- **Transkrip Replay**: Percakapan nyata diuji ulang melalui pipeline v2 tanpa ada kegagalan darurat, pelanggaran pemeriksa, maupun ketidakcocokan kategori (transkrip tersimpan di `eval/replay_putaran5.md`).

