# LAPORAN VERIFIKASI SISTEM (VERIFY.md)
*Seluruh data dan metrik dalam dokumen ini dihasilkan secara programatik oleh `scripts/verify.py`.*

## 1. Status Repositori & Riwayat Commit
- **Hash Commit Terkini (HEAD)**: `2fef42b`
- **Riwayat Commit sejak `1d65c32`** (47 commit):
  - `2fef42b putaran6-tahap5`
  - `375ec2e putaran6-tahap4`
  - `bb64230 putaran6-tahap4-probe-labels`
  - `d6e3523 putaran6-tahap3`
  - `b5e4e26 putaran6-tahap2-tes-merah`
  - `7757bc0 putaran6-tahap1`
  - `ab83677 chore(security): add logs/, catalog.db, and problem_sessions_report.json to .gitignore`
  - `1c7189c chore: untrack scratch/ and catalog.db`
  - `b30f579 chore(security): untrack .env`
  - `5f793e8 eval(putaran5): generate replay transcript and comprehensive Putaran 5 report`
  - `48d7f23 chore(hygiene): untrack logs and sqlite databases, create catalog seeder, and archive legacy scripts`
  - `653e0c1 refactor(branding): rename Bobby Computer to ReIn Komputer and configure mock staff contact`
  - `ec9b037 feat(pipeline): default to antigravity_v2, log startup config, and singleton pipeline`
  - `3e0bf9b test(scenarios): A1-A12 & B1-B13: add comprehensive deterministic test suite`
  - `f384203 feat(checker): B-grounding: reject hardware specs on non-product turns and prevent internal terms leakage`
  - `1e9ee36 refactor(knowledge): B4: remove forced profiles and evaluate RAG probe behavior`
  - `2d331d6 feat(prompt): B-prompt: add synthetic few-shots and enforce Rule C response constraints`
  - `6dd5426 feat(engine): B1-B13: implement behavior table rules and deterministic fallback logic`
  - `572bb79 fix(logger): B-log: enforce explicit penguji, HMAC env key, test log isolation, and session boundaries`
  - `967f055 docs(verify): refresh VERIFY.md with replay commit and latest test summary`
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
- **Baris Ringkasan Verbatim**: `223 passed, 20 skipped, 2 warnings in 179.27s (0:02:59)`
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
- **Kriteria Potongan**: Minimum 3 kata ATAU >= 15 karakter per kalimat yang dicocokkan.
- **Total Kalimat Unik Dipindai**: 242 kalimat (dari `eval/parse_gold.csv`, `eval/regression_telegram.jsonl`, `logs/chat_history.jsonl`)
- **Direktori yang Dipindai**: Seluruh repositori kecuali `eval/`, `tests/`, `logs/`, `scratch/`
- **Kebocoran pada KODE AKTIF (`services/`, `core/`, `telegram_bot.py`)**: `20 temuan`

| Berkas Kode Aktif | Potongan Kalimat | Sumber Bocoran |
|---|---|---|
| `core/acts.py` | "Printer tipe lain" | `logs/chat_history.cleaned.jsonl` |
| `core/acts.py` | "Beliau gak mau kalo Ryzen" | `logs/chat_history.cleaned.jsonl` |
| `core/engine.py` | "Lebih mahal ya?" | `logs/chat_history.cleaned.jsonl` |
| `core/engine.py` | "Buat mama sih" | `logs/chat_history.cleaned.jsonl` |
| `core/engine.py` | "Ada yang core i7?" | `logs/chat_history.cleaned.jsonl` |
| `core/engine.py` | "Itu semua untuk kantoran?" | `logs/chat_history.cleaned.jsonl` |
| `core/engine.py` | "buat mama sih" | `logs/chat_history.cleaned.jsonl` |
| `core/engine.py` | "Beliau gak mau kalo Ryzen" | `logs/chat_history.cleaned.jsonl` |
| `core/engine.py` | "Emangnya bisa pake itu?" | `logs/chat_history.cleaned.jsonl` |
| `services/agentic_tool_engine.py` | "Kan sudah dibilang buat hiburan" | `eval/parse_gold.csv` |
| `services/agentic_tool_engine.py` | "jual laptop acer?" | `eval/parse_gold.csv` |
| `services/agentic_tool_engine.py` | "yang ASUS aja" | `logs/chat_history.cleaned.jsonl` |
| `services/dynamic_rag_engine.py` | "ada yang lebih murah?" | `logs/chat_history.cleaned.jsonl` |
| `services/dynamic_rag_engine.py` | "Yang lebih mahal dikit" | `logs/chat_history.cleaned.jsonl` |
| `services/dynamic_rag_engine.py` | "Yang kelas di atas itu?" | `logs/chat_history.cleaned.jsonl` |
| `services/intent_router.py` | "jual laptop acer?" | `eval/parse_gold.csv` |
| `services/intent_router.py` | "Buat mama sih" | `logs/chat_history.cleaned.jsonl` |
| `services/intent_router.py` | "buat mama sih" | `logs/chat_history.cleaned.jsonl` |
| `services/intent_router.py` | "yang ASUS aja" | `logs/chat_history.cleaned.jsonl` |
| `services/slot_nlu_service.py` | "Untuk ibu saya yang sudah sepuh" | `eval/parse_gold.csv` |

- **Kebocoran pada BERKAS LEGACY & DOKUMEN (`baseline/`, `docs/`, `dokumen/`, dll)**: `304 temuan`

| Berkas Legacy / Dokumen | Potongan Kalimat | Sumber Bocoran |
|---|---|---|
| `baseline/chatgpt_era/test_full_12_action_oneof.py` | "ada yang lebih murah?" | `logs/chat_history.cleaned.jsonl` |
| `docs/5_real_telegram_conversations.json` | "Emang spek segitu cukup?" | `eval/parse_gold.csv` |
| `docs/5_real_telegram_conversations.json` | "Yang tanya HP 14 siapa?" | `eval/parse_gold.csv` |
| `docs/5_real_telegram_conversations.json` | "yang kedua bagus nggak?" | `eval/parse_gold.csv` |
| `docs/5_real_telegram_conversations.json` | "tokonya ada di mana ya lokasinya?" | `eval/parse_gold.csv` |
| `docs/5_real_telegram_conversations.json` | "Mau cari laptop" | `logs/chat_history.cleaned.jsonl` |
| `docs/ablation_study_results.json` | "Emang spek segitu cukup?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "Yang tanya HP 14 siapa?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "yang kedua bagus nggak?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "Aku tanya kok malah dikasih spek lain" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "Kan sudah dibilang buat hiburan" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "siang min mau nanya2 nih" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "jual laptop acer?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "laptop lenovo dibawah 10 juta ada ga?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "laptp asus ram 16gb" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "ada printer canon ga ya" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "Buat mama sih bukan buat aku" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "Paling cuma cari resep dan nonton youtube" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "Untuk ibu saya yang sudah sepuh" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "butuh laptop buat anak dkv semester 1" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "budget maksimal 7 jutaan aja" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "ada yang lebih murah?" | `logs/chat_history.cleaned.jsonl` |
| `docs/ablation_study_results.json` | "ada opsi merk lain ga selain acer?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "garansinya berapa lama min?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "tokonya ada di mana ya lokasinya?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "bisa bayar pake kartu kredit cicilan?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "bagusan nomor 1 apa nomor 2?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "makasih banyak infonya sangat membantu" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "ok sip makasih ya" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "hmm gimana ya" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "pc dekstop gaming rtx 4060" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "laptop murah buat ngetik word aja" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "yang ram 32gb ada?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "bisa buat main valorant ga laptop ini?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "bukan itu yang kumaksud" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "jam buka toko sampe jam berapa?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "apakah ada garansi resmi?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "laptop layar 15.6 inch buat kakek" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "ada printer brother?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "layarnya udah ips?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "assalamualaikum min" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "laptop asus tuf gaming ada?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "butuh buat kasir toko sembako" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "cuma buat zoom meeting dan skripsi aja" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "yang ketiga baterainya tahan berapa lama?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "antara ideapad sama vivobook bagusan mana?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "ada yang di bawah 5 juta?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "bisa gosend instan hari ini?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "kok ngulang salam lagi sih" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "makasih banyak infonya kak" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "halo selamat sore" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "printer epson l3210 ada ga?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "laptop gaming rtx 4050 murah" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "buat anak sma belajar coding python" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "budget maksimal 12 juta pas" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "cukup ga ram segitu buat buka 20 tab chrome?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "tampilin opsi yang lenovo aja dong" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "ada garansi tukar unit baru ga kalau rusak?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "bukan laptop gaming min maksud saya laptop tipis" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "siap nanti saya kabari lagi ya" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "cari pc meja all in one" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "laptop buat arsitek autocad dan sketchup" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "buat bapak saya" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "yang pertama ini ssd nya berapa gb?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "beda spek no 2 sama no 3 apa aja ya?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "ada pilihan warna lain ga?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "alamat service center resminya di mana?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "kok malah rekomendasiin yang mahal banget" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "mantap makasih rekomendasinya" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "ada laptop monitor 14 inch?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "butuh laptop ringan enteng dibawa ke kampus" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "buat kantor administrasi input excel" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "apakah prosesornya i5 atau i3?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "kalau dibanding macbook air m1 kencengan mana?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "ada yang harganya 8 jutaan?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "bisa split payment sebagian transfer sebagian cash?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "maksud saya bukan merek itu" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "terima kasih banyak min" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "monitor 24 inch 144hz ada?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "laptop buat ngetik tesis s2" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "budget sekitar 15 jutaan" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "apakah keyboardnya ada backlight nyala?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "tampilkan merek asus saja" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "apakah bisa klaim nota untuk kantor?" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "lho kan tadi saya bilang budget 6 juta" | `eval/parse_gold.csv` |
| `docs/ablation_study_results.json` | "Buat mama sih" | `logs/chat_history.cleaned.jsonl` |
| `docs/ablation_study_results.json` | "buat mama sih" | `logs/chat_history.cleaned.jsonl` |
| `docs/ablation_study_results.json` | "laptop asus tuf" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "ada yang lebih murah?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Mau cari laptop" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Nitro cocok gak buat desain?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Ukuran layar berapa?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Merek lain yang setara apa?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Lebih mahal ya?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Ya bukan intel dong. Kan printer?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Harga di bawah 1 juta, pilihannya apa aja?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Pilihan lain ada?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Maksudku selain tipe ini" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Printer tipe lain" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Wih..keren juga" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Kalo yang di atas itu?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Yang lebih mahal dikit" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Kan tanya printer?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Yang kelas di atas itu?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Sama dong harganya dengan yang tadi?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Ya sama dengan epson ecotank" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Kan tadi aku tanya kelas di atasnya" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Buat mama sih" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Paling cari resep masakan" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Berapaan harganya?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Lah..kan itu gak bisa buat main game?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Cek yang bisa sekalian main game" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Itu bukan 10 juta dong" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Tapi, mama maunya tanya resep sama Chatgpt juga" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Ram berapa itu emangnya?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Ada yang gpu nvidia gak?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Merek lain juga gak ada yang pake nvidia?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Tipe apa gpu-nya?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Wah, tanggung. Sayang banget. Kalo yang pake rtx 3050 ada?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Merek lain ada yang pake rtx 3050?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Produk laptop apa aja yang pake gpu?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Tapi, kata mama yang bisa sekalian tanya resep ke chatgpt" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Emangnya yang pertama tadi gak bisa chatgpt?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "RTX 3050 bukan geforce?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Papaku konsultan IT" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Ada yang core i7?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Papaku suka koding juga" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Kadang main LLM lokal juga" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Aku tanya spek" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Lah...aku tanya spek kenapa mesti tanya budget dulu?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Aku butuh yang bisa dipake koding" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Laptop, bukan desktop" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Jangan terlalu mahal. Dananya cuma 14 juta" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Spek lengkapnya dong" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Malah kasih gambar desktop" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Kan cari laptop?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Aku butuh yang bisa koding" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Tapi aku juga lagi eksplorasi LLM lokal" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Yang ketiga gak punya gpu?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Sudah tau butuh untuk LLM lokal" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Itu ada gpu. Kenapa dibilang gak cocok dengan LLM?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Tolong spek lenovo ini" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Baiklah. Aku mau sekalian printer warna" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Gak mesti untuk foto" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Wih..mahal juga ya? Ada yang 1 jutaan?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Yang ink tank gak ada yang sekitar 1 juta?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Aku juga butuh monitor eksternal" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Kan aku minta monitor, bukan desktop?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Laptop asus ada?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Kok gak ada info ramnya berapa?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Itu semua untuk kantoran?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "buat mama sih" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Tapi, mama adalah interior designer" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Laptop acer ada?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Paling cuma browsing" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Nonton youtube juga" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Tapi mau belajar koding juga" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Emangnya bisa pake itu?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Yang aku tanya yang ini nih" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Itu...nitro itu" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Emang bisa pake itu buat koding" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Dari tadi juga sudah ngomongin nitro ini" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Emang bisa pake yang ini?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Halo min, lagi cari laptop nih" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Buat ngetik tugas sama nonton drakor" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Emang layarnya enak dipake lama?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Menurut kamu worth it gak yang pertama itu?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "ada printer dibawah 1 juta?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Yang kelas di atas itu ada apa aja?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Berapaan harga yang Epson itu?" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "Kata mama buat cari resep" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "laptop buat edit video 4k" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "yang bisa dipake apa aja" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "laptop RAM 128GB" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "laptop Test Laptop Null VRAM" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "laptop buat main Cyberpunk tapi juga buat kasir toko" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "komputer buat game berat tapi juga buat kasir toko" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "laptop asus tuf" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "kebutuhan jelas: laptop buat edit video 4k" | `logs/chat_history.cleaned.jsonl` |
| `docs/problem_sessions_report.json` | "yang ASUS aja" | `logs/chat_history.cleaned.jsonl` |
| `dokumen/INSTRUKSI_ANTIGRAVITY_RAG.md` | "laptop buat edit video 4k" | `logs/chat_history.cleaned.jsonl` |
| `dokumen/INSTRUKSI_ANTIGRAVITY_RAG.md` | "harga Acer Nitro V 15" | `logs/chat_history.cleaned.jsonl` |
| `dokumen/INSTRUKSI_ANTIGRAVITY_V2_LLM_PARSER.md` | "Emang spek segitu cukup?" | `eval/parse_gold.csv` |
| `dokumen/INSTRUKSI_ANTIGRAVITY_V2_LLM_PARSER.md` | "Yang tanya HP 14 siapa?" | `eval/parse_gold.csv` |
| `dokumen/INSTRUKSI_ANTIGRAVITY_V2_LLM_PARSER.md` | "yang kedua bagus nggak?" | `eval/parse_gold.csv` |
| `dokumen/INSTRUKSI_ANTIGRAVITY_V2_LLM_PARSER.md` | "Aku tanya kok malah dikasih spek lain" | `eval/parse_gold.csv` |
| `dokumen/INSTRUKSI_ANTIGRAVITY_V2_LLM_PARSER.md` | "Kan sudah dibilang buat hiburan" | `eval/parse_gold.csv` |
| `dokumen/INSTRUKSI_ANTIGRAVITY_V2_LLM_PARSER.md` | "jual laptop acer?" | `eval/parse_gold.csv` |
| `dokumen/INSTRUKSI_ANTIGRAVITY_V2_LLM_PARSER.md` | "Buat mama sih bukan buat aku" | `eval/parse_gold.csv` |
| `dokumen/INSTRUKSI_ANTIGRAVITY_V2_LLM_PARSER.md` | "Paling cuma cari resep dan nonton youtube" | `eval/parse_gold.csv` |
| `dokumen/INSTRUKSI_ANTIGRAVITY_V2_LLM_PARSER.md` | "ada yang lebih murah?" | `logs/chat_history.cleaned.jsonl` |
| `dokumen/INSTRUKSI_ANTIGRAVITY_V2_LLM_PARSER.md` | "Buat mama sih" | `logs/chat_history.cleaned.jsonl` |
| `dokumen/INSTRUKSI_ANTIGRAVITY_V2_LLM_PARSER.md` | "buat mama sih" | `logs/chat_history.cleaned.jsonl` |
| `scripts/create_parse_gold.py` | "Emang spek segitu cukup?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "Yang tanya HP 14 siapa?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "yang kedua bagus nggak?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "Aku tanya kok malah dikasih spek lain" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "Kan sudah dibilang buat hiburan" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "siang min mau nanya2 nih" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "jual laptop acer?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "laptop lenovo dibawah 10 juta ada ga?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "laptp asus ram 16gb" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "ada printer canon ga ya" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "Buat mama sih bukan buat aku" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "Paling cuma cari resep dan nonton youtube" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "Untuk ibu saya yang sudah sepuh" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "butuh laptop buat anak dkv semester 1" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "budget maksimal 7 jutaan aja" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "ada yang lebih murah?" | `logs/chat_history.cleaned.jsonl` |
| `scripts/create_parse_gold.py` | "ada opsi merk lain ga selain acer?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "garansinya berapa lama min?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "tokonya ada di mana ya lokasinya?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "bisa bayar pake kartu kredit cicilan?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "bagusan nomor 1 apa nomor 2?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "makasih banyak infonya sangat membantu" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "ok sip makasih ya" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "hmm gimana ya" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "pc dekstop gaming rtx 4060" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "laptop murah buat ngetik word aja" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "yang ram 32gb ada?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "bisa buat main valorant ga laptop ini?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "bukan itu yang kumaksud" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "jam buka toko sampe jam berapa?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "apakah ada garansi resmi?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "laptop layar 15.6 inch buat kakek" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "ada printer brother?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "layarnya udah ips?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "apakah produk nomor 1 bisa ditambah ram?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "terima servis atau ganti pasta laptop?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "halo permisi mau konsultasi laptop" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "assalamualaikum min" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "laptop asus tuf gaming ada?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "butuh buat kasir toko sembako" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "cuma buat zoom meeting dan skripsi aja" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "yang ketiga baterainya tahan berapa lama?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "antara ideapad sama vivobook bagusan mana?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "ada yang di bawah 5 juta?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "bisa gosend instan hari ini?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "kok ngulang salam lagi sih" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "makasih banyak infonya kak" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "halo selamat sore" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "printer epson l3210 ada ga?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "laptop gaming rtx 4050 murah" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "buat anak sma belajar coding python" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "budget maksimal 12 juta pas" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "cukup ga ram segitu buat buka 20 tab chrome?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "tampilin opsi yang lenovo aja dong" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "ada garansi tukar unit baru ga kalau rusak?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "bukan laptop gaming min maksud saya laptop tipis" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "siap nanti saya kabari lagi ya" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "cari pc meja all in one" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "laptop buat arsitek autocad dan sketchup" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "buat bapak saya" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "yang pertama ini ssd nya berapa gb?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "beda spek no 2 sama no 3 apa aja ya?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "ada pilihan warna lain ga?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "alamat service center resminya di mana?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "kok malah rekomendasiin yang mahal banget" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "mantap makasih rekomendasinya" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "ada laptop monitor 14 inch?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "butuh laptop ringan enteng dibawa ke kampus" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "buat kantor administrasi input excel" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "apakah prosesornya i5 atau i3?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "kalau dibanding macbook air m1 kencengan mana?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "ada yang harganya 8 jutaan?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "bisa split payment sebagian transfer sebagian cash?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "maksud saya bukan merek itu" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "terima kasih banyak min" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "monitor 24 inch 144hz ada?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "laptop buat ngetik tesis s2" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "budget sekitar 15 jutaan" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "apakah keyboardnya ada backlight nyala?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "tampilkan merek asus saja" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "apakah bisa klaim nota untuk kantor?" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "lho kan tadi saya bilang budget 6 juta" | `eval/parse_gold.csv` |
| `scripts/create_parse_gold.py` | "Buat mama sih" | `logs/chat_history.cleaned.jsonl` |
| `scripts/create_parse_gold.py` | "buat mama sih" | `logs/chat_history.cleaned.jsonl` |
| `scripts/create_parse_gold.py` | "laptop asus tuf" | `logs/chat_history.cleaned.jsonl` |
| `scripts/measure_e2e_telegram_latency.py` | "ada pilihan warna lain ga?" | `eval/parse_gold.csv` |
| `scripts/run_5_telegram_conversations.py` | "Emang spek segitu cukup?" | `eval/parse_gold.csv` |
| `scripts/run_5_telegram_conversations.py` | "Yang tanya HP 14 siapa?" | `eval/parse_gold.csv` |
| `scripts/run_5_telegram_conversations.py` | "yang kedua bagus nggak?" | `eval/parse_gold.csv` |
| `scripts/run_5_telegram_conversations.py` | "tokonya ada di mana ya lokasinya?" | `eval/parse_gold.csv` |
| `scripts/run_ablation_study.py` | "Emang spek segitu cukup?" | `eval/parse_gold.csv` |
| `scripts/run_ablation_study.py` | "Yang tanya HP 14 siapa?" | `eval/parse_gold.csv` |
| `scripts/run_ablation_study.py` | "yang kedua bagus nggak?" | `eval/parse_gold.csv` |
| `scripts/run_ablation_study.py` | "Aku tanya kok malah dikasih spek lain" | `eval/parse_gold.csv` |
| `scripts/run_ablation_study.py` | "jual laptop acer?" | `eval/parse_gold.csv` |
| `scripts/run_ablation_study.py` | "Buat mama sih bukan buat aku" | `eval/parse_gold.csv` |
| `scripts/run_ablation_study.py` | "Paling cuma cari resep dan nonton youtube" | `eval/parse_gold.csv` |
| `scripts/run_ablation_study.py` | "Untuk ibu saya yang sudah sepuh" | `eval/parse_gold.csv` |
| `scripts/run_ablation_study.py` | "ada opsi merk lain ga selain acer?" | `eval/parse_gold.csv` |
| `scripts/run_ablation_study.py` | "tokonya ada di mana ya lokasinya?" | `eval/parse_gold.csv` |
| `scripts/run_ablation_study.py` | "bagusan nomor 1 apa nomor 2?" | `eval/parse_gold.csv` |
| `scripts/run_ablation_study.py` | "pc dekstop gaming rtx 4060" | `eval/parse_gold.csv` |
| `scripts/run_ablation_study.py` | "layarnya udah ips?" | `eval/parse_gold.csv` |
| `scripts/run_ablation_study.py` | "Buat mama sih" | `logs/chat_history.cleaned.jsonl` |
| `scripts/run_ablation_study.py` | "buat mama sih" | `logs/chat_history.cleaned.jsonl` |
| `scripts/run_e2e_api.py` | "ada yang lebih murah?" | `logs/chat_history.cleaned.jsonl` |
| `scripts/run_e2e_api.py` | "laptop buat edit video 4k" | `logs/chat_history.cleaned.jsonl` |
| `scripts/run_e2e_api.py` | "yang bisa dipake apa aja" | `logs/chat_history.cleaned.jsonl` |
| `scripts/run_e2e_api.py` | "harga Acer Nitro V 15" | `logs/chat_history.cleaned.jsonl` |
| `scripts/run_rag_scores.py` | "yang bisa dipake apa aja" | `logs/chat_history.cleaned.jsonl` |
| `scripts/run_rag_scores.py` | "harga Acer Nitro V 15" | `logs/chat_history.cleaned.jsonl` |

## 6. Kunci Integritas Dataset Gold
- **Path Berkas**: `eval/parse_gold.csv`
- **SHA-256 Terhitung**: `13e7007e63bcb0e78f3982ee2515b273c0085c65ff1c1838016d9d7727d84fde`
- **SHA-256 Terkunci (`eval/gold.sha256`)**: `13e7007e63bcb0e78f3982ee2515b273c0085c65ff1c1838016d9d7727d84fde`
- **Status Kunci Integritas**: `TERKUNCI & SESUAI`

