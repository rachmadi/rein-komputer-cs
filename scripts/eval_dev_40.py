# -*- coding: utf-8 -*-
"""
scripts/eval_dev_40.py
Menjalankan evaluasi parser LLM pada 40 kalimat dev (Fase 1 Gatekeeper).
"""
import sys
import os
sys.path.append('.')
sys.stdout.reconfigure(encoding='utf-8')
import json
import time
import math

def calc_percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    d0 = sorted_data[int(f)] * (c - k)
    d1 = sorted_data[int(c)] * (k - f)
    return d0 + d1

from services.llm_parser import parse_user_message


def run_eval_40():
    gold_path = "eval/parse_gold.jsonl"
    items = []
    with open(gold_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            if data.get("split") == "dev":
                items.append(data)
            if len(items) >= 40:
                break

    print(f"Loaded {len(items)} dev items for Gatekeeper evaluation.")

    results = []
    latencies = []
    correct_actions = 0
    valid_json_count = 0

    for idx, it in enumerate(items, 1):
        pesan = it["pesan"]
        state = it.get("state", {})
        label_aksi = it["label_aksi"]
        label_arg = it.get("label_argumen", {})

        print(f"[{idx}/40] Running: '{pesan}' ...", end="", flush=True)
        out, metrics = parse_user_message(pesan, state=state)
        pred_aksi = out.aksi.value
        dt = metrics["latency_ms"]
        latencies.append(dt)

        if metrics.get("json_valid", False):
            valid_json_count += 1

        is_correct = (pred_aksi == label_aksi)
        if is_correct:
            correct_actions += 1

        # Format compact args string
        pred_args = {k: v for k, v in out.argumen.model_dump().items() if v is not None}
        args_str = json.dumps(pred_args, ensure_ascii=False) if pred_args else "{}"

        results.append({
            "no": idx,
            "id": it["id"],
            "pesan": pesan,
            "pred_aksi": pred_aksi,
            "gold_aksi": label_aksi,
            "args_str": args_str,
            "benar": is_correct,
            "latency_ms": dt,
            "json_valid": metrics.get("json_valid", False)
        })
        status_sym = "[BENAR]" if is_correct else "[SALAH]"
        print(f" {status_sym} ({pred_aksi} vs {label_aksi}) in {dt:.0f}ms")

    p50 = float(calc_percentile(latencies, 50))
    p95 = float(calc_percentile(latencies, 95))
    acc = (correct_actions / len(items)) * 100.0
    valid_pct = (valid_json_count / len(items)) * 100.0

    summary = {
        "total": len(items),
        "correct": correct_actions,
        "accuracy_pct": round(acc, 2),
        "valid_json_pct": round(valid_pct, 2),
        "latency_p50_ms": round(p50, 2),
        "latency_p95_ms": round(p95, 2),
        "results": results
    }

    with open("eval/dev_40_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"HASIL EVALUASI 40 KALIMAT DEV:")
    print(f"- Akurasi Aksi    : {acc:.1f}% ({correct_actions}/{len(items)})")
    print(f"- Valid JSON      : {valid_pct:.1f}%")
    print(f"- Latensi p50     : {p50:.1f} ms")
    print(f"- Latensi p95     : {p95:.1f} ms")
    print("=" * 60)


if __name__ == "__main__":
    run_eval_40()
