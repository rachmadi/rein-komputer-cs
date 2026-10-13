# -*- coding: utf-8 -*-
"""
Replay 14 giliran pesan pelanggan sesi 11 Okt 20:42–20:52 lewat jalur yang SAMA dengan bot Telegram:
load_dotenv() lalu process_chat_message().
"""
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from services.chat_service import process_chat_message, CHAT_ENGINE_MODE

TEST_MESSAGES = [
    "Halo, mbak",
    "Desktop mini ada?",
    "Ada pilihan lain?",
    "Apa pilihan lainnya?",
    "Kasih pilihannya dulu. Ntar aku pilih",
    "Aku minta dikasih semua pilihan yang ada",
    "Ngomongnya banyak. Tapi cuma kasih 1 pilihan. Gimana sih?",
    "Mana pilihannya?",
    "Emangnya ada berapa produk desktop mini yang dijual di sini?",
    "Kan tinggal jawab ada berapa bukan ditampilkan semua. Masa gak bisa?",
    "Kan tinggal cek katalog ada berapa dekstop mini",
    "Bilang aja gak ada",
    "Kalau ada, tinggal kamu cek ada berapa produk",
    "Ribet"
]

def run_replay():
    session_id = f"replay_p18b_{int(time.time())}"
    print(f"=== MEMULAI REPLAY 14 GILIRAN (Session: {session_id}) ===")
    print(f"CHAT_ENGINE_MODE: {CHAT_ENGINE_MODE}\n")

    results = []

    for idx, user_msg in enumerate(TEST_MESSAGES, start=1):
        print(f"==================================================")
        print(f"GILIRAN {idx}")
        print(f"User: {user_msg}")
        t0 = time.perf_counter()
        resp = process_chat_message(session_id=session_id, user_text=user_msg)
        durasi_s = time.perf_counter() - t0

        reply = resp.get("reply", "")
        route = resp.get("route", "")
        metrics = resp.get("metrics", {})
        tool_calls = metrics.get("tool_calls", [])
        llm_calls = metrics.get("llm_calls", [])

        # Extract eval count and tool calls info
        eval_counts = [call.get("eval_count") for call in llm_calls if call.get("eval_count") is not None]
        total_eval_tokens = sum(eval_counts) if eval_counts else 0

        tool_calls_info = []
        for tc in tool_calls:
            nama = tc.get("nama")
            args = tc.get("argumen")
            ringkasan = tc.get("ringkasan_hasil")
            tool_calls_info.append({
                "nama": nama,
                "argumen": args,
                "ringkasan": ringkasan
            })

        print(f"Engine Mode    : {CHAT_ENGINE_MODE}")
        print(f"Panggilan Alat : {json.dumps(tool_calls_info, ensure_ascii=False)}")
        print(f"Eval Count     : {eval_counts} (total: {total_eval_tokens})")
        print(f"Latensi        : {durasi_s:.2f} s")
        print(f"Balasan Akhir (VERBATIM):")
        print(reply)
        print(f"==================================================\n")
        sys.stdout.flush()

        results.append({
            "giliran": idx,
            "user_text": user_msg,
            "engine_mode": CHAT_ENGINE_MODE,
            "tool_calls": tool_calls_info,
            "eval_counts": eval_counts,
            "total_eval_tokens": total_eval_tokens,
            "latensi_s": round(durasi_s, 2),
            "reply_verbatim": reply
        })

    with open("scratch/replay_putaran18b_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("Replay selesai! Disimpan di scratch/replay_putaran18b_results.json")

if __name__ == "__main__":
    run_replay()
