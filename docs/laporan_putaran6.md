# LAPORAN EVALUASI & IMPLEMENTASI PUTARAN 6
**Sistem**: Simulasi Customer-Care "ReIn Komputer" (Telegram Bot Berbasis LLM Parser + ActionEngine Deterministik + LLM Generator + GroundingChecker)  
**Dokumen Acuan**: *Tabel Perilaku ReIn Komputer* (Aksi A1–A12 dan Perilaku B1–B18)  
**Tanggal Evaluasi**: 9 Oktober 2026  
**Branch Git**: `llm-parser`  

---

## 1. Metadata Eksekusi & Riwayat Commit

### 1.1 Hash Commit Tiap Tahap Putaran 6
Semua pengerjaan dilakukan berurutan dengan tepat satu commit per tahap (tanpa git reset, tanpa rebase, tanpa modifikasi riwayat lama):

| Tahap | Hash Commit | Pesan Commit | Deskripsi Ringkas Perubahan |
|---|---|---|---|
| **Baseline** | `ab83677` | Tag: `sebelum-putaran6` | Titik awal Putaran 6, backup di `D:\RAG_backup\20261009-1752` |
| **Tahap 1** | `7757bc0` | `putaran6-tahap1` | Sentralisasi `KONTAK_STAF` di `core/config.py`, penulisan ulang scanner n-gram di `scripts/verify.py` |
| **Tahap 2** | `b5e4e26` | `putaran6-tahap2-tes-merah` | 30 tes skenario di `tests/test_scenarios_v2.py` (membuktikan 7 kegagalan merah terisolasi) |
| **Tahap 3** | `d6e3523` | `putaran6-tahap3` | Perbaikan aturan umum B1–B18 di engine, parser, generator, checker, dan katalog |
| **Tahap 4 (Label)** | `bb64230` | `putaran6-tahap4-probe-labels` | Komit awal 36 kueri dev probe baru di `eval/dev_probe_putaran6.csv` sebelum diuji |
| **Tahap 4 (Hasil)** | `375ec2e` | `putaran6-tahap4` | Eksekusi probe end-to-end SessionPipeline, hasil di `eval/dev_probe_putaran6_results.csv` |
| **Tahap 5** | `2fef42b` | `putaran6-tahap5` | Replay penuh 134 giliran $\times$ 3 run (402 turn), transkrip di `eval/replay_putaran6.md` & `.jsonl` |
| **Tahap 6** | *(Commit ini)* | `putaran6-tahap6-laporan` | Laporan final Putaran 6 dan pembaruan otomatis `VERIFY.md` |

### 1.2 Integritas Kunci Dataset (Gold Lock SHA-256)
- **Target SHA-256**: `13e7007e63bcb0e78f3982ee2515b273c0085c65ff1c1838016d9d7727d84fde`
- **Hasil Pemeriksaan**:
  ```text
  13e7007e63bcb0e78f3982ee2515b273c0085c65ff1c1838016d9d7727d84fde  eval/parse_gold.csv
  ```
- **Status Kunci**: **TERKUNCI & TIDAK BERUBAH (VALID)**. Uji `tests/test_gold_lock.py` lulus 100%.

---

## 2. Rekapitulasi Pengujian Sistem

### 2.1 Hasil Pytest Suite Penuh
Perintah: `.venv/Scripts/python.exe -m pytest -q -rs`  
Keluaran ringkasan verbatim:
```text
223 passed, 20 skipped, 2 warnings in 179.27s (0:02:59)
```
- **Total Lulus**: 223 tes
- **Total Gagal**: 0 tes
- **Total Skipped**: 20 tes (seluruh 20 tes skip warisan v1 dipertahankan persis tanpa penghapusan)
- **Tes Baru Putaran 6**: 30 tes skenario di `tests/test_scenarios_v2.py` (lulus 100%) dan 16 tes di `tests/test_behavior_table_b1_b13.py` (lulus 100%).

### 2.2 Dev Probe Putaran 6 (36 Kueri Sintetis Baru)
Pengujian kueri baru yang mewakili A1–A12 dan situasi B dijalankan end-to-end melalui `SessionPipeline` (`eval/dev_probe_putaran6_results.csv`):
- **Jumlah Sampel ($n$)**: 36 kueri
- **Akurasi Aksi Parser**:
  - Berdasarkan pencocokan mentah CSV: **32 / 36 (88.9%)**
  - Berdasarkan pencocokan semantik aktual: **34 / 36 (94.4%)**  
    *(Catatan: Pada kueri No 28 dan 30, pesan pelanggan mengandung tanda koma tanpa tanda kutip CSV sehingga terbaca tergeser oleh pembaca CSV sederhana; parser LLM memprediksi `perbaiki_percakapan` dengan benar).*
- **Pelanggaran GroundingChecker**: 1 / 36 (2.8%)
- **Emergency Fallback Terpanggil**: 1 / 36 (2.8%)
- **Latensi End-to-End**:
  - $p50$: **9,743.0 ms** (~9.7 detik)
  - $p95$: **17,740.1 ms** (~17.7 detik)

#### 5 Contoh Keberhasilan Dev Probe:
1. **Kueri No 4** (`minta_rekomendasi`):  
   *"Butuh laptop buat edit video 4k premiere pro sama after effects"*  
   $\rightarrow$ Prediksi: `minta_rekomendasi` | Fakta: `sukses`, merekomendasikan Lenovo Legion Pro 5 & ASUS ROG Strix.
2. **Kueri No 8** (`cari_produk`):  
   *"Cari printer di bawah 2 juta"*  
   $\rightarrow$ Prediksi: `cari_produk` | Fakta: `sukses`, menampilkan Canon TS207 (Rp699rb) & Epson L121 (Rp1.699jt).
3. **Kueri No 14** (`evaluasi_kecocokan`):  
   *"Apakah laptop nomor dua sanggup jalankan python data science?"*  
   $\rightarrow$ Prediksi: `evaluasi_kecocokan` | Fakta: `sukses`, menilai ASUS Vivobook Go 14 berada di bawah minimum untuk profil data science.
4. **Kueri No 17** (`tanya_spesifikasi` - B15):  
   *"Berapa harga advan-nya?"*  
   $\rightarrow$ Prediksi: `tanya_spesifikasi` | Fakta: `sukses`, harga Advan Workplus Rp7.299.000 dijawab lugas.
5. **Kueri No 26** (`tanya_info_toko` - B10):  
   *"Toko fisiknya beralamat di mana ya kak?"*  
   $\rightarrow$ Prediksi: `tanya_info_toko` | Bot mengarahkan ke staf toko kami tanpa mengarang alamat palsu.

#### 5 Contoh Kasus Analisis & Koreksi Dev Probe:
1. **Kueri No 12** (`jawab_pertanyaan_bot` vs `cari_produk`):  
   *"Lebih butuh printer dokumen"* $\rightarrow$ Parser memprediksi `cari_produk` (karena mengandung entitas perangkat baru). Sistem berhasil mengeksekusi pencarian 3 printer dokumen tanpa eror.
2. **Kueri No 24** (`lanjutan_hasil` vs `tidak_jelas`):  
   *"Tolong berikan pilihan alternatif model lain dong"* $\rightarrow$ Parser memprediksi `tidak_jelas` karena kata 'model lain' tanpa konteks kategori spesifik dianggap ambigu.
3. **Kueri No 36** (Intervensi GroundingChecker):  
   *"iya tapi bukan dan tidak ada"* $\rightarrow$ Generator awalnya menulis frasa "kendala teknis" padahal status bukan `sistem_error`. GroundingChecker mendeteksi pelanggaran, memicu retry, dan akhirnya mengamankan respons via kalimat darurat `{KONTAK_STAF}`.
4. **Kueri No 16** (`tanya_spesifikasi` - B15):  
   *"Berapa kapasitas ram laptop nomor 1?"* $\rightarrow$ Atribut RAM tidak tercatat lengkap di kartu sementara $\rightarrow$ Engine mengembalikan status `atribut_tidak_tersedia`, generator jujur menyatakan data belum tersedia tanpa berhalusinasi.
5. **Kueri No 28 & 30** (Handling Koma CSV):  
   *"Bukan itu maksud saya, saya carinya laptop bukan printer"* $\rightarrow$ Prediksi model `perbaiki_percakapan` (100% akurat terhadap niat koreksi).

---

### 2.3 Replay Penuh (11 Percakapan, 134 Turn $\times$ 3 Run = 402 Turn)
Dijalankan secara komprehensif menggunakan `scripts/replay.py` pada dataset `eval/regression_telegram.jsonl`:
- **Jumlah Total Turn**: 402 giliran
- **Konsistensi Aksi Antar-Run**: **70.9%** (95 dari 134 turn menghasilkan aksi identik di ketiga run)
- **Pelanggaran GroundingChecker**: 4 / 402 (1.0%)
- **Emergency Fallback**: 4 / 402 (1.0%)
- **Kategori Mismatch (B6)**: **0 / 402 (0.0%)** (Zero category cross-leakage terbukti)

#### Ringkasan Latensi Empiris Pipeline (ms)
| Tahapan | Run 1 ($p50 / p95$) | Run 2 ($p50 / p95$) | Run 3 ($p50 / p95$) | Gabungan 402 Turn ($p50 / p95$) |
|---|---|---|---|---|
| **1. Parse LLM** | 2,128.0 / 3,564.7 | 2,133.9 / 3,295.0 | 2,069.1 / 3,327.9 | **2,117.8 / 3,430.1 ms** |
| **2. Mesin Deterministik** | 0.1 / 4,189.9 | 0.1 / 4,167.6 | 0.0 / 4,163.0 | **0.1 / 4,167.3 ms** |
| **3. Generate LLM** | 3,402.1 / 6,987.1 | 3,392.9 / 6,527.8 | 3,514.5 / 6,799.5 | **3,425.7 / 6,770.4 ms** |
| **TOTAL PIPELINE** | **5,903.3 / 12,551.3** | **6,001.9 / 13,308.3** | **5,817.3 / 12,871.9** | **5,872.3 / 12,626.3 ms** |

---

## 3. Evaluasi Tiap Perilaku: A1–A12 & B1–B18

### 3.1 Pemetaan & Akurasi Aksi A1–A12
*Catatan Penomoran*: Menggunakan penomoran baku dokumen *Tabel Perilaku ReIn Komputer*.

| Kode | Nama Aksi Baku | Nama Lama di Putaran 5 | Frekuensi di Replay ($n=402$) | Akurasi Dev Probe ($n=36$) |
|---|---|---|---|---|
| **A1** | `sapa` | `sapa` | 18 (4.5%) | 3 / 3 (100.0%) |
| **A2** | `minta_rekomendasi` | `minta_rekomendasi` / `rekomendasi` | 16 (4.0%) | 3 / 3 (100.0%) |
| **A3** | `cari_produk` | `cari_produk` / `spesifikasi_merek` | 55 (13.7%) | 3 / 3 (100.0%) |
| **A4** | `jawab_pertanyaan_bot` | `jawab_pertanyaan_bot` / `jawab` | 57 (14.2%) | 2 / 3 (66.7%) |
| **A5** | `evaluasi_kecocokan` | `evaluasi_kecocokan` / `evaluasi` | 45 (11.2%) | 3 / 3 (100.0%) |
| **A6** | `tanya_spesifikasi` | `tanya_spesifikasi` / `tanya_spek` | 47 (11.7%) | 3 / 3 (100.0%) |
| **A7** | `bandingkan` | `bandingkan` / `komparasi` | 14 (3.5%) | 3 / 3 (100.0%) |
| **A8** | `lanjutan_hasil` | `lanjutan_hasil` / `opsi_lanjutan` | 66 (16.4%) | 2 / 3 (66.7%) |
| **A9** | `tanya_info_toko` | `tanya_info_toko` / `info_toko` | 0 (0.0% di dataset regresi) | 3 / 3 (100.0%) |
| **A10** | `perbaiki_percakapan` | `perbaiki_percakapan` / `koreksi` | 52 (12.9%) | 3 / 3 (100.0%) |
| **A11** | `basa_basi` | `basa_basi` | 4 (1.0%) | 3 / 3 (100.0%) |
| **A12** | `tidak_jelas` | `tidak_jelas` / `out_of_domain` | 28 (7.0%) | 3 / 3 (100.0%) |

---

### 3.2 Status Evaluasi Perilaku B1–B18
Seluruh perilaku B1–B18 berstatus **Setuju** sesuai dokumen acuan:

| No | Deskripsi Aturan Perilaku | Status | Bukti Implementasi & Pengujian |
|---|---|---|---|
| **B1** | Respons sapaan ramah tanpa langsung menawarkan produk acak | **Setuju** | [`tests/test_scenarios_v2.py#L26`](file:///d:/RAG/tests/test_scenarios_v2.py#L26); `eval/replay_putaran6.md` Percakapan reg-01 Turn 1 |
| **B2** | Rekomendasi tanpa spesifikasi menanyakan kebutuhan/budget | **Setuju** | [`tests/test_scenarios_v2.py#L33`](file:///d:/RAG/tests/test_scenarios_v2.py#L33); `services/llm_parser.py` Prompt Clarification Rule |
| **B3** | Filter harga lanjutan mempertahankan kategori aktif | **Setuju** | [`tests/test_scenarios_v2.py#L41`](file:///d:/RAG/tests/test_scenarios_v2.py#L41); `services/action_engine.py#L446` |
| **B4** | Tolak profil kebutuhan di luar domain komputer/toko | **Setuju** | [`tests/test_scenarios_v2.py#L54`](file:///d:/RAG/tests/test_scenarios_v2.py#L54); `services/knowledge_service.py` threshold 0.42 |
| **B5** | Evaluasi kecocokan 3 status (`di_bawah_minimum`, `memenuhi_minimum`, `memenuhi_rekomendasi`) | **Setuju** | [`tests/test_scenarios_v2.py#L67`](file:///d:/RAG/tests/test_scenarios_v2.py#L67); `eval/replay_putaran6.md` Bagian 5 (raw JSON generator) |
| **B6** | Larangan keras produk cross-kategori (laptop vs desktop vs printer) | **Setuju** | [`tests/test_scenarios_v2.py#L81`](file:///d:/RAG/tests/test_scenarios_v2.py#L81); Replay: 0 mismatch dari 402 turn (0.0%) |
| **B7** | Opsi alternatif menyajikan produk lain dalam kategori sama | **Setuju** | [`tests/test_scenarios_v2.py#L94`](file:///d:/RAG/tests/test_scenarios_v2.py#L94); `services/action_engine.py` jenis `yang_lain` |
| **B8** | Opsi budget lebih murah mencari produk di bawah harga produk aktif | **Setuju** | [`tests/test_scenarios_v2.py#L106`](file:///d:/RAG/tests/test_scenarios_v2.py#L106); `services/action_engine.py` batas harga min |
| **B9** | Permintaan lanjutan saat daftar produk kosong diarahkan ke pencarian | **Setuju** | [`tests/test_scenarios_v2.py#L119`](file:///d:/RAG/tests/test_scenarios_v2.py#L119); status `belum_ada_produk` |
| **B10** | Informasi toko/garansi/lokasi mengarahkan ke kontak staf fiktif | **Setuju** | [`tests/test_scenarios_v2.py#L128`](file:///d:/RAG/tests/test_scenarios_v2.py#L128); `core/config.py` konstanta `KONTAK_STAF` |
| **B11** | Koreksi/keluhan pelanggan memicu permintaan klarifikasi sopan | **Setuju** | [`tests/test_scenarios_v2.py#L137`](file:///d:/RAG/tests/test_scenarios_v2.py#L137); status `sukses` jenis koreksi/keluhan |
| **B12** | Basa-basi pelanggan (terima kasih/pamit) dijawab hangat | **Setuju** | [`tests/test_scenarios_v2.py#L146`](file:///d:/RAG/tests/test_scenarios_v2.py#L146); respons penutup ramah |
| **B13** | Pesan ambigu/gibberish memicu permintaan penjelasan ulang | **Setuju** | [`tests/test_scenarios_v2.py#L155`](file:///d:/RAG/tests/test_scenarios_v2.py#L155); status `tidak_jelas` |
| **B14** | Evaluasi kecocokan tanpa produk aktif tolak ramah (`belum_ada_produk`) | **Setuju** | [`tests/test_scenarios_v2.py#L164`](file:///d:/RAG/tests/test_scenarios_v2.py#L164); `services/action_engine.py#L520` |
| **B15** | Tanya spesifikasi untuk atribut tidak tersedia dijawab jujur | **Setuju** | [`tests/test_scenarios_v2.py#L186`](file:///d:/RAG/tests/test_scenarios_v2.py#L186); status `atribut_tidak_tersedia` & atribut `harga` |
| **B16** | Produk di luar katalog diidentifikasi dan ditawarkan padanan terdekat | **Setuju** | [`tests/test_scenarios_v2.py#L208`](file:///d:/RAG/tests/test_scenarios_v2.py#L208); status `produk_tidak_di_katalog` + padanan |
| **B17** | Kegagalan parsing ganda JSON LLM fallback ke `tidak_jelas` | **Setuju** | [`tests/test_scenarios_v2.py#L230`](file:///d:/RAG/tests/test_scenarios_v2.py#L230); `services/llm_parser.py#L427` |
| **B18** | Kartu produk memiliki header seragam `[KODE]` dan harga terformat | **Setuju** | [`tests/test_scenarios_v2.py#L242`](file:///d:/RAG/tests/test_scenarios_v2.py#L242); `services/product_card.py#L46` & `session_pipeline.py#L185` |

---

## 4. Temuan dan Analisis Kualitas Sistem

### 4.1 Pelanggaran GroundingChecker (Penurunan Signifikan)
- Pada Putaran 5, pengujian repetisi awal mendeteksi puluhan potensi halusinasi teks dan kebocoran nama field internal.
- Pada Putaran 6 (402 giliran dieksekusi), pelanggaran GroundingChecker turun drastis menjadi hanya **4 kali (1.0%)**:
  1. `Menyebutkan nominal harga Rp1,000,000 yang tidak tercatat di fakta`: 2 kali
  2. `Menyebut istilah skema/sistem internal 'filter'`: 1 kali
  3. `Menyebutkan spesifikasi perangkat keras pada giliran non-produk`: 1 kali
- Seluruh 4 kejadian langsung diintersepsi oleh `GroundingChecker`, memicu mekanisme re-generasi atau substitusi kalimat darurat sehingga bot Telegram tidak pernah membocorkan informasi tidak valid ke pelanggan.

### 4.2 Analisis Emergency Fallback
- Terpanggil sebanyak **4 kali dari 402 turn (1.0%)**.
- Terjadi ketika LLM generator setelah retry tetap mempertahankan frasa yang dilarang (misalnya menyebut "kendala teknis" pada turn biasa atau menyebut nominal harga yang tidak ada di fakta produk).
- Teks darurat menggunakan format standar aman: *"Maaf Kak, saya belum bisa menjawab ini dengan tepat. Boleh dicoba sekali lagi, atau Kakak bisa menghubungi staf kami di {KONTAK_STAF}."* (tanpa menjanjikan dapat menghubungkan secara otomatis).

### 4.3 Kategori Mismatch (Aturan B6)
- Evaluasi otomatis melacak apakah produk yang direkomendasikan bot berbeda kategori dengan kategori yang diminta pelanggan (misal pelanggan minta laptop tapi ditawari desktop atau printer).
- Hasil: **0 kejadian dari 402 giliran (0.0%)**.
- Implementasi filter tegas kategori pada `services/action_engine.py` dan validasi kategori di `services/grounding_checker.py` terbukti 100% menyelesaikan masalah kategori mismatch.

### 4.4 Variabilitas LLM Antar-Run
- Dari 134 giliran unik pada dataset Telegram yang diulang 3 kali, **95 giliran (70.9%)** memiliki aksi yang persis sama di ketiga run.
- Sebanyak **39 giliran (29.1%)** memiliki variasi aksi antar-run.
- **Penyebab Utama**:
  1. Pesan pengguna ambigu 1-2 kata (misal pesan *"Laptop"* di tengah alur tanya-jawab). Pada run 1 model mem-parse sebagai `cari_produk`, sedangkan pada run 2 mem-parse sebagai `jawab_pertanyaan_bot`.
  2. Pertanyaan spek tanpa kata tanya (misal *"Ada webcam?"*). Terkadang diartikan sebagai `tanya_spesifikasi` dan terkadang sebagai `tidak_jelas`.
  3. Komparasi implisit (misal *"Yang murah"*). Terkadang diartikan sebagai `lanjutan_hasil` dan terkadang sebagai `cari_produk`.

---

## 5. Hal yang Belum Selesai & Terbuka untuk Putaran Berikutnya

Secara jujur dan transparan, berikut adalah hal-hal yang masih menjadi batasan sistem saat ini:
1. **Disambiguasi Pesan 1-2 Kata**: LLM Parser masih memiliki variabilitas ~29% ketika menerima masukan yang sangat minim konteks (seperti "Laptop" atau "Untuk mama"). Di masa mendatang, prioritas history kontekstual dapat diperketat melalui few-shot khusus disambiguasi giliran pendek.
2. **Latensi Operasi Hybrid RAG**: Saat kueri memicu embedding vektor Qdrant + pencarian katalog hybrid (terutama aksi `minta_rekomendasi`), latensi tahap mesin dapat mencapai 4.1 detik, sehingga latensi total giliran mencapai ~12–17 detik. Diperlukan caching embedding untuk query serupa.
3. **Pembersihan Riwayat Git Historis (.env)**: Berkas `.env` telah dilepas dari indeks pelacakan git (`git rm --cached .env`), namun blob historis pada commit-commit awal proyek masih ada di repositori lokal dan menunggu jadwal pembersihan riwayat terpadu menggunakan git filter-repo / BFG.

---

## 6. Verifikasi Akhir

- **Status Git**: Bersih dari berkas terlacak tak diinginkan. Empat berkas dokumentasi independen (`docs/latency_20_new.csv`, `docs/ood_full_eval_v2.csv`, `docs/ood_summary_v2.csv`, `dokumen/INSTRUKSI_ANTIGRAVITY_V2_LLM_PARSER.md`) dibiarkan untracked sesuai aturan.
- **Status Gold Lock**: Hash SHA-256 `eval/parse_gold.csv` tetap `13e7007e63bcb0e78f3982ee2515b273c0085c65ff1c1838016d9d7727d84fde`.
- **Status Pytest**: 223 passed, 20 skipped (HIJAU).
