import time
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

from services.chat_service import process_chat_message, reset_chat_session

convos = [
    {
        "nama": "Percakapan 1: Multi-turn Video Editing P03 (ASUS & Lebih Murah)",
        "session_id": "eval_tg_convo_1",
        "turns": [
            "laptop buat edit video 4k",
            "yang ASUS aja",
            "ada yang lebih murah?"
        ]
    },
    {
        "nama": "Percakapan 2: Kebutuhan Gabungan Game Berat + Kasir (P05+P15)",
        "session_id": "eval_tg_convo_2",
        "turns": [
            "komputer buat game berat tapi kasir"
        ]
    },
    {
        "nama": "Percakapan 3: Spesifikasi Ekstrem Melebihi Katalog",
        "session_id": "eval_tg_convo_3",
        "turns": [
            "laptop RAM 128GB"
        ]
    },
    {
        "nama": "Percakapan 4: Customer Care Sapaan, Kategori-saja, dan Lanjutan",
        "session_id": "eval_tg_convo_4",
        "turns": [
            "halo kak, selamat pagi",
            "laptop",
            "cuma itu?"
        ]
    },
    {
        "nama": "Percakapan 5: Customer Care Meta Question & Kebutuhan Baterai Awet",
        "session_id": "eval_tg_convo_5",
        "turns": [
            "Dari mana kamu tahu kebutuhanku?",
            "laptop baterai awet"
        ]
    }
]

print("=== 5 EVALUASI PERCAKAPAN TELEGRAM LENGKAP ===")

for c in convos:
    sid = c["session_id"]
    reset_chat_session(sid)
    print(f"\n" + "="*60)
    print(f"[{c['nama']}]")
    print("="*60)
    for user_msg in c["turns"]:
        t0 = time.perf_counter()
        res = process_chat_message(sid, user_msg)
        elapsed = time.perf_counter() - t0
        
        reply = res.get("reply", "")
        route = res.get("route", "-")
        tools = res.get("tools_called", [])
        active_prof = res.get("active_profile_id", "-")
        prods = [p["kode"] for p in res.get("products", [])]
        
        print(f"\nUser: {user_msg}")
        print(f"Tool Dipanggil: {', '.join(tools) if tools else '-'}")
        print(f"Profil Aktif: {active_prof}")
        print(f"Waktu Respons: {elapsed:.3f} detik")
        print(f"Produk Kode: {prods}")
        print(f"Jawaban Utuh Bot:\n{reply}")
        print("-" * 50)
