# -*- coding: utf-8 -*-
"""
scripts/recalc_heldout_metrics.py
Menghitung ulang presisi, recall, dan F1 argumen pada 50 held-out items dengan aturan:
1. ho-005, ho-025, ho-026: normalisasi nomor urut/ordinal ke kode produk berdasarkan produk_tampil.
2. ho-043: pencocokan longgar konsisten (token overlap / containment) untuk teks bebas (persona, kebutuhan_teks, nilai).
3. ho-003: laporkan sebagai kemungkinan masalah label, gold tetap dipertahankan.
4. Argumen terstruktur (kategori, merek, gpu, atribut, dll): exact match.
"""
import csv
import json
import re
from collections import defaultdict

def normalize_text_tokens(text: str) -> set:
    if not text:
        return set()
    cleaned = re.sub(r"[^\w\s]", " ", str(text).lower())
    return set(cleaned.split())

def is_loose_match(gold_val, pred_val) -> bool:
    if gold_val is None or pred_val is None:
        return False
    g_str = str(gold_val).strip().lower()
    p_str = str(pred_val).strip().lower()
    if g_str == p_str:
        return True
    # Containment / substring
    if g_str in p_str or p_str in g_str:
        return True
    # Token Jaccard overlap
    g_tok = normalize_text_tokens(g_str)
    p_tok = normalize_text_tokens(p_str)
    if not g_tok or not p_tok:
        return False
    if g_tok.issubset(p_tok) or p_tok.issubset(g_tok):
        return True
    overlap = len(g_tok & p_tok)
    return (overlap / len(g_tok)) >= 0.5

def resolve_ordinal_to_code(val, produk_tampil_list):
    # Jika val adalah int atau digit string
    val_str = str(val).strip().lower()
    if val_str.isdigit():
        idx = int(val_str) - 1
        if 0 <= idx < len(produk_tampil_list):
            return produk_tampil_list[idx].get("kode", val_str)
    # Jika list
    if isinstance(val, list):
        res = []
        for x in val:
            res.append(resolve_ordinal_to_code(x, produk_tampil_list))
        return res
    return val_str

def main():
    # Muat held-out dari docs/ablation_study_results.json atau eval/held_out_raw_results.json
    results_file = "docs/ablation_study_results.json"
    with open(results_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Ambil items held-out kondisi (b)
    ho_items = data.get("held_out_b", {}).get("items", [])
    if not ho_items:
        print("Tidak menemukan held-out items di ablation results.")
        return

    # Ambil info produk_tampil asli dari eval/parse_gold.csv
    produk_tampil_map = {}
    with open("eval/parse_gold.csv", "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("id"):
                pt_raw = r.get("produk_tampil", "")
                try:
                    pt_list = json.loads(pt_raw) if pt_raw else []
                except:
                    pt_list = []
                produk_tampil_map[r["id"]] = pt_list

    slot_counts = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    free_text_slots = {"persona", "kebutuhan_teks", "nilai", "rujukan", "alasan"}

    detailed_errors = []

    for item in ho_items:
        item_id = item["id"]
        pt_list = produk_tampil_map.get(item_id, [])
        gold_args = dict(item.get("gold_args") or {})
        pred_args = dict(item.get("pred_args") or {})

        # 1. Normalisasi ordinal pada rujukan produk / produk dan unifikasi ke 'produk'
        for p_dict in [gold_args, pred_args]:
            if "rujukan_produk" in p_dict and "produk" not in p_dict:
                p_dict["produk"] = p_dict.pop("rujukan_produk")
            elif "rujukan_produk" in p_dict and "produk" in p_dict:
                p_dict.pop("rujukan_produk")

        if "produk" in gold_args:
            gold_args["produk"] = resolve_ordinal_to_code(gold_args["produk"], pt_list)
        if "produk" in pred_args:
            pred_args["produk"] = resolve_ordinal_to_code(pred_args["produk"], pt_list)

        all_keys = set(gold_args.keys()) | set(pred_args.keys())
        for k in all_keys:
            gv = gold_args.get(k)
            pv = pred_args.get(k)

            if gv is not None and pv is not None:
                # Periksa kecocokan
                if k in free_text_slots:
                    matched = is_loose_match(gv, pv)
                else:
                    # Normalisasi tipe dan case
                    g_clean = str(gv).strip().lower()
                    p_clean = str(pv).strip().lower()
                    matched = (g_clean == p_clean)

                if matched:
                    slot_counts[k]["tp"] += 1
                else:
                    slot_counts[k]["fp"] += 1
                    slot_counts[k]["fn"] += 1
                    detailed_errors.append({
                        "id": item_id,
                        "slot": k,
                        "gold": gv,
                        "pred": pv,
                        "type": "mismatch"
                    })
            elif gv is not None and pv is None:
                slot_counts[k]["fn"] += 1
                detailed_errors.append({
                    "id": item_id,
                    "slot": k,
                    "gold": gv,
                    "pred": None,
                    "type": "missing_prediction (FN)"
                })
            elif gv is None and pv is not None:
                slot_counts[k]["fp"] += 1
                detailed_errors.append({
                    "id": item_id,
                    "slot": k,
                    "gold": None,
                    "pred": pv,
                    "type": "unexpected_prediction (FP)"
                })

    print("=" * 80)
    print("HASIL HITUNG ULANG METRIK ARGUMEN HELD-OUT (50 ITEMS) DENGAN ATURAN TERNORMALISASI")
    print("=" * 80)
    print(f"{'Slot':<20} | {'TP':<4} | {'FP':<4} | {'FN':<4} | {'Presisi':<9} | {'Recall':<9} | {'F1':<9}")
    print("-" * 80)

    total_tp = 0
    total_fp = 0
    total_fn = 0

    for slot, c in sorted(slot_counts.items()):
        tp, fp, fn = c["tp"], c["fp"], c["fn"]
        total_tp += tp
        total_fp += fp
        total_fn += fn
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        print(f"{slot:<20} | {tp:<4} | {fp:<4} | {fn:<4} | {prec*100:>8.2f}% | {rec*100:>8.2f}% | {f1*100:>8.2f}%")

    tot_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    tot_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    tot_f1 = (2 * tot_prec * tot_rec) / (tot_prec + tot_rec) if (tot_prec + tot_rec) > 0 else 0.0

    print("-" * 80)
    print(f"{'TOTAL MIKRO':<20} | {total_tp:<4} | {total_fp:<4} | {total_fn:<4} | {tot_prec*100:>8.2f}% | {tot_rec*100:>8.2f}% | {tot_f1*100:>8.2f}%")
    print("=" * 80)

    print("\nDAFTAR KESALAHAN ARGUMEN YANG TERSISA:")
    for err in detailed_errors:
        print(f"- [{err['id']}] Slot '{err['slot']}': Gold={err['gold']} | Pred={err['pred']} ({err['type']})")

if __name__ == "__main__":
    main()
