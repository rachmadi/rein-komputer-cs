# -*- coding: utf-8 -*-
import json
import csv

print("=== EVALUASI KESALAHAN ARGUMEN PARSER (produk, persona, kategori, topik) ===")
arg_slots = ["produk", "persona", "kategori", "topik"]
slot_counts = {s: {"total_gold": 0, "correct": 0, "pred_total": 0, "errors": []} for s in arg_slots}

with open("eval/heldout_v1_rerun_clean.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        item_id = row["id"]
        pesan = row["pesan"]
        gold_args = json.loads(row["gold_args"])
        pred_args = json.loads(row["pred_args"])

        for slot in arg_slots:
            g_val = gold_args.get(slot)
            p_val = pred_args.get(slot)

            if g_val is not None:
                slot_counts[slot]["total_gold"] += 1
            if p_val is not None:
                slot_counts[slot]["pred_total"] += 1

            if g_val is not None or p_val is not None:
                match = False
                if g_val is not None and p_val is not None:
                    if slot == "produk":
                        g_set = set(str(x) for x in (g_val if isinstance(g_val, list) else [g_val]))
                        p_set = set(str(x) for x in (p_val if isinstance(p_val, list) else [p_val]))
                        match = (g_set == p_set)
                    else:
                        match = (str(g_val).lower().strip() == str(p_val).lower().strip())

                if match:
                    slot_counts[slot]["correct"] += 1
                else:
                    slot_counts[slot]["errors"].append({
                        "id": item_id,
                        "pesan": pesan,
                        "slot": slot,
                        "gold": g_val,
                        "pred": p_val
                    })

for slot, data in slot_counts.items():
    precision = (data["correct"] / data["pred_total"]) if data["pred_total"] > 0 else 1.0
    recall = (data["correct"] / data["total_gold"]) if data["total_gold"] > 0 else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    print(f"\nSlot: {slot.upper()} | Gold: {data['total_gold']} | Pred: {data['pred_total']} | Correct: {data['correct']} | P: {precision:.2f} | R: {recall:.2f} | F1: {f1:.2f}")
    if data["errors"]:
        print(f"  Daftar Kesalahan ({len(data['errors'])} item):")
        for err in data["errors"]:
            print(f"  - [{err['id']}] \"{err['pesan']}\" -> Gold: {err['gold']} | Pred: {err['pred']}")
    else:
        print("  Tidak ada kesalahan!")
