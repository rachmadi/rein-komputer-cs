# -*- coding: utf-8 -*-
import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

from services.chat_service import process_chat_message, reset_chat_session

USER_MESSAGES = [
    "halo",
    "Tanya mini pc",
    "Speknya dong",
    "Yang kedua",
    "Belum sama monitor ya?",
    "Bukan gitu. Penjualannya belum sama monitor?",
    "Mana bisa aku cek sendiri. Kamu yang jelasin",
    "Caranya gimana?",
    "Mini pc itu dijual sudah termasuk monitor?",
    "Apa sih bedanya mini pc dengan desktop pc?",
    "Bisa dibawa-bawa dong?",
    "Boleh",
    "Monitor apa yang cocok kalo aku mau beli nuc?",
    "Ada yang 24 inci?",
    "Cuma ada 2 monitor yang dijual?",
    "Coba kasih aku spek 5 monitor sebagai perbandingan",
    "Itu bukan 5, tapi 3. Dan, itu bukan spek, cuma keterangan singkat",
    "Ya gak perlu tanya. Panggil aja mas katalognya",
    "Sama aja. Aku kan minta 5 spek monitor?",
    "Emang gak ada gambarnya?"
]

def run_replay():
    session_id = "replay_18e_20turns"
    reset_chat_session(session_id)

    print("================================================================================")
    print("PUTAR ULANG 20 PESAN PELANGGAN SESI 12 OKT 05:05-05:17 (PUTARAN 18e)")
    print("================================================================================\n")

    results = []

    for turn_num, user_msg in enumerate(USER_MESSAGES, 1):
        print(f"--- GILIRAN {turn_num} ---")
        print(f"Pelanggan: {user_msg}")

        res = process_chat_message(session_id, user_msg)

        # 1. Panggilan alat (nama + argumen)
        tool_calls = res.get("tool_calls") or res.get("metrics", {}).get("tool_calls", [])
        tc_display = []
        for tc in tool_calls:
            name = tc.get("nama") or tc.get("name")
            args = tc.get("argumen") or tc.get("arguments") or {}
            tc_display.append(f"{name}({json.dumps(args, ensure_ascii=False)})")
        tc_str = ", ".join(tc_display) if tc_display else "-"
        print(f"Panggilan Alat: {tc_str}")

        # 2. Jumlah produk yang disebut
        mentioned = res.get("products", [])
        print(f"Jumlah Produk Disebut: {len(mentioned)}")

        # 3. Jumlah kartu
        # Kartu HTML dirender jika ada kartu_produk_html
        cards_html = res.get("kartu_produk_html") or ""
        # Jumlah kartu di HTML (dihitung dari tag <b> atau card chunks)
        # Atau dari len(mentioned) yang di-cap format_product_cards_message
        card_count = min(len(mentioned), 5) if cards_html else 0
        print(f"Jumlah Kartu: {card_count}")

        # 4. Kode produk kartu
        card_codes = [p.get("kode") for p in mentioned[:5] if p.get("kode")]
        print(f"Kode Produk Kartu: {card_codes}")

        # 5. Balasan akhir VERBATIM
        reply_verbatim = res.get("reply", "")
        print(f"Balasan Akhir (VERBATIM):\n{reply_verbatim}\n")

        results.append({
            "turn": turn_num,
            "user_msg": user_msg,
            "tool_calls": tc_display,
            "mentioned_count": len(mentioned),
            "card_count": card_count,
            "card_codes": card_codes,
            "reply": reply_verbatim
        })

    out_json = "scratch/replay_20_turns_result.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Hasil lengkap tersimpan di: {out_json}")

if __name__ == "__main__":
    run_replay()
