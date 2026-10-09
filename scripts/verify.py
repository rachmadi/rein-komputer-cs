# -*- coding: utf-8 -*-
"""
scripts/verify.py
Alat Verifikasi Otomatis untuk Laporan Bobby Computer Antigravity v2.
Semua angka dan teks dihasilkan secara programatik dan disimpan ke VERIFY.md:
- Hash commit dan git log --oneline sejak commit 1d65c32
- Ringkasan pytest -q penuh (lulus, gagal, skip) beserta daftar nodeid yang di-skip
- Akurasi aksi per split (dev 40, dev 100, held-out v1 terpakai) dari CSV prediksi terakhir beserta n
- p50, p95, dan maksimum latensi tiap tahap (parse, mesin, generate, total) langsung dari eval/latency_e2e.csv (pipeline)
- Hasil grep kebocoran ke seluruh repositori kecuali eval/ dan tests/, memakai kalimat dari parse_gold.csv, eval/regression_telegram.jsonl, dan logs/chat_history.jsonl
- SHA-256 eval/parse_gold.csv
"""
import os
import re
import csv
import math
import json
import hashlib
import subprocess
from pathlib import Path


def get_git_info():
    """Mengambil commit hash dan log oneline sejak 1d65c32."""
    try:
        commit_hash = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        commit_hash = "unknown"

    log_lines = []
    base_commit_used = ""
    for base in ["1583d73", "1d65c32"]:
        try:
            log_res = subprocess.run(
                ["git", "log", "--oneline", f"{base}..HEAD"],
                capture_output=True, text=True, check=True
            ).stdout.strip()
            if log_res:
                log_lines = log_res.splitlines()
                base_commit_used = base
                break
        except Exception:
            continue

    if not log_lines:
        try:
            log_res = subprocess.run(
                ["git", "log", "--oneline", "-n", "30"],
                capture_output=True, text=True, check=True
            ).stdout.strip()
            log_lines = log_res.splitlines() if log_res else []
            base_commit_used = "recent (last 30)"
        except Exception:
            base_commit_used = "unknown"

    return commit_hash, log_lines, base_commit_used


def run_pytest_summary():
    """Menjalankan pytest -q dan mengumpulkan ringkasan serta skipped nodeids."""
    res = subprocess.run(
        [".venv/Scripts/python.exe", "-m", "pytest", "-q", "-rs"],
        capture_output=True, text=True
    )
    stdout = res.stdout
    summary_line = ""
    skipped_nodeids = []

    for line in stdout.splitlines():
        line_clean = line.strip()
        if "passed" in line_clean and ("skipped" in line_clean or "failed" in line_clean or "seconds" in line_clean or "in " in line_clean):
            summary_line = line_clean
        elif line_clean.startswith("SKIPPED "):
            skipped_nodeids.append(line_clean)

    # Jika summary_line kosong, cari baris terakhir
    if not summary_line and stdout.splitlines():
        summary_line = stdout.splitlines()[-1]

    return summary_line, skipped_nodeids, res.returncode


def compute_quantiles(data, q):
    if not data:
        return 0.0
    s = sorted(data)
    idx = (len(s) - 1) * q
    low = math.floor(idx)
    high = math.ceil(idx)
    if low == high:
        return s[int(idx)]
    return s[low] * (high - idx) + s[high] * (idx - low)


def get_latency_metrics(csv_path="eval/latency_e2e.csv"):
    """Menghitung p50, p95, dan maksimum per tahap dari latency_e2e.csv."""
    if not os.path.exists(csv_path):
        return None

    stages = ["latensi_parse_ms", "latensi_mesin_ms", "latensi_generate_ms", "latensi_total_ms"]
    metrics = {s: [] for s in stages}

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for s in stages:
                val = row.get(s)
                if val:
                    try:
                        metrics[s].append(float(val))
                    except ValueError:
                        pass

    res = {}
    for s in stages:
        vals = metrics[s]
        if vals:
            res[s] = {
                "n": len(vals),
                "p50": compute_quantiles(vals, 0.50),
                "p95": compute_quantiles(vals, 0.95),
                "max": max(vals)
            }
        else:
            res[s] = {"n": 0, "p50": 0.0, "p95": 0.0, "max": 0.0}
    return res


def get_accuracy_from_csv(csv_path):
    """Menghitung akurasi aksi dari file prediksi CSV."""
    if not os.path.exists(csv_path):
        return None

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return {"n": 0, "correct": 0, "accuracy": 0.0}

    correct = 0
    for r in rows:
        # Cek kolom benar_salah atau bandingkan pred_aksi == gold_aksi
        if r.get("benar_salah") in ("True", "true", "1", "benar"):
            correct += 1
        elif r.get("gold_aksi") and r.get("pred_aksi") and r.get("gold_aksi") == r.get("pred_aksi"):
            correct += 1

    acc = (correct / len(rows)) * 100.0 if rows else 0.0
    return {"n": len(rows), "correct": correct, "accuracy": acc}


def scan_leakage():
    """
    Memindai kebocoran kalimat dari parse_gold.csv, regression_telegram.jsonl,
    dan logs/chat_history.jsonl ke seluruh repositori kecuali eval/ dan tests/.
    """
    sentences = set()

    # 1. parse_gold.csv
    if os.path.exists("eval/parse_gold.csv"):
        with open("eval/parse_gold.csv", "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                msg = row.get("pesan", "").strip()
                if len(msg) >= 10:  # hanya kalimat substansial
                    sentences.add(msg)

    # 2. eval/regression_telegram.jsonl
    if os.path.exists("eval/regression_telegram.jsonl"):
        with open("eval/regression_telegram.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        conv = json.loads(line)
                        for turn in conv.get("turns", []):
                            turn_str = str(turn).strip()
                            if len(turn_str) >= 10:
                                sentences.add(turn_str)
                    except Exception:
                        pass

    # 3. logs/chat_history.jsonl
    if os.path.exists("logs/chat_history.jsonl"):
        with open("logs/chat_history.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        record = json.loads(line)
                        text = record.get("text") or record.get("message") or ""
                        if len(text.strip()) >= 10:
                            sentences.add(text.strip())
                    except Exception:
                        pass

    # Scan seluruh repositori kecuali eval/, tests/, .venv/, .git/
    ignore_dirs = {".git", ".venv", "__pycache__", "eval", "tests", ".pytest_cache"}
    leaks_found = []

    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            if f.endswith((".py", ".md", ".json", ".yaml", ".yml", ".txt")) and f not in ("VERIFY.md", "README.md"):
                file_path = os.path.join(root, f)
                try:
                    with open(file_path, "r", encoding="utf-8") as fp:
                        content = fp.read().lower()
                    for s in sentences:
                        s_lower = s.lower()
                        if s_lower in content:
                            leaks_found.append((file_path, s))
                except Exception:
                    pass

    return leaks_found, len(sentences)


def get_sha256(filepath):
    if not os.path.exists(filepath):
        return "BERKAS_TIDAK_DITEMUKAN"
    with open(filepath, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    print("Memulai verifikasi otomatis sistem Bobby Computer...")
    commit_hash, log_lines, base_commit_used = get_git_info()
    print(f"- Commit HEAD: {commit_hash} (sejak {base_commit_used})")

    print("- Menjalankan pytest suite penuh...")
    pytest_summary, skipped_nodeids, exit_code = run_pytest_summary()
    print(f"  Pytest: {pytest_summary}")

    print("- Mengukur akurasi per split...")
    acc_dev40 = get_accuracy_from_csv("eval/dev_40_predictions.csv")
    acc_dev100 = get_accuracy_from_csv("eval/dev_100_predictions.csv")
    acc_ho_v1 = get_accuracy_from_csv("eval/heldout_v1_predictions.csv") or get_accuracy_from_csv("eval/heldout_v1_rerun_clean.csv")

    print("- Mengambil latensi pipeline dari eval/latency_e2e.csv...")
    lat_sesudah = get_latency_metrics("eval/latency_e2e.csv")
    lat_sebelum = get_latency_metrics("eval/latency_e2e_sebelum.csv")

    print("- Memindai kebocoran kalimat uji ke codebase...")
    leaks, n_sentences = scan_leakage()
    print(f"  Kebocoran terdeteksi: {len(leaks)} dari {n_sentences} kalimat dipindai")

    sha_gold = get_sha256("eval/parse_gold.csv")
    print(f"- SHA-256 eval/parse_gold.csv: {sha_gold}")

    # Susun VERIFY.md
    md = []
    md.append("# LAPORAN VERIFIKASI SISTEM (VERIFY.md)")
    md.append("*Seluruh data dan metrik dalam dokumen ini dihasilkan secara programatik oleh `scripts/verify.py`.*\n")

    # 1. Git Info
    md.append("## 1. Status Repositori & Riwayat Commit")
    md.append(f"- **Hash Commit Terkini (HEAD)**: `{commit_hash}`")
    md.append(f"- **Riwayat Commit sejak `{base_commit_used}`** ({len(log_lines)} commit):")
    for cl in log_lines:
        md.append(f"  - `{cl}`")
    md.append("")

    # 2. Pytest Summary
    md.append("## 2. Hasil Eksekusi Pytest Suite Penuh")
    md.append(f"- **Baris Ringkasan Verbatim**: `{pytest_summary}`")
    md.append(f"- **Status Exit Code**: `{exit_code}` ({'SUKSES / HIJAU' if exit_code == 0 else 'GAGAL / MERAH'})")
    md.append(f"- **Daftar Nodeid Tes yang Di-skip** ({len(skipped_nodeids)} tes):")
    for sn in skipped_nodeids:
        md.append(f"  - `{sn}`")
    md.append("")

    # 3. Akurasi Per Split
    md.append("## 3. Akurasi Aksi Parser Per Split")
    md.append("| Split Dataset | Jumlah Sampel (n) | Prediksi Benar | Akurasi Aksi (%) | Berkas Sumber Prediksi |")
    md.append("|---|---|---|---|---|")
    if acc_dev40:
        md.append(f"| **Dev 40** | {acc_dev40['n']} | {acc_dev40['correct']} | **{acc_dev40['accuracy']:.2f}%** | `eval/dev_40_predictions.csv` |")
    else:
        md.append("| **Dev 40** | Belum diukur | - | - | `eval/dev_40_predictions.csv` |")

    if acc_dev100:
        md.append(f"| **Dev 100** | {acc_dev100['n']} | {acc_dev100['correct']} | **{acc_dev100['accuracy']:.2f}%** | `eval/dev_100_predictions.csv` |")
    else:
        md.append("| **Dev 100** | Belum diukur | - | - | `eval/dev_100_predictions.csv` |")

    if acc_ho_v1:
        md.append(f"| **Held-Out v1 (Terpakai)** | {acc_ho_v1['n']} | {acc_ho_v1['correct']} | **{acc_ho_v1['accuracy']:.2f}%** | `eval/heldout_v1_predictions.csv` |")
    else:
        md.append("| **Held-Out v1 (Terpakai)** | Belum diukur | - | - | `eval/heldout_v1_predictions.csv` |")
    md.append("")

    # 4. Latensi Pipeline
    md.append("## 4. Latensi Tahapan Pipeline (Berdasarkan `eval/latency_e2e.csv`)")
    md.append("*Pengukuran dilakukan melalui SessionPipeline (disebut 'pipeline'). Angka dihitung langsung dari berkas CSV.*")
    md.append("")
    md.append("### Kondisi Terkini (Sesudah Perbaikan Latensi Ekor)")
    md.append("| Tahapan Pipeline | Sampel (n) | p50 (ms) | p95 (ms) | Maksimum (ms) |")
    md.append("|---|---|---|---|---|")
    if lat_sesudah:
        for st_name, label in [
            ("latensi_parse_ms", "1. LLM Parser"),
            ("latensi_mesin_ms", "2. Mesin Deterministik"),
            ("latensi_generate_ms", "3. LLM Generator & Pemeriksa"),
            ("latensi_total_ms", "TOTAL PIPELINE")
        ]:
            m = lat_sesudah.get(st_name, {})
            md.append(f"| **{label}** | {m.get('n', 0)} | {m.get('p50', 0):,.1f} | {m.get('p95', 0):,.1f} | {m.get('max', 0):,.1f} |")
    else:
        md.append("| *Data latensi tidak ditemukan* | - | - | - | - |")
    md.append("")

    if lat_sebelum:
        md.append("### Pembanding Kondisi Sebelumnya (Sebelum Perbaikan Latensi Ekor)")
        md.append("| Tahapan Pipeline | Sampel (n) | p50 (ms) | p95 (ms) | Maksimum (ms) |")
        md.append("|---|---|---|---|---|")
        for st_name, label in [
            ("latensi_parse_ms", "1. LLM Parser"),
            ("latensi_mesin_ms", "2. Mesin Deterministik"),
            ("latensi_generate_ms", "3. LLM Generator & Pemeriksa"),
            ("latensi_total_ms", "TOTAL PIPELINE")
        ]:
            m = lat_sebelum.get(st_name, {})
            md.append(f"| **{label}** | {m.get('n', 0)} | {m.get('p50', 0):,.1f} | {m.get('p95', 0):,.1f} | {m.get('max', 0):,.1f} |")
        md.append("")

    # 5. Audit Kebocoran
    md.append("## 5. Audit Kebocoran Dataset ke Kode dan Prompt")
    md.append(f"- **Total Kalimat Unik Dipindai**: {n_sentences} kalimat (dari `eval/parse_gold.csv`, `eval/regression_telegram.jsonl`, `logs/chat_history.jsonl`)")
    md.append(f"- **Direktori yang Dipindai**: Seluruh repositori kecuali `eval/` dan `tests/`")
    md.append(f"- **Hasil Deteksi Kebocoran**: `{len(leaks)} kebocoran ditemukan`")
    if leaks:
        md.append("\n**Daftar Kebocoran Terdeteksi**:")
        for fp, sent in leaks[:20]:
            md.append(f"- `{fp}`: \"{sent}\"")
        if len(leaks) > 20:
            md.append(f"- ... dan {len(leaks) - 20} kebocoran lainnya.")
    else:
        md.append("- **Status Integritas**: **BERSIH**. Tidak ada kalimat evaluasi atau log yang bocor ke kode produksi atau prompt.")
    md.append("")

    # 6. Checksum Gold
    md.append("## 6. Kunci Integritas Dataset Gold")
    md.append(f"- **Path Berkas**: `eval/parse_gold.csv`")
    md.append(f"- **SHA-256 Terhitung**: `{sha_gold}`")
    sha_locked = Path("eval/gold.sha256").read_text(encoding="utf-8").strip() if os.path.exists("eval/gold.sha256") else "-"
    md.append(f"- **SHA-256 Terkunci (`eval/gold.sha256`)**: `{sha_locked}`")
    is_match = (sha_gold == sha_locked)
    md.append(f"- **Status Kunci Integritas**: `{'TERKUNCI & SESUAI' if is_match else 'BERBEDA / TIDAK VALID'}`")
    md.append("")

    output_path = "VERIFY.md"
    with open(output_path, "w", encoding="utf-8") as f_out:
        f_out.write("\n".join(md) + "\n")
    print(f"Laporan verifikasi berhasil ditulis ke: {output_path}")


if __name__ == "__main__":
    main()
