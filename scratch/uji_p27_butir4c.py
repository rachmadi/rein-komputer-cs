# -*- coding: utf-8 -*-
"""
scratch/uji_p27_butir4c.py
Pengujian Regresi Putaran 27 Butir 4c pada Varian B (Bawaan Baru: KATALOG_SQL=True)
- 26 pesan live 12 Okt (2 rep)
- 20 pesan multigiliran (2 rep)
- 27 pesan satu giliran (2 rep)
"""
import sys
import os
import json
import csv
import time
import math
import uuid
from pathlib import Path
from typing import Any, Dict, List, Set

# Setup path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)


from services.chat_service import process_chat_message
import services.agent_tools as agent_tools

PESAN_LIVE_26 = [
    "Halo",
    "Ada laptop?",
    "Cuma 1 yang ada gambar?",
    "Dari tadi cuma kasih 1 gambar. Bukannya di awal nawarin 3 produk?",
    "Yang lenovo gak ada gambarnya?",
    "Ideapad ini bisa dipake untuk apa?",
    "Keknya terlalu bagus buat nenek",
    "Kalo spek kegedean kan mubazir?",
    "Cari yang murah aja. Yang penting nenek bisa nonton drama cina di youtube",
    "Apa bedanya celeron sama n100?",
    "Sekalian beliin printer deh. Nenek suka cetak foto-foto cucunya",
    "Nyetak fotonya biasanya banyak kalo nenek lagi kangen cucu",
    "Iya sih. Tapi mahal. Bisa kurang gak harganya?",
    "Ada garansi?",
    "Mantab, Ren. Reni tinggal di mana?",
    "Mau ngajak Reni jalan aja",
    "Oh gitu. Gpp deh. Sekalian mau tanya mini pc boleh?",
    "NUC gak ada gambarnya?",
    "Murah, tapi belum termasuk ram dan SSD ya?",
    "Belum termasuk monitor?",
    "Kalau apple yang mini itu, belum dapat monitor juga?",
    "Kok gak jawab?",
    "Mac mini itu belum dapat monitor juga?",
    "Nah...diem lagi deh reni",
    "Aku tadi tanya apa mac mini belum termasuk monitor juga?",
    "Tapi tinggal tambah sendiri monitor, keyboard, dan mouse, terus siap pakai?",
]

PERLU_ALAT_TURNS_20: Set[int] = {2, 3, 4, 5, 6, 9, 10, 11, 13, 14, 15, 16, 18, 19}

def hitung_persentil(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_v[int(k)]
    d0 = sorted_v[int(f)] * (c - k)
    d1 = sorted_v[int(c)] * (k - f)
    return d0 + d1

def ekstrak_tool_calls(res: Dict[str, Any]) -> List[Dict[str, Any]]:
    tc_list = res.get("metrics", {}).get("tool_calls", [])
    if not tc_list:
        tc_list = res.get("tool_calls", [])
    cleaned = []
    for tc in tc_list:
        cleaned.append({
            "nama": tc.get("nama") or tc.get("function", {}).get("name"),
            "argumen": tc.get("argumen") or tc.get("function", {}).get("arguments", {}),
            "latensi_ms": tc.get("latensi_ms", 0.0)
        })
    return cleaned

def jalankan_suite_live26(reps: int = 2) -> Dict[str, Any]:
    print(f"\n=======================================================")
    print(f"--- SUITE 1: REPLAY LIVE 26 PESAN | VARIAN B ({reps} ULANGAN) ---")
    print(f"=======================================================")
    runs = []
    all_lats = []
    turn9_records = []

    for rep in range(1, reps + 1):
        session_id = f"p27_live26_rep{rep}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        print(f"\n[Live26 | Varian B | Rep {rep}/{reps}] Sesi: {session_id}")
        turn_list = []

        for idx, u_msg in enumerate(PESAN_LIVE_26, 1):
            t0 = time.time()
            res = process_chat_message(
                session_id=session_id,
                user_text=u_msg,
                penguji="uji_otomatis"
            )
            dur = time.time() - t0
            all_lats.append(dur)
            reply = res.get("reply", "").strip()
            tools_called = res.get("tools_called", [])
            tool_calls_detail = ekstrak_tool_calls(res)

            print(f"  [T{idx:02d}] ({dur:4.1f}s) tools={tools_called} | {u_msg[:35]}")

            rec = {
                "turn": idx,
                "user_msg": u_msg,
                "balasan_verbatim": reply,
                "latensi_s": round(dur, 2),
                "tools_called": tools_called,
                "tool_calls_detail": tool_calls_detail,
            }
            turn_list.append(rec)

            if idx == 9:
                turn9_records.append({
                    "rep": rep,
                    "session_id": session_id,
                    "latensi_s": round(dur, 2),
                    "tools_called": tools_called,
                    "tool_calls_detail": tool_calls_detail,
                    "balasan_verbatim": reply
                })

        runs.append({
            "rep": rep,
            "session_id": session_id,
            "turns": turn_list
        })

    return {
        "suite": "live26",
        "reps": reps,
        "latensi_median_s": round(hitung_persentil(all_lats, 0.50), 2),
        "latensi_p95_s": round(hitung_persentil(all_lats, 0.95), 2),
        "latensi_max_s": round(max(all_lats) if all_lats else 0.0, 2),
        "turn9_murah": turn9_records,
        "runs": runs,
        "all_latencies": all_lats
    }

def jalankan_suite_multi20(reps: int = 2) -> Dict[str, Any]:
    print(f"\n=======================================================")
    print(f"--- SUITE 2: MULTIGILIRAN 20 PESAN | VARIAN B ({reps} ULANGAN) ---")
    print(f"=======================================================")
    runs = []
    all_lats = []

    with open("scratch/replay_20_turns_result.json", "r", encoding="utf-8") as f:
        replay_data = json.load(f)

    for rep in range(1, reps + 1):
        session_id = f"p27_multi20_rep{rep}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        print(f"\n[Multi20 | Varian B | Rep {rep}/{reps}] Sesi: {session_id}")
        turn_list = []

        for item in replay_data:
            idx = item["turn"]
            u_msg = item["user_msg"]

            t0 = time.time()
            res = process_chat_message(
                session_id=session_id,
                user_text=u_msg,
                penguji="uji_otomatis"
            )
            dur = time.time() - t0
            all_lats.append(dur)
            reply = res.get("reply", "").strip()
            tools_called = res.get("tools_called", [])
            tool_calls_detail = ekstrak_tool_calls(res)

            print(f"  [T{idx:02d}] ({dur:4.1f}s) tools={tools_called} | {u_msg[:35]}")

            turn_list.append({
                "turn": idx,
                "user_msg": u_msg,
                "balasan_verbatim": reply,
                "latensi_s": round(dur, 2),
                "tools_called": tools_called,
                "tool_calls_detail": tool_calls_detail
            })

        runs.append({
            "rep": rep,
            "session_id": session_id,
            "turns": turn_list
        })

    return {
        "suite": "multi20",
        "reps": reps,
        "latensi_median_s": round(hitung_persentil(all_lats, 0.50), 2),
        "latensi_p95_s": round(hitung_persentil(all_lats, 0.95), 2),
        "latensi_max_s": round(max(all_lats) if all_lats else 0.0, 2),
        "runs": runs,
        "all_latencies": all_lats
    }

def jalankan_suite_satugiliran27(reps: int = 2) -> Dict[str, Any]:
    print(f"\n=======================================================")
    print(f"--- SUITE 3: SATU GILIRAN 27 PESAN | VARIAN B ({reps} ULANGAN) ---")
    print(f"=======================================================")
    all_lats = []
    runs = []

    cases = []
    with open("eval/uji_alat.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cases.append({
                "pesan": row["pesan"].strip(),
                "alat_diharapkan": row["alat_diharapkan"].strip()
            })

    for rep in range(1, reps + 1):
        print(f"\n[SatuGiliran27 | Varian B | Rep {rep}/{reps}]")
        results = []
        for idx, c in enumerate(cases, 1):
            u_msg = c["pesan"]
            exp_tool = c["alat_diharapkan"]
            session_id = f"p27_single27_rep{rep}_t{idx}_{int(time.time())}_{uuid.uuid4().hex[:4]}"

            t0 = time.time()
            res = process_chat_message(
                session_id=session_id,
                user_text=u_msg,
                penguji="uji_otomatis"
            )
            dur = time.time() - t0
            all_lats.append(dur)
            reply = res.get("reply", "").strip()
            tools_called = res.get("tools_called", [])
            tool_calls_detail = ekstrak_tool_calls(res)

            perlu_alat = (exp_tool != "tidak_ada")
            ada_alat = (len(tools_called) > 0)
            panggil_benar = (ada_alat if perlu_alat else not ada_alat)

            print(f"  [R{rep} T{idx:02d}/27] ({dur:4.1f}s) exp={exp_tool:<10} act={tools_called} | {u_msg[:30]}")

            results.append({
                "idx": idx,
                "pesan": u_msg,
                "alat_diharapkan": exp_tool,
                "tools_called": tools_called,
                "tool_calls_detail": tool_calls_detail,
                "balasan_verbatim": reply,
                "latensi_s": round(dur, 2),
                "panggil_benar": panggil_benar
            })
        runs.append({
            "rep": rep,
            "results": results
        })

    return {
        "suite": "satugiliran27",
        "reps": reps,
        "latensi_median_s": round(hitung_persentil(all_lats, 0.50), 2),
        "latensi_p95_s": round(hitung_persentil(all_lats, 0.95), 2),
        "latensi_max_s": round(max(all_lats) if all_lats else 0.0, 2),
        "runs": runs,
        "all_latencies": all_lats
    }

def main():
    print("=== MEMULAI PENGUJIAN REGRESI PUTARAN 27 BUTIR 4c ===")
    t_start = time.time()

    # Pastikan KATALOG_SQL aktif
    agent_tools.KATALOG_SQL = True

    # 1. Jalankan Suite Live 26 (2 reps)
    res_live = jalankan_suite_live26(reps=2)
    with open("scratch/uji_p27_live26.json", "w", encoding="utf-8") as f:
        json.dump(res_live, f, ensure_ascii=False, indent=2)

    # 2. Jalankan Suite Multi 20 (2 reps)
    res_multi = jalankan_suite_multi20(reps=2)
    with open("scratch/uji_p27_multi20.json", "w", encoding="utf-8") as f:
        json.dump(res_multi, f, ensure_ascii=False, indent=2)

    # 3. Jalankan Suite Satu Giliran 27 (2 reps)
    res_single = jalankan_suite_satugiliran27(reps=2)
    with open("scratch/uji_p27_satugiliran27.json", "w", encoding="utf-8") as f:
        json.dump(res_single, f, ensure_ascii=False, indent=2)

    # Hitung ringkasan gabungan
    total_lats = res_live["all_latencies"] + res_multi["all_latencies"] + res_single["all_latencies"]

    # Hitung panggil saat perlu & salah panggil di multi20
    # 20 giliran * 2 reps = 40 giliran
    panggil_saat_perlu_multi = 0
    salah_panggil_multi = 0
    for r in res_multi["runs"]:
        for t in r["turns"]:
            t_idx = t["turn"]
            act = len(t["tools_called"]) > 0
            if t_idx in PERLU_ALAT_TURNS_20:
                if act:
                    panggil_saat_perlu_multi += 1
            else:
                if act:
                    salah_panggil_multi += 1

    # Single 27 (2 reps = 54 turns)
    perlu_28_count = 0
    for r in res_single["runs"]:
        for t in r["results"]:
            if t["alat_diharapkan"] != "tidak_ada" and len(t["tools_called"]) > 0:
                perlu_28_count += 1

    ringkasan = {
        "suite_live26": {
            "median_s": res_live["latensi_median_s"],
            "p95_s": res_live["latensi_p95_s"],
            "max_s": res_live["latensi_max_s"],
            "turn9_records": res_live["turn9_murah"]
        },
        "suite_multi20": {
            "median_s": res_multi["latensi_median_s"],
            "p95_s": res_multi["latensi_p95_s"],
            "max_s": res_multi["latensi_max_s"],
            "panggil_saat_perlu": f"{panggil_saat_perlu_multi}/28", # 14 perlu per rep * 2 = 28
            "salah_panggil": f"{salah_panggil_multi}/12" # 6 tidak perlu per rep * 2 = 12
        },
        "suite_single27": {
            "median_s": res_single["latensi_median_s"],
            "p95_s": res_single["latensi_p95_s"],
            "max_s": res_single["latensi_max_s"],
            "panggil_alat_sesuai": f"{perlu_28_count}/54"
        },
        "keseluruhan": {
            "total_turns": len(total_lats),
            "median_s": round(hitung_persentil(total_lats, 0.50), 2),
            "p95_s": round(hitung_persentil(total_lats, 0.95), 2),
            "max_s": round(max(total_lats), 2),
            "total_durasi_menit": round((time.time() - t_start) / 60, 2)
        }
    }

    with open("scratch/uji_p27_ringkasan.json", "w", encoding="utf-8") as f:
        json.dump(ringkasan, f, ensure_ascii=False, indent=2)

    print("\n=== RINGKASAN PENGUJIAN REGRESI BUTIR 4c ===")
    print(f"Total giliran: {len(total_lats)}")
    print(f"Latensi Keseluruhan: Median={ringkasan['keseluruhan']['median_s']}s, P95={ringkasan['keseluruhan']['p95_s']}s, Max={ringkasan['keseluruhan']['max_s']}s")
    print(f"Live 26: Median={res_live['latensi_median_s']}s, P95={res_live['latensi_p95_s']}s, Max={res_live['latensi_max_s']}s")
    print(f"Multi 20: Median={res_multi['latensi_median_s']}s, P95={res_multi['latensi_p95_s']}s, Max={res_multi['latensi_max_s']}s")
    print(f"Single 27: Median={res_single['latensi_median_s']}s, P95={res_single['latensi_p95_s']}s, Max={res_single['latensi_max_s']}s")

if __name__ == "__main__":
    main()
