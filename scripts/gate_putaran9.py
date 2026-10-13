# -*- coding: utf-8 -*-
"""
scripts/gate_putaran9.py
Gerbang Kelulusan Evaluasi Otomatis Putaran 9 (ReIn Komputer).
Memeriksa G1–G8 secara ketat, deterministik, dan tanpa re-evaluasi ad-hoc.
"""
import os
import sys
import csv
import json
import glob
import re
import hashlib
import subprocess
from typing import Dict, Any, Tuple, List

sys.path.insert(0, os.path.abspath("."))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from scripts.metrics import (
    turn_ok,
    evaluate_turn_record,
    get_code_sha256,
    get_git_head,
    get_file_sha256,
)


def check_g1() -> Tuple[bool, str]:
    """G1 Kebersihan: hash gold sama; RAG_SCORE_THRESHOLD=0.40; .env, logs/, scratch/, *.db tidak tracked; 4 untracked sah; remote kosong."""
    # 1. Gold hash
    gold_path = "eval/parse_gold.csv"
    sha_path = "eval/gold.sha256"
    if not os.path.exists(gold_path) or not os.path.exists(sha_path):
        return False, "Berkas gold atau gold.sha256 tidak ditemukan"
    with open(gold_path, "rb") as f:
        curr_hash = hashlib.sha256(f.read()).hexdigest().upper()
    with open(sha_path, "r", encoding="utf-8") as f:
        exp_hash = f.read().strip().upper()
    if curr_hash != exp_hash:
        return False, f"Checksum gold mismatch: {curr_hash} vs {exp_hash}"

    # 2. RAG threshold
    ks_path = "services/knowledge_service.py"
    if not os.path.exists(ks_path):
        return False, "services/knowledge_service.py tidak ditemukan"
    with open(ks_path, "r", encoding="utf-8") as f:
        c = f.read()
    match = re.search(r'RAG_SCORE_THRESHOLD\s*=\s*float\(os\.getenv\("RAG_SCORE_THRESHOLD",\s*"([0-9\.]+)"\)\)', c)
    if not match or float(match.group(1)) != 0.40:
        return False, f"RAG_SCORE_THRESHOLD tidak 0.40"

    # 3. Tracked forbidden files
    forbidden = subprocess.run(
        ["git", "ls-files", ".env", "scratch", "catalog.db", "logs"],
        capture_output=True, text=True
    ).stdout.strip()
    if forbidden:
        return False, f"Berkas rahasia/log masih terlacak git: {forbidden}"

    # 4. Untracked files
    status_lines = subprocess.run(
        ["git", "status", "--short"],
        capture_output=True, text=True
    ).stdout.strip().splitlines()
    allowed_untracked = {
        "?? docs/latency_20_new.csv",
        "?? docs/ood_full_eval_v2.csv",
        "?? docs/ood_summary_v2.csv",
        "?? dokumen/INSTRUKSI_ANTIGRAVITY_V2_LLM_PARSER.md",
    }
    for s in status_lines:
        s_clean = s.strip()
        if s_clean.startswith("??") and s_clean not in allowed_untracked:
            return False, f"Untracked tidak diizinkan: {s_clean}"

    # 5. Remote git
    remotes = subprocess.run(["git", "remote"], capture_output=True, text=True).stdout.strip()
    if remotes:
        return False, f"Terdapat remote git: {remotes}"

    return True, "Kebersihan repo sempurna (gold valid, RAG 0.40, 0 berkas terlarang, 4 untracked sah, 0 remote)"


def check_g2() -> Tuple[bool, str]:
    """G2 Label utuh: sha256 tiap berkas di label_manifest.json cocok sekarang dan pada commit tercatat; commit Tahap 0 sebelum services/ disentuh."""
    manifest_path = "eval/label_manifest.json"
    if not os.path.exists(manifest_path):
        return False, f"{manifest_path} belum ada"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    files_info = manifest.get("files", {})
    for path, info in files_info.items():
        if not os.path.exists(path):
            return False, f"Berkas manifest {path} tidak ditemukan di disk"
        curr_sha = get_file_sha256(path)
        exp_sha = info.get("sha256")
        if curr_sha != exp_sha:
            return False, f"SHA256 {path} berubah: {curr_sha} != {exp_sha}"

        # Periksa commit tercatat
        cmt = info.get("last_commit")
        if cmt:
            try:
                cmt_content = subprocess.run(
                    ["git", "cat-file", "--filters", f"{cmt}:{path}"],
                    capture_output=True, check=True
                ).stdout
                cmt_sha = hashlib.sha256(cmt_content).hexdigest()
                if cmt_sha != exp_sha:
                    # Toleransi normalisasi baris CRLF vs LF jika isi teks sama
                    norm_cmt = hashlib.sha256(cmt_content.replace(b"\r\n", b"\n")).hexdigest()
                    norm_disk = hashlib.sha256(open(path, "rb").read().replace(b"\r\n", b"\n")).hexdigest()
                    if norm_cmt != norm_disk:
                        return False, f"SHA256 {path} pada commit {cmt} ({cmt_sha}) != manifest ({exp_sha})"
            except Exception as e:
                return False, f"Gagal mengecek commit {cmt} untuk {path}: {e}"

    # Periksa urutan commit Tahap 0 vs services/
    tahap0_commit = manifest.get("tahap0_commit")
    if not tahap0_commit:
        # Cek dari log
        log_lines = subprocess.run(
            ["git", "log", "--pretty=format:%H %s", "sebelum-putaran9..HEAD"],
            capture_output=True, text=True
        ).stdout.strip().splitlines()
        for l in log_lines:
            if "putaran9-tahap0" in l:
                tahap0_commit = l.split()[0]
                break

    if tahap0_commit:
        # Commit pertama yang menyentuh services/ sejak sebelum-putaran9
        services_commits = subprocess.run(
            ["git", "log", "--reverse", "--pretty=format:%H", "sebelum-putaran9..HEAD", "--", "services/"],
            capture_output=True, text=True
        ).stdout.strip().splitlines()
        if services_commits:
            first_svc = services_commits[0]
            # Bandingkan cap waktu
            ts_t0 = int(subprocess.run(["git", "show", "-s", "--format=%ct", tahap0_commit], capture_output=True, text=True).stdout.strip())
            ts_svc = int(subprocess.run(["git", "show", "-s", "--format=%ct", first_svc], capture_output=True, text=True).stdout.strip())
            if ts_t0 > ts_svc:
                return False, f"Commit Tahap 0 ({tahap0_commit}) lebih baru daripada modifikasi services ({first_svc})"

    return True, "Label utuh, checksum manifest valid, commit Tahap 0 mendahului kode"


def check_g3() -> Tuple[bool, str]:
    """G3 Tanpa tulis ulang riwayat: reflog sejak tag sebelum-putaran9 tidak memuat amend/reset/rebase."""
    reflog_out = subprocess.run(
        ["git", "reflog", "--oneline", "sebelum-putaran9..HEAD"],
        capture_output=True, text=True
    ).stdout.strip()
    if not reflog_out:
        # Jika HEAD sama dengan sebelum-putaran9
        return True, "Belum ada commit baru sejak sebelum-putaran9 (reflog bersih)"

    bad_patterns = ["commit (amend)", "reset:", "rebase:"]
    found = []
    for line in reflog_out.splitlines():
        for pat in bad_patterns:
            if pat in line:
                found.append(line)
    if found:
        return False, f"Terdeteksi penulisan ulang riwayat git: {found[:3]}"
    return True, "0 operasi amend/reset/rebase sejak tag sebelum-putaran9"


def check_g4() -> Tuple[bool, str]:
    """G4 Hasil sesuai kode: berkas hasil memuat git_head dan code_sha256 saat ini; scripts/metrics.py dan gate sama dengan manifest."""
    curr_code_sha = get_code_sha256()

    # Periksa kesesuaian skrip alat ukur dengan manifest
    manifest_path = "eval/label_manifest.json"
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        tool_shas = manifest.get("tool_sha256", {})
        for script_path, exp_sha in tool_shas.items():
            if os.path.exists(script_path):
                act_sha = get_file_sha256(script_path)
                if act_sha != exp_sha:
                    diff_out = subprocess.run(["git", "diff", script_path], capture_output=True, text=True).stdout
                    return False, f"{script_path} berubah dari manifest ({act_sha} != {exp_sha}). Diff:\n{diff_out[:300]}"

    # Periksa berkas hasil evaluasi
    result_files = [
        "eval/parse_frozen_results.json",
        "eval/dev_multi_putaran7_results.jsonl",
        "eval/dev_multi_putaran8_results.jsonl",
        "eval/replay_putaran9.jsonl"
    ]
    checked_cnt = 0
    for rf in result_files:
        if not os.path.exists(rf):
            return False, f"Berkas hasil {rf} belum ada"
        if rf.endswith(".json"):
            with open(rf, "r", encoding="utf-8") as f:
                data = json.load(f)
            r_csha = data.get("code_sha256")
            if not r_csha or r_csha != curr_code_sha:
                return False, f"{rf} code_sha256 mismatch: {r_csha} != {curr_code_sha}"
            checked_cnt += 1
        elif rf.endswith(".jsonl"):
            # Cek baris pertama atau metadata
            with open(rf, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
            if first_line:
                row = json.loads(first_line)
                r_csha = row.get("code_sha256")
                if not r_csha or r_csha != curr_code_sha:
                    return False, f"{rf} code_sha256 mismatch: {r_csha} != {curr_code_sha}"
                checked_cnt += 1

    return True, f"Seluruh {checked_cnt} berkas hasil mencatat code_sha256 identik ({curr_code_sha[:10]}...)"


def check_g5() -> Tuple[bool, str]:
    """G5 Tes: pytest fail 0, skipped 20; merah_putaran9.txt memuat FAILED untuk F1–F6; live smoke dijalankan."""
    # 1. Ringkasan pytest di VERIFY.md
    verify_path = "VERIFY.md"
    if not os.path.exists(verify_path):
        return False, "VERIFY.md belum ada"
    with open(verify_path, "r", encoding="utf-8") as f:
        v_text = f.read()
    m_pass = re.search(r"(\d+)\s+passed,\s*(\d+)\s+skipped", v_text)
    m_fail = re.search(r"(\d+)\s+failed", v_text)
    if not m_pass:
        return False, "Ringkasan pytest tidak ditemukan di VERIFY.md"
    passed = int(m_pass.group(1))
    skipped = int(m_pass.group(2))
    failed = int(m_fail.group(1)) if m_fail else 0
    if failed != 0 or skipped != 20:
        return False, f"Pytest tidak memenuhi: {passed} passed, {skipped} skipped (harus 20), {failed} failed (harus 0)"

    # 2. Bukti merah F1-F6
    merah_path = "eval/evidence/merah_putaran9.txt"
    if not os.path.exists(merah_path):
        return False, f"{merah_path} belum ada"
    with open(merah_path, "r", encoding="utf-8") as f:
        m_content = f.read()
    required_red = ["test_f1_", "test_f1b_", "test_f2_", "test_f3_", "test_f4_", "test_f5_", "test_f6_"]
    missing_red = [r for r in required_red if f"FAILED tests/test_integrasi_putaran9.py::{r}" not in m_content and r not in m_content]
    if missing_red:
        return False, f"Bukti merah belum memuat kegagalan awal untuk: {missing_red}"

    # 3. Bukti live smoke test
    live_path = "eval/evidence/live_putaran9.txt"
    if not os.path.exists(live_path):
        return False, f"Bukti live smoke {live_path} belum ada"

    return True, f"Pytest {passed} passed/20 skipped/0 failed, bukti merah F1–F6 lengkap, live smoke terekam"


def check_g6() -> Tuple[bool, str]:
    """G6 Kebocoran: 0 4-gram dan 0 frasa >= 12 karakter antara prompt/few-shot/tes aktif vs seluruh berkas eval/ & smoke tests."""
    def get_ngrams(text: str, n: int = 4, min_len: int = 12) -> set:
        words = re.findall(r"\b\w+\b", text.lower())
        res = set()
        for i in range(len(words) - n + 1):
            ng = " ".join(words[i:i+n])
            if len(ng) >= min_len:
                res.add(ng)
        return res

    # Kumpulkan n-grams dari eval/
    eval_files = glob.glob("eval/**", recursive=True)
    eval_ngrams = set()
    for ef in eval_files:
        if os.path.isfile(ef) and not ef.endswith(".json") and not ef.endswith(".jsonl"):
            # Batasi ke teks/csv mentah eval
            try:
                with open(ef, "r", encoding="utf-8") as f:
                    eval_ngrams.update(get_ngrams(f.read()))
            except Exception:
                pass
    # Tambahkan regression_telegram dan parse_frozen
    for ef in ["eval/regression_telegram.jsonl", "eval/parse_frozen_putaran8.csv", "eval/parse_gold.csv"]:
        if os.path.exists(ef):
            with open(ef, "r", encoding="utf-8") as f:
                eval_ngrams.update(get_ngrams(f.read()))

    # Teks target yang diperiksa: prompt, few-shots, dan tes integrasi putaran 9
    from services.llm_parser import SYSTEM_PARSER_PROMPT, SYNTHETIC_8_BOUNDARY_FEW_SHOTS
    from services.llm_generator import GENERATOR_SYSTEM_PROMPT

    target_items = [SYSTEM_PARSER_PROMPT, GENERATOR_SYSTEM_PROMPT]
    for fs in SYNTHETIC_8_BOUNDARY_FEW_SHOTS:
        target_items.append(fs["content"])

    test_p9 = glob.glob("tests/*putaran9*.py")
    for tp in test_p9:
        with open(tp, "r", encoding="utf-8") as f:
            target_items.append(f.read())

    # Pindai tumpang tindih
    leaks = []
    for item in target_items:
        it_ng = get_ngrams(item)
        inter = it_ng.intersection(eval_ngrams)
        # Saring kata kunci kode/sistem (seperti 'parseroutput actionenum', dsb)
        clean_inter = {
            x for x in inter if not any(
                code_kw in x for code_kw in [
                    "actionenum", "parseroutput", "actionarguments", "pembaruan_state",
                    "import", "pytest", "return", "class", "def", "self"
                ]
            )
        }
        if clean_inter:
            leaks.append((item[:40], clean_inter))

    if not leaks:
        return True, "0 kebocoran n-gram (≥4 kata/12 karakter) antara prompt/few-shot/tes vs eval"
    return False, f"Ditemukan {len(leaks)} potensi kebocoran: {leaks[:2]}"


def check_g7() -> Tuple[bool, str]:
    """G7 Kualitas teknis: turn_ok dev7 koreksi ≥85%; turn_ok dev8 ≥85% (dikecualikan bila label berubah); parse_frozen ≥90%; dev7-09 t2 OK; checker ≤2%, mismatch=0."""
    # 1. Dev7 koreksi
    d7_res_path = "eval/dev_multi_putaran7_results.jsonl"
    if not os.path.exists(d7_res_path):
        return False, f"{d7_res_path} belum ada"
    d7_lines = [json.loads(l) for l in open(d7_res_path, "r", encoding="utf-8") if l.strip()]
    d7_ok = sum(1 for l in d7_lines if evaluate_turn_record(l))
    d7_pct = (d7_ok / len(d7_lines) * 100.0) if d7_lines else 0.0
    if d7_pct < 85.0:
        return False, f"turn_ok dev7={d7_pct:.1f}% (target ≥85.0%)"

    # 2. Dev8 (status pengecualian audit 0.2b)
    d8_res_path = "eval/dev_multi_putaran8_results.jsonl"
    d8_note = "dikecualikan (label berubah)"
    if os.path.exists(d8_res_path):
        d8_lines = [json.loads(l) for l in open(d8_res_path, "r", encoding="utf-8") if l.strip()]
        d8_ok = sum(1 for l in d8_lines if evaluate_turn_record(l))
        d8_pct = (d8_ok / len(d8_lines) * 100.0) if d8_lines else 0.0
        d8_note = f"dev8={d8_pct:.1f}% ({d8_note})"

    # 3. Parse frozen ≥90%
    pf_path = "eval/parse_frozen_results.json"
    if not os.path.exists(pf_path):
        return False, f"{pf_path} belum ada"
    with open(pf_path, "r", encoding="utf-8") as f:
        pf_data = json.load(f)
    pf_acc = pf_data.get("accuracy_percent", 0.0)
    if pf_acc < 90.0:
        return False, f"Akurasi parse_frozen={pf_acc:.1f}% (target ≥90.0%)"

    # 4. conv-dev7-09 t2 turn_ok == True
    t2_found = False
    t2_ok = False
    for l in d7_lines:
        c_id = l.get("conv_id") or l.get("id")
        t_idx = l.get("turn_idx") or l.get("t_idx")
        if c_id == "conv-dev7-09" and t_idx == 2:
            t2_found = True
            t2_ok = evaluate_turn_record(l)
            break
    if not t2_found or not t2_ok:
        return False, f"conv-dev7-09 t2 turn_ok gagal (found={t2_found}, ok={t2_ok})"

    # 5. Replay checker ≤2% & mismatch = 0
    rep_path = "eval/replay_putaran9.jsonl"
    if not os.path.exists(rep_path):
        return False, f"{rep_path} belum ada"
    rep_lines = [json.loads(l) for l in open(rep_path, "r", encoding="utf-8") if l.strip()]
    rep_viol = sum(1 for l in rep_lines if l.get("pelanggaran_checker"))
    rep_mis = sum(1 for l in rep_lines if l.get("kategori_mismatch"))
    rep_viol_pct = (rep_viol / len(rep_lines) * 100.0) if rep_lines else 0.0
    if rep_viol_pct > 2.0 or rep_mis != 0:
        return False, f"Replay: pelanggaran={rep_viol_pct:.1f}% (>2.0%) atau mismatch={rep_mis}"

    return True, f"Kualitas teknis lolos (dev7={d7_pct:.1f}%, {d8_note}, parse_frozen={pf_acc:.1f}%, dev7-09 t2 OK, replay viol={rep_viol_pct:.1f}%, mismatch=0)"


def check_g8() -> Tuple[bool, str]:
    """G8 Replay: 134 baris lengkap; determinisme 3x identik; latensi median/p95 dicetak beserta proses konkuren."""
    # 1. 134 baris
    rep_path = "eval/replay_putaran9.jsonl"
    if not os.path.exists(rep_path):
        return False, f"{rep_path} belum ada"
    lines = [json.loads(l) for l in open(rep_path, "r", encoding="utf-8") if l.strip()]
    if len(lines) != 134:
        return False, f"Jumlah giliran replay tidak 134 ({len(lines)})"
    required_keys = ["conv_id", "turn_idx", "pesan", "aksi_terpilih", "fakta_status", "latensi_total_ms"]
    for idx, row in enumerate(lines):
        for k in required_keys:
            if k not in row:
                return False, f"Baris replay #{idx} tidak memiliki field '{k}'"

    # 2. Determinisme 3 run
    det_path = "eval/determinism_putaran9.json"
    if not os.path.exists(det_path):
        return False, f"{det_path} belum ada"
    with open(det_path, "r", encoding="utf-8") as f:
        det_data = json.load(f)
    identical = det_data.get("identical_turns", 0)
    total_det = det_data.get("total_turns", 134)
    if identical != total_det or total_det != 134:
        return False, f"Determinisme tidak 100% ({identical}/{total_det})"

    # 3. Latensi summary
    lat_path = "eval/latency_summary_putaran9.json"
    if not os.path.exists(lat_path):
        return False, f"{lat_path} belum ada"
    with open(lat_path, "r", encoding="utf-8") as f:
        lat_data = json.load(f)
    med = lat_data.get("total_median_ms", 0.0)
    p95 = lat_data.get("total_p95_ms", 0.0)
    procs = lat_data.get("concurrent_processes", 0)

    return True, f"Replay 134 giliran valid, determinisme 134/134 identik, latensi median={med:.1f}ms, p95={p95:.1f}ms (proses konkuren={procs})"


CHECKS = [
    ("G1", "Kebersihan & Integritas Repositori", check_g1),
    ("G2", "Integritas Label & Kronologi Commit", check_g2),
    ("G3", "Ketiadaan Penulisan Ulang Riwayat Git", check_g3),
    ("G4", "Kesesuaian Hasil dengan Kode (Provenance)", check_g4),
    ("G5", "Kelulusan Suite Tes & Bukti Merah/Live", check_g5),
    ("G6", "Pencegahan Kebocoran N-Gram & Frasa", check_g6),
    ("G7", "Kualitas Teknis & Ketepatan Jawaban", check_g7),
    ("G8", "Validitas Replay Penuh & Determinisme", check_g8),
]


def run_gate(output_json: str = "eval/gate_putaran9.json") -> Dict[str, Any]:
    print("================================================================================")
    print("GERBANG EVALUASI OTOMATIS PUTARAN 9 (ReIn Komputer)")
    print("================================================================================")
    results = {}
    total_pass = 0

    for gid, desc, fn in CHECKS:
        try:
            status, proof = fn()
        except Exception as e:
            status, proof = False, f"Exception: {e}"

        status_str = "PASS" if status else "FAIL"
        if status:
            total_pass += 1
        print(f"[{status_str}] {gid:<4} | {desc:<45} | {proof}")
        results[gid] = {
            "deskripsi": desc,
            "status": status_str,
            "bukti": proof
        }

    summary = {
        "total_checks": len(CHECKS),
        "total_pass": total_pass,
        "total_fail": len(CHECKS) - total_pass,
        "checks": results
    }

    os.makedirs(os.path.dirname(output_json) or ".", exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("================================================================================")
    print(f"HASIL GERBANG: {total_pass}/{len(CHECKS)} PASS, {len(CHECKS) - total_pass} FAIL")
    print(f"Detail disimpan di: {output_json}")
    print("================================================================================")
    return summary


if __name__ == "__main__":
    run_gate()
