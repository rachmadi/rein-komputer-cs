# -*- coding: utf-8 -*-
"""
scratch/uji_satugiliran_p21.py
Pengujian Satu Giliran 27 Pesan eval/uji_alat.csv (Putaran 21 Butir 3c).

Menjalankan 27 pesan dari eval/uji_alat.csv dengan riwayat kosong (history=[])
lewat run_agentic_tool untuk 4 varian (V4, A, B, AB), masing-masing 1 ulangan.

Metrik:
  - Panggil saat perlu (/20): pesan dengan alat_diharapkan in (katalog, pengetahuan, keduanya) yang memanggil alat
  - Salah panggil (/7): pesan dengan alat_diharapkan == "tidak_ada" yang memanggil alat
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.agentic_tool_engine import run_agentic_tool
from services.catalog_service import get_active_catalog

VARIANT_CONFIGS: Dict[str, Dict[str, Any]] = {
    "V4": {"pemeriksaan_ulang_janji": False, "mode_berpikir": False, "prompt_varian": "V4"},
    "A": {"pemeriksaan_ulang_janji": True, "mode_berpikir": False, "prompt_varian": "V4"},
    "B": {"pemeriksaan_ulang_janji": False, "mode_berpikir": True, "prompt_varian": "V4"},
    "AB": {"pemeriksaan_ulang_janji": True, "mode_berpikir": True, "prompt_varian": "V4"},
}


def load_test_cases(csv_path: str = "eval/uji_alat.csv") -> List[Dict[str, str]]:
    cases: List[Dict[str, str]] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pesan = row["pesan"].strip()
            alat = row["alat_diharapkan"].strip()
            if pesan:
                cases.append({"pesan": pesan, "alat_diharapkan": alat})
    return cases


def main():
    parser = argparse.ArgumentParser(description="Uji Satu Giliran Putaran 21")
    parser.add_argument("--variants", default="V4,A,B,AB", help="Varian yang diuji (default: V4,A,B,AB)")
    parser.add_argument("--csv", default="eval/uji_alat.csv", help="Path CSV uji (default: eval/uji_alat.csv)")
    args = parser.parse_args()

    variants = [v.strip().upper() for v in args.variants.split(",") if v.strip()]
    cases = load_test_cases(args.csv)
    cat = get_active_catalog()

    print(f"=== UJI SATU GILIRAN PUTARAN 21 ===")
    print(f"Varian: {variants} | Total kasus: {len(cases)}")
    print(f"Katalog aktif: {len(cat.by_code)} produk")

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = f"scratch/uji_satugiliran_{timestamp_str}.json"
    out_csv = f"scratch/uji_satugiliran_{timestamp_str}.csv"

    all_results: Dict[str, List[Dict[str, Any]]] = {}
    summary: Dict[str, Dict[str, Any]] = {}

    sumber_pengetahuan_global: Dict[str, int] = {}
    alasan_cadangan_global: Dict[str, int] = {}

    csv_rows: List[Dict[str, Any]] = []

    for var in variants:
        cfg = VARIANT_CONFIGS.get(var, {
            "pemeriksaan_ulang_janji": False,
            "mode_berpikir": False,
            "prompt_varian": var
        })

        print(f"\n>>> [VARIAN {var}] Menguji {len(cases)} pesan satu giliran...", flush=True)
        var_records: List[Dict[str, Any]] = []

        perlu_called = 0
        salah_called = 0
        total_perlu = 0
        total_tidak_perlu = 0

        for idx, item in enumerate(cases, 1):
            pesan = item["pesan"]
            expected = item["alat_diharapkan"]
            is_perlu = expected != "tidak_ada"

            if is_perlu:
                total_perlu += 1
            else:
                total_tidak_perlu += 1

            t0 = time.perf_counter()
            res = run_agentic_tool(
                user_text=pesan,
                history=[],
                catalog=cat,
                varian=cfg["prompt_varian"],
                pemeriksaan_ulang_janji=cfg["pemeriksaan_ulang_janji"],
                mode_berpikir=cfg["mode_berpikir"]
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000

            tools_called = res.get("tools_called", [])
            has_tool = len(tools_called) > 0

            if is_perlu and has_tool:
                perlu_called += 1
            elif not is_perlu and has_tool:
                salah_called += 1

            for tc in res.get("tool_calls", []):
                if tc.get("nama") == "pengetahuan":
                    src = tc.get("sumber", "tidak_tercatat")
                    sumber_pengetahuan_global[src] = sumber_pengetahuan_global.get(src, 0) + 1
                    if tc.get("alasan_cadangan"):
                        alasan = tc["alasan_cadangan"]
                        alasan_cadangan_global[alasan] = alasan_cadangan_global.get(alasan, 0) + 1

            record = {
                "varian": var,
                "nomor": idx,
                "pesan": pesan,
                "alat_diharapkan": expected,
                "tools_called": tools_called,
                "tool_calls": res.get("tool_calls", []),
                "pemeriksaan_ulang": bool(res.get("pemeriksaan_ulang")),
                "balasan": res.get("reply", ""),
                "latensi_ms": round(elapsed_ms, 2),
                "sukses_panggil_saat_perlu": bool(is_perlu and has_tool),
                "salah_panggil": bool(not is_perlu and has_tool),
            }
            var_records.append(record)
            csv_rows.append(record)

            tool_str = ", ".join(tools_called) if tools_called else "-"
            pu_flag = " [PU]" if res.get("pemeriksaan_ulang") else ""
            print(f"  [{idx:02d}/27] Exp: {expected:<11} | Got: {tool_str:<18}{pu_flag} | {elapsed_ms/1000:.2f}s | Msg: {pesan[:30]}", flush=True)

        all_results[var] = var_records
        summary[var] = {
            "panggil_saat_perlu": f"{perlu_called}/{total_perlu}",
            "panggil_saat_perlu_num": perlu_called,
            "total_perlu": total_perlu,
            "salah_panggil": f"{salah_called}/{total_tidak_perlu}",
            "salah_panggil_num": salah_called,
            "total_tidak_perlu": total_tidak_perlu,
        }

    # Simpan JSON
    payload = {
        "timestamp": timestamp_str,
        "variants": variants,
        "summary": summary,
        "sumber_pengetahuan_global": sumber_pengetahuan_global,
        "alasan_cadangan_global": alasan_cadangan_global,
        "details": all_results
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    # Simpan CSV
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "varian", "nomor", "pesan", "alat_diharapkan", "tools_called",
            "pemeriksaan_ulang", "latensi_ms", "sukses_panggil_saat_perlu", "salah_panggil"
        ])
        for r in csv_rows:
            writer.writerow([
                r["varian"], r["nomor"], r["pesan"], r["alat_diharapkan"],
                ",".join(r["tools_called"]), r["pemeriksaan_ulang"],
                r["latensi_ms"], r["sukses_panggil_saat_perlu"], r["salah_panggil"]
            ])

    print("\n" + "=" * 60)
    print("### HASIL UJI SATU GILIRAN (PUTARAN 21)")
    print("=" * 60)
    print("| Varian | Panggil Saat Perlu (/20) | Salah Panggil (/7) |")
    print("|---|---|---|")
    for var, s in summary.items():
        print(f"| {var:<6} | {s['panggil_saat_perlu']:<24} | {s['salah_panggil']:<18} |")
    print("=" * 60)
    print(f"Hasil JSON: {out_json}")
    print(f"Hasil CSV:  {out_csv}\n")


if __name__ == "__main__":
    main()
