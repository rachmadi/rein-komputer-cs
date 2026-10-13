# Dokumentasi Tindak Lanjut Sisa Temuan Putaran 6

Dokumen ini mendokumentasikan 4 aspek audit dan kebersihan artefak yang menjadi catatan reviewer pada Putaran 6 dan dituntaskan secara tertulis pada Putaran 8.

---

## 1. Selisih Log 444 vs 448

Pada audit Putaran 6, tercatat adanya perbedaan hitungan antara 444 entri percakapan pada file log chat versus 448 baris pada versi mentah.
- **Penyebab Teknis**:
  1. Terdapat 4 baris entri kosong (empty lines/trailing newlines) pada file mentah lama `logs/chat_history.jsonl` sebelum proses sanitasi dan dedup.
  2. Saat di-parse menggunakan `json.loads` per baris non-kosong, total record valid adalah tepat 444 objek turn.
  3. Skrip `scripts/clean_chat_history.py` kini memastikan setiap pembacaan mengabaikan baris kosong dan memvalidasi integritas JSON per baris sehingga selisih log 444 vs 448 tidak lagi menimbulkan inkonsistensi data.

---

## 2. Daftar Scratch

Seluruh berkas eksperimen sementara yang sebelumnya berada di direktori kerja telah dipindahkan/diabaikan melalui `.gitignore` (`scratch/`).
- **Daftar Berkas Scratch**:
  - `scratch/` direktori lokal untuk skrip debugging ad-hoc, pengujian parser sementara, dan dump log uji coba.
  - Berkas-berkas di dalam `scratch/` telah dilepas dari indeks pelacakan git (`git rm -r --cached scratch/`) dan diproteksi oleh entri `scratch/` pada `.gitignore`.
  - Tidak ada berkas scratch yang di-commit ke repositori pada Putaran 8.

---

## 3. Status Privasi feedback.jsonl

- Berkas `logs/feedback.jsonl` memuat umpan balik pengguna riil dan percakapan.
- **Tindakan Perlindungan**:
  1. `logs/` telah dimasukkan ke dalam `.gitignore`.
  2. Berkas `logs/feedback.jsonl` telah dilepas sepenuhnya dari pelacakan git (`git rm --cached`).
  3. Pemeriksaan `git ls-files logs feedback.jsonl` menghasilkan status kosong (0 file terlacak).
  4. Pengujian `git check-ignore -v logs/feedback.jsonl` mengonfirmasi bahwa pola `.gitignore` aktif mencegah masuknya kembali data log ini ke repositori.

---

## 4. Status 4 Berkas Untracked

Terdapat 4 berkas yang sengaja dipertahankan dalam status *untracked* sesuai kesepakatan dan aturan keras evaluasi:
1. `docs/latency_20_new.csv`: Berkas pengukuran latensi historis Putaran 5 untuk perbandingan dasar.
2. `docs/ood_full_eval_v2.csv`: Hasil uji out-of-distribution (OOD) historis Putaran 5.
3. `docs/ood_summary_v2.csv`: Ringkasan ringkas metrik OOD Putaran 5.
4. `dokumen/INSTRUKSI_ANTIGRAVITY_V2_LLM_PARSER.md`: Dokumen acuan instruksi historis.

Keempat berkas ini tidak di-stage atau di-commit agar tidak mengotori riwayat git dan mematuhi aturan strict untracked files yang diverifikasi oleh `scripts/gate_putaran8.py` (pemeriksaan G13).
