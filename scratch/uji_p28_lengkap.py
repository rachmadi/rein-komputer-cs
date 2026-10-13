# -*- coding: utf-8 -*-
"""
scratch/uji_p28_lengkap.py
Pengujian Putaran 28 Butir 7:
1. Replay live 13 Okt 05:38–06:15 (37 pesan Rachmadi, urutan sama), ATURAN_LAYANAN_P28 False vs True, 2 ulangan.
2. Regresi dengan bawaan baru (flag ATURAN_LAYANAN_P28=False):
   - live26 (2 ulangan)
   - multi20 (2 ulangan, jalur produksi)
   - satu giliran 27 (2 ulangan)
Catat ke logs/uji_history.jsonl (via CHAT_LOG_TARGET=eval).
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

# Setup path & environment
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
os.environ["CHAT_LOG_TARGET"] = "eval"
os.environ["LOG_HMAC_KEY"] = "test_hmac_secret_for_test_suite_2026"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True, encoding="utf-8")

from services.chat_service import process_chat_message
from services.agentic_tool_engine import pilih_foto_yang_akan_dikirim
from services.catalog_service import get_active_catalog
import services.agent_tools as agent_tools

# 37 Pesan Rachmadi sesi live 13 Okt 05:38–06:15
PESAN_LIVE_37 = [
    "Alhamdulillah. Aku baik. Jual laptop untuk desain gak?",
    "Butuh untuk desain 3D",
    "Ada jual gak?",
    "ROG itu bukannya untuk gaming?",
    "Oh gitu ya? Jadi beda dengan untuk desain 2D?",
    "Tapi, aku juga mulai eksplorasi AI lokal sih",
    "Jadi, rekomendasinya 2 produk tadi?",
    "Kasih aku spek ROG tadi deh sama gambarnya",
    "Gambarnya mana?",
    "Mana? Gak ada",
    "Aku kan mau lihat gambarnya dulu",
    "Aku juga butuh monitor eksternal biar bisa enak kerja dengan laptop",
    "Mahal banget. Yang paling murah yang mana?",
    "Paling mahal berapa sih?",
    "LG lebih gede, tapi harganya gak paling mahal",
    "Kalo desktop untuk desain 3D, apa rekomendasimu?",
    "Mana rekomendasi produknya??",
    "Gak ada yang ram 32 GB?",
    "Kalo gak ada, kenapa harus naikkan budget?",
    "Aku tahu. Makanya aku tanya ada yang ram 32 GB gak?",
    "Baiklah. DAri model yang kamu tawarkan, mana yang bisa upgrade ram?",
    "Lihat di mana?",
    "Aku bisa lihat di mana lembar spesifikasi itu?",
    "Yang ROG deh",
    "Mana lembar spesifikasi yang kamu bilang?",
    "Itu sama aja dengan spek sebelumnya, bukan spek lengkap yang aku bisa lihat bisa upgrade ram apa gak",
    "Makanya aku tanya di mana aku bisa lihat itu",
    "Ya sudahlah kalo gitu.",
    "Temenku sekalian mau tanya printer yang irit buat cetak banyak dokumen",
    "Kasih rekomendasi",
    "Lihat spek ecotank deh. Kalo ada sama gambarnya",
    "Gak ada fotonya?",
    "Di mana aku bisa lihat katalog kamu?",
    "Sama Reni kan?",
    "Reni tinggal di mana?",
    "Aku tanya kamu tinggal di mana?",
    "Itu aja. Terima kasih, Reni"
]

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

def hitung_foto_dikirim(res: Dict[str, Any], cat) -> List[str]:
    foto_raw = res.get("foto_akan_dikirim", [])
    prods = res.get("products", [])
    reply = res.get("reply", "")
    chosen_codes = pilih_foto_yang_akan_dikirim(
        foto_akan_dikirim=foto_raw,
        produk_disebut=prods,
        reply_text=reply,
        catalog_by_code=cat.by_code
    )
    # Filter hanya yang berkasnya benar-benar ada di disk
    valid_codes = []
    for c in chosen_codes:
        p = cat.by_code.get(c)
        if p:
            img_f = (p.get("image_file") or "").strip()
            if img_f and Path(img_f).is_file():
                valid_codes.append(c)
    return valid_codes

def jalankan_live37(aturan_layanan: bool, reps: int = 2) -> Dict[str, Any]:
    var_label = "True" if aturan_layanan else "False"
    print(f"\n=======================================================")
    print(f"--- REPLAY LIVE 37 PESAN | ATURAN_LAYANAN_P28={var_label} ({reps} ULANGAN) ---")
    print(f"=======================================================")
    cat = get_active_catalog()
    runs = []
    all_lats = []

    for rep in range(1, reps + 1):
        session_id = f"p28_live37_layanan{var_label}_rep{rep}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        print(f"\n[Live37 | Layanan={var_label} | Rep {rep}/{reps}] Sesi: {session_id}")
        turn_list = []

        for idx, u_msg in enumerate(PESAN_LIVE_37, 1):
            t0 = time.time()
            res = process_chat_message(
                session_id=session_id,
                user_text=u_msg,
                aturan_layanan_p28=aturan_layanan,
                penguji="uji_otomatis"
            )
            dur = time.time() - t0
            all_lats.append(dur)
            reply = res.get("reply", "").strip()
            tools_called = res.get("tools_called", [])
            tool_calls_detail = ekstrak_tool_calls(res)
            foto_sent = hitung_foto_dikirim(res, cat)

            print(f"  [T{idx:02d}] ({dur:4.1f}s) tools={tools_called} foto={foto_sent} | {u_msg[:30]}")

            rec = {
                "turn": idx,
                "user_msg": u_msg,
                "balasan_verbatim": reply,
                "latensi_s": round(dur, 2),
                "tools_called": tools_called,
                "tool_calls_detail": tool_calls_detail,
                "foto_dikirim": foto_sent,
                "kartu_produk": [p.get("kode") for p in res.get("products", [])]
            }
            turn_list.append(rec)

        runs.append({
            "rep": rep,
            "session_id": session_id,
            "turns": turn_list
        })

    return {
        "varian_aturan_layanan": aturan_layanan,
        "reps": reps,
        "latensi_median_s": round(hitung_persentil(all_lats, 0.50), 2),
        "latensi_p95_s": round(hitung_persentil(all_lats, 0.95), 2),
        "latensi_max_s": round(max(all_lats) if all_lats else 0.0, 2),
        "runs": runs,
        "all_latencies": all_lats
    }

def jalankan_live26(reps: int = 2) -> Dict[str, Any]:
    print(f"\n=======================================================")
    print(f"--- REGRESI LIVE 26 PESAN | BAWAAN BARU ({reps} ULANGAN) ---")
    print(f"=======================================================")
    cat = get_active_catalog()
    runs = []
    all_lats = []

    for rep in range(1, reps + 1):
        session_id = f"p28_live26_rep{rep}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        print(f"\n[Live26 | Rep {rep}/{reps}] Sesi: {session_id}")
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
            foto_sent = hitung_foto_dikirim(res, cat)

            print(f"  [T{idx:02d}] ({dur:4.1f}s) tools={tools_called} foto={foto_sent} | {u_msg[:30]}")

            rec = {
                "turn": idx,
                "user_msg": u_msg,
                "balasan_verbatim": reply,
                "latensi_s": round(dur, 2),
                "tools_called": tools_called,
                "tool_calls_detail": tool_calls_detail,
                "foto_dikirim": foto_sent,
                "kartu_produk": [p.get("kode") for p in res.get("products", [])]
            }
            turn_list.append(rec)

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
        "runs": runs,
        "all_latencies": all_lats
    }

def jalankan_multi20(reps: int = 2) -> Dict[str, Any]:
    print(f"\n=======================================================")
    print(f"--- REGRESI MULTIGILIRAN 20 PESAN | BAWAAN BARU ({reps} ULANGAN) ---")
    print(f"=======================================================")
    cat = get_active_catalog()
    runs = []
    all_lats = []

    with open("scratch/replay_20_turns_result.json", "r", encoding="utf-8") as f:
        replay_data = json.load(f)

    for rep in range(1, reps + 1):
        session_id = f"p28_multi20_rep{rep}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        print(f"\n[Multi20 | Rep {rep}/{reps}] Sesi: {session_id}")
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
            foto_sent = hitung_foto_dikirim(res, cat)

            print(f"  [T{idx:02d}] ({dur:4.1f}s) tools={tools_called} foto={foto_sent} | {u_msg[:30]}")

            rec = {
                "turn": idx,
                "user_msg": u_msg,
                "balasan_verbatim": reply,
                "latensi_s": round(dur, 2),
                "tools_called": tools_called,
                "tool_calls_detail": tool_calls_detail,
                "foto_dikirim": foto_sent
            }
            turn_list.append(rec)

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

def jalankan_single27(reps: int = 2) -> Dict[str, Any]:
    print(f"\n=======================================================")
    print(f"--- REGRESI SATU GILIRAN 27 PESAN | BAWAAN BARU ({reps} ULANGAN) ---")
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
        print(f"\n[Single27 | Rep {rep}/{reps}]")
        results = []
        for idx, c in enumerate(cases, 1):
            u_msg = c["pesan"]
            exp_tool = c["alat_diharapkan"]
            session_id = f"p28_single27_rep{rep}_t{idx}_{int(time.time())}_{uuid.uuid4().hex[:4]}"

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

            print(f"  [R{rep} T{idx:02d}/27] ({dur:4.1f}s) exp={exp_tool:<10} act={tools_called} | {u_msg[:25]}")

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
    print("===============================================================")
    print("=== MEMULAI EKSEKUSI PENGUJIAN LENGKAP PUTARAN 28 BUTIR 7 ===")
    print("===============================================================")
    t_global_start = time.time()

    # 1. Replay Live 37 (ATURAN_LAYANAN_P28 = False, 2 reps)
    res_live37_false = jalankan_live37(aturan_layanan=False, reps=2)
    with open("scratch/uji_p28_live37_false.json", "w", encoding="utf-8") as f:
        json.dump(res_live37_false, f, ensure_ascii=False, indent=2)

    # 2. Replay Live 37 (ATURAN_LAYANAN_P28 = True, 2 reps)
    res_live37_true = jalankan_live37(aturan_layanan=True, reps=2)
    with open("scratch/uji_p28_live37_true.json", "w", encoding="utf-8") as f:
        json.dump(res_live37_true, f, ensure_ascii=False, indent=2)

    # 3. Regresi Live 26 (2 reps, bawaan baru)
    res_live26 = jalankan_live26(reps=2)
    with open("scratch/uji_p28_regresi_live26.json", "w", encoding="utf-8") as f:
        json.dump(res_live26, f, ensure_ascii=False, indent=2)

    # 4. Regresi Multi 20 (2 reps, bawaan baru)
    res_multi20 = jalankan_multi20(reps=2)
    with open("scratch/uji_p28_regresi_multi20.json", "w", encoding="utf-8") as f:
        json.dump(res_multi20, f, ensure_ascii=False, indent=2)

    # 5. Regresi Single 27 (2 reps, bawaan baru)
    res_single27 = jalankan_single27(reps=2)
    with open("scratch/uji_p28_regresi_single27.json", "w", encoding="utf-8") as f:
        json.dump(res_single27, f, ensure_ascii=False, indent=2)

    # Hitung metrik P26
    # Multi20 (14 perlu alat per rep * 2 reps = 28)
    panggil_saat_perlu_multi = 0
    salah_panggil_multi = 0
    for r in res_multi20["runs"]:
        for t in r["turns"]:
            t_idx = t["turn"]
            act = len(t["tools_called"]) > 0
            if t_idx in PERLU_ALAT_TURNS_20:
                if act:
                    panggil_saat_perlu_multi += 1
            else:
                if act:
                    salah_panggil_multi += 1

    # Single 27 (20 perlu alat, 7 tidak perlu alat)
    panggil_saat_perlu_single_rep1 = 0
    salah_panggil_single_rep1 = 0
    panggil_saat_perlu_single_rep2 = 0
    salah_panggil_single_rep2 = 0

    for idx_rep, r in enumerate(res_single27["runs"]):
        for t in r["results"]:
            perlu = (t["alat_diharapkan"] != "tidak_ada")
            act = len(t["tools_called"]) > 0
            if idx_rep == 0:
                if perlu and act:
                    panggil_saat_perlu_single_rep1 += 1
                elif (not perlu) and act:
                    salah_panggil_single_rep1 += 1
            else:
                if perlu and act:
                    panggil_saat_perlu_single_rep2 += 1
                elif (not perlu) and act:
                    salah_panggil_single_rep2 += 1

    all_total_lats = (
        res_live37_false["all_latencies"]
        + res_live37_true["all_latencies"]
        + res_live26["all_latencies"]
        + res_multi20["all_latencies"]
        + res_single27["all_latencies"]
    )

    ringkasan = {
        "live37_false": {
            "median_s": res_live37_false["latensi_median_s"],
            "p95_s": res_live37_false["latensi_p95_s"],
            "max_s": res_live37_false["latensi_max_s"]
        },
        "live37_true": {
            "median_s": res_live37_true["latensi_median_s"],
            "p95_s": res_live37_true["latensi_p95_s"],
            "max_s": res_live37_true["latensi_max_s"]
        },
        "regresi_live26": {
            "median_s": res_live26["latensi_median_s"],
            "p95_s": res_live26["latensi_p95_s"],
            "max_s": res_live26["latensi_max_s"]
        },
        "regresi_multi20": {
            "median_s": res_multi20["latensi_median_s"],
            "p95_s": res_multi20["latensi_p95_s"],
            "max_s": res_multi20["latensi_max_s"],
            "multigiliran_perlu_alat": f"{panggil_saat_perlu_multi}/28",
            "salah_panggil": f"{salah_panggil_multi}/12"
        },
        "regresi_single27": {
            "median_s": res_single27["latensi_median_s"],
            "p95_s": res_single27["latensi_p95_s"],
            "max_s": res_single27["latensi_max_s"],
            "rep1_dipanggil_saat_perlu": f"{panggil_saat_perlu_single_rep1}/20",
            "rep1_salah_panggil": f"{salah_panggil_single_rep1}/7",
            "rep2_dipanggil_saat_perlu": f"{panggil_saat_perlu_single_rep2}/20",
            "rep2_salah_panggil": f"{salah_panggil_single_rep2}/7",
        },
        "keseluruhan": {
            "total_turns": len(all_total_lats),
            "median_s": round(hitung_persentil(all_total_lats, 0.50), 2),
            "p95_s": round(hitung_persentil(all_total_lats, 0.95), 2),
            "max_s": round(max(all_total_lats), 2),
            "total_durasi_menit": round((time.time() - t_global_start) / 60, 2)
        }
    }

    with open("scratch/uji_p28_ringkasan.json", "w", encoding="utf-8") as f:
        json.dump(ringkasan, f, ensure_ascii=False, indent=2)

    print("\n===============================================================")
    print("=== SELESAI PENGUJIAN LENGKAP PUTARAN 28 ===")
    print(f"Total giliran: {len(all_total_lats)}")
    print(f"Total durasi: {ringkasan['keseluruhan']['total_durasi_menit']} menit")
    print(f"Latensi Keseluruhan: Median={ringkasan['keseluruhan']['median_s']}s, P95={ringkasan['keseluruhan']['p95_s']}s, Max={ringkasan['keseluruhan']['max_s']}s")
    print(f"Multi20 Multigiliran: {ringkasan['regresi_multi20']['multigiliran_perlu_alat']}")
    print(f"Single27 Rep 1: dipanggil saat perlu {ringkasan['regresi_single27']['rep1_dipanggil_saat_perlu']}, salah panggil {ringkasan['regresi_single27']['rep1_salah_panggil']}")
    print(f"Single27 Rep 2: dipanggil saat perlu {ringkasan['regresi_single27']['rep2_dipanggil_saat_perlu']}, salah panggil {ringkasan['regresi_single27']['rep2_salah_panggil']}")
    print("===============================================================")

if __name__ == "__main__":
    main()
