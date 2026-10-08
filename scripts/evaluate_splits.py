# -*- coding: utf-8 -*-
"""
scripts/evaluate_splits.py
Mengevaluasi parser pada split dataset:
1. dev-40 (40 kalimat dev pertama)
2. dev-100 (100 kalimat dev lengkap)
3. held-out-v1-terpakai (50 kalimat held-out v1)
Menyimpan hasil per-item ke:
- eval/dev_40_predictions.csv
- eval/dev_100_predictions.csv
- eval/heldout_v1_predictions.csv
"""
import os
import sys
import csv
import json
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.llm_parser import parse_user_message


def evaluate_items(items, out_csv):
    fieldnames = ["id", "pesan", "gold_aksi", "pred_aksi", "benar_salah", "gold_args", "pred_args", "latensi_ms", "retried"]
    rows_out = []
    correct_count = 0

    print(f"\nMemulai evaluasi {len(items)} item -> {out_csv}...")
    for idx, item in enumerate(items, 1):
        item_id = item["id"]
        pesan = item["pesan"]
        gold_aksi = item["label_aksi"]
        gold_args = item.get("label_argumen", "{}")

        # Parsing state dari data gold jika ada
        state = {}
        if item.get("pending_question"):
            state["pending_question"] = item["pending_question"]
        if item.get("produk_tampil"):
            try:
                state["produk_tampil"] = json.loads(item["produk_tampil"])
            except Exception:
                pass
        if item.get("kebutuhan_diketahui"):
            state["kebutuhan_diketahui"] = item["kebutuhan_diketahui"]

        t0 = time.perf_counter()
        parsed, metrics = parse_user_message(pesan, state=state)
        dur_ms = (time.perf_counter() - t0) * 1000.0

        pred_aksi = parsed.aksi.value
        is_correct = (pred_aksi == gold_aksi)
        if is_correct:
            correct_count += 1

        row = {
            "id": item_id,
            "pesan": pesan,
            "gold_aksi": gold_aksi,
            "pred_aksi": pred_aksi,
            "benar_salah": is_correct,
            "gold_args": gold_args,
            "pred_args": json.dumps(parsed.argumen.model_dump(exclude_none=True), ensure_ascii=False),
            "latensi_ms": round(dur_ms, 1),
            "retried": metrics.get("retried", False)
        }
        rows_out.append(row)
        mark = "OK" if is_correct else "ERR"
        print(f"[{idx:03d}/{len(items):03d}] {item_id:8s} | {mark:3s} | Gold: {gold_aksi:20s} | Pred: {pred_aksi:20s} ({dur_ms:6.1f}ms)")

    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    acc = (correct_count / len(items)) * 100.0 if items else 0.0
    print(f"\nSelesai! Akurasi {out_csv}: {correct_count}/{len(items)} = {acc:.2f}%")
    return correct_count, len(items), acc


def main():
    gold_path = "eval/parse_gold.csv"
    with open(gold_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_items = list(reader)

    dev_items = [r for r in all_items if r.get("split") == "dev"]
    ho_items = [r for r in all_items if r.get("split") in ("held-out", "held-out-v1-terpakai")]

    dev_40 = dev_items[:40]
    dev_100 = dev_items[:100]

    # Evaluasi dev 40
    evaluate_items(dev_40, "eval/dev_40_predictions.csv")

    # Evaluasi dev 100
    evaluate_items(dev_100, "eval/dev_100_predictions.csv")

    # Evaluasi held-out v1
    evaluate_items(ho_items, "eval/heldout_v1_predictions.csv")


if __name__ == "__main__":
    main()
