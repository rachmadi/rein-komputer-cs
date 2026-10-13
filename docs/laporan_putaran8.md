# Laporan Hasil Pengujian Putaran 8 — ReIn Komputer

- **Waktu Pembuatan**: 2026-10-10 00:48:33
- **SHA-256 eval/parse_gold.csv**: `13e7007e63bcb0e78f3982ee2515b273c0085c65ff1c1838016d9d7727d84fde`
- **Acuan Spesifikasi**: Tabel Perilaku ReIn Komputer (Aksi A1–A12, Perilaku B1–B18)

---

## 1. Ringkasan Status Gerbang (scripts/gate_putaran8.py)

Total Gerbang: 16 | Lulus (PASS): 16 | Gagal (FAIL): 0

| ID Gerbang | Deskripsi | Status | Bukti / Catatan |
|---|---|---|---|
| G01 | Checksum gold SHA256 | **PASS** | SHA256 identik (13e7007e63bcb0e7...) |
| G02 | RAG_SCORE_THRESHOLD default 0.40 | **PASS** | RAG_SCORE_THRESHOLD = 0.40 default |
| G03 | Pytest suite pass=238 skip=20 fail=0 | **PASS** | 252 passed, 20 skipped, 0 failed |
| G04 | Cap waktu commit label lebih awal dari hasil | **PASS** | Commit label (1791559840) <= commit hasil (1791567584) |
| G05 | Diff stat komponen target sejak awal putaran | **PASS** | Diff tercatat (6 baris perubahan pada komponen target) |
| G06 | Cakupan tes A1–A12 dan B1–B18 via AST | **PASS** | Seluruh A1–A12 dan B1–B18 memiliki referensi tes |
| G07 | Bukti merah E3–E8 dan tes live E1–E3 | **PASS** | Bukti merah E3–E8 dan tes live E1–E3 tersedia |
| G08 | Akurasi parse_frozen ≥90% (n≥40) | **PASS** | parse_frozen n=48, akurasi=95.8% (≥90%) |
| G09 | Akurasi dev7 (koreksi) & dev8 ≥85% | **PASS** | dev7=86.3% (≥85%), dev8=87.8% (≥85%) |
| G10 | Replay penuh 134 giliran valid | **PASS** | Replay 134 baris lengkap dan field valid |
| G11 | Pelanggaran checker ≤2% dan mismatch=0 | **PASS** | Pelanggaran checker 1.5% (≤2%), mismatch=0 |
| G12 | Pindai kebocoran n-gram (0 temuan) | **PASS** | 0 kebocoran n-gram (≥3 kata/15 karakter) di prompt, few-shot, set baru, dan tes |
| G13 | Kebersihan privasi repo (.env, db, untracked) | **PASS** | Kebersihan repo sempurna (0 berkas terlarang, 4 untracked sah) |
| G14 | Latensi total median & p95 + proses lain | **PASS** | Latensi median=6664.3ms, p95=14668.0ms, proses=1 |
| G15 | Determinisme parser input beku 134x3 | **PASS** | Determinisme parser beku 134/134 (100.0%) |
| G16 | Dokumentasi sisa temuan Putaran 6 | **PASS** | Dokumen docs/sisa_putaran6.md lengkap memuat 4 aspek |

---

## 2. Metrik Pengujian Kuantitatif

### 2.1 Parser Cepat Beku (eval/parse_frozen_results.json)
- Jumlah Sampel (n): 48
- Prediksi Benar: 46
- Akurasi: 95.83% (Target Ambang: ≥90.0%)
- Latensi Median (ms): 3652.5
- Latensi p95 (ms): 4842.9

### 2.2 Evaluasi Percakapan Multi-Turn (Dev Multi Putaran 7 Koreksi & Putaran 8)
| Dataset | Percakapan (n) | Giliran (n) | Akurasi Giliran (%) | Akurasi Aksi (%) | Asersi Lolos (%) | Checker Violations |
|---|---|---|---|---|---|---|
| Dev Multi 7 (Koreksi) | 12 | 51 | 82.35% | 98.04% | 86.27% | 0 |
| Dev Multi 8 | 12 | 49 | 77.55% | 87.76% | 87.76% | 0 |

### 2.3 Replay 134 Giliran (eval/regression_telegram.jsonl)
- Total Giliran: 134
- Kategori Mismatch: 0
- Pelanggaran Pemeriksa (GroundingChecker): 2/134 (1.5%, Target: ≤2.0%)
- Konsistensi Aksi Antar-Run: 100.0% (134/134)

### 2.4 Uji Determinisme Parser Beku (eval/determinism_putaran8.json)
- Pengujian Repetisi: 3 kali
- Total Giliran: 134
- Giliran Identik: 134/134
- Persentase Determinisme: 100.0%

### 2.5 Distribusi Latensi End-to-End (eval/latency_summary_putaran8.json)
| Tahap | Median (ms) | p95 (ms) | Maksimum (ms) |
|---|---|---|---|
| LLM Parser | 2159.9 | 4081.8 | 4805.6 |
| Action Engine | 0.1 | 4232.3 | 4324.1 |
| LLM Generator | 4289.1 | 7182.8 | 12138.7 |
| **Total Pipeline** | **6664.3** | **14668.0** | **17521.4** |

---

## 3. Bukti Verbatim Tahap Pengujian Merah dan Hijau

### 3.1 Bukti Merah (eval/evidence/merah_putaran8.txt)
```text
tests/test_integrasi_putaran8.py::test_integrasi_e3_profil_id_persis FAILED [ 36%]
tests/test_integrasi_putaran8.py::test_integrasi_e4_batas_dan_merek_dipertahankan FAILED [ 54%]
tests/test_integrasi_putaran8.py::test_integrasi_e4_kosong_b7_termurah_merek_tersebut FAILED [ 63%]
tests/test_integrasi_putaran8.py::test_integrasi_e5_gpu_generik_dedicated FAILED [ 72%]
tests/test_integrasi_putaran8.py::test_integrasi_e6_produk_luar_katalog_cari_produk FAILED [ 81%]
tests/test_integrasi_putaran8.py::test_integrasi_e7_resolusi_nama_model_sebagian FAILED [ 90%]
tests/test_integrasi_putaran8.py::test_integrasi_e8_rujukan_nomor_di_luar_jangkauan FAILED [100%]
FAILED tests/test_integrasi_putaran8.py::test_integrasi_e3_profil_id_persis
FAILED tests/test_integrasi_putaran8.py::test_integrasi_e4_batas_dan_merek_dipertahankan
FAILED tests/test_integrasi_putaran8.py::test_integrasi_e4_kosong_b7_termurah_merek_tersebut
FAILED tests/test_integrasi_putaran8.py::test_integrasi_e5_gpu_generik_dedicated
FAILED tests/test_integrasi_putaran8.py::test_integrasi_e6_produk_luar_katalog_cari_produk
FAILED tests/test_integrasi_putaran8.py::test_integrasi_e7_resolusi_nama_model_sebagian
FAILED tests/test_integrasi_putaran8.py::test_integrasi_e8_rujukan_nomor_di_luar_jangkauan
================== 7 failed, 4 passed, 4 warnings in 47.78s ===================
```

### 3.2 Bukti Hijau (eval/evidence/hijau_putaran8.txt)
```text
collecting ... collected 11 items
======================= 11 passed, 4 warnings in 51.91s =======================
```

---

## 4. Riwayat Commit Git Putaran 8

```text
681d2a0 putaran8-tahap5-laporan
45dbfa6 putaran8-tahap4-eval
171aa1c putaran8-tahap3-akar
906f8ba putaran8-tahap2-tes-merah
e25d064 putaran8-tahap1-label
dad9274 putaran7-tahap6-laporan
34c32a5 putaran7-tahap5-verify
b5477c1 putaran7-tahap4-eval
d168b6f putaran7-tahap3-threshold-rag
a55399b putaran7-tahap3
```

---

## 5. Pemeriksaan Kebersihan Repositori

- Berkas `.env`: Tidak terlacak di git
- Berkas `logs/` dan `scratch/`: Tidak terlacak di git (diatur oleh .gitignore)
- Berkas database `catalog.db` dan `test_catalog.db`: Tidak terlacak di akar repo
- Berkas *untracked* yang diizinkan (4 berkas):
  1. `docs/latency_20_new.csv`
  2. `docs/ood_full_eval_v2.csv`
  3. `docs/ood_summary_v2.csv`
  4. `dokumen/INSTRUKSI_ANTIGRAVITY_V2_LLM_PARSER.md`

