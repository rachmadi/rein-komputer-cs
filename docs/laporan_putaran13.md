# Laporan Pengujian dan Eksekusi Putaran 13 (Pengganti) — ReIn Komputer

- **Waktu Penyelesaian**: 2026-10-10 20:30 WIB
- **Git HEAD**: `a4a86aa` (branch: `llm-parser`)
- **Baseline Tag**: `sebelum-putaran13` (`934dba8`)
- **Model**: `gemma4:e4b` (Ollama, tidak diubah)
- **Status Test Suite**: 310 passed, 20 skipped, 0 failed (Total: 330 items)

---

## 1. Ringkasan Diagnosa Awal (Butir A)

Hasil lengkap terdokumentasi pada `docs/diagnosa_putaran13.md` (commit `0264770`):

1. **A1. Penulisan dan Penimpaan State Produk (`produk_tampil`, `produk_terakhir_dibahas`, `history_produk_tampil`)**:
   - `update_session_product_tracking` di `services/session_pipeline.py`: Menimpa `state["produk_tampil"]` pada setiap giliran yang menghasilkan kartu atau daftar produk dari fakta mesin, serta menambahkan produk yang ditampilkan ke tumpukan riwayat `state["history_produk_tampil"]`.
   - `lanjutan_hasil`:
     - Opsi `yang_lain` dan `lebih_murah` menggantikan `state["produk_tampil"]` dengan kandidat katalog baru yang memenuhi filter.
     - Opsi `termurah_dari_tampil` menyeleksi unit termurah dari `state["produk_tampil"]` (atau riwayat sebelumnya) tanpa menimpa seluruh kumpulan jika tidak ada unit baru.
   - `perbaiki_percakapan`: Jika memicu pencarian baru (koreksi kriteria), `state["produk_tampil"]` ditimpa dengan hasil baru. Jika hanya keluhan/permohonan maaf, `state["produk_tampil"]` dipertahankan.
   - `bandingkan` dan `evaluasi_kecocokan`: Menimpa `state["produk_tampil"]` dengan entri produk yang dibandingkan/dievaluasi.

2. **A2. Penyebab `tanya_beruntun` / `pilihan_konkret` Tidak Aktif pada Pertanyaan Budget Berulang**:
   - Penghitung lama `state["tanya_beruntun"]` di-reset menjadi 0 setiap kali giliran pengguna bukan merupakan pengisian slot (misalnya respon keluhan, koreksi, atau pertanyaan balik), sehingga tidak pernah mencapai ambang batas >= 3.
   - Solusi di Putaran 13: Mengimplementasikan dua penghitung spesifik: `state["tanya_budget_beruntun"]` dan `state["tanya_kebutuhan_beruntun"]` yang melacak pengulangan slot tertentu, serta memicu pilihan rentang konkret pada giliran ke-3.

3. **A3. Estimasi Ukuran Konteks Prompt + Lembar Spesifikasi (3 Laptop + 3 Printer) terhadap `num_ctx: 4096`**:
   - Prompt sistem generator: ~350 token.
   - Riwayat percakapan 8 giliran: ~800–1.100 token.
   - Lembar spesifikasi 3 laptop (raw_data + spek): ~3 × 200 = ~600 token.
   - Lembar spesifikasi 3 printer: ~3 × 120 = ~360 token.
   - Metadata fakta lainnya: ~300 token.
   - Total konteks input: ~2.400–2.750 token.
   - Kesimpulan: Sangat aman berada di bawah limit `num_ctx: 4096` (~60–67% kapasitas), menyisakan >1.300 token untuk generasi balasan.

---

## 2. Rincian Implementasi per Butir (A s/d H)

| Butir | Deskripsi Singkat | Commit | File Utama yang Diubah |
|---|---|---|---|
| **A** | Diagnosa awal A1, A2, A3 | `0264770` | `docs/diagnosa_putaran13.md` |
| **B** | Pelacakan produk (`produk_dibahas`, `produk_dibahas_sebelumnya`, resolusi rujukan berlapis, deteksi ambigu) | `e431105` | `services/action_engine.py`, `services/session_pipeline.py`, `services/llm_generator.py` |
| **C** | Lembar spesifikasi lengkap (`build_lembar_spesifikasi`), syarat minimum diubah menjadi `catatan_minimum`, printer bebas syarat PC, larangan klaim "cocok" jika tidak memenuhi di GroundingChecker & prompt generator | `700f587` | `services/action_engine.py`, `services/grounding_checker.py`, `services/llm_generator.py` |
| **D** | Parser budget multi-format (`parse_budget_from_text`), sanitasi input string budget, rerun `minta_rekomendasi` pada `lebih_murah` yang membawa budget dan ada kebutuhan | `f5cfe36` | `services/catalog_search.py`, `services/action_engine.py`, `services/validator.py` |
| **E** | Kebersihan state: tolak `kebutuhan_teks` yang hanya berisi kategori/merek katalog via `is_valid_kebutuhan_teks`, gunakan `get_catalog_categories()` dinamis | `e502279` | `services/validator.py`, `services/action_engine.py` |
| **F** | Alternatif & pertanyaan berulang: counter `tanya_budget_beruntun` & `tanya_kebutuhan_beruntun`, sajikan rentang opsi konkret di giliran ke-3, isi `alternatif_cocok` dan kartu HTML saat evaluasi kecocokan di bawah minimum | `2149b69` | `services/action_engine.py`, `services/session_pipeline.py` |
| **G** | Prompt parser: contoh sintetis angka budget sebagai slot budget dan pertanyaan teknis sebagai `tanya_info_toko`, pasca-proses deterministik `strip_repeated_opening_interjection` | `8e676ae` | `services/llm_parser.py`, `services/session_pipeline.py` |
| **H** | Kolom log SQLite/JSONL baru (`is_emergency_fallback`, `jumlah_retry`, `pelanggaran`, `kartu_isi`, `produk_dibahas`, `produk_dibahas_sebelumnya`, `catatan_minimum`), tes sintetis baru di `test_putaran13_synthetic.py`, dan eksekusi replay | `a4a86aa` | `core/chat_logger.py`, `services/session_pipeline.py`, `services/chat_service.py`, `tests/test_putaran13_synthetic.py` |

---

## 3. Hasil Pengujian Unit & Integrasi (Pytest)

Pengujian dijalankan pada seluruh suite tes `tests/`:
```text
============================= test session starts =============================
platform win32 -- Python 3.13.15, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\RAG
configfile: pytest.ini
plugins: anyio-4.15.1
collected 330 items

tests\test_acceptance_v1_2.py .......................................    [ 11%]
tests\test_action_engine.py ............                                 [ 15%]
tests\test_admin_vram.py .                                               [ 15%]
tests\test_anti_hallucination.py .                                       [ 16%]
tests\test_audit_feedback.py ...                                         [ 16%]
tests\test_behavior_table_b1_b13.py ................                     [ 21%]
tests\test_c12_intro.py .                                                [ 22%]
tests\test_catalog_service.py .                                          [ 22%]
tests\test_chat_logger.py .....                                          [ 23%]
tests\test_conversational_rubric.py sss.sssssss                          [ 27%]
tests\test_e2e_golden.py ..                                              [ 27%]
tests\test_evaluasi_kecocokan_numbers.py ..                              [ 28%]
tests\test_factual_consistency.py ........                               [ 30%]
tests\test_fast_path_context.py .                                        [ 31%]
tests\test_fast_path_guard.py .                                          [ 31%]
tests\test_gold_lock.py .                                                [ 31%]
tests\test_golden_operator.py .                                          [ 32%]
tests\test_held_out_conversations.py .....sss.ssssss                     [ 36%]
tests\test_integrasi_putaran7.py ...............                         [ 41%]
tests\test_integrasi_putaran8.py ...........                             [ 44%]
tests\test_integrasi_putaran9.py ...................                     [ 50%]
tests\test_intent_router.py .                                            [ 50%]
tests\test_kebutuhan_gabungan.py ...                                     [ 51%]
tests\test_null_row.py .                                                 [ 51%]
tests\test_ood_retention.py .                                            [ 52%]
tests\test_operators.py ..                                               [ 52%]
tests\test_parser.py ....                                                [ 53%]
tests\test_pending_question_answers.py .....                             [ 55%]
tests\test_persona_salutation.py ....                                    [ 56%]
tests\test_putaran10_synthetic.py .......                                [ 58%]
tests\test_putaran11_synthetic.py ................                       [ 63%]
tests\test_putaran12_synthetic.py ......                                 [ 65%]
tests\test_putaran13_synthetic.py ..........                             [ 68%]
tests\test_real_catalog.py ............                                  [ 72%]
tests\test_real_conversations.py ......................................  [ 83%]
tests\test_regression_baseline.py .                                      [ 83%]
tests\test_scenarios_v2.py ..............................                [ 93%]
tests\test_schema_validator.py ...............                           [ 97%]
tests\test_screen_flow_5_turns.py s                                      [ 97%]
tests\test_session_isolation.py ..                                       [ 98%]
tests\test_turn2_failures.py .                                           [ 98%]
tests\test_vram_admin.py ...                                             [ 99%]
tests\test_vram_guard.py .                                               [100%]

=========== 310 passed, 20 skipped, 7 warnings in 327.18s (0:05:27) ===========
```

### Rekapitulasi:
- **Total Pengujian**: 330
- **Lulus (Passed)**: 310 (100% dari tes aktif)
- **Dilewati (Skipped)**: 20 (tes live evaluasi offline / benchmark panjang)
- **Gagal (Failed)**: 0

---

## 4. Hasil Pengujian Replay Model (`scratch\replay_model.py gemma_p13 gemma4:e4b`)

Eksekusi replay model terhadap 63 giliran percakapan:

```json
{
  "model": "gemma4:e4b",
  "mode_riwayat": "asli (konteks sama dengan sesi nyata)",
  "giliran": 63,
  "error": 0,
  "aksi_sama_dengan_asli": 49,
  "median_latensi_s": 11.3,
  "maks_latensi_s": 21.2
}
```

### Observasi Kunci Replay:
1. **Rantai Giliran Laptop (Giliran 27–33)**: Seluruh giliran pada rantai laptop berhasil dialihkan dan dieksekusi melalui pencarian katalog (`cari_produk [sukses]`) tanpa terjebak dalam perulangan printer.
2. **Penolakan Klaim Palsu Produk Tidak Memenuhi (Giliran 39)**:
   ```text
   Pelanggaran pemeriksa: ["Menyebut produk yang tidak memenuhi spesifikasi (Acer Nitro V 15) sebagai 'cocok'/'sangat membantu'/'memadai'."]. Meminta generator menulis ulang...
   ```
   GroundingChecker berhasil mendeteksi dan meminta perbaikan saat generator mencoba mengklaim produk dengan `catatan_minimum: memenuhi=False` sebagai cocok.
3. **Pembersihan State Kebutuhan Teks (Giliran 36)**:
   ```text
   E: Pembaruan state kebutuhan_teks 'printer canon' hanya berisi kategori/merek katalog, diabaikan.
   ```
   Sistem secara otomatis mengabaikan pembaruan `kebutuhan_teks` yang hanya berisi kategori/merek katalog.
4. **Validasi State Pertanyaan Bot (Giliran 58–59)**:
   ```text
   Aksi 'jawab_pertanyaan_bot' tidak konsisten dengan state: jawab_pertanyaan_bot hanya sah bila pending_question ada. Melakukan parse ulang 1x dengan enum aksi dibatasi...
   59 tanya_spesifikasi -> tanya_spesifikasi [sukses]
   ```
   Pipeline berhasil mereparasi kesalahan aksi ketika state `pending_question` kosong menjadi aksi spesifikasi yang tepat.

---

## 5. Ringkasan Log dan Kolom Baru

Tabel SQLite `chat_turns` dan log JSONL kini mencatat kolom-kolom baru sesuai Butir H:
- `is_emergency_fallback`: Penanda boolean apakah respon menggunakan kalimat darurat B13.
- `jumlah_retry`: Jumlah perulangan generasi LLM akibat penolakan pemeriksa (0, 1, atau 2).
- `pelanggaran`: Daftar teks alasan penolakan dari `GroundingChecker`.
- `kartu_isi`: Rincian kode, nama, harga, dan spesifikasi produk yang ditampilkan di kartu HTML.
- `produk_dibahas`: Kode produk fokus percakapan saat ini (1–3 kode).
- `produk_dibahas_sebelumnya`: Tumpukan LIFO hingga 5 entri riwayat fokus sebelumnya beserta label kebutuhan dan nomor giliran.
- `catatan_minimum`: Rangkuman status pemenuhan spesifikasi minimum profil pengguna (`memenuhi=True/False` dan alasan).
