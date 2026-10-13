# -*- coding: utf-8 -*-
"""
scripts/eval_dev_metrics.py
Evaluasi Parser LLM pada dataset Dev Bobby Computer.
- Akurasi aksi
- F1 / akurasi argumen dipisah:
  * Argumen terstruktur (enum, angka, kode): exact match
  * Argumen teks bebas (kebutuhan_teks, nilai, rujukan, persona): loose match (kata kunci inti)
- Tabel kesalahan argumen untuk produk, persona, kategori, topik.
- Latensi p50 dan p95.
"""
import sys
import os
import re
import json
import math
from typing import Any, Dict, List, Tuple

sys.path.append('.')
sys.stdout.reconfigure(encoding='utf-8')

from services.llm_parser import parse_user_message


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


STOPWORDS = {"dan", "atau", "di", "ke", "buat", "untuk", "yang", "aku", "saya", "mau", "nih", "ya", "sih", "aja", "dong", "ga", "gak"}

def extract_core_keywords(text: str) -> set[str]:
    if not text:
        return set()
    tokens = re.findall(r'[a-zA-Z0-9]+', str(text).lower())
    return {t for t in tokens if t not in STOPWORDS and len(t) > 1}


def compare_free_text(pred_val: Any, gold_val: Any) -> bool:
    """Loose matching deterministik untuk teks bebas tanpa LLM."""
    if pred_val is None and gold_val is None:
        return True
    if pred_val is None or gold_val is None:
        return False
    p_str = str(pred_val).strip().lower()
    g_str = str(gold_val).strip().lower()
    if p_str == g_str:
        return True
    # Substring containment
    if p_str in g_str or g_str in p_str:
        return True
    # Keyword token overlap
    p_kw = extract_core_keywords(p_str)
    g_kw = extract_core_keywords(g_str)
    if p_kw and g_kw and (p_kw & g_kw):
        return True
    return False


def normalize_val(val: Any) -> Any:
    if val is None:
        return None
    if hasattr(val, "value"):
        return val.value
    if isinstance(val, list):
        return [normalize_val(x) for x in val]
    return val


def compare_structured(pred_val: Any, gold_val: Any) -> bool:
    """Exact matching untuk argumen terstruktur (enum, angka, list kode/ref)."""
    p_norm = normalize_val(pred_val)
    g_norm = normalize_val(gold_val)
    if p_norm is None and g_norm is None:
        return True
    if p_norm is None or g_norm is None:
        return False
    if isinstance(g_norm, list) and isinstance(p_norm, list):
        return sorted([str(x).lower().strip() for x in p_norm]) == sorted([str(x).lower().strip() for x in g_norm])
    if str(p_norm).strip().lower() == str(g_norm).strip().lower():
        return True
    try:
        if float(p_norm) == float(g_norm):
            return True
    except (ValueError, TypeError):
        pass
    return False


def run_dev_evaluation(limit: int | None = None):
    gold_path = "eval/parse_gold.jsonl"
    items = []
    with open(gold_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            if data.get("split") == "dev":
                items.append(data)
                if limit and len(items) >= limit:
                    break

    print(f"=== Memulai Evaluasi Dev ({len(items)} items) ===")

    latencies = []
    valid_json_count = 0
    correct_actions = 0

    # Metrik per kategori argumen
    structured_slots = ["kategori", "merek", "merek_kecuali", "gpu", "min_harga", "max_harga", "ram_gb_min", "storage_gb_min", "ukuran_layar", "slot", "atribut", "jenis", "topik", "rujukan_produk", "produk"]
    free_text_slots = ["kebutuhan_teks", "nilai", "rujukan", "persona"]

    arg_stats = {
        "structured": {"tp": 0, "fp": 0, "fn": 0},
        "free_text": {"tp": 0, "fp": 0, "fn": 0}
    }

    # Tracking error per slot spesifik: produk, persona, kategori, topik
    target_focus_slots = ["produk", "rujukan_produk", "persona", "kategori", "topik"]
    argument_errors = []

    for idx, it in enumerate(items, 1):
        pesan = it["pesan"]
        state = it.get("state", {})
        gold_aksi = it["label_aksi"]
        gold_args = it.get("label_argumen", {})

        out, metrics = parse_user_message(pesan, state=state)
        pred_aksi = out.aksi.value
        dt = metrics.get("latency_ms", 0.0)
        latencies.append(dt)

        if metrics.get("json_valid", False):
            valid_json_count += 1

        is_act_correct = (pred_aksi == gold_aksi)
        if is_act_correct:
            correct_actions += 1

        pred_args = {k: v for k, v in out.argumen.model_dump().items() if v is not None}
        
        # Check structured slots
        all_keys = set(gold_args.keys()) | set(pred_args.keys())
        for k in all_keys:
            # Normalize rujukan_produk / produk
            is_prod_key = (k in ("produk", "rujukan_produk"))
            g_v = gold_args.get(k)
            p_v = pred_args.get(k)
            
            if is_prod_key:
                if "rujukan_produk" in gold_args:
                    g_v = gold_args.get("rujukan_produk")
                    p_v = pred_args.get("rujukan_produk")
                else:
                    g_v = gold_args.get("produk")
                    p_v = out.argumen.produk

            if k in structured_slots or is_prod_key:
                if g_v is not None and p_v is not None:
                    if compare_structured(p_v, g_v):
                        arg_stats["structured"]["tp"] += 1
                    else:
                        arg_stats["structured"]["fp"] += 1
                        arg_stats["structured"]["fn"] += 1
                        if k in target_focus_slots or is_prod_key:
                            argument_errors.append({
                                "no": idx, "pesan": pesan, "slot": "produk" if is_prod_key else k,
                                "prediksi": p_v, "gold": g_v, "tipe": "mismatch"
                            })
                elif g_v is not None and p_v is None:
                    arg_stats["structured"]["fn"] += 1
                    if k in target_focus_slots or is_prod_key:
                        argument_errors.append({
                            "no": idx, "pesan": pesan, "slot": "produk" if is_prod_key else k,
                            "prediksi": None, "gold": g_v, "tipe": "missing_pred"
                        })
                elif g_v is None and p_v is not None:
                    arg_stats["structured"]["fp"] += 1
                    if k in target_focus_slots or is_prod_key:
                        argument_errors.append({
                            "no": idx, "pesan": pesan, "slot": "produk" if is_prod_key else k,
                            "prediksi": p_v, "gold": None, "tipe": "extra_pred"
                        })

            elif k in free_text_slots:
                if g_v is not None and p_v is not None:
                    if compare_free_text(p_v, g_v):
                        arg_stats["free_text"]["tp"] += 1
                    else:
                        arg_stats["free_text"]["fp"] += 1
                        arg_stats["free_text"]["fn"] += 1
                        if k in target_focus_slots:
                            argument_errors.append({
                                "no": idx, "pesan": pesan, "slot": k,
                                "prediksi": p_v, "gold": g_v, "tipe": "mismatch"
                            })
                elif g_v is not None and p_v is None:
                    arg_stats["free_text"]["fn"] += 1
                    if k in target_focus_slots:
                        argument_errors.append({
                            "no": idx, "pesan": pesan, "slot": k,
                            "prediksi": None, "gold": g_v, "tipe": "missing_pred"
                        })
                elif g_v is None and p_v is not None:
                    arg_stats["free_text"]["fp"] += 1
                    if k in target_focus_slots:
                        argument_errors.append({
                            "no": idx, "pesan": pesan, "slot": k,
                            "prediksi": p_v, "gold": None, "tipe": "extra_pred"
                        })

        status_str = "OK" if is_act_correct else "ERR"
        print(f"[{idx:03d}/{len(items)}] {status_str} | '{pesan[:35]}' -> {pred_aksi} ({dt:.0f}ms)")

    p50 = calc_percentile(latencies, 50)
    p95 = calc_percentile(latencies, 95)
    acc = (correct_actions / len(items)) * 100.0
    valid_pct = (valid_json_count / len(items)) * 100.0

    def calc_f1(stats):
        tp, fp, fn = stats["tp"], stats["fp"], stats["fn"]
        prec = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        return prec * 100.0, rec * 100.0, f1 * 100.0

    prec_s, rec_s, f1_s = calc_f1(arg_stats["structured"])
    prec_f, rec_f, f1_f = calc_f1(arg_stats["free_text"])

    print("\n" + "="*50)
    print("HASIL EVALUASI DEV")
    print("="*50)
    print(f"Total Sampel       : {len(items)}")
    print(f"Akurasi Aksi       : {acc:.2f}% ({correct_actions}/{len(items)})")
    print(f"% JSON Valid       : {valid_pct:.2f}%")
    print(f"Latensi p50        : {p50:.1f} ms")
    print(f"Latensi p95        : {p95:.1f} ms")
    print("\n--- METRIK ARGUMEN TERPISAH ---")
    print(f"1. Argumen Terstruktur (Exact Match): Prec={prec_s:.1f}%, Rec={rec_s:.1f}%, F1={f1_s:.1f}%")
    print(f"2. Argumen Teks Bebas (Loose Match) : Prec={prec_f:.1f}%, Rec={rec_f:.1f}%, F1={f1_f:.1f}%")
    
    # Filter unique argument errors in focus slots
    seen_err = set()
    dedup_errs = []
    for err in argument_errors:
        sig = (err["pesan"], err["slot"], str(err["prediksi"]), str(err["gold"]))
        if sig not in seen_err:
            seen_err.add(sig)
            dedup_errs.append(err)

    print(f"\n--- TABEL KESALAHAN ARGUMEN (produk, persona, kategori, topik): Total {len(dedup_errs)} kesalahan ---")
    print(f"{'No':<4} | {'Slot':<10} | {'Kalimat':<32} | {'Prediksi':<20} | {'Gold':<20}")
    print("-" * 95)
    for err in dedup_errs:
        p_str = str(err['prediksi'])[:18]
        g_str = str(err['gold'])[:18]
        print(f"{err['no']:<4} | {err['slot']:<10} | {err['pesan'][:30]:<32} | {p_str:<20} | {g_str:<20}")

    output_summary = {
        "total": len(items),
        "accuracy_pct": round(acc, 2),
        "valid_json_pct": round(valid_pct, 2),
        "latency_p50_ms": round(p50, 1),
        "latency_p95_ms": round(p95, 1),
        "f1_structured_pct": round(f1_s, 1),
        "f1_free_text_pct": round(f1_f, 1),
        "argument_errors_focus": dedup_errs
    }

    with open("eval/dev_eval_report.json", "w", encoding="utf-8") as f:
        json.dump(output_summary, f, ensure_ascii=False, indent=2)

    return output_summary


if __name__ == "__main__":
    limit_arg = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_dev_evaluation(limit=limit_arg)
