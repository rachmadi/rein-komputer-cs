# Laporan Pengujian dan Eksekusi Putaran 13b — ReIn Komputer

- **Waktu Penyelesaian**: 2026-10-10 21:40 WIB
- **Cabang Git**: `llm-parser`
- **Baseline Tag**: `sebelum-putaran13b` (`30a7e3d`)
- **Model**: `gemma4:e4b` (Ollama, tidak diubah)
- **Status Test Suite Penuh**: 317 passed, 20 skipped, 0 failed (Total: 337 items)

---

## 1. Rincian Perubahan per Butir & Commit

### BUTIR 1 — Pencegahan Kebocoran Teks Internal ke Pelanggan
- **Commit**: `c4f4927` (`putaran13b-butir1-cegah-kebocoran-teks-internal`)
- **Penelusuran Jalur Kebocoran (Tracing)**:
  Pada giliran 56 replay `gemma_p13`, LLM generator mengalami kegagalan validasi GroundingChecker setelah retry dan mengalihkan respon ke `build_deterministic_fallback_text` di `services/llm_generator.py`. Pada fungsi tersebut, teks kekurangan produk diambil langsung dari `fakta["produk_terdekat"]["kekurangan"]` yang bersumber dari string mentah evaluasi `catalog_search.apply_filters` (misalnya `"storage_ssd_gb >= 1000 (got 512)"`, `"ram_gb >= 16 (got 8)"`, `"cpu_tier >= 3 (got 1)"`) tanpa melalui konversi format alami.
- **Perbaikan di Sumber**:
  1. Menambahkan fungsi `format_natural_unmet_list` pada `services/catalog_search.py` yang menerjemahkan string operator dan atribut teknis ke bahasa Indonesia percakapan yang ramah pengguna (mis. `"RAM 8 GB (butuh 16 GB)"`, `"SSD 512 GB (butuh 1 TB)"`, `"VRAM 4 GB (butuh 8 GB)"`, `"prosesor tingkat 1 (butuh tingkat 3)"`), dengan penanganan batas kata (*word boundary*) regex yang ketat untuk membedakan `ram` dan `vram`.
  2. Menggunakan `format_natural_unmet_list` pada pembentukan fakta kekurangan di `services/action_engine.py` (baris 624 dan 667) serta pada fallback deterministik di `services/llm_generator.py`.
- **Jaring Pengaman Output (Safety Net Filter)**:
  Menambahkan inspeksi keluaran akhir di `services/session_pipeline.py` sebelum balasan diserahkan kepada pengguna. Jika teks balasan terdeteksi memuat pola `["(got ", ">=", "<=", "cpu_tier", "ram_gb", "storage_ssd_gb", "vram_gb", "gpu_dedicated"]`, teks secara deterministik disanitasi dan diganti dengan penjelasan spesifikasi yang bersih, serta insiden dicatat di log percakapan.
- **Tes Baru**:
  - `test_butir1_format_natural_unmet_list`
  - `test_butir1_deterministic_fallback_tanpa_kebocoran`
  - `test_butir1_jaring_pengaman_output_filter`
  - `test_butir1_skenario_budget_15jt_ai_lokal_bebas_pola`
- **Diff Stat Butir 1** (`30a7e3d..c4f4927`):
  ```text
   services/action_engine.py          | 13 ++++--
   services/catalog_search.py         | 55 ++++++++++++++++--------
   services/grounding_checker.py      |  7 ++-
   services/llm_generator.py          | 10 ++++-
   services/session_pipeline.py       | 11 +++++
   tests/test_putaran13b_synthetic.py | 88 ++++++++++++++++++++++++++++++++++++++
   6 files changed, 160 insertions(+), 24 deletions(-)
  ```

---

### BUTIR 2 — Budget Sebagai Filter Keras
- **Commit**: `84b5991` (`putaran13b-butir2-budget-filter-keras`)
- **Penelusuran Masalah**:
  Pada giliran 50–53 replay `gemma_p13`, pengguna mendiskusikan laptop kelas atas (`KB-L09` ASUS TUF Rp16.999.000 dan `KB-L10` Legion Pro 5 Rp23.999.000). Saat giliran 54 pengguna menetapkan batas budget Rp15 juta, `_handle_minta_rekomendasi` awalnya mengembalikan `produk_list = []` karena tidak ada laptop <= 15 juta yang memenuhi 100% spesifikasi AI lokal. Akibat `produk_list` kosong, `state["produk_tampil"]` tidak diperbarui dan tetap menyimpan unit Rp16.999.000 dan Rp23.999.000. Generator LLM kemudian melihat produk tersebut di state dan menawarkannya sebagai opsi "mendekati budget".
- **Perbaikan yang Diterapkan**:
  1. **Filter Keras di Action Engine (`services/action_engine.py`)**:
     - Bila pengguna menetapkan budget, produk dengan harga melebihi angka tersebut tidak diizinkan masuk ke kandidat rekomendasi.
     - Bila tidak ada produk dalam budget yang memenuhi seluruh syarat: sistem memilih kandidat dalam budget yang paling mendekati (mis. Acer Nitro V 15 Rp12.999.000 dan Lenovo LOQ 15 Rp14.799.000) dengan label jujur `catatan_minimum = {"memenuhi": False, "alasan": ...}`, dan mengembalikannya dalam `produk_list` serta `fakta["produk"]`.
     - Bila benar-benar tidak ada produk di dalam budget, mengembalikan status `"tidak_ada_dalam_anggaran"` dengan menyertakan `harga_termurah_kategori` untuk menanyakan apakah pengguna bersedia menaikkan budget, tanpa pernah menawarkan unit di luar budget.
  2. **Pembersihan State & Kartu di Session Pipeline (`services/session_pipeline.py`)**:
     - Saat budget aktif, menyaring `state["produk_tampil"]`, `action_res.produk_list`, dan kartu HTML sehingga unit dengan harga > budget langsung dibuang dari memori sesi.
  3. **Penegakan di Generator & Grounding Checker (`services/llm_generator.py`, `services/grounding_checker.py`)**:
     - Menyaring data produk yang dikirim ke prompt LLM agar hanya menyertakan unit dalam budget.
     - Menambahkan aturan prompt ke-10 yang melarang menawarkan atau menyebut produk berharga di atas budget.
     - Memperbarui `GroundingChecker` agar menolak dan meminta revisi jika balasan bot menyebutkan nominal harga di atas budget pengguna.
- **Tes Baru & Penguatan**:
  - `test_butir2_action_engine_minta_rekomendasi_budget_15jt`
  - `test_butir2_session_pipeline_budget_15jt_tidak_menampilkan_di_atas_15jt`
  - `test_butir2_budget_rendah_tidak_ada_dalam_anggaran`
  - Memperkuat assertion harga pada `test_budget_dan_kebutuhan_menjalankan_rekomendasi` di `tests/test_putaran13_synthetic.py`.
- **Diff Stat Butir 2** (`c4f4927..84b5991`):
  ```text
   services/action_engine.py          | 71 ++++++++++++++++++++++++++-----------
   services/grounding_checker.py      | 14 ++++++++
   services/llm_generator.py          | 20 +++++++++++
   services/session_pipeline.py       | 19 ++++++++++
   tests/test_putaran13_synthetic.py  |  3 ++
   tests/test_putaran13b_synthetic.py | 72 ++++++++++++++++++++++++++++++++++++++
   6 files changed, 178 insertions(+), 21 deletions(-)
  ```

---

## 2. Bukti Pengujian Unit & Integrasi Penuh (Pytest)

Eksekusi penuh terhadap seluruh direktori `tests/`:
```text
============================= test session starts =============================
platform win32 -- Python 3.13.15, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\RAG
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.15.1
collected 337 items

tests\test_acceptance_v1_2.py .......................................    [ 11%]
tests\test_action_engine.py ............                                 [ 15%]
tests\test_admin_vram.py .                                               [ 15%]
tests\test_anti_hallucination.py .                                       [ 15%]
tests\test_audit_feedback.py ...                                         [ 16%]
tests\test_behavior_table_b1_b13.py ................                     [ 21%]
tests\test_c12_intro.py .                                                [ 21%]
tests\test_catalog_service.py .                                          [ 21%]
tests\test_chat_logger.py .....                                          [ 23%]
tests\test_conversational_rubric.py sss.sssssss                          [ 26%]
tests\test_e2e_golden.py ..                                              [ 27%]
tests\test_evaluasi_kecocokan_numbers.py ..                              [ 27%]
tests\test_factual_consistency.py ........                               [ 30%]
tests\test_fast_path_context.py .                                        [ 30%]
tests\test_fast_path_guard.py .                                          [ 30%]
tests\test_gold_lock.py .                                                [ 31%]
tests\test_golden_operator.py .                                          [ 31%]
tests\test_held_out_conversations.py .....sss.ssssss                     [ 35%]
tests\test_integrasi_putaran7.py ...............                         [ 40%]
tests\test_integrasi_putaran8.py ...........                             [ 43%]
tests\test_integrasi_putaran9.py ...................                     [ 49%]
tests\test_intent_router.py .                                            [ 49%]
tests\test_kebutuhan_gabungan.py ...                                     [ 50%]
tests\test_null_row.py .                                                 [ 50%]
tests\test_ood_retention.py .                                            [ 51%]
tests\test_operators.py ..                                               [ 51%]
tests\test_parser.py ....                                                [ 52%]
tests\test_parser_putaran10.py .                                         [ 52%]
tests\test_pending_question_answers.py .....                             [ 54%]
tests\test_persona_salutation.py ....                                    [ 55%]
tests\test_putaran10_synthetic.py .......                                [ 57%]
tests\test_putaran11_synthetic.py ................                       [ 62%]
tests\test_putaran12_synthetic.py ......                                 [ 64%]
tests\test_putaran13_synthetic.py ..........                             [ 67%]
tests\test_putaran13b_synthetic.py .......                               [ 69%]
tests\test_real_catalog.py ............                                  [ 72%]
tests\test_real_conversations.py ......................................  [ 83%]
tests\test_regression_baseline.py .                                      [ 84%]
tests\test_scenarios_v2.py ..............................                [ 93%]
tests\test_schema_validator.py ...............                           [ 97%]
tests\test_screen_flow_5_turns.py s                                      [ 97%]
tests\test_session_isolation.py ..                                       [ 98%]
tests\test_turn2_failures.py .                                           [ 98%]
tests\test_vram_admin.py ...                                             [ 99%]
tests\test_vram_guard.py .                                               [100%]

=========== 317 passed, 20 skipped, 7 warnings in 322.45s (0:05:22) ===========
```
- **Lulus (Passed)**: 317
- **Dilewati (Skipped)**: 20 (tetap persis 20)
- **Gagal (Failed)**: 0

---

## 3. Bukti Perbandingan Replay Gemma (`gemma_p13` vs `gemma_p13b`)

Perintah eksekusi replay:
```bash
.\.venv\Scripts\python.exe scratch\replay_model.py gemma_p13b gemma4:e4b
```

### Ringkasan Replay `gemma_p13b`:
```json
{
  "model": "gemma4:e4b",
  "mode_riwayat": "asli (konteks sama dengan sesi nyata)",
  "giliran": 63,
  "error": 0,
  "aksi_sama_dengan_asli": 47,
  "median_latensi_s": 11.2,
  "maks_latensi_s": 19.4
}
```

---

### Bukti Giliran 54–56 (Sebelum vs Sesudah)

#### Giliran 54
- **Input Pelanggan**: `"Kalau bisa, budget maksimal 15 juta ya"`
- **Sebelum (`gemma_p13`)**:
  - *Produk tampil*: `['KB-L09', 'KB-L10']`
  - *Balasan*:
    > "Terima kasih Kak sudah menginformasikan batas budgetnya ya. Dengan budget maksimal Rp15 juta, sayangnya dari beberapa pilihan yang kami lihat sebelumnya, belum ada yang benar-benar memenuhi semua kebutuhan Kakak untuk bikin model bisnis pakai AI lokal. Tapi, kalau Kakak berkenan, kami ada dua pilihan yang harganya mendekati atau sedikit di bawah budget tersebut, yaitu **ASUS TUF Gaming A15 seharga Rp16.999.000** dan Acer Nitro V 15 seharga Rp12.999.000. Kira-kira Kakak mau lihat detail salah satunya? Atau mungkin ada hal lain yang bisa kami bantu cek?"
- **Sesudah (`gemma_p13b`)**:
  - *Produk tampil*: `['KB-L06', 'KB-L07', 'KB-L08']` (Acer Nitro V 15 Rp12.999.000, Lenovo LOQ 15 Rp14.799.000, HP Victus 15 Rp11.999.000 — **seluruhnya $\le$ 15 juta**)
  - *Balasan*:
    > "Saat ini belum ada produk dalam budget tersebut yang memenuhi seluruh spesifikasi minimum yang dibutuhkan, Kak. Pilihan dalam budget yang paling mendekati adalah Acer Nitro V 15 (SSD 512 GB (butuh 1000 GB), prosesor tingkat 2 (butuh tingkat 3), VRAM 4 GB (butuh 8 GB))."
  - *Evaluasi*: Unit di atas Rp15 juta langsung disaring keluar. Tidak ada lagi penawaran ASUS TUF Rp16.999.000.

#### Giliran 55
- **Input Pelanggan**: `"Loh...malah ditawari yang murah. Katanya tadi nawarin yang spek tinggi biar bisa AI lokal. SEkarang malah spek rendah"`
- **Sebelum (`gemma_p13`)**:
  - *Produk tampil*: `['KB-L09', 'KB-L10']`
  - *Balasan*:
    > "Mohon maaf Kak, kalau tadi yang ditampilkan kurang sesuai ekspektasi Kakak ya. Untuk kebutuhan membuat model bisnis pakai AI lokal, memang perlu spesifikasi yang cukup tinggi. Berdasarkan kebutuhan Kakak, kami ada dua pilihan laptop yang speknya lebih mendekati kebutuhan tersebut, yaitu **ASUS TUF Gaming A15 seharga Rp16.999.000**, dan **Lenovo Legion Pro 5 16 seharga Rp23.999.000**. Kira-kira Kakak mau lihat detail dari kedua unit ini dulu?"
- **Sesudah (`gemma_p13b`)**:
  - *Produk tampil*: `['KB-L06', 'KB-L07', 'KB-L08']`
  - *Balasan*:
    > "Mohon maaf Kak, saya paham betul kalau Kakak sedang mencari laptop yang paling optimal untuk kebutuhan bikin model bisnis pakai AI lokal. Ini memang kebutuhan yang cukup spesifik dan menuntut performa tinggi, terutama di bagian GPU dan RAM."
  - *Evaluasi*: Bot tidak lagi mengulang menawarkan produk Rp16.999.000 maupun Rp23.999.000 yang melanggar batas budget pengguna.

#### Giliran 56
- **Input Pelanggan**: `"Tadi, kamu nawarin 3 pilihan yang bisa AI lokal. Yang paling murah kan masih di bawah 15 juta?"`
- **Sebelum (`gemma_p13`)**:
  - *Balasan*:
    > "Saat ini belum ada produk yang memenuhi seluruh spesifikasi minimum yang dibutuhkan, Kak. Pilihan terdekat kami adalah Acer Aspire Lite 14 **(ram_gb >= 16 (got 8), storage_ssd_gb >= 1000 (got 512), cpu_tier >= 3 (got 1), gpu_dedicated = 1 (got 0), vram_gb >= 8 (got 0))**."
- **Sesudah (`gemma_p13b`)**:
  - *Balasan*:
    > "Mohon maaf Kak, untuk kebutuhan menjalankan model bisnis AI lokal, saat ini belum ada produk di bawah budget Rp15.000.000 yang bisa memenuhi semua spesifikasi minimum yang dibutuhkan. Namun, yang paling mendekati dan masih dalam kisaran harga itu adalah Acer Aspire Lite 14 seharga Rp5.199.000. Perlu Kakak tahu bahwa unit ini masih memiliki beberapa kekurangan, seperti RAM 8 GB dan SSD 512 GB, dibandingkan kebutuhan minimumnya. Kira-kira Kakak mau lihat detail kekurangan dari unit ini atau apakah Kakak bersedia mempertimbangkan menaikkan budgetnya?"
  - *Evaluasi*: **Bersih total dari kebocoran teks internal**. String seperti `(got 8)`, `>= 16`, `cpu_tier >= 3` berhasil dieliminasi dan digantikan penjelasan percakapan yang jujur dan ramah.

---

### Bukti Giliran 61–63 (Sebelum vs Sesudah)

#### Giliran 61
- **Input Pelanggan**: `"Kenapa juga balik lagi ke spek paling rendah?"`
- **Sebelum (`gemma_p13`)**:
  - *Produk tampil*: `['KB-L09']`
  - *Balasan*:
    > "Mohon maaf Kak, kalau tadi terasa seperti kembali ke spek yang kurang memadai. Tujuan saya tadi adalah memastikan bahwa untuk kebutuhan AI lokal yang berat, memang dibutuhkan kartu grafis khusus yang lebih mumpuni. Kalau Kakak melihat ke unit **ASUS TUF Gaming A15** yang tadi tampil, unit ini sudah dilengkapi dengan NVIDIA GeForce RTX 4060 8 GB, yang seharusnya jauh lebih optimal untuk pengembangan AI dibandingkan yang sebelumnya..."
- **Sesudah (`gemma_p13b`)**:
  - *Produk tampil*: `['KB-L06', 'KB-L07', 'KB-L08']`
  - *Balasan*:
    > "Mohon maaf Kak, kalau tadi penjelasan saya terasa berputar-putar dan kembali ke spek yang kurang memuaskan. Saya paham betul Kakak butuh informasi yang lebih fokus dan akurat untuk kebutuhan penelitian AI lokal. Untuk menjelaskan detail kemampuan RTX 2050 pada Acer Nitro V 15, secara umum, kartu grafis ini memang dirancang untuk mendukung tugas komputasi yang membutuhkan akselerasi GPU, seperti yang dibutuhkan dalam menjalankan model AI lokal. Namun, perlu saya sampaikan juga bahwa unit ini memiliki beberapa batasan dibandingkan kebutuhan ideal Kakak, misalnya VRAM-nya 4 GB dan SSD-nya 512 GB."
  - *Evaluasi*: Bot konsisten fokus membahas Acer Nitro V 15 (dalam budget Rp15 juta) dan tidak melarikan percakapan ke ASUS TUF Gaming di luar budget.

#### Giliran 62
- **Input Pelanggan**: `"Kan kamu tadi menawarkan penjelasan lebih detail tentang kemampuan kartu grafisnya?"`
- **Sebelum (`gemma_p13`)**:
  - *Produk tampil*: `['KB-L09']`
  - *Balasan*:
    > "...Sebagai perbandingan, unit seperti **ASUS TUF Gaming A15** yang tadi saya tampilkan itu sudah dilengkapi NVIDIA GeForce RTX 4060 dengan VRAM 8 GB, ini jauh lebih mendukung untuk pengembangan AI dibandingkan grafis terintegrasi. Apakah Kakak ingin saya jelaskan lebih lanjut mengenai kemampuan RTX 4060 untuk keperluan penelitian Kakak?"
- **Sesudah (`gemma_p13b`)**:
  - *Produk tampil*: `['KB-L06', 'KB-L07', 'KB-L08']`
  - *Balasan*:
    > "Betul Kak, tadi memang saya sempat menyebutkan spesifikasi tanpa penjelasan lengkap. Maaf ya kalau bikin Kakak merasa kurang mendapatkan penjelasan yang diharapkan. Jadi begini, kemampuan kartu grafis seperti NVIDIA GeForce RTX 2050 4 GB pada Acer Nitro V 15 itu memang dirancang untuk membantu komputasi yang lebih berat, termasuk untuk keperluan AI lokal seperti yang Kakak tekankan. Secara umum, GPU dengan arsitektur seperti itu akan mempercepat proses training atau inferensi model AI dibandingkan hanya mengandalkan grafis bawaan prosesor."
  - *Evaluasi*: Bot menjawab langsung mengenai kemampuan kartu grafis RTX 2050 pada Acer Nitro V 15 yang relevan dengan pertanyaan pelanggan dan batas budget.

#### Giliran 63
- **Input Pelanggan**: `"Bukannya kita mau bahas Nitro?"`
- **Sebelum (`gemma_p13`)**:
  - *Produk tampil*: `['KB-L09']`
  - *Balasan*:
    > "Betul Kak, kita memang sedang membahas laptop yang lebih tangguh untuk kebutuhan AI lokal, jadi fokus kita memang ke tipe seperti Nitro atau yang setara ya. Untuk kebutuhan AI lokal yang Kakak sebutkan, **saya sarankan kita lihat unit yang memang sudah dilengkapi kartu grafis khusus (dedicated GPU) seperti ASUS TUF Gaming A15**. Unit ini punya NVIDIA GeForce RTX 4060 8 GB..."
- **Sesudah (`gemma_p13b`)**:
  - *Produk tampil*: `['KB-L06', 'KB-L07', 'KB-L08']`
  - *Balasan*:
    > "Betul Kak, kita memang harus kembali membahas unit yang lebih mumpuni untuk kebutuhan AI lokal, jadi fokus kita memang ke seri Nitro yang tadi. Untuk Acer Nitro V 15 yang speknya NVIDIA GeForce RTX 2050 4 GB, secara umum kartu grafis ini memang dirancang untuk memberikan performa yang lebih baik dibanding grafis terintegrasi. Untuk kebutuhan AI lokal, kemampuan RTX 2050 ini bisa membantu proses komputasi yang lebih berat, namun perlu diingat ya Kak, untuk performa optimal di AI, biasanya dibutuhkan VRAM yang lebih besar."
  - *Evaluasi*: Bot tetap konsisten membahas Acer Nitro V 15, membedah kemampuan grafisnya secara objektif, dan tidak pernah mengalihkan pengguna ke ASUS TUF Gaming di luar budget.
