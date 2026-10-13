# -*- coding: utf-8 -*-
"""
scripts/measure_e2e_telegram_latency.py
Mengukur latensi end-to-end (E2E) pipeline nyata sebanyak >= 30 pesan berurutan
yang bervariasi (sapa, cari, lanjutan, evaluasi, tidak_jelas, spesifikasi, bandingkan, dll).
Mencatat timestamp, durasi tiap tahap, re-parse flag, prompt_eval_count, dan eval_count ke eval/latency_e2e.csv.
Menghitung p50 dan p95 empiris langsung dari kolom total per pesan.
"""
import os
import sys
import csv
import time
import json
from datetime import datetime, timezone
import math

# Pastikan root workspace ada di sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.session_pipeline import SessionPipeline

TURNS_SCENARIOS = [
    # Dialog 1: Sapa, Cari Laptop Sekolah, Tanya Spek, Evaluasi, Basa-basi
    {"session": "ses_01", "text": "Halo mas, selamat siang"},
    {"session": "ses_01", "text": "Saya lagi cari laptop buat anak sekolah SMP"},
    {"session": "ses_01", "text": "Budgetnya sekitar 5 jutaan ada ga?"},
    {"session": "ses_01", "text": "Yang pertama itu merk apa ya?"},
    {"session": "ses_01", "text": "RAM nya berapa giga?"},
    {"session": "ses_01", "text": "Bisa buat ngetik word sama zoom lancar ga?"},
    {"session": "ses_01", "text": "Ada pilihan warna lain ga?"},
    {"session": "ses_01", "text": "Oke makasih infonya"},

    # Dialog 2: Sapa, Laptop Gaming, Spesifikasi, Bandingkan, Filter Merek, Info Toko
    {"session": "ses_02", "text": "Pagi kak"},
    {"session": "ses_02", "text": "Ada laptop gaming ASUS?"},
    {"session": "ses_02", "text": "Yang ada RTX nya dong"},
    {"session": "ses_02", "text": "Kalau dibanding Lenovo LOQ kencengan mana?"},
    {"session": "ses_02", "text": "Kuat ga buat main Cyberpunk 2077?"},
    {"session": "ses_02", "text": "Ada opsi merk lain ga selain asus?"},
    {"session": "ses_02", "text": "Yang paling murah yang mana dari situ?"},
    {"session": "ses_02", "text": "Toko buka jam berapa ya?"},

    # Dialog 3: Sapa, Desktop Kantor, Koreksi/Perbaiki, Info Toko Garansi & Servis
    {"session": "ses_03", "text": "Halo Bobby Computer"},
    {"session": "ses_03", "text": "Mau cari PC desktop untuk kantor administrasi"},
    {"session": "ses_03", "text": "Bisa sekalian monitornya ga?"},
    {"session": "ses_03", "text": "Bukan, maksud saya yang all in one ada?"},
    {"session": "ses_03", "text": "Garansinya berapa lama ya?"},
    {"session": "ses_03", "text": "Kalau servis bisa langsung ke toko?"},

    # Dialog 4: Desain Grafis, Rekomendasi, Filter Layar, Evaluasi, Negosiasi/Tidak Jelas
    {"session": "ses_04", "text": "Halo"},
    {"session": "ses_04", "text": "Rekomendasi laptop untuk kerja desain grafis dan edit video 4k"},
    {"session": "ses_04", "text": "Budget maksimal 15 juta"},
    {"session": "ses_04", "text": "Yang layarnya 15 inci atau lebih ada?"},
    {"session": "ses_04", "text": "Yang kedua storage nya SSD berapa GB?"},
    {"session": "ses_04", "text": "Kuat ga buat render After Effects?"},
    {"session": "ses_04", "text": "Ada diskon ga kak?"},
    {"session": "ses_04", "text": "Sip terima kasih banyak infonya"},

    # Dialog 5: Edge cases (pesan pendek typo / gaul)
    {"session": "ses_05", "text": "p"},
    {"session": "ses_05", "text": "ada asus?"},
    {"session": "ses_05", "text": "murahin dikit"}
]


def main():
    print(f"Memulai pengukuran latensi E2E pada {len(TURNS_SCENARIOS)} pesan berurutan...")
    pipeline = SessionPipeline()
    sessions_state = {}

    output_rows = []
    re_parse_count = 0

    os.makedirs("eval", exist_ok=True)
    csv_path = "eval/latency_e2e.csv"

    for idx, item in enumerate(TURNS_SCENARIOS, 1):
        sid = item["session"]
        user_msg = item["text"]
        current_state = sessions_state.get(sid, {})

        t_turn_start = time.perf_counter()
        timestamp_iso = datetime.now(timezone.utc).isoformat()

        res, updated_state = pipeline.process_turn(user_msg, current_state)
        t_turn_end = time.perf_counter()

        sessions_state[sid] = updated_state

        lat_total = (t_turn_end - t_turn_start) * 1000.0
        if res.re_parse:
            re_parse_count += 1

        row = {
            "turn_id": idx,
            "session_id": sid,
            "timestamp": timestamp_iso,
            "pesan": user_msg,
            "aksi": res.aksi_terpilih,
            "latensi_parse_ms": round(res.latensi_parse_ms, 2),
            "latensi_mesin_ms": round(res.latensi_mesin_ms, 2),
            "latensi_generate_ms": round(res.latensi_generate_ms, 2),
            "latensi_total_ms": round(lat_total, 2),
            "re_parse": res.re_parse,
            "prompt_eval_count": res.prompt_eval_count,
            "eval_count": res.eval_count,
            "json_valid": res.json_valid,
            "pelanggaran_pemeriksa": len(res.pelanggaran_pemeriksa),
            "teks_jawaban": res.teks_jawaban.replace("\n", " ")
        }
        output_rows.append(row)
        print(f"[{idx:02d}/{len(TURNS_SCENARIOS)}] {sid} | Aksi: {res.aksi_terpilih:20s} | Total: {lat_total:7.1f} ms | Parse: {res.latensi_parse_ms:6.1f} ms | Gen: {res.latensi_generate_ms:6.1f} ms | Tokens: {res.prompt_eval_count} in / {res.eval_count} out | Re-parse: {res.re_parse}", flush=True)

    # Tulis ke CSV
    fieldnames = [
        "turn_id", "session_id", "timestamp", "pesan", "aksi",
        "latensi_parse_ms", "latensi_mesin_ms", "latensi_generate_ms", "latensi_total_ms",
        "re_parse", "prompt_eval_count", "eval_count", "json_valid", "pelanggaran_pemeriksa", "teks_jawaban"
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"\nBerhasil menyimpan {len(output_rows)} baris ke {csv_path}")

    # Hitung persentil empiris dari kolom
    totals = [r["latensi_total_ms"] for r in output_rows]
    parses = [r["latensi_parse_ms"] for r in output_rows]
    gens = [r["latensi_generate_ms"] for r in output_rows]
    prompt_tokens = [r["prompt_eval_count"] for r in output_rows]

    def calc_percentile(data, p):
        if not data:
            return 0.0
        s = sorted(data)
        k = (len(s) - 1) * (p / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return float(s[int(k)])
        return float(s[int(f)] * (c - k) + s[int(c)] * (k - f))

    p50_total = calc_percentile(totals, 50)
    p95_total = calc_percentile(totals, 95)
    p50_parse = calc_percentile(parses, 50)
    p95_parse = calc_percentile(parses, 95)
    p50_gen = calc_percentile(gens, 50)
    p95_gen = calc_percentile(gens, 95)
    max_prompt_tokens = max(prompt_tokens)
    p95_prompt_tokens = calc_percentile(prompt_tokens, 95)

    print("=" * 60)
    print("HASIL PENGUKURAN EMPIRIS REAL E2E (n = %d):" % len(output_rows))
    print(f"- Jumlah pesan (n): {len(output_rows)}")
    print(f"- Jumlah re-parse: {re_parse_count}")
    print(f"- Total Latensi E2E: p50 = {p50_total:.1f} ms, p95 = {p95_total:.1f} ms")
    print(f"- Komponen Parser:   p50 = {p50_parse:.1f} ms, p95 = {p95_parse:.1f} ms")
    print(f"- Komponen Generator:p50 = {p50_gen:.1f} ms, p95 = {p95_gen:.1f} ms")
    print(f"- Prompt Tokens:     max = {max_prompt_tokens}, p95 = {p95_prompt_tokens:.1f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
