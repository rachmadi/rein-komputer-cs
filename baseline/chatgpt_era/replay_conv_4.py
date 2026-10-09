# -*- coding: utf-8 -*-
"""
scripts/replay_conv_4.py
Replay Percakapan 4 dengan LLM sungguhan (Ollama gemma4:e4b).
Turn 1: "ada asus?"
Turn 2: "ada opsi merk lain ga selain asus?"
Mencatat JSON parse mentah, hasil validator, fakta mesin, teks balasan verbatim, dan kartu produk.
"""
import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.stdout.reconfigure(encoding='utf-8')

from services.session_pipeline import SessionPipeline
from services.llm_parser import parse_user_message
from services.validator import validate_parser_output, check_state_consistency

pipeline = SessionPipeline()
state = {}

turns = [
    "ada asus?",
    "ada opsi merk lain ga selain asus?"
]

for i, user_msg in enumerate(turns, 1):
    print(f"==================================================")
    print(f"TURN {i}: \"{user_msg}\"")
    print(f"==================================================")
    
    res, state = pipeline.process_turn(user_msg, state)
    
    print(f"1. RAW LLM PARSE:")
    print(res.raw_llm_content)
    
    print(f"\n2. HASIL VALIDATOR & AKSI TERVALIDASI:")
    print(f"- Aksi: {res.aksi_terpilih}")
    print(f"- Parsed: {json.dumps(res.parsed_output, ensure_ascii=False)}")
    print(f"- JSON Valid: {res.json_valid}")
    print(f"- Re-parse Terjadi: {res.re_parse}")
    
    print(f"\n3. FAKTA MESIN DETERMINISTIK:")
    print(json.dumps(res.fakta_eksekusi, ensure_ascii=False, indent=2))
    
    print(f"\n4. TEKS JAWABAN VERBATIM:")
    print(res.teks_jawaban)
    
    print(f"\n5. KARTU PRODUK HTML:")
    if res.kartu_produk_html:
        print(res.kartu_produk_html)
    else:
        print("(Tidak ada kartu produk yang dikirim)")
        
    print(f"\n6. DIAGNOSTIK & METRIK:")
    print(f"- Latensi Parse: {res.latensi_parse_ms:.1f} ms")
    print(f"- Latensi Mesin: {res.latensi_mesin_ms:.1f} ms")
    print(f"- Latensi Generator: {res.latensi_generate_ms:.1f} ms")
    print(f"- Latensi Total: {res.latensi_total_ms:.1f} ms")
    print(f"- Pelanggaran Pemeriksa: {res.pelanggaran_pemeriksa}")
    print()
