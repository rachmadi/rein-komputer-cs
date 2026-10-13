# -*- coding: utf-8 -*-
"""
scripts/run_5_telegram_conversations.py
Menjalankan 5 percakapan Telegram multi-turn secara nyata melalui SessionPipeline / process_chat_message,
mencatat keluaran asli: jawaban utuh, aksi, fakta, latensi per tahap, dan pelanggaran pemeriksa.
"""
import os
import sys
import json
import time
import statistics

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Pastikan import dari root repo
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.chat_service import process_chat_message, get_session_manager

CONVERSATIONS = [
    {
        "id": "conv-1",
        "title": "Percakapan 1: Persona 'mama', Kebutuhan Ringan, dan 'Emang spek segitu cukup?'",
        "turns": [
            "laptop buat mama",
            "cuma buat cari resep dan youtube",
            "Emang spek segitu cukup?"
        ]
    },
    {
        "id": "conv-2",
        "title": "Percakapan 2: Koreksi & Keluhan 'Yang tanya HP 14 siapa?' lalu Asus",
        "turns": [
            "Cari laptop asus 14 inch",
            "Yang tanya HP 14 siapa?",
            "ada asus vivobook ga?"
        ]
    },
    {
        "id": "conv-3",
        "title": "Percakapan 3: Persona/Aktivitas 'Buat hiburan', Bawa Kategori, dan 'yang kedua bagus nggak?'",
        "turns": [
            "Buat hiburan",
            "laptop aja kak",
            "yang kedua bagus nggak?"
        ]
    },
    {
        "id": "conv-4",
        "title": "Percakapan 4: Pencarian Merek 'ada asus?', Pengecualian Merek, dan 'murahin dikit'",
        "turns": [
            "ada asus?",
            "ada opsi merk lain ga selain asus?",
            "murahin dikit"
        ]
    },
    {
        "id": "conv-5",
        "title": "Percakapan 5: Sapaan 'halo bobby', GPU Gaming 'rtx 4060', dan Info Toko Alamat",
        "turns": [
            "halo bobby",
            "mau laptop gaming rtx 4060",
            "tokonya ada di mana ya lokasinya?"
        ]
    }
]

def main():
    print("=" * 80)
    print("MENJALANKAN 5 PERCAKAPAN TELEGRAM ASLI (ANTIGRAVITY V2 PIPELINE)")
    print("=" * 80)

    sm = get_session_manager()

    parse_latencies = []
    mesin_latencies = []
    generate_latencies = []
    total_latencies = []
    all_violations = []

    full_results = []

    for conv in CONVERSATIONS:
        cid = conv["id"]
        title = conv["title"]
        print(f"\n>>> {title} (Session: {cid})")
        sm.reset_session(cid)

        conv_record = {
            "id": cid,
            "title": title,
            "turns": []
        }

        for turn_idx, user_text in enumerate(conv["turns"], 1):
            print(f"\n--- Giliran {turn_idx}: Pelanggan: \"{user_text}\" ---")
            t0 = time.time()
            res = process_chat_message(cid, user_text)
            dt_wall = (time.time() - t0) * 1000.0

            reply = res.get("reply", "")
            kartu_html = res.get("kartu_produk_html")
            route = res.get("route", "")
            metrics = res.get("metrics", {})

            lat_parse = metrics.get("latensi_parse_ms", 0.0)
            lat_mesin = metrics.get("latensi_mesin_ms", 0.0)
            lat_gen = metrics.get("latensi_generate_ms", 0.0)
            lat_tot = metrics.get("latensi_total_ms", dt_wall)
            violations = metrics.get("pelanggaran_pemeriksa", [])
            is_fallback = metrics.get("is_fallback", False)
            fakta = res.get("fakta", {})

            parse_latencies.append(lat_parse)
            mesin_latencies.append(lat_mesin)
            generate_latencies.append(lat_gen)
            total_latencies.append(lat_tot)
            if violations:
                all_violations.extend(violations)

            # Ekstrak snapshot state
            sess = sm.get_session(cid)
            state_now = sess["state"]

            turn_data = {
                "turn": turn_idx,
                "user": user_text,
                "aksi": route,
                "fakta": fakta,
                "reply": reply,
                "kartu_html": kartu_html,
                "latensi": {
                    "parse_ms": lat_parse,
                    "mesin_ms": lat_mesin,
                    "generate_ms": lat_gen,
                    "total_ms": lat_tot
                },
                "pelanggaran_pemeriksa": violations,
                "is_fallback": is_fallback,
                "state_snapshot": {
                    "persona": state_now.get("persona"),
                    "sebutan": state_now.get("sebutan"),
                    "kebutuhan_teks": state_now.get("kebutuhan_teks"),
                    "kategori": state_now.get("kategori"),
                    "budget": state_now.get("budget"),
                    "profil_aktif": state_now.get("profil_aktif"),
                    "produk_tampil_count": len(state_now.get("produk_tampil", []))
                }
            }
            conv_record["turns"].append(turn_data)

            print(f"Aksi: {route}")
            print(f"Fakta: {json.dumps(fakta, ensure_ascii=False)}")
            print(f"Jawaban: {reply}")
            if kartu_html:
                print(f"[Kartu Produk HTML Terkirim ({len(res.get('products', []))} produk)]")
            print(f"Latensi: Parse={lat_parse}ms | Mesin={lat_mesin}ms | Gen={lat_gen}ms | Total={lat_tot}ms")
            if violations:
                print(f"PELANGGARAN PEMERIKSA: {violations}")

        full_results.append(conv_record)

    # Simpan log utuh
    out_path = os.path.join(os.path.dirname(__file__), "..", "docs", "5_real_telegram_conversations.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(full_results, f, ensure_ascii=False, indent=2)

    def pct(vals, q):
        if not vals:
            return 0.0
        sorted_v = sorted(vals)
        k = (len(sorted_v) - 1) * (q / 100.0)
        f = int(k)
        c = f + 1
        if c < len(sorted_v):
            return sorted_v[f] + (k - f) * (sorted_v[c] - sorted_v[f])
        return sorted_v[f]

    def avg(vals):
        return sum(vals) / len(vals) if vals else 0.0

    print("\n" + "=" * 80)
    print("RINGKASAN METRIK LATENSI DAN PEMERIKSA (15 GILIRAN ASLI)")
    print("=" * 80)
    print(f"Jumlah Giliran: {len(total_latencies)}")
    print(f"Latensi Parse (ms):    p50 = {pct(parse_latencies, 50):.1f} | p95 = {pct(parse_latencies, 95):.1f} | mean = {avg(parse_latencies):.1f}")
    print(f"Latensi Mesin (ms):    p50 = {pct(mesin_latencies, 50):.1f} | p95 = {pct(mesin_latencies, 95):.1f} | mean = {avg(mesin_latencies):.1f}")
    print(f"Latensi Generate (ms): p50 = {pct(generate_latencies, 50):.1f} | p95 = {pct(generate_latencies, 95):.1f} | mean = {avg(generate_latencies):.1f}")
    print(f"Latensi Total (ms):    p50 = {pct(total_latencies, 50):.1f} | p95 = {pct(total_latencies, 95):.1f} | mean = {avg(total_latencies):.1f}")
    print(f"Total Pelanggaran Pemeriksa: {len(all_violations)}")
    if all_violations:
        for v in all_violations:
            print(f"  - {v}")
    else:
        print("  (0 pelanggaran - Semua jawaban lolos grounding & batas fakta!)")
    print("=" * 80)

if __name__ == "__main__":
    main()
