# -*- coding: utf-8 -*-
"""
scripts/metrics.py
Acuan Tunggal Perhitungan Metrik Evaluasi Putaran 9 (ReIn Komputer).
Semua skrip evaluasi (multi-turn, replay, probe) dan skrip gerbang (gate_putaran9.py)
WAJIB menggunakan fungsi turn_ok di modul ini.
"""
import os
import glob
import hashlib
import subprocess
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple


def get_code_sha256() -> str:
    """Menghitung hash SHA-256 gabungan dari seluruh berkas services/*.py secara deterministik."""
    files = sorted(glob.glob("services/*.py"))
    hasher = hashlib.sha256()
    for fp in files:
        with open(fp, "rb") as f:
            hasher.update(f.read())
    return hasher.hexdigest()


def get_git_head() -> str:
    """Mengambil commit HEAD saat ini."""
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "unknown"


def get_file_sha256(path: str) -> str:
    """Menghitung hash SHA-256 dari berkas tertentu."""
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def get_provenance_metadata(label_path: str = None) -> Dict[str, Any]:
    """Mencatat metadata provenance wajib Putaran 9 (0.5): git_head, code_sha256, label_sha256, waktu_utc."""
    return {
        "git_head": get_git_head(),
        "code_sha256": get_code_sha256(),
        "label_sha256": get_file_sha256(label_path) if label_path else "",
        "waktu_utc": datetime.now(timezone.utc).isoformat()
    }


def turn_ok(aksi_match: bool, status_match: bool, asersi_pass: bool) -> bool:
    """
    SATU Fungsi Baku turn_ok untuk Putaran 9:
    Suatu giliran dinyatakan LULUS (turn_ok == True) jika dan hanya jika:
    1. Aksi final benar (aksi_match == True)
    2. Status fakta eksekusi mesin benar (status_match == True)
    3. Seluruh asersi mekanis lolos (asersi_pass == True)

    Jika salah satu dari ketiga kriteria ini False, maka turn_ok == False.
    """
    return bool(aksi_match and status_match and asersi_pass)


def evaluate_turn_record(record: Dict[str, Any]) -> bool:
    """
    Mengevaluasi apakah suatu dictionary record hasil giliran berstatus turn_ok.
    Menerima record yang memiliki field:
    - 'aksi_match', 'status_match', 'asersi_pass', atau
    - 'aksi_pred' / 'aksi_terpilih' vs 'aksi_gold'
    - 'fakta_status' / 'status_pred' vs 'status_gold' / 'status_fakta_benar'
    - 'asersi_pass'
    """
    if "turn_ok" in record and isinstance(record["turn_ok"], bool):
        return record["turn_ok"]

    if "aksi_match" in record and "status_match" in record and "asersi_pass" in record:
        return turn_ok(record["aksi_match"], record["status_match"], record["asersi_pass"])

    aksi_pred = record.get("aksi_pred") or record.get("aksi_terpilih") or ""
    aksi_gold = record.get("aksi_gold") or record.get("aksi_benar") or ""
    aksi_match = (aksi_pred.lower().strip() == aksi_gold.lower().strip()) if aksi_gold else True

    status_pred = record.get("fakta_status") or record.get("status_pred") or ""
    status_gold = record.get("status_gold") or record.get("status_fakta_benar") or ""
    status_match = (str(status_pred).lower().strip() == str(status_gold).lower().strip()) if status_gold else True

    asersi_pass = record.get("asersi_pass", True)

    return turn_ok(aksi_match, status_match, asersi_pass)


def summarize_turn_metrics(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Menghitung ringkasan agregat metrik untuk kumpulan record giliran.
    """
    total = len(records)
    if total == 0:
        return {
            "total_turns": 0,
            "turns_ok": 0,
            "turn_ok_percent": 0.0,
            "aksi_match_percent": 0.0,
            "status_match_percent": 0.0,
            "asersi_pass_percent": 0.0
        }

    ok_cnt = 0
    aksi_cnt = 0
    status_cnt = 0
    asersi_cnt = 0

    for r in records:
        is_ok = evaluate_turn_record(r)
        if is_ok:
            ok_cnt += 1

        a_match = r.get("aksi_match")
        if a_match is None:
            ap = r.get("aksi_pred") or r.get("aksi_terpilih") or ""
            ag = r.get("aksi_gold") or r.get("aksi_benar") or ""
            a_match = (ap.lower().strip() == ag.lower().strip()) if ag else True
        if a_match:
            aksi_cnt += 1

        s_match = r.get("status_match")
        if s_match is None:
            sp = r.get("fakta_status") or r.get("status_pred") or ""
            sg = r.get("status_gold") or r.get("status_fakta_benar") or ""
            s_match = (str(sp).lower().strip() == str(sg).lower().strip()) if sg else True
        if s_match:
            status_cnt += 1

        if r.get("asersi_pass", True):
            asersi_cnt += 1

    return {
        "total_turns": total,
        "turns_ok": ok_cnt,
        "turn_ok_percent": round(ok_cnt / total * 100.0, 2),
        "aksi_correct": aksi_cnt,
        "aksi_match_percent": round(aksi_cnt / total * 100.0, 2),
        "status_correct": status_cnt,
        "status_match_percent": round(status_cnt / total * 100.0, 2),
        "assertions_passed": asersi_cnt,
        "asersi_pass_percent": round(asersi_cnt / total * 100.0, 2),
    }
