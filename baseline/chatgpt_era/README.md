# Arsip Skrip dan Artefak Era ChatGPT / Eksperimen Legacy

Direktori ini menyimpan skrip pengujian satu kali, eksperimen awal, dan perkakas historis yang sudah digantikan oleh arsitektur Antigravity v2 (LLM Parser + Deterministic Action Engine + LLM Generator + Grounding Checker).

## Daftar Berkas yang Diarsipkan
- Skrip pengujian skema awal: `test_compact_schema.py`, `test_full_12_action_oneof.py`, `test_ollama_union_schema.py`
- Skrip evaluasi parsial: `eval_point_9.py`, `eval_dev_errors_clean.py`, `replay_conv_4.py`
- Skrip diagnostik dan eksperimen heuristik awal.

Seluruh alur produksi resmi kini dikonsolidasikan pada:
- `services/session_pipeline.py`
- `services/action_engine.py`
- `services/llm_parser.py`
- `services/llm_generator.py`
- `services/grounding_checker.py`
- `services/validator.py`
