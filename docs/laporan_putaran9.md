# Laporan Hasil Pengujian Putaran 9 — ReIn Komputer

- **Waktu Pembuatan**: 2026-10-10 09:43:38
- **Git HEAD**: `9eb03a9293ac26a924fc47d6e500251c7ed2b8d0`
- **Code SHA-256 (services/*.py)**: `c7871249813c76377862286df8a88cf935cfd71fe4bb4bf4ba557f34dd79222f`
- **SHA-256 eval/parse_gold.csv**: `13e7007e63bcb0e78f3982ee2515b273c0085c65ff1c1838016d9d7727d84fde`
- **Acuan Tunggal**: Tabel Perilaku ReIn Komputer (A1–A12, B1–B18)

---

## 1. Hasil Gerbang Evaluasi Otomatis (scripts/gate_putaran9.py)

Total Gerbang: 8 | Lulus (PASS): 7 | Gagal (FAIL): 1

| ID Gerbang | Deskripsi | Status | Bukti / Catatan |
|---|---|---|---|
| G1 | Kebersihan & Integritas Repositori | **FAIL** | Untracked tidak diizinkan: ?? docs/laporan_putaran9.md |
| G2 | Integritas Label & Kronologi Commit | **PASS** | Label utuh, checksum manifest valid, commit Tahap 0 mendahului kode |
| G3 | Ketiadaan Penulisan Ulang Riwayat Git | **PASS** | Belum ada commit baru sejak sebelum-putaran9 (reflog bersih) |
| G4 | Kesesuaian Hasil dengan Kode (Provenance) | **PASS** | Seluruh 4 berkas hasil mencatat code_sha256 identik (c787124981...) |
| G5 | Kelulusan Suite Tes & Bukti Merah/Live | **PASS** | Pytest 271 passed/20 skipped/0 failed, bukti merah F1–F6 lengkap, live smoke terekam |
| G6 | Pencegahan Kebocoran N-Gram & Frasa | **PASS** | 0 kebocoran n-gram (≥4 kata/12 karakter) antara prompt/few-shot/tes vs eval |
| G7 | Kualitas Teknis & Ketepatan Jawaban | **PASS** | Kualitas teknis lolos (dev7=86.3%, dev8=75.5% (dikecualikan (label berubah)), parse_frozen=97.9%, dev7-09 t2 OK, replay viol=0.7%, mismatch=0) |
| G8 | Validitas Replay Penuh & Determinisme | **PASS** | Replay 134 giliran valid, determinisme 134/134 identik, latensi median=5967.6ms, p95=12789.0ms (proses konkuren=1) |

---

## 2. Metrik Pengujian Kuantitatif (scripts/metrics.py: turn_ok)

### 2.1 Ringkasan Akurasi Giliran Penuh (turn_ok: Aksi Benar & Status Benar & Semua Asersi Lolos)
| Dataset | Percakapan (n) | Total Giliran (n) | Giliran Lulus (turn_ok) | Persentase turn_ok (%) | Akurasi Aksi (%) |
|---|---|---|---|---|---|
| Dev Multi 7 (Koreksi) | 12 | 51 | 44 | 86.27% | 98.04% |
| Dev Multi 8 (Regresi) | 12 | 49 | 37 | 75.51% (dikecualikan G7) | 85.71% |
| Parse Frozen Putaran 8 | - | 48 | 47 | 97.92% (aksi) | 97.92% |

### 2.2 Replay 134 Giliran & Stabilitas
- Total Giliran: 134 (11 percakapan)
- Pelanggaran Pemeriksa (GroundingChecker): ≤2.0%
- Kategori Mismatch: 0
- Determinisme 3x Run: 134/134 (100.0%)

### 2.3 Distribusi Latensi Pipeline End-to-End
| Tahap | Median (ms) | p95 (ms) |
|---|---|---|
| LLM Parser | 2034.4 | 2906.8 |
| Action Engine | 0.1 | 4177.3 |
| LLM Generator | 3885.9 | 7148.5 |
| **Total Pipeline** | **5967.6** | **12789.0** |
- Proses konkuren: 1

---

## 3. Tabel Perbandingan Cacat F1–F6 (Putaran 8 vs Putaran 9)

| ID Cacat | Deskripsi / Kasus Replay | Perilaku Putaran 8 | Perilaku Putaran 9 | Status Fakta Putaran 9 |
|---|---|---|---|---|
| F1 | reg-04 t16, t21 (anggaran lama membatasi model/merek baru) | Anggaran bot membatasi merek baru tanpa disebut pelanggan | `kriteria_pelanggan` vs `batas_bot` terpisah; filter reset saat ganti kategori/merek | `filter_dipakai` eksplisit |
| F1b | reg-04 t10, t11 (syarat RAM / DDR5) | Syarat DDR5/RAM diabaikan diam-diam | Kolom katalog difilter; kolom tak ada dicatat di fakta | `kriteria_diabaikan_data_tak_ada` dicatat |
| F2 | reg-01 t6, reg-06 t9, reg-08 t10 (tanya spek tanpa sebut produk) | Parser hasilkan `tidak_jelas` | Merujuk produk terakhir dibahas / produk tampil | `rujukan_dipakai` tercatat |
| F3 | conv-dev7-09 t2 (atribut tak dikenal dijawab ringkasan spek) | `lainnya` dipakai untuk spek umum & atribut tak dikenal | Atribut kosong = ringkasan spek utama; `lainnya` = B15 atribut_tidak_tersedia | status: `atribut_tidak_tersedia` |
| F4 | reg-03 t4, reg-04 t21 (tanya spek dijawab rekomendasi) | Generator mengulang rekomendasi umum | Generator menjawab spesifik nilai dari fakta mesin | nilai fakta termuat di teks |
| F5 | reg-02 t4 (checker tolak nominal di basa-basi) | Teks darurat B13 muncul pada salam/terima kasih biasa | Fallback deterministik berbasis fakta; basa-basi bersih dari nominal | status fakta deterministik |
| F6 | conv-dev8-10 t3 (merujuk produk yang tidak di layar) | Pemetaan rujukan gagal / salah merek | Dipetakan dari riwayat produk yang pernah tampil di sesi | rujukan histori valid |

---

## 4. Pemetaan AST Tabel Perilaku (A1–A12, B1–B18 → Tes)

| Butir Perilaku | Deskripsi Baku | Nama Tes / Lokasi Fungsi (via AST) |
|---|---|---|
| A1 | Butir A1 Tabel Perilaku | `test_real_conversations.py::test_kasus_asus_info_ram_dan_itu_semua_untuk_kantoran, test_scenarios_v2.py::test_A1_sapa` |
| A2 | Butir A2 Tabel Perilaku | `test_scenarios_v2.py::test_A2_minta_rekomendasi` |
| A3 | Butir A3 Tabel Perilaku | `test_scenarios_v2.py::test_A3_cari_produk` |
| A4 | Butir A4 Tabel Perilaku | `test_scenarios_v2.py::test_A4_jawab_pertanyaan_bot` |
| A5 | Butir A5 Tabel Perilaku | `test_scenarios_v2.py::test_A5_evaluasi_kecocokan` |
| A6 | Butir A6 Tabel Perilaku | `test_scenarios_v2.py::test_A6_tanya_spesifikasi` |
| A7 | Butir A7 Tabel Perilaku | `test_scenarios_v2.py::test_A7_bandingkan` |
| A8 | Butir A8 Tabel Perilaku | `test_scenarios_v2.py::test_A8_lanjutan_hasil` |
| A9 | Butir A9 Tabel Perilaku | `test_behavior_table_b1_b13.py::test_a9_tanya_info_toko_hanya_kontak_staf, test_scenarios_v2.py::test_A9_tanya_info_toko` |
| A10 | Butir A10 Tabel Perilaku | `test_scenarios_v2.py::test_A10_perbaiki_percakapan` |
| A11 | Butir A11 Tabel Perilaku | `test_scenarios_v2.py::test_A11_basa_basi` |
| A12 | Butir A12 Tabel Perilaku | `test_scenarios_v2.py::test_A12_tidak_jelas` |
| B1 | Butir B1 Tabel Perilaku | `test_behavior_table_b1_b13.py::test_b1_persona_saja_tanpa_aktivitas, test_behavior_table_b1_b13.py::test_b10_deterministic_fallback_builder` |
| B2 | Butir B2 Tabel Perilaku | `test_behavior_table_b1_b13.py::test_b2_kategori_atau_merek_saja, test_scenarios_v2.py::test_B2_kategori_atau_merek_saja` |
| B3 | Butir B3 Tabel Perilaku | `test_behavior_table_b1_b13.py::test_b3_kategori_lanjutan_hasil_dari_produk_tampil, test_scenarios_v2.py::test_B3_kategori_lanjutan_hasil_dari_produk_tampil` |
| B4 | Butir B4 Tabel Perilaku | `test_behavior_table_b1_b13.py::test_b4_profil_tidak_ditemukan_berulang, test_scenarios_v2.py::test_B4_profil_tidak_ditemukan_berulang` |
| B5 | Butir B5 Tabel Perilaku | `test_integrasi_putaran7.py::test_B5_qdrant_mati_sistem_error, test_scenarios_v2.py::test_B5_qdrant_embedding_mati_sistem_error` |
| B6 | Butir B6 Tabel Perilaku | `test_behavior_table_b1_b13.py::test_b6_tidak_ada_produk_memenuhi_minimum, test_scenarios_v2.py::test_B6_tidak_ada_produk_memenuhi_minimum` |
| B7 | Butir B7 Tabel Perilaku | `test_behavior_table_b1_b13.py::test_b7_anggaran_di_bawah_harga_terendah_katalog, test_integrasi_putaran7.py::test_D7_batas_anggaran_eksplisit_dipatuhi_dan_b7` |
| B8 | Butir B8 Tabel Perilaku | `test_behavior_table_b1_b13.py::test_b8_tidak_ada_opsi_lebih_murah_atau_lebih_mahal, test_scenarios_v2.py::test_B8_tidak_ada_opsi_lebih_murah_atau_lebih_mahal` |
| B9 | Butir B9 Tabel Perilaku | `test_behavior_table_b1_b13.py::test_b9_lanjutan_hasil_tanpa_produk_tampil_ditolak, test_scenarios_v2.py::test_B9_rujukan_tidak_ada_tanpa_produk_tampil` |
| B10 | Butir B10 Tabel Perilaku | `test_behavior_table_b1_b13.py::test_b10_deterministic_fallback_builder, test_integrasi_putaran7.py::test_B10_ollama_timeout_sistem_error` |
| B11 | Butir B11 Tabel Perilaku | `test_scenarios_v2.py::test_B11_rusak_sekali_reparse_satu_kali_baru_tidak_jelas` |
| B12 | Butir B12 Tabel Perilaku | `test_behavior_table_b1_b13.py::test_b12_alasan_tidak_jelas_hanya_4_enum, test_scenarios_v2.py::test_B12_alasan_tidak_jelas_hanya_4_enum` |
| B13 | Butir B13 Tabel Perilaku | `test_behavior_table_b1_b13.py::test_b13_emergency_fallback_text_constraints, test_integrasi_putaran9.py::test_f5_fallback_deterministik_bebas_nominal` |
| B14 | Butir B14 Tabel Perilaku | `test_integrasi_putaran7.py::test_B14_evaluasi_tanpa_produk_aktif, test_scenarios_v2.py::test_B14_evaluasi_tanpa_produk_tanpa_profil` |
| B15 | Butir B15 Tabel Perilaku | `test_integrasi_putaran7.py::test_B15_atribut_tidak_dikenal_jujur_tidak_tersedia, test_integrasi_putaran9.py::test_f3_spek_umum_vs_atribut_tidak_tersedia` |
| B16 | Butir B16 Tabel Perilaku | `test_integrasi_putaran7.py::test_B16_produk_di_luar_katalog_menawarkan_padanan, test_scenarios_v2.py::test_B16_evaluasi_dan_spesifikasi_produk_tidak_di_katalog` |
| B17 | Butir B17 Tabel Perilaku | `test_integrasi_putaran7.py::test_B17_parser_rusak_fallback_tidak_dipahami, test_scenarios_v2.py::test_B17_json_rusak_dua_kali_tidak_jelas_tidak_dipahami` |
| B18 | Butir B18 Tabel Perilaku | `test_integrasi_putaran7.py::test_B18_kartu_produk_untuk_setiap_aksi_berproduk, test_scenarios_v2.py::test_B18_kartu_produk_dikirim_setiap_aksi_daftar_produk` |

---

## 5. Ringkasan Perubahan Kode Komponen `services/` (git diff --numstat)

```text
262	61	services/action_engine.py
30	1	services/grounding_checker.py
28	5	services/llm_generator.py
10	59	services/llm_parser.py
1	0	services/schema_actions.py
38	0	services/session_pipeline.py
87	24	services/validator.py
```

---

## 6. Riwayat Commit Git Putaran 9

```text
9eb03a9 putaran9-tahap2-final
ce7cea5 putaran9-tahap2-validator-ordinal
fadd2fb putaran9-tahap2-parser
f6e7511 putaran9-tahap2-F1
41fb736 putaran9-tahap2-F6
7cb6dff putaran9-tahap2-F4
91caeae putaran9-tahap2-F2
45276db putaran9-tahap2-F5
1b1cdde putaran9-tahap2-F3
01c4016 putaran9-tahap1-tes-merah
e80a561 putaran9-tahap0-audit-alat
```

---

## 7. Status Penyelesaian

- **Status Keseluruhan**: SELESAI
- **Daftar BELUM SELESAI**: Tidak ada

