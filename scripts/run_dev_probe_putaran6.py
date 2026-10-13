# -*- coding: utf-8 -*-
"""
scripts/run_dev_probe_putaran6.py
Menjalankan probe pengujian dev Putaran 6 (36 kueri sintetis A1-A12 & B)
melalui SessionPipeline end-to-end secara deterministik/LLM.
"""
import os
import sys
import csv
import json
import time

sys.path.insert(0, os.path.abspath("."))
from services.session_pipeline import SessionPipeline

def main():
    probe_path = "eval/dev_probe_putaran6.csv"
    results_path = "eval/dev_probe_putaran6_results.csv"

    if not os.path.exists(probe_path):
        print(f"Error: {probe_path} tidak ditemukan.")
        return

    with open(probe_path, mode="r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    pipeline = SessionPipeline()
    results = []

    aksi_benar = 0
    total = len(reader)
    pelanggaran_checker_cnt = 0
    fallback_cnt = 0
    latencies = []

    print(f"=== Menjalankan Dev Probe Putaran 6 (n={total}) ===")

    for idx, row in enumerate(reader, 1):
        no = row["no"]
        pesan = row["pesan"]
        aksi_gold = row["aksi_gold"]
        state_awal = json.loads(row.get("state_awal_json") or "{}")

        t0 = time.perf_counter()
        turn_res, new_state = pipeline.process_turn(pesan, session_state=state_awal)
        dur = (time.perf_counter() - t0) * 1000.0
        latencies.append(dur)

        aksi_pred = turn_res.aksi_terpilih
        cocok = 1 if aksi_pred.lower().strip() == aksi_gold.lower().strip() else 0
        if cocok:
            aksi_benar += 1

        checker_v = len(turn_res.pelanggaran_pemeriksa)
        if checker_v > 0:
            pelanggaran_checker_cnt += 1

        fb = 1 if turn_res.is_emergency_fallback else 0
        if fb:
            fallback_cnt += 1

        print(f"[{idx}/{total}] No {no} | Gold: {aksi_gold:<20} | Pred: {aksi_pred:<20} | Cocok: {cocok} | Lat: {dur:.1f}ms")

        results.append({
            "no": no,
            "pesan": pesan,
            "aksi_gold": aksi_gold,
            "aksi_pred": aksi_pred,
            "aksi_cocok": cocok,
            "fakta_status": turn_res.fakta_eksekusi.get("status"),
            "pelanggaran_checker": "; ".join(turn_res.pelanggaran_pemeriksa),
            "is_emergency_fallback": fb,
            "latensi_total_ms": round(dur, 1),
            "teks_jawaban": turn_res.teks_jawaban.replace("\n", " ")
        })

    fieldnames = [
        "no", "pesan", "aksi_gold", "aksi_pred", "aksi_cocok",
        "fakta_status", "pelanggaran_checker", "is_emergency_fallback",
        "latensi_total_ms", "teks_jawaban"
    ]

    with open(results_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    latencies.sort()
    p50 = latencies[len(latencies) // 2] if latencies else 0.0
    p95_idx = int(len(latencies) * 0.95)
    p95 = latencies[min(p95_idx, len(latencies) - 1)] if latencies else 0.0

    print("\n=== RINGKASAN HASIL DEV PROBE PUTARAN 6 ===")
    print(f"Total Sampel (n)             : {total}")
    print(f"Aksi Benar                   : {aksi_benar}/{total} ({(aksi_benar/total)*100:.1f}%)")
    print(f"Pelanggaran GroundingChecker : {pelanggaran_checker_cnt}/{total} ({(pelanggaran_checker_cnt/total)*100:.1f}%)")
    print(f"Emergency Fallback Terpanggil: {fallback_cnt}/{total} ({(fallback_cnt/total)*100:.1f}%)")
    print(f"Latensi Total p50            : {p50:.1f} ms")
    print(f"Latensi Total p95            : {p95:.1f} ms")
    print(f"Hasil disimpan di            : {results_path}")

if __name__ == "__main__":
    main()
