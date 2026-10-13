# -*- coding: utf-8 -*-
"""
scripts/eval_parse_frozen.py
Mengukur performa LLM Parser saja pada set input beku (eval/parse_frozen_putaran8.csv).
Menghasilkan berkas keluaran JSON dan CSV dengan format dan quoting yang benar.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath("."))
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from services.llm_parser import parse_user_message


def run_eval_parse_frozen(
    input_file: str = "eval/parse_frozen_putaran8.csv",
    output_json: str = "eval/parse_frozen_results.json",
    output_csv: str = "eval/parse_frozen_results.csv",
) -> Dict[str, Any]:
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Berkas input tidak ditemukan: {input_file}")

    rows: List[Dict[str, Any]] = []
    with open(input_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    total_rows = len(rows)
    print(f"=== Menjalankan Evaluasi Parser Input Beku ({total_rows} baris) ===")

    results: List[Dict[str, Any]] = []
    latencies: List[float] = []
    correct_actions = 0
    action_stats: Dict[str, Dict[str, int]] = {}

    for idx, row in enumerate(rows, 1):
        pesan = row["pesan"]
        state_dict = json.loads(row["state_json"]) if row.get("state_json") else {}
        gold_aksi = row["aksi_benar"].strip()
        gold_argumen = json.loads(row["argumen_kunci"]) if row.get("argumen_kunci") else {}

        t0 = time.perf_counter()
        parser_out, metrics = parse_user_message(pesan, state=state_dict)
        dur = time.perf_counter() - t0
        latencies.append(dur)

        pred_aksi = parser_out.aksi.value
        is_action_match = (pred_aksi.lower() == gold_aksi.lower())
        if is_action_match:
            correct_actions += 1

        pred_args = parser_out.argumen.model_dump(exclude_none=True)

        # Update per-action stats
        if gold_aksi not in action_stats:
            action_stats[gold_aksi] = {"total": 0, "correct": 0}
        action_stats[gold_aksi]["total"] += 1
        if is_action_match:
            action_stats[gold_aksi]["correct"] += 1

        status_flag = "PASS" if is_action_match else "FAIL"
        print(f"[{idx:02d}/{total_rows:02d}] {dur:.2f}s | {status_flag} | Gold: {gold_aksi:<18} | Pred: {pred_aksi:<18} | {pesan[:40]}")

        res_item = {
            "index": idx,
            "pesan": pesan,
            "gold_aksi": gold_aksi,
            "pred_aksi": pred_aksi,
            "action_match": is_action_match,
            "gold_argumen": gold_argumen,
            "pred_argumen": pred_args,
            "latency_sec": round(dur, 4),
            "state_json": state_dict,
        }
        results.append(res_item)

    # Hitung p50 dan p95 latensi
    sorted_lat = sorted(latencies)
    p50_lat = sorted_lat[int(len(sorted_lat) * 0.50)] if sorted_lat else 0.0
    p95_lat = sorted_lat[int(len(sorted_lat) * 0.95)] if sorted_lat else 0.0

    acc = (correct_actions / total_rows * 100.0) if total_rows > 0 else 0.0

    summary = {
        "total_rows": total_rows,
        "correct_actions": correct_actions,
        "accuracy_percent": round(acc, 2),
        "latency_median_sec": round(p50_lat, 4),
        "latency_p95_sec": round(p95_lat, 4),
        "per_action_stats": action_stats,
        "results": results,
    }

    # Tulis JSON
    os.makedirs(os.path.dirname(output_json) or ".", exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Tulis CSV
    os.makedirs(os.path.dirname(output_csv) or ".", exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["index", "pesan", "gold_aksi", "pred_aksi", "action_match", "latency_sec", "pred_argumen_json"])
        for r in results:
            writer.writerow([
                r["index"],
                r["pesan"],
                r["gold_aksi"],
                r["pred_aksi"],
                r["action_match"],
                r["latency_sec"],
                json.dumps(r["pred_argumen"], ensure_ascii=False)
            ])

    print("\n============================================================")
    print("HASIL EVALUASI PARSER INPUT BEKU")
    print("============================================================")
    print(f"Total Baris (n)        : {total_rows}")
    print(f"Aksi Benar            : {correct_actions}/{total_rows} ({acc:.2f}%)")
    print(f"Latensi Median (p50)  : {p50_lat:.3f} s")
    print(f"Latensi p95           : {p95_lat:.3f} s")
    print("Rincian per Aksi:")
    for act, st in sorted(action_stats.items()):
        act_acc = (st["correct"] / st["total"] * 100.0) if st["total"] > 0 else 0.0
        print(f"  - {act:<20}: {st['correct']}/{st['total']} ({act_acc:.1f}%)")
    print(f"Disimpan di: {output_json} dan {output_csv}")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluasi LLM Parser Input Beku")
    parser.add_argument("--input", default="eval/parse_frozen_putaran8.csv", help="Jalur berkas CSV input")
    parser.add_argument("--output_json", default="eval/parse_frozen_results.json", help="Jalur berkas JSON output")
    parser.add_argument("--output_csv", default="eval/parse_frozen_results.csv", help="Jalur berkas CSV output")
    args = parser.parse_args()

    run_eval_parse_frozen(args.input, args.output_json, args.output_csv)
