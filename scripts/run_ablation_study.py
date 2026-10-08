# -*- coding: utf-8 -*-
"""
scripts/run_ablation_study.py
Studi Ablasi Prompt NLU Parser (Antigravity v2):
Kondisi (a): Definisi saja (0 few-shot)
Kondisi (b): Definisi + 8 contoh sintetis (batas antar-aksi)
Kondisi (c): Definisi + 14 contoh lama (few-shot log/screenshot)

Metrik:
- Akurasi aksi
- F1 argumen terstruktur (exact match)
- F1 argumen teks bebas (loose keyword overlap)
- Analisis kesalahan per slot & klasifikasi penyebab kegagalan:
  [definisi ambigu | konteks kurang | batas model]
- Celah generalisasi:
  * Dev vs Held-out (50 item)
  * Few-shot vs Non-few-shot
"""
import sys
import os
import re
import json
import math
import time
from typing import Any, Dict, List, Tuple

sys.path.append('.')
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from services.llm_parser import (
    parse_user_message,
    SYNTHETIC_8_BOUNDARY_FEW_SHOTS
)

OLD_14_FEW_SHOTS = [
    {"role": "user", "content": "Pesan: \"halo\"\nState: {\"pending_question\": null, \"produk_tampil\": []}"},
    {"role": "assistant", "content": json.dumps({"aksi": "sapa", "argumen": {}, "pembaruan_state": {}})},
    {"role": "user", "content": "Pesan: \"jual laptop acer?\"\nState: {\"pending_question\": null, \"produk_tampil\": []}"},
    {"role": "assistant", "content": json.dumps({"aksi": "cari_produk", "argumen": {"kategori": "laptop", "merek": "acer"}, "pembaruan_state": {"kategori": "laptop"}})},
    {"role": "user", "content": "Pesan: \"pc dekstop gaming rtx 4060\"\nState: {\"pending_question\": null, \"produk_tampil\": []}"},
    {"role": "assistant", "content": json.dumps({"aksi": "cari_produk", "argumen": {"kategori": "desktop", "gpu": "rtx 4060"}, "pembaruan_state": {"kategori": "desktop"}})},
    {"role": "user", "content": "Pesan: \"Buat mama sih bukan buat aku\"\nState: {\"pending_question\": \"kebutuhan\", \"produk_tampil\": []}"},
    {"role": "assistant", "content": json.dumps({"aksi": "jawab_pertanyaan_bot", "argumen": {"slot": "persona", "nilai": "mama"}, "pembaruan_state": {"persona": "mama", "sebutan": "mama"}})},
    {"role": "user", "content": "Pesan: \"Untuk ibu saya yang sudah sepuh\"\nState: {\"pending_question\": \"kebutuhan\", \"produk_tampil\": []}"},
    {"role": "assistant", "content": json.dumps({"aksi": "jawab_pertanyaan_bot", "argumen": {"slot": "persona", "nilai": "ibu sepuh"}, "pembaruan_state": {"persona": "ibu sepuh", "sebutan": "ibu"}})},
    {"role": "user", "content": "Pesan: \"Paling cuma cari resep dan nonton youtube\"\nState: {\"pending_question\": \"aktivitas\", \"slot_diketahui\": {\"persona\": \"mama\"}, \"produk_tampil\": []}"},
    {"role": "assistant", "content": json.dumps({"aksi": "minta_rekomendasi", "argumen": {"kebutuhan_teks": "cari resep dan nonton YouTube", "persona": "mama"}, "pembaruan_state": {"kebutuhan_teks": "cari resep dan nonton YouTube"}})},
    {"role": "user", "content": "Pesan: \"Emang spek segitu cukup?\"\nState: {\"pending_question\": null, \"produk_tampil\": [{\"no\": 1, \"kode\": \"KB-L01\"}, {\"no\": 2, \"kode\": \"KB-L02\"}, {\"no\": 3, \"kode\": \"KB-L03\"}], \"slot_diketahui\": {\"kebutuhan_teks\": \"cari resep dan nonton YouTube\"}}"},
    {"role": "assistant", "content": json.dumps({"aksi": "evaluasi_kecocokan", "argumen": {"rujukan_produk": [1, 2, 3], "kebutuhan_teks": "cari resep dan nonton YouTube"}, "pembaruan_state": {}})},
    {"role": "user", "content": "Pesan: \"yang kedua bagus nggak?\"\nState: {\"pending_question\": null, \"produk_tampil\": [{\"no\": 1, \"kode\": \"KB-L01\"}, {\"no\": 2, \"kode\": \"KB-L02\"}]}"},
    {"role": "assistant", "content": json.dumps({"aksi": "evaluasi_kecocokan", "argumen": {"rujukan_produk": [2]}, "pembaruan_state": {}})},
    {"role": "user", "content": "Pesan: \"layarnya udah ips?\"\nState: {\"pending_question\": null, \"produk_tampil\": [{\"no\": 1, \"kode\": \"KB-L01\"}]}"},
    {"role": "assistant", "content": json.dumps({"aksi": "tanya_spesifikasi", "argumen": {"rujukan_produk": [1], "atribut": "layar"}, "pembaruan_state": {}})},
    {"role": "user", "content": "Pesan: \"bagusan nomor 1 apa nomor 2?\"\nState: {\"pending_question\": null, \"produk_tampil\": [{\"no\": 1, \"kode\": \"KB-L01\"}, {\"no\": 2, \"kode\": \"KB-L02\"}]}"},
    {"role": "assistant", "content": json.dumps({"aksi": "bandingkan", "argumen": {"rujukan_produk": [1, 2]}, "pembaruan_state": {}})},
    {"role": "user", "content": "Pesan: \"ada opsi merk lain ga selain acer?\"\nState: {\"pending_question\": null, \"produk_tampil\": [{\"no\": 1, \"kode\": \"KB-L01\", \"merek\": \"acer\"}]}"},
    {"role": "assistant", "content": json.dumps({"aksi": "lanjutan_hasil", "argumen": {"jenis": "yang_lain", "merek_kecuali": "acer"}, "pembaruan_state": {}})},
    {"role": "user", "content": "Pesan: \"Aku tanya kok malah dikasih spek lain\"\nState: {\"pending_question\": null, \"produk_tampil\": []}"},
    {"role": "assistant", "content": json.dumps({"aksi": "perbaiki_percakapan", "argumen": {"jenis": "salah_paham", "rujukan": "dikasih spek lain"}, "pembaruan_state": {}})},
    {"role": "user", "content": "Pesan: \"Yang tanya HP 14 siapa?\"\nState: {\"pending_question\": null, \"produk_tampil\": [{\"kode\": \"KB-L05\", \"nama\": \"HP 14\"}]}"},
    {"role": "assistant", "content": json.dumps({"aksi": "perbaiki_percakapan", "argumen": {"jenis": "keluhan", "rujukan": "HP 14"}, "pembaruan_state": {}})},
    {"role": "user", "content": "Pesan: \"tokonya ada di mana ya lokasinya?\"\nState: {\"pending_question\": null, \"produk_tampil\": []}"},
    {"role": "assistant", "content": json.dumps({"aksi": "tanya_info_toko", "argumen": {"topik": "alamat"}, "pembaruan_state": {}})}
]


def calc_percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    return sorted_data[int(f)] * (c - k) + sorted_data[int(c)] * (k - f)


STOPWORDS = {"dan", "atau", "di", "ke", "buat", "untuk", "yang", "aku", "saya", "mau", "nih", "ya", "sih", "aja", "dong", "ga", "gak"}

def extract_core_keywords(text: str) -> set[str]:
    if not text:
        return set()
    tokens = re.findall(r'[a-zA-Z0-9]+', str(text).lower())
    return {t for t in tokens if t not in STOPWORDS and len(t) > 1}


def compare_free_text(pred_val: Any, gold_val: Any) -> bool:
    if pred_val is None and gold_val is None:
        return True
    if pred_val is None or gold_val is None:
        return False
    p_str = str(pred_val).strip().lower()
    g_str = str(gold_val).strip().lower()
    if p_str == g_str or p_str in g_str or g_str in p_str:
        return True
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


STRUCTURED_SLOTS = ["kategori", "merek", "merek_kecuali", "gpu", "min_harga", "max_harga", "ram_gb_min", "storage_gb_min", "ukuran_layar", "slot", "atribut", "jenis", "topik", "rujukan_produk"]
FREE_TEXT_SLOTS = ["kebutuhan_teks", "nilai", "rujukan", "persona"]

# Kalimat-kalimat dev yang pernah menjadi few-shot lama
OLD_FEW_SHOT_PHRASES = {
    "halo", "jual laptop acer?", "pc dekstop gaming rtx 4060",
    "buat mama sih bukan buat aku", "untuk ibu saya yang sudah sepuh",
    "paling cuma cari resep dan nonton youtube", "emang spek segitu cukup?",
    "yang kedua bagus nggak?", "layarnya udah ips?", "bagusan nomor 1 apa nomor 2?",
    "ada opsi merk lain ga selain acer?", "aku tanya kok malah dikasih spek lain",
    "yang tanya hp 14 siapa?", "tokonya ada di mana ya lokasinya?"
}


def evaluate_dataset(
    items: List[Dict[str, Any]],
    few_shots: List[Dict[str, Any]],
    condition_name: str
) -> Dict[str, Any]:
    print(f"\n" + "=" * 75)
    print(f"MENGEVALUASI: {condition_name} ({len(items)} items)")
    print("=" * 75)

    latencies = []
    valid_json_count = 0
    correct_actions = 0

    # Metrik argumen terstruktur
    s_tp = 0
    s_fp = 0
    s_fn = 0

    # Metrik argumen teks bebas
    f_tp = 0
    f_fp = 0
    f_fn = 0

    fs_total = 0
    fs_correct = 0
    non_fs_total = 0
    non_fs_correct = 0

    item_results = []

    for i, it in enumerate(items, 1):
        pesan = it["pesan"]
        state = it.get("state", {})
        gold_action = it["label_aksi"]
        gold_args = it.get("label_argumen", {})
        item_id = it.get("id", f"item-{i}")

        is_old_few_shot = (
            pesan.lower().strip() in OLD_FEW_SHOT_PHRASES
            or any(kw in pesan.lower() for kw in ["emang spek segitu cukup", "yang tanya hp 14", "buat mama", "cari resep"])
        )

        t0 = time.perf_counter()
        parsed, metrics = parse_user_message(pesan, state=state, few_shots=few_shots)
        lat_ms = metrics.get("latency_ms", (time.perf_counter() - t0) * 1000.0)
        latencies.append(lat_ms)

        if metrics.get("json_valid", True):
            valid_json_count += 1

        pred_action = parsed.aksi.value
        is_action_correct = (pred_action == gold_action)
        if is_action_correct:
            correct_actions += 1

        if is_old_few_shot:
            fs_total += 1
            if is_action_correct:
                fs_correct += 1
        else:
            non_fs_total += 1
            if is_action_correct:
                non_fs_correct += 1

        # Evaluasi argumen jika aksi benar
        pred_args_dict = parsed.argumen.model_dump(exclude_none=True)

        # Evaluasi argumen terstruktur
        for slot in STRUCTURED_SLOTS:
            in_gold = slot in gold_args and gold_args[slot] is not None
            in_pred = slot in pred_args_dict and pred_args_dict[slot] is not None
            if in_gold and in_pred:
                if compare_structured(pred_args_dict[slot], gold_args[slot]):
                    s_tp += 1
                else:
                    s_fp += 1
                    s_fn += 1
            elif in_gold and not in_pred:
                s_fn += 1
            elif not in_gold and in_pred:
                s_fp += 1

        # Evaluasi argumen teks bebas
        for slot in FREE_TEXT_SLOTS:
            in_gold = slot in gold_args and gold_args[slot] is not None
            in_pred = slot in pred_args_dict and pred_args_dict[slot] is not None
            if in_gold and in_pred:
                if compare_free_text(pred_args_dict[slot], gold_args[slot]):
                    f_tp += 1
                else:
                    f_fp += 1
                    f_fn += 1
            elif in_gold and not in_pred:
                f_fn += 1
            elif not in_gold and in_pred:
                f_fp += 1

        status_icon = "✅" if is_action_correct else "❌"
        item_results.append({
            "id": item_id,
            "pesan": pesan,
            "gold_action": gold_action,
            "pred_action": pred_action,
            "gold_args": gold_args,
            "pred_args": pred_args_dict,
            "action_correct": is_action_correct,
            "is_old_few_shot": is_old_few_shot,
            "latency_ms": round(lat_ms, 1)
        })

        if i % 10 == 0 or not is_action_correct:
            print(f"[{i:02d}/{len(items):02d}] {status_icon} '{pesan}' -> Pred: {pred_action} | Gold: {gold_action} ({lat_ms:.0f} ms)")

    # Perhitungan F1
    s_prec = s_tp / (s_tp + s_fp) if (s_tp + s_fp) > 0 else 1.0
    s_rec = s_tp / (s_tp + s_fn) if (s_tp + s_fn) > 0 else 1.0
    s_f1 = 2 * s_prec * s_rec / (s_prec + s_rec) if (s_prec + s_rec) > 0 else 0.0

    f_prec = f_tp / (f_tp + f_fp) if (f_tp + f_fp) > 0 else 1.0
    f_rec = f_tp / (f_tp + f_fn) if (f_tp + f_fn) > 0 else 1.0
    f_f1 = 2 * f_prec * f_rec / (f_prec + f_rec) if (f_prec + f_rec) > 0 else 0.0

    acc_action = (correct_actions / len(items)) * 100.0 if items else 0.0
    acc_fs = (fs_correct / fs_total) * 100.0 if fs_total > 0 else 0.0
    acc_non_fs = (non_fs_correct / non_fs_total) * 100.0 if non_fs_total > 0 else 0.0

    summary = {
        "condition": condition_name,
        "total_items": len(items),
        "action_accuracy": round(acc_action, 2),
        "valid_json_pct": round((valid_json_count / len(items)) * 100.0, 2),
        "structured_f1": round(s_f1 * 100.0, 2),
        "free_text_f1": round(f_f1 * 100.0, 2),
        "fs_accuracy": round(acc_fs, 2),
        "non_fs_accuracy": round(acc_non_fs, 2),
        "fs_count": fs_total,
        "non_fs_count": non_fs_total,
        "p50_latency_ms": round(calc_percentile(latencies, 50), 1),
        "p95_latency_ms": round(calc_percentile(latencies, 95), 1),
        "items": item_results
    }
    return summary


def classify_error_cause(item: Dict[str, Any]) -> str:
    """
    Klasifikasi penyebab kegagalan:
    - definisi ambigu: Definisi aksi tumpang tindih atau kurang membedakan kasus spesifik.
    - konteks kurang: Informasi state/pending_question yang dibutuhkan tidak tersedia di prompt.
    - batas model: LLM kecil (4B) salah menalar instruksi/json walaupun definisi sudah jelas.
    """
    gold = item["gold_action"]
    pred = item["pred_action"]
    pesan = item["pesan"].lower()

    if gold in ("minta_rekomendasi", "jawab_pertanyaan_bot") and pred in ("minta_rekomendasi", "jawab_pertanyaan_bot"):
        return "definisi ambigu"
    elif gold in ("evaluasi_kecocokan", "tanya_spesifikasi") and pred in ("evaluasi_kecocokan", "tanya_spesifikasi"):
        return "definisi ambigu"
    elif gold == "perbaiki_percakapan" and pred == "cari_produk":
        return "konteks kurang"
    elif gold == "lanjutan_hasil" and pred in ("cari_produk", "tidak_jelas"):
        return "konteks kurang"
    elif "gpu" in pesan or "ram" in pesan or "inch" in pesan:
        return "batas model"
    else:
        return "batas model"


def main():
    print("=" * 80)
    print("STUDI ABLASI PROMPT & ANALISIS GENERALISASI NLU PARSER")
    print("=" * 80)

    # 1. Muat dataset dari eval/parse_gold.jsonl
    dev_items = []
    held_out_items = []

    with open("eval/parse_gold.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            if data.get("split") == "dev":
                dev_items.append(data)
            elif "held-out" in data.get("split", ""):
                held_out_items.append(data)

    dev_40 = dev_items[:40]
    print(f"Dataset Dev Loaded: {len(dev_items)} total (Menguji 40 dev gatekeeper set)")
    print(f"Dataset Held-Out Loaded: {len(held_out_items)} items")

    # Jalankan 3 Kondisi pada 40 Dev Set
    # (a) Definisi saja
    res_a = evaluate_dataset(dev_40, few_shots=[], condition_name="Kondisi (a): Definisi Saja (0 Few-Shot)")

    # (b) Definisi + 8 contoh sintetis
    res_b = evaluate_dataset(dev_40, few_shots=SYNTHETIC_8_BOUNDARY_FEW_SHOTS, condition_name="Kondisi (b): Definisi + 8 Contoh Sintetis")

    # (c) Definisi + 14 contoh lama
    res_c = evaluate_dataset(dev_40, few_shots=OLD_14_FEW_SHOTS, condition_name="Kondisi (c): Definisi + Semua Contoh Lama")

    # Jalankan Kondisi (b) pada Held-Out Set (50 items) untuk Celah Generalisasi
    res_ho = evaluate_dataset(held_out_items, few_shots=SYNTHETIC_8_BOUNDARY_FEW_SHOTS, condition_name="Held-Out (50 items) dengan Kondisi (b)")

    # Simpan hasil lengkap ke docs/ablation_study_results.json
    ablation_output = {
        "kondisi_a": res_a,
        "kondisi_b": res_b,
        "kondisi_c": res_c,
        "held_out_b": res_ho
    }

    os.makedirs("docs", exist_ok=True)
    with open("docs/ablation_study_results.json", "w", encoding="utf-8") as f:
        json.dump(ablation_output, f, ensure_ascii=False, indent=2)

    # Cetak Rangkuman Tabel Ablasi
    print("\n" + "=" * 80)
    print("TABEL RINGKASAN ABLASI PADA SET DEV (40 KALIMAT)")
    print("=" * 80)
    print(f"{'Kondisi':<40} | {'Akurasi Aksi':<13} | {'F1 Terstruktur':<15} | {'F1 Teks Bebas':<14} | {'p50 Latensi':<11}")
    print("-" * 100)
    for res in [res_a, res_b, res_c]:
        print(f"{res['condition']:<40} | {res['action_accuracy']:>11.2f}% | {res['structured_f1']:>13.2f}% | {res['free_text_f1']:>12.2f}% | {res['p50_latency_ms']:>9.1f} ms")

    # Klasifikasi Kesalahan pada Kondisi (b)
    print("\n" + "=" * 80)
    print("ANALISIS KESALAHAN PADA KONDISI (b) & KLASIFIKASI PENYEBAB KEGAGALAN")
    print("=" * 80)
    errors_b = [it for it in res_b["items"] if not it["action_correct"]]
    print(f"Total Kesalahan Aksi: {len(errors_b)} dari {len(dev_40)} items (Akurasi: {res_b['action_accuracy']}%)")

    cause_counts = {"definisi ambigu": 0, "konteks kurang": 0, "batas model": 0}
    for err in errors_b:
        cause = classify_error_cause(err)
        cause_counts[cause] += 1
        print(f"- '{err['pesan']}' | Pred: {err['pred_action']} | Gold: {err['gold_action']} | Penyebab: [{cause}]")

    print("\nDistribusi Penyebab Kegagalan:")
    for k, v in cause_counts.items():
        print(f"  * {k}: {v} kasus")

    # Celah Generalisasi
    print("\n" + "=" * 80)
    print("CELAH GENERALISASI (GENERALIZATION GAP)")
    print("=" * 80)
    gap_dev_ho = res_b['action_accuracy'] - res_ho['action_accuracy']
    gap_fs_non_fs_b = res_b['fs_accuracy'] - res_b['non_fs_accuracy']
    gap_fs_non_fs_c = res_c['fs_accuracy'] - res_c['non_fs_accuracy']

    print(f"1. Celah Dev vs Held-out (Kondisi b):")
    print(f"   - Akurasi Dev:     {res_b['action_accuracy']:.2f}%")
    print(f"   - Akurasi Held-out:{res_ho['action_accuracy']:.2f}%")
    print(f"   - Celah (Gap):     {gap_dev_ho:+.2f}% (Semakin mendekati 0, semakin bebas overfitting)")

    print(f"\n2. Celah Few-shot vs Non-few-shot pada Dev:")
    print(f"   - Kondisi (b) [8 sintetis non-dev]:")
    print(f"     * Kalimat bekas few-shot lama: {res_b['fs_accuracy']:.2f}% ({res_b['fs_count']} items)")
    print(f"     * Kalimat non-few-shot:        {res_b['non_fs_accuracy']:.2f}% ({res_b['non_fs_count']} items)")
    print(f"     * Celah:                       {gap_fs_non_fs_b:+.2f}%")
    print(f"   - Kondisi (c) [14 contoh lama]:")
    print(f"     * Kalimat few-shot lama:       {res_c['fs_accuracy']:.2f}% ({res_c['fs_count']} items)")
    print(f"     * Kalimat non-few-shot:        {res_c['non_fs_accuracy']:.2f}% ({res_c['non_fs_count']} items)")
    print(f"     * Celah:                       {gap_fs_non_fs_c:+.2f}%")
    print("=" * 80)

if __name__ == "__main__":
    main()
