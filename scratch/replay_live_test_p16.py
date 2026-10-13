# -*- coding: utf-8 -*-
"""
scratch/replay_live_test_p16.py
Menjalankan ulang 9 giliran live test 11 Okt 15:36–15:41 lewat pipeline saat ini.
"""
import sys
import os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')
import json
from services.session_pipeline import SessionPipeline

turns = [
    "Halo",
    "Jual monitor?",
    "Aku butuh 24 inci",
    "Apa speknya?",
    "GAk ada gambarnya?",
    "Kalo laptop ada?",
    "Aku tanya laptop",
    "Aku belum bilang untuk apa. Kok kamu menduga untuk kerja kantor dan kuliah?",
    "Cuma tanya laptop aja gak bisa jawab"
]

pipeline = SessionPipeline()
state = {}
history = []

results = []

for idx, user_msg in enumerate(turns):
    print(f"\n--- Memproses Turn {idx+1}: '{user_msg}' ---")
    turn_res, new_state = pipeline.process_turn(user_msg, session_state=state, history=history)
    state = new_state
    history = state.get("history", [])

    res = {
        "turn": idx + 1,
        "user_text": user_msg,
        "route": turn_res.aksi_terpilih,
        "status_hasil": turn_res.status_fakta,
        "sumber_balasan": turn_res.sumber_balasan,
        "generator_error": turn_res.generator_error,
        "latency_ms": turn_res.latensi_total_ms,
        "teks_jawaban": turn_res.teks_jawaban,
        "kategori_state": state.get("kategori"),
        "kebutuhan_state": state.get("kebutuhan_teks"),
        "budget_state": state.get("budget"),
    }
    results.append(res)
    print(f"Route: {res['route']} | Status: {res['status_hasil']} | Sumber: {res['sumber_balasan']}")
    print(f"Error: {res['generator_error']}")
    print(f"Reply: {res['teks_jawaban']}")

with open("scratch/replay_live_test_p16_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\nSelesai! Hasil disimpan di scratch/replay_live_test_p16_results.json")
