# -*- coding: utf-8 -*-
"""
scripts/eval_point_9.py
Menjalankan evaluasi Poin 9:
1. Re-run 50 kalimat held-out v1 dengan prompt bersih gemma4:e4b, simpan CSV per item dan diff terhadap run sebelumnya.
2. Re-run 7 kalimat dev yang sempat salah:
   - dengan konteks lengkap di input
   - evaluasi gemma4:e4b
   - bandingkan dengan model lebih kuat (qwen2.5-coder:7b)
   - klasifikasikan penyebab kesalahan: definisi ambigu / konteks kurang / batas model
"""
import sys
import os
import json
import csv
import time
from typing import Any, Dict, List

sys.path.append('.')
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from services.llm_parser import parse_user_message, PARSER_MODEL
from services.schema_actions import ParserOutput

DEV_7_IDS = ["dev-003", "dev-004", "dev-005", "dev-006", "dev-010", "dev-016", "dev-030"]

BOT_HISTORY_MAPPING = {
    "dev-003": [{"role": "assistant", "content": "Kira-kira perangkat ini akan digunakan untuk aktivitas apa ya Kak?"}],
    "dev-004": [{"role": "assistant", "content": "Baik Kak, dicatat untuk kebutuhan hiburan nonton YouTube."}],
    "dev-005": [{"role": "assistant", "content": "Halo Kak, ada yang bisa kami bantu carikan di Bobby Computer?"}],
    "dev-006": [{"role": "assistant", "content": "Berikut 2 pilihan laptop yang kami rekomendasikan:"}],
    "dev-010": [],
    "dev-016": [{"role": "assistant", "content": "Untuk siapa laptop ini akan digunakan Kak?"}],
    "dev-030": [{"role": "assistant", "content": "Ada spesifikasi atau budget yang ingin dicari?"}]
}


def run_heldout_rerun():
    print("=" * 80)
    print("1. MENJALANKAN ULANG 50 HELD-OUT V1 DENGAN PROMPT BERSIH (gemma4:e4b)")
    print("=" * 80)

    # Muat held-out items dari parse_gold.jsonl
    heldout_items = []
    with open("eval/parse_gold.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("split") == "held-out-v1-terpakai":
                heldout_items.append(item)

    print(f"Total held-out v1 items: {len(heldout_items)}")

    # Muat run sebelumnya jika ada
    prev_errors = {}
    try:
        with open("eval/heldout_eval_report.json", "r", encoding="utf-8") as f:
            prev_rep = json.load(f)
            for err in prev_rep.get("held_out", {}).get("errors", []):
                prev_errors[err["id"]] = err
    except Exception as e:
        print(f"Info: Tidak dapat memuat report sebelumnya: {e}")

    results = []
    correct_count = 0
    csv_rows = []

    for i, it in enumerate(heldout_items, 1):
        item_id = it["id"]
        pesan = it["pesan"]
        state = it.get("state", {})
        gold_aksi = it["label_aksi"]
        gold_args = it.get("label_argumen", {})

        t0 = time.perf_counter()
        parsed, metrics = parse_user_message(pesan, state=state, model=PARSER_MODEL)
        lat_ms = metrics.get("latency_ms", (time.perf_counter() - t0) * 1000.0)

        pred_aksi = parsed.aksi.value
        pred_args = {k: v for k, v in parsed.argumen.model_dump().items() if v is not None}
        is_correct = (pred_aksi == gold_aksi)
        if is_correct:
            correct_count += 1

        rec = {
            "no": i,
            "id": item_id,
            "pesan": pesan,
            "gold_aksi": gold_aksi,
            "pred_aksi": pred_aksi,
            "benar_aksi": is_correct,
            "gold_args": gold_args,
            "pred_args": pred_args,
            "latency_ms": lat_ms,
            "retried": metrics.get("retried", False)
        }
        results.append(rec)

        csv_rows.append([
            item_id,
            pesan,
            gold_aksi,
            pred_aksi,
            "BENAR" if is_correct else "SALAH",
            json.dumps(gold_args, ensure_ascii=False),
            json.dumps(pred_args, ensure_ascii=False),
            round(lat_ms, 1),
            "ya" if metrics.get("retried") else "tidak"
        ])

        status_str = "✅" if is_correct else "❌"
        print(f"[{i:02d}/50] {status_str} {item_id}: '{pesan}' -> Pred: {pred_aksi} | Gold: {gold_aksi} ({lat_ms:.0f}ms)")

    # Simpan ke CSV
    csv_headers = ["id", "pesan", "gold_aksi", "pred_aksi", "benar_salah", "gold_args", "pred_args", "latensi_ms", "retried"]
    os.makedirs("eval", exist_ok=True)
    csv_path = "eval/heldout_v1_rerun_clean.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(csv_headers)
        writer.writerows(csv_rows)

    acc_pct = (correct_count / len(heldout_items)) * 100.0
    print(f"\nHeld-out v1 Re-run Akurasi: {correct_count}/{len(heldout_items)} ({acc_pct:.1f}%)")
    print(f"CSV disimpan ke: {csv_path}")

    # Tampilkan diff terhadap run sebelumnya
    print("\n--- DIFF TERHADAP RUN SEBELUMNYA (47/50) ---")
    current_errors = {r["id"]: r for r in results if not r["benar_aksi"]}
    print(f"Error Sebelumnya: {len(prev_errors)} item -> {list(prev_errors.keys())}")
    print(f"Error Sekarang: {len(current_errors)} item -> {list(current_errors.keys())}")

    for cid, cur_err in current_errors.items():
        if cid in prev_errors:
            print(f"  [TETAP SALAH] {cid}: '{cur_err['pesan']}' | Gold: {cur_err['gold_aksi']} | Pred Lama: {prev_errors[cid]['pred_aksi']} | Pred Baru: {cur_err['pred_aksi']}")
        else:
            print(f"  [BARU SALAH] {cid}: '{cur_err['pesan']}' | Gold: {cur_err['gold_aksi']} | Pred Baru: {cur_err['pred_aksi']}")

    for pid, p_err in prev_errors.items():
        if pid not in current_errors:
            print(f"  [MEMBAIK/LULUS] {pid}: '{p_err['pesan']}' | Gold: {p_err['gold_aksi']} | Sebelumnya salah ({p_err['pred_aksi']}) sekarang BENAR!")

    return results


def run_dev_7_errors_comparison():
    print("\n" + "=" * 80)
    print("2. EVALUASI 7 KESALAHAN DEV DENGAN KONTEKS LENGKAP & MODEL LEBIH KUAT")
    print("=" * 80)

    # Muat 7 items dari parse_gold.jsonl
    target_items = []
    with open("eval/parse_gold.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("id") in DEV_7_IDS:
                target_items.append(item)

    stronger_model = "qwen2.5-coder:7b"
    print(f"Total target dev items to test: {len(target_items)}")

    # 1. Jalankan semua item dengan gemma4:e4b
    print("\n--- Phase A: Running gemma4:e4b ---")
    gemma_results = {}
    for it in target_items:
        item_id = it["id"]
        pesan = it["pesan"]
        state = it.get("state", {})
        history = BOT_HISTORY_MAPPING.get(item_id, [])
        print(f"Testing gemma4:e4b on {item_id}: '{pesan}'...", flush=True)
        parsed_gemma, m_gemma = parse_user_message(
            pesan, state=state, history=history, model=PARSER_MODEL, timeout=60.0
        )
        gemma_results[item_id] = parsed_gemma.aksi.value
        print(f"  -> Pred: {parsed_gemma.aksi.value}", flush=True)

    # 2. Jalankan semua item dengan qwen2.5-coder:7b
    print("\n--- Phase B: Running qwen2.5-coder:7b ---")
    qwen_results = {}
    for it in target_items:
        item_id = it["id"]
        pesan = it["pesan"]
        state = it.get("state", {})
        history = BOT_HISTORY_MAPPING.get(item_id, [])
        print(f"Testing {stronger_model} on {item_id}: '{pesan}'...", flush=True)
        parsed_strong, m_strong = parse_user_message(
            pesan, state=state, history=history, model=stronger_model, timeout=90.0
        )
        qwen_results[item_id] = parsed_strong.aksi.value
        print(f"  -> Pred: {parsed_strong.aksi.value}", flush=True)

    # 3. Klasifikasi perbandingan
    comparison_results = []
    for it in target_items:
        item_id = it["id"]
        pesan = it["pesan"]
        state = it.get("state", {})
        gold_aksi = it["label_aksi"]
        gold_args = it.get("label_argumen", {})
        pred_gemma = gemma_results.get(item_id, "tidak_jelas")
        pred_strong = qwen_results.get(item_id, "tidak_jelas")

        correct_gemma = (pred_gemma == gold_aksi)
        correct_strong = (pred_strong == gold_aksi)

        if correct_gemma:
            klasifikasi = "terselesaikan_lewat_konteks"
            penjelasan = "Dengan konteks lengkap (history bot/state consistency), gemma4:e4b berhasil memprediksi aksi dengan benar."
        elif correct_strong and not correct_gemma:
            klasifikasi = "batas_model"
            penjelasan = f"gemma4:e4b gagal ({pred_gemma}), tetapi {stronger_model} berhasil ({pred_strong}) dengan prompt & konteks yang sama persis."
        else:
            if gold_aksi == "jawab_pertanyaan_bot" and not state.get("pending_question"):
                klasifikasi = "konteks_kurang"
                penjelasan = "State tidak memiliki pending_question yang valid sehingga jawab_pertanyaan_bot ditolak oleh aturan state."
            else:
                klasifikasi = "definisi_ambigu"
                penjelasan = f"Kedua model memilih {pred_gemma} / {pred_strong}; batas definisi aksi antara {gold_aksi} dan prediksi memerlukan panduan skema lebih eksplisit."

        rec = {
            "id": item_id,
            "pesan": pesan,
            "gold_aksi": gold_aksi,
            "gold_args": gold_args,
            "pred_gemma4": pred_gemma,
            "benar_gemma4": correct_gemma,
            "pred_qwen7b": pred_strong,
            "benar_qwen7b": correct_strong,
            "klasifikasi_penyebab": klasifikasi,
            "penjelasan": penjelasan
        }
        comparison_results.append(rec)
        print(f"\n[{item_id}] '{pesan}' (Gold: {gold_aksi}):")
        print(f"  - gemma4:e4b   : {pred_gemma} ({'✅' if correct_gemma else '❌'})")
        print(f"  - {stronger_model}: {pred_strong} ({'✅' if correct_strong else '❌'})")
        print(f"  -> Klasifikasi : {klasifikasi}")

    # Simpan hasil perbandingan ke JSON
    out_path = "eval/dev_7_errors_comparison.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(comparison_results, f, indent=2, ensure_ascii=False)
    print(f"\nHasil perbandingan 7 dev errors disimpan ke: {out_path}", flush=True)


if __name__ == "__main__":
    if not os.path.exists("eval/heldout_v1_rerun_clean.csv"):
        run_heldout_rerun()
    else:
        print("eval/heldout_v1_rerun_clean.csv sudah ada, melewati run heldout v1.")
    run_dev_7_errors_comparison()

