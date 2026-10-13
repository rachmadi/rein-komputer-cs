# -*- coding: utf-8 -*-
"""
scripts/eval_heldout_and_dev.py
Evaluasi komprehensif Parser LLM Antigravity v2:
1. 50 Kalimat Held-Out (Evaluasi satu kali):
   - Akurasi Aksi
   - F1 Argumen per Slot
   - % JSON Valid
   - % tidak_jelas
   - Matriks Kebingungan (Confusion Matrix)
   - Rincian Kesalahan Satu per Satu
2. 40 Kalimat Dev:
   - Terpisah antara yang ada di few-shot (18 item) dan yang bukan (22 item).
3. Pengukuran Latensi (p50 & p95)
"""
import sys
import os
sys.path.append('.')
sys.stdout.reconfigure(encoding='utf-8')
import json
import time
import math
from collections import defaultdict, Counter

from services.llm_parser import parse_user_message, DEV_FEW_SHOTS


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


def normalize_val(v):
    if v is None:
        return None
    if isinstance(v, (list, tuple)):
        return sorted([str(x).lower().strip() for x in v if x is not None])
    if isinstance(v, dict):
        return {str(k).lower(): normalize_val(val) for k, val in v.items()}
    if hasattr(v, 'value'):
        return str(v.value).lower().strip()
    return str(v).lower().strip()


def run_evaluation():
    # 1. Muat dataset parse_gold.jsonl
    dev_items = []
    held_out_items = []
    with open("eval/parse_gold.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("split") == "dev":
                dev_items.append(item)
            elif item.get("split") == "held-out":
                held_out_items.append(item)

    # Identifikasi teks yang ada di few-shot prompt
    few_shot_texts = set()
    for fs in DEV_FEW_SHOTS:
        if fs.get("role") == "user":
            content = fs.get("content", "")
            # Ekstrak pesan di dalam tanda kutip
            if 'Pesan: "' in content:
                msg = content.split('Pesan: "')[1].split('"\nState:')[0]
                few_shot_texts.add(msg.lower().strip())

    print(f"Loaded {len(dev_items)} dev items and {len(held_out_items)} held-out items.")
    print(f"Identified {len(few_shot_texts)} unique few-shot prompt examples.\n")

    # =========================================================================
    # PART 1: EVALUASI 50 HELD-OUT ITEMS
    # =========================================================================
    print("=" * 70)
    print("MENJALANKAN EVALUASI 50 KALIMAT HELD-OUT (BEKU TANPA MODIFIKASI PROMPT)...")
    print("=" * 70)

    ho_results = []
    ho_latencies = []
    ho_actions_correct = 0
    ho_json_valid_count = 0
    ho_tidak_jelas_count = 0

    # Untuk confusion matrix
    all_actions = [
        "sapa", "cari_produk", "minta_rekomendasi", "jawab_pertanyaan_bot",
        "evaluasi_kecocokan", "tanya_spesifikasi", "bandingkan", "lanjutan_hasil",
        "tanya_info_toko", "perbaiki_percakapan", "basa_basi", "tidak_jelas"
    ]
    confusion_matrix = defaultdict(lambda: defaultdict(int))

    # Untuk F1 argumen per slot
    slot_stats = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    ho_errors = []

    for idx, it in enumerate(held_out_items, 1):
        pesan = it["pesan"]
        state = it.get("state", {})
        gold_aksi = it["label_aksi"]
        gold_args = it.get("label_argumen", {})

        print(f"[HeldOut {idx}/50] '{pesan}' ...", end="", flush=True)
        out, met = parse_user_message(pesan, state=state)
        pred_aksi = out.aksi.value
        dt = met["latency_ms"]
        ho_latencies.append(dt)

        if met.get("json_valid", False):
            ho_json_valid_count += 1
        if pred_aksi == "tidak_jelas":
            ho_tidak_jelas_count += 1

        is_action_correct = (pred_aksi == gold_aksi)
        if is_action_correct:
            ho_actions_correct += 1

        confusion_matrix[gold_aksi][pred_aksi] += 1

        # Hitung slot F1
        pred_args_raw = {k: v for k, v in out.argumen.model_dump().items() if v is not None}
        all_arg_keys = set(gold_args.keys()) | set(pred_args_raw.keys())

        item_arg_match = True
        for k in all_arg_keys:
            gv = normalize_val(gold_args.get(k))
            pv = normalize_val(pred_args_raw.get(k))

            if gv is not None and pv is not None:
                if gv == pv:
                    slot_stats[k]["tp"] += 1
                else:
                    slot_stats[k]["fp"] += 1
                    slot_stats[k]["fn"] += 1
                    item_arg_match = False
            elif gv is not None and pv is None:
                slot_stats[k]["fn"] += 1
                item_arg_match = False
            elif gv is None and pv is not None:
                slot_stats[k]["fp"] += 1
                item_arg_match = False

        status_sym = "[BENAR]" if is_action_correct else "[SALAH]"
        print(f" {status_sym} (pred: {pred_aksi} vs gold: {gold_aksi}) in {dt:.0f}ms")

        record = {
            "no": idx,
            "id": it["id"],
            "pesan": pesan,
            "pred_aksi": pred_aksi,
            "gold_aksi": gold_aksi,
            "pred_args": pred_args_raw,
            "gold_args": gold_args,
            "benar_aksi": is_action_correct,
            "benar_args": item_arg_match,
            "latency_ms": dt,
            "json_valid": met.get("json_valid", False)
        }
        ho_results.append(record)

        if not is_action_correct:
            ho_errors.append(record)

    ho_acc = (ho_actions_correct / len(held_out_items)) * 100.0
    ho_valid_json_pct = (ho_json_valid_count / len(held_out_items)) * 100.0
    ho_tidak_jelas_pct = (ho_tidak_jelas_count / len(held_out_items)) * 100.0
    ho_p50 = calc_percentile(ho_latencies, 50)
    ho_p95 = calc_percentile(ho_latencies, 95)

    # Hitung F1 per slot
    slot_f1_summary = {}
    for slot_name, s in slot_stats.items():
        tp = s["tp"]
        fp = s["fp"]
        fn = s["fn"]
        prec = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        slot_f1_summary[slot_name] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(prec, 3),
            "recall": round(rec, 3),
            "f1": round(f1, 3)
        }

    # =========================================================================
    # PART 2: EVALUASI 40 KALIMAT DEV (PISAHKAN FEW-SHOT VS NON-FEW-SHOT)
    # =========================================================================
    print("\n" + "=" * 70)
    print("MENJALANKAN EVALUASI 40 KALIMAT DEV (PEMISAHAN FEW-SHOT VS NON-FEW-SHOT)...")
    print("=" * 70)

    dev_40 = dev_items[:40]
    dev_results = []
    dev_latencies = []
    dev_fs_correct = 0
    dev_fs_total = 0
    dev_non_fs_correct = 0
    dev_non_fs_total = 0

    for idx, it in enumerate(dev_40, 1):
        pesan = it["pesan"]
        state = it.get("state", {})
        gold_aksi = it["label_aksi"]
        is_few_shot = (pesan.lower().strip() in few_shot_texts)

        out, met = parse_user_message(pesan, state=state)
        pred_aksi = out.aksi.value
        dt = met["latency_ms"]
        dev_latencies.append(dt)

        is_correct = (pred_aksi == gold_aksi)
        if is_few_shot:
            dev_fs_total += 1
            if is_correct:
                dev_fs_correct += 1
        else:
            dev_non_fs_total += 1
            if is_correct:
                dev_non_fs_correct += 1

        tag = "FEW-SHOT" if is_few_shot else "NON-FEW-SHOT"
        status_sym = "[BENAR]" if is_correct else "[SALAH]"
        print(f"[Dev {idx}/40][{tag}] '{pesan}' ... {status_sym} ({pred_aksi} vs {gold_aksi}) in {dt:.0f}ms")

        dev_results.append({
            "no": idx,
            "id": it["id"],
            "pesan": pesan,
            "is_few_shot": is_few_shot,
            "pred_aksi": pred_aksi,
            "gold_aksi": gold_aksi,
            "benar": is_correct,
            "latency_ms": dt
        })

    dev_p50 = calc_percentile(dev_latencies, 50)
    dev_p95 = calc_percentile(dev_latencies, 95)
    fs_acc = (dev_fs_correct / dev_fs_total * 100.0) if dev_fs_total > 0 else 0.0
    non_fs_acc = (dev_non_fs_correct / dev_non_fs_total * 100.0) if dev_non_fs_total > 0 else 0.0
    dev_total_acc = ((dev_fs_correct + dev_non_fs_correct) / len(dev_40)) * 100.0

    # Simpan laporan lengkap
    report = {
        "held_out": {
            "total": len(held_out_items),
            "correct_actions": ho_actions_correct,
            "accuracy_pct": round(ho_acc, 2),
            "valid_json_pct": round(ho_valid_json_pct, 2),
            "tidak_jelas_pct": round(ho_tidak_jelas_pct, 2),
            "latency_p50_ms": round(ho_p50, 2),
            "latency_p95_ms": round(ho_p95, 2),
            "slot_f1": slot_f1_summary,
            "confusion_matrix": confusion_matrix,
            "errors": ho_errors,
            "results": ho_results
        },
        "dev_40": {
            "total": len(dev_40),
            "total_accuracy_pct": round(dev_total_acc, 2),
            "few_shot": {
                "total": dev_fs_total,
                "correct": dev_fs_correct,
                "accuracy_pct": round(fs_acc, 2)
            },
            "non_few_shot": {
                "total": dev_non_fs_total,
                "correct": dev_non_fs_correct,
                "accuracy_pct": round(non_fs_acc, 2)
            },
            "latency_p50_ms": round(dev_p50, 2),
            "latency_p95_ms": round(dev_p95, 2),
            "results": dev_results
        }
    }

    with open("eval/heldout_eval_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print("HASIL LENGKAP EVALUASI:")
    print("1. HELD-OUT SET (50 KALIMAT):")
    print(f"   - Akurasi Aksi    : {ho_acc:.1f}% ({ho_actions_correct}/50)")
    print(f"   - Valid JSON      : {ho_valid_json_pct:.1f}%")
    print(f"   - % tidak_jelas   : {ho_tidak_jelas_pct:.1f}%")
    print(f"   - Latensi p50     : {ho_p50:.1f} ms")
    print(f"   - Latensi p95     : {ho_p95:.1f} ms")
    print(f"   - Total Kesalahan : {len(ho_errors)}")
    print("\n2. DEV SET (40 KALIMAT):")
    print(f"   - Total Akurasi   : {dev_total_acc:.1f}% ({dev_fs_correct + dev_non_fs_correct}/40)")
    print(f"   - Subgrup Few-Shot: {fs_acc:.1f}% ({dev_fs_correct}/{dev_fs_total})")
    print(f"   - Subgrup Non-FS  : {non_fs_acc:.1f}% ({dev_non_fs_correct}/{dev_non_fs_total})")
    print(f"   - Latensi p50     : {dev_p50:.1f} ms")
    print(f"   - Latensi p95     : {dev_p95:.1f} ms")
    print("=" * 70)


if __name__ == "__main__":
    run_evaluation()
