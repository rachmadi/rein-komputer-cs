# Catatan Iterasi Parser Beku (eval/parse_frozen_putaran8.csv)

Set ukur beku: 48 baris input sintetis (eval/parse_frozen_putaran8.csv).
Target gerbang (G04 & G05): Akurasi >= 90.0% (>= 44/48), Latensi p50 <= 6.0s, p95 <= 10.0s.

---

## Iterasi 0 (Baseline Awal Putaran 8)
- **Ringkasan Perubahan**: Kode awal dari commit sebelum putaran 8 tanpa penyesuaian untuk set beku.
- **Akurasi**: 38/48 (79.17%)
- **Latensi p50**: 3.71 s
- **Latensi p95**: 6.40 s
- **Daftar Baris Salah**:
  - Baris 01, 02, 03, 04, 05, 06, 07, 08, 11 (lanjutan_hasil rejected / override ke tidak_jelas karena argumen 'jenis' seperti 'lainnya' / 'yang_setara' tidak dikenali di enum validator).
  - Baris 15 (tanya_spesifikasi gagal resolusi 'Pro 15' karena format produk_tampil di state berupa string kode produk tanpa hidrasi nama).

---

## Iterasi 1
- **Ringkasan Perubahan**:
  - `services/validator.py`: Normalisasi sinonim argumen `jenis` pada `lanjutan_hasil` (`lainnya`, `merek_lain`, `yang_setara` -> `yang_lain`; `di_bawah_itu` -> `lebih_murah`; `di_atas_itu` -> `lebih_mahal`).
  - `services/llm_parser.py`: Menambahkan 3 boundary few-shots sintetis baru (opsi lain / lebih murah, tanya spesifikasi harga unit, kebutuhan baru di tengah sesi).
- **Akurasi**: 43/48 (89.58%)
- **Latensi p50**: 3.66 s
- **Latensi p95**: 6.02 s
- **Daftar Baris Salah**:
  - Baris 15: `tanya_spesifikasi` ("Varian Pro 15 tersebut apakah dibekali...") -> resolusi rujukan produk gagal karena `produk_tampil` hanya berisi kode string di state pengujian tanpa field `nama` / `brand`.
  - Baris 21: `tanya_spesifikasi` ("Apakah laptop HP 14s itu layarnya...") -> sama seperti baris 15.
  - Baris 30: `evaluasi_kecocokan` -> diprediksi `minta_rekomendasi`.
  - Baris 32: `evaluasi_kecocokan` -> diprediksi `minta_rekomendasi`.
  - Baris 37: `lanjutan_hasil` -> diprediksi `cari_produk`.

---

## Iterasi 2 (Final)
- **Ringkasan Perubahan**:
  - `services/validator.py`:
    - Hidrasi otomatis nama dan brand produk dari katalog (`get_active_catalog().by_code`) di dalam `resolve_product_references` apabila elemen `produk_tampil` hanya memuat kode produk.
    - Dukungan pencocokan nama parsial jika kode/brand terisi.
  - `services/llm_parser.py`:
    - Penanganan `raw_pt` jika elemen berupa string kode atau dictionary.
    - Penegasan instruksi parser untuk kebutuhan baru di pesan pelanggan (`kebutuhan_teks` wajib diisi).
- **Akurasi**: 46/48 (95.83%)
- **Latensi p50**: 3.65 s
- **Latensi p95**: 4.84 s
- **Daftar Baris Salah**:
  - Baris 32: Gold `evaluasi_kecocokan`, Pred `minta_rekomendasi` ("Komputer ini rencananya dipakai untuk ko...")
  - Baris 37: Gold `lanjutan_hasil`, Pred `cari_produk` ("Anggaran saya saat ini hanya sekitar 4 j...")
- **Status Gerbang**: LULUS (Akurasi 95.83% >= 90.0%, p50 3.65s <= 6.0s, p95 4.84s <= 10.0s).
