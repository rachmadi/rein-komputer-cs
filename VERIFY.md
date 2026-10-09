# LAPORAN VERIFIKASI SISTEM (VERIFY.md)
*Seluruh data dan metrik dalam dokumen ini dihasilkan secara programatik oleh `scripts/verify.py`.*

## 1. Status Repositori & Riwayat Commit
- **Hash Commit Terkini (HEAD)**: `5049f8a`
- **Riwayat Commit sejak `1d65c32`** (27 commit):
  - `5049f8a eval(replay): record 3-run replay transcript and evaluasi_kecocokan raw generator output`
  - `9c04c7f docs(verify): generate VERIFY.md via automated verification script`
  - `67d6467 docs(backlog): record technical debt explanations and Phase 3 migration roadmap`
  - `dedcdaf feat(verify): enhance git commit range detection with fallback in verify.py`
  - `03d2dc5 feat(replay): update replay script with aligned test cases and track regression dataset`
  - `8bbe735 fix(checker): safely parse string budgets in extract_prices_from_facts with unit test`
  - `2dfb0e8 fix(engine): safely parse string budgets and specs in ActionEngine with unit test`
  - `7ff9287 eval(splits): measure 33-turn latency with keep_alive 30m and record predictions across dev40, dev100, heldout-v1`
  - `2621cf7 feat(verify): add verify.py, replay.py, and evaluate_splits.py tool scripts`
  - `5e1de05 perf(latency): configure keep_alive 30m, CPU embedding, and capture load durations`
  - `31228a1 feat(checker): dynamic fact schema rejection and customer friendly cpu descriptions`
  - `cdffd25 refactor(engine): remove unsourced store focus claims from action engine and prompt`
  - `2b9ef98 test(gold): add gold dataset lock test and sha256 checksum`
  - `edc78bc eval(dialogue): replay conversation 4 with real LLM and compute normalized argument F1 metrics`
  - `cc5fda8 eval(latency): measure empirical 33-turn end-to-end latency with token counts and save to latency_e2e.csv`
  - `a247e45 feat(checker): enforce deterministic consistency between generator spec assessment and numerical deltas`
  - `ce8948a feat(engine): support out-of-catalog product references in bandingkan without falling back to tidak_jelas`
  - `a3245c9 refactor(prompt): remove literal gold sentences and quotes from action definitions and few-shots`
  - `6d79023 test(suite): mark legacy v1 conversational rubric tests as skip with explicit nodeids and align chat_service return slots`
  - `226cd8d test(engine): align test_action_engine with Point 6 numerical facts and add argument error analysis script`
  - `c9338cc eval(heldout): rerun held-out v1 with clean prompt and evaluate 7 dev errors with full context and stronger model`
  - `085e9ba feat(checker): enforce factual consistency between claims, cards, and exceptions`
  - `9e0ecd8 feat(engine): output raw numerical deltas for evaluasi_kecocokan`
  - `d4cc24d fix(session): clarify persona as device user and allow multi-slot extraction`
  - `28d8111 fix(validator): reject negation and empty slot values and update gold dev state snapshots`
  - `778d583 test(session): prove session isolation and add multi-session isolation test`
  - `6a79c50 fix(parser): enforce state consistency with 1x reparse retry, split jenis enums, and clarify cari_produk`

## 2. Hasil Eksekusi Pytest Suite Penuh
- **Baris Ringkasan Verbatim**: `172 passed, 20 skipped, 2 warnings in 146.41s (0:02:26)`
- **Status Exit Code**: `0` (SUKSES / HIJAU)
- **Daftar Nodeid Tes yang Di-skip** (20 tes):
  - `SKIPPED [1] tests\test_conversational_rubric.py:43: Legacy v1 test: asserts obsolete route 'GREETING' instead of v2 ActionEnum 'sapa'; requires rewrite to v2 action & facts architecture`
  - `SKIPPED [1] tests\test_conversational_rubric.py:69: Legacy v1 test: asserts obsolete route 'CLARIFY_CATEGORY' instead of v2 ActionEnum 'jawab_pertanyaan_bot'/'minta_rekomendasi'; requires rewrite to v2 action & facts architecture`
  - `SKIPPED [1] tests\test_conversational_rubric.py:95: Legacy v1 test: asserts obsolete routes 'FAST_AGENTIC', 'FOLLOWUP_OPTIONS', 'META_CLARIFY'; requires rewrite to v2 action & facts architecture`
  - `SKIPPED [1] tests\test_conversational_rubric.py:181: Legacy v1 test: asserts obsolete routes 'GREETING', 'CLARIFY_CATEGORY', 'META_CLARIFY'; requires rewrite to v2 action & facts architecture`
  - `SKIPPED [1] tests\test_conversational_rubric.py:241: Legacy v1 test: asserts legacy template framing wording for session isolation; replaced by v2 test in test_session_isolation.py`
  - `SKIPPED [1] tests\test_conversational_rubric.py:274: Legacy v1 test: asserts obsolete internal profile IDs ('P01', 'P16') removed in v2 architecture`
  - `SKIPPED [1] tests\test_conversational_rubric.py:316: Legacy v1 test: asserts obsolete route strings and legacy deterministic parser behavior`
  - `SKIPPED [1] tests\test_conversational_rubric.py:356: Legacy v1 test: asserts legacy multi-turn template failure wording`
  - `SKIPPED [1] tests\test_conversational_rubric.py:383: Legacy v1 test: asserts obsolete routes 'BRAND_STOCK' and 'BRAND_STOCK_UNAVAILABLE'`
  - `SKIPPED [1] tests\test_conversational_rubric.py:426: Legacy v1 test: asserts obsolete route 'META_CLARIFY'`
  - `SKIPPED [1] tests\test_held_out_conversations.py:121: Legacy v1 test: asserts obsolete route 'BRAND_STOCK' instead of v2 ActionEnum 'cari_produk'`
  - `SKIPPED [1] tests\test_held_out_conversations.py:134: Legacy v1 test: asserts obsolete route 'CLARIFY_CATEGORY' instead of v2 ActionEnum 'jawab_pertanyaan_bot'`
  - `SKIPPED [1] tests\test_held_out_conversations.py:148: Legacy v1 test: asserts obsolete route 'FOLLOWUP_OPTIONS' instead of v2 ActionEnum 'lanjutan_hasil'`
  - `SKIPPED [1] tests\test_held_out_conversations.py:178: Legacy v1 test: asserts obsolete route 'META_CLARIFY' instead of v2 ActionEnum`
  - `SKIPPED [1] tests\test_held_out_conversations.py:193: Legacy v1 test: asserts obsolete route 'OUT_OF_DOMAIN' instead of v2 ActionEnum 'tidak_jelas'`
  - `SKIPPED [1] tests\test_held_out_conversations.py:207: Legacy v1 test: asserts legacy template text 'Kebutuhan gabungan' instead of LLM generator phrasing`
  - `SKIPPED [1] tests\test_held_out_conversations.py:220: Legacy v1 test: asserts legacy product field dictionary formatting`
  - `SKIPPED [1] tests\test_held_out_conversations.py:234: Legacy v1 test: asserts legacy template wording for battery queries`
  - `SKIPPED [1] tests\test_held_out_conversations.py:251: Legacy v1 test: asserts obsolete route 'GREETING' in Turn 1`
  - `SKIPPED [1] tests\test_screen_flow_5_turns.py:11: Legacy v1 test: menguji pencocokan kata harfiah ('ibu' di teks respons) dan rute v1; memerlukan pembaruan ke arsitektur v2`

## 3. Akurasi Aksi Parser Per Split
| Split Dataset | Jumlah Sampel (n) | Prediksi Benar | Akurasi Aksi (%) | Berkas Sumber Prediksi |
|---|---|---|---|---|
| **Dev 40** | 40 | 35 | **87.50%** | `eval/dev_40_predictions.csv` |
| **Dev 100** | 100 | 95 | **95.00%** | `eval/dev_100_predictions.csv` |
| **Held-Out v1 (Terpakai)** | 50 | 47 | **94.00%** | `eval/heldout_v1_predictions.csv` |

## 4. Latensi Tahapan Pipeline (Berdasarkan `eval/latency_e2e.csv`)
*Pengukuran dilakukan melalui SessionPipeline (disebut 'pipeline'). Angka dihitung langsung dari berkas CSV.*

### Kondisi Terkini (Sesudah Perbaikan Latensi Ekor)
| Tahapan Pipeline | Sampel (n) | p50 (ms) | p95 (ms) | Maksimum (ms) |
|---|---|---|---|---|
| **1. LLM Parser** | 33 | 4,086.6 | 4,859.8 | 5,504.1 |
| **2. Mesin Deterministik** | 33 | 0.0 | 830.0 | 4,218.4 |
| **3. LLM Generator & Pemeriksa** | 33 | 4,991.2 | 9,333.6 | 9,854.7 |
| **TOTAL PIPELINE** | 33 | 9,193.5 | 15,511.1 | 16,987.4 |

### Pembanding Kondisi Sebelumnya (Sebelum Perbaikan Latensi Ekor)
| Tahapan Pipeline | Sampel (n) | p50 (ms) | p95 (ms) | Maksimum (ms) |
|---|---|---|---|---|
| **1. LLM Parser** | 33 | 4,079.0 | 4,943.7 | 5,397.9 |
| **2. Mesin Deterministik** | 33 | 0.0 | 829.7 | 10,132.2 |
| **3. LLM Generator & Pemeriksa** | 33 | 4,906.3 | 8,717.5 | 17,262.5 |
| **TOTAL PIPELINE** | 33 | 8,993.0 | 18,718.8 | 23,198.6 |

## 5. Audit Kebocoran Dataset ke Kode dan Prompt
- **Total Kalimat Unik Dipindai**: 220 kalimat (dari `eval/parse_gold.csv`, `eval/regression_telegram.jsonl`, `logs/chat_history.jsonl`)
- **Direktori yang Dipindai**: Seluruh repositori kecuali `eval/` dan `tests/`
- **Hasil Deteksi Kebocoran**: `343 kebocoran ditemukan`

**Daftar Kebocoran Terdeteksi**:
- `.\telegram_bot.py`: "Untuk kerja"
- `.\core\acts.py`: "Printer tipe lain"
- `.\core\engine.py`: "Itu semua untuk kantoran?"
- `.\core\engine.py`: "buat mama sih"
- `.\core\engine.py`: "Ada yang core i7?"
- `.\core\engine.py`: "Untuk desain"
- `.\core\engine.py`: "Untuk kerja"
- `.\core\engine.py`: "Buat mama sih"
- `.\core\engine.py`: "Lebih mahal ya?"
- `.\data\knowledge\panduan_kebutuhan_v2.md`: "Untuk desain"
- `.\data\knowledge\panduan_kebutuhan_v2.md`: "Untuk kerja"
- `.\docs\5_real_telegram_conversations.json`: "Yang tanya HP 14 siapa?"
- `.\docs\5_real_telegram_conversations.json`: "Mau cari laptop"
- `.\docs\5_real_telegram_conversations.json`: "yang kedua bagus nggak?"
- `.\docs\5_real_telegram_conversations.json`: "Untuk kerja"
- `.\docs\5_real_telegram_conversations.json`: "Buat hiburan"
- `.\docs\5_real_telegram_conversations.json`: "Emang spek segitu cukup?"
- `.\docs\5_real_telegram_conversations.json`: "tokonya ada di mana ya lokasinya?"
- `.\docs\ablation_study_results.json`: "bisa gosend instan hari ini?"
- `.\docs\ablation_study_results.json`: "wkwkwk mantap"
- ... dan 323 kebocoran lainnya.

## 6. Kunci Integritas Dataset Gold
- **Path Berkas**: `eval/parse_gold.csv`
- **SHA-256 Terhitung**: `13e7007e63bcb0e78f3982ee2515b273c0085c65ff1c1838016d9d7727d84fde`
- **SHA-256 Terkunci (`eval/gold.sha256`)**: `13e7007e63bcb0e78f3982ee2515b273c0085c65ff1c1838016d9d7727d84fde`
- **Status Kunci Integritas**: `TERKUNCI & SESUAI`

