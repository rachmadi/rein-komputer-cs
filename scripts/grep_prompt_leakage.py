# -*- coding: utf-8 -*-
import json
import glob
import os

with open("eval/parse_gold.jsonl", "r", encoding="utf-8") as f:
    gold_items = [json.loads(line) for line in f if line.strip()]

target_files = glob.glob("services/*.py")
print(f"Checking {len(gold_items)} gold sentences against {len(target_files)} service files...")

leaks = []
for item in gold_items:
    pesan = item["pesan"].strip()
    # Hindari kecocokan satu huruf/kata umum seperti 'p' atau 'halo'
    if len(pesan) < 3:
        continue
    for tf in target_files:
        with open(tf, "r", encoding="utf-8") as f:
            content = f.read()
        if pesan.lower() in content.lower():
            # Temukan baris tempat kemunculannya
            for lno, line in enumerate(content.splitlines(), 1):
                if pesan.lower() in line.lower():
                    leaks.append((item["id"], item["split"], pesan, tf, lno, line.strip()))

print(f"\nTotal phrase matches found: {len(leaks)}")
for item_id, split, pesan, tf, lno, line in leaks:
    print(f"[{split}] {item_id}: \"{pesan}\" -> {tf}:{lno}")
    print(f"   Line: {line}\n")
