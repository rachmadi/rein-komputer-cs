# -*- coding: utf-8 -*-
"""
scratch/uji_p29_lengkap.py
Pengujian Putaran 29 Butir 5:
1. Replay live 13 Okt 05:38–06:15 (37 pesan persis dari log), 3 ulangan:
   - Varian A: CATATAN_PENGETAHUAN_KATALOG=False, PRODUK_TERDEKAT=False
   - Varian B: CATATAN_PENGETAHUAN_KATALOG=True, PRODUK_TERDEKAT=True
2. Regresi Varian B (kedua flag True, jalur produksi):
   - live26 (2 ulangan)
   - multi20 (2 ulangan, jalur produksi)
   - satu giliran 27 (2 ulangan)
Catat ke logs/uji_history.jsonl (via CHAT_LOG_TARGET=eval, penguji=uji_otomatis).
Simpan hasil alat LENGKAP per panggilan di JSON uji.
Ekstrak tabel 10 giliran khusus dan daftar SEMUA giliran yang balasannya memuat foto/gambar.
"""
import sys
import os
import json
import csv
import time
import math
import uuid
import re
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

# 37 Pesan Rachmadi sesi live 13 Okt 05:38–06:15
PESAN_LIVE_37 = [
    "Alhamdulillah. Aku baik. Jual laptop untuk desain gak?",           # T01
    "Butuh untuk desain 3D",                                            # T02
    "Ada jual gak?",                                                    # T03
    "ROG itu bukannya untuk gaming?",                                   # T04
    "Oh gitu ya? Jadi beda dengan untuk desain 2D?",                    # T05
    "Tapi, aku juga mulai eksplorasi AI lokal sih",                     # T06
    "Jadi, rekomendasinya 2 produk tadi?",                              # T07
    "Kasih aku spek ROG tadi deh sama gambarnya",                       # T08
    "Gambarnya mana?",                                                  # T09
    "Mana? Gak ada",                                                    # T10
    "Aku kan mau lihat gambarnya dulu",                                 # T11
    "Aku juga butuh monitor eksternal biar bisa enak kerja dengan laptop", # T12
    "Mahal banget. Yang paling murah yang mana?",                       # T13
    "Paling mahal berapa sih?",                                         # T14
    "LG lebih gede, tapi harganya gak paling mahal",                    # T15
    "Kalo desktop untuk desain 3D, apa rekomendasimu?",                 # T16
    "Mana rekomendasi produknya??",                                     # T17
    "Gak ada yang ram 32 GB?",                                          # T18
    "Kalo gak ada, kenapa harus naikkan budget?",                       # T19
    "Aku tahu. Makanya aku tanya ada yang ram 32 GB gak?",              # T20
    "Baiklah. DAri model yang kamu tawarkan, mana yang bisa upgrade ram?", # T21
    "Lihat di mana?",                                                   # T22
    "Aku bisa lihat di mana lembar spesifikasi itu?",                   # T23
    "Yang ROG deh",                                                     # T24
    "Mana lembar spesifikasi yang kamu bilang?",                        # T25
    "Itu sama aja dengan spek sebelumnya, bukan spek lengkap yang aku bisa lihat bisa upgrade ram apa gak", # T26
    "Makanya aku tanya di mana aku bisa lihat itu",                     # T27
    "Ya sudahlah kalo gitu.",                                           # T28
    "Temenku sekalian mau tanya printer yang irit buat cetak banyak dokumen", # T29
    "Kasih rekomendasi",                                                # T30
    "Lihat spek ecotank deh. Kalo ada sama gambarnya",                  # T31
    "Gak ada fotonya?",                                                 # T32
    "Di mana aku bisa lihat katalog kamu?",                             # T33
    "Sama Reni kan?",                                                   # T34
    "Reni tinggal di mana?",                                            # T35
    "Aku tanya kamu tinggal di mana?",                                  # T36
    "Itu aja. Terima kasih, Reni"                                       # T37
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

SEPULUH_GILIRAN_TARGET = [
    "Alhamdulillah. Aku baik. Jual laptop untuk desain gak?",
    "Butuh untuk desain 3D",
    "Kalo desktop untuk desain 3D, apa rekomendasimu?",
    "Gak ada yang ram 32 GB?",
    "Kasih aku spek ROG tadi deh sama gambarnya",
    "Gambarnya mana?",
    "Mana? Gak ada",
    "Aku kan mau lihat gambarnya dulu",
    "Lihat spek ecotank deh. Kalo ada sama gambarnya",
    "Gak ada fotonya?"
]

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
            "ringkasan_hasil": tc.get("ringkasan_hasil"),
            "hasil_lengkap": tc.get("hasil"),
            "latensi_ms": tc.get("latensi_ms", 0.0)
        })
    return cleaned

def hitung_foto_dikirim(res: Dict[str, Any], cat) -> List[str]:
    foto_raw = res.get("foto_tersedia") or res.get("foto_akan_dikirim", [])
    prods = res.get("products", [])
    reply = res.get("reply", "")
    chosen_codes = pilih_foto_yang_akan_dikirim(
        foto_tersedia=foto_raw,
        produk_disebut=prods,
        reply_text=reply,
        catalog_by_code=cat.by_code
    )
    valid_codes = []
    for c in chosen_codes:
        p = cat.by_code.get(c)
        if p:
            img_f = (p.get("image_file") or "").strip()
            if img_f and Path(img_f).is_file():
                valid_codes.append(c)
    return valid_codes

def jalankan_live37(catatan_pengetahuan: bool, produk_terdekat: bool, reps: int = 3, label_varian: str = "A") -> Dict[str, Any]:
    print(f"\n=======================================================")
    print(f"--- REPLAY LIVE 37 PESAN | VARIAN {label_varian} (Catatan={catatan_pengetahuan}, Terdekat={produk_terdekat}) ({reps} ULANGAN) ---")
    print(f"=======================================================")
    cat = get_active_catalog()
    runs = []
    all_lats = []

    for rep in range(1, reps + 1):
        session_id = f"p29_live37_var{label_varian}_rep{rep}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        print(f"\n[Live37 | Varian {label_varian} | Rep {rep}/{reps}] Sesi: {session_id}")
        turn_list = []

        for idx, u_msg in enumerate(PESAN_LIVE_37, 1):
            t0 = time.time()
            res = process_chat_message(
                session_id=session_id,
                user_text=u_msg,
                catatan_pengetahuan_katalog=catatan_pengetahuan,
                produk_terdekat=produk_terdekat,
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
                "foto_tersedia": res.get("foto_tersedia", []),
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
        "varian": label_varian,
        "catatan_pengetahuan_katalog": catatan_pengetahuan,
        "produk_terdekat": produk_terdekat,
        "reps": reps,
        "latensi_median_s": round(hitung_persentil(all_lats, 0.50), 2),
        "latensi_p95_s": round(hitung_persentil(all_lats, 0.95), 2),
        "latensi_max_s": round(max(all_lats) if all_lats else 0.0, 2),
        "runs": runs,
        "all_latencies": all_lats
    }

def jalankan_live26(reps: int = 2) -> Dict[str, Any]:
    print(f"\n=======================================================")
    print(f"--- REGRESI LIVE 26 PESAN | VARIAN B (KEDUA FLAG TRUE) ({reps} ULANGAN) ---")
    print(f"=======================================================")
    cat = get_active_catalog()
    runs = []
    all_lats = []

    for rep in range(1, reps + 1):
        session_id = f"p29_live26_varB_rep{rep}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        print(f"\n[Live26 | Rep {rep}/{reps}] Sesi: {session_id}")
        turn_list = []

        for idx, u_msg in enumerate(PESAN_LIVE_26, 1):
            t0 = time.time()
            res = process_chat_message(
                session_id=session_id,
                user_text=u_msg,
                catatan_pengetahuan_katalog=True,
                produk_terdekat=True,
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
                "foto_tersedia": res.get("foto_tersedia", []),
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
        "varian": "B",
        "reps": reps,
        "latensi_median_s": round(hitung_persentil(all_lats, 0.50), 2),
        "latensi_p95_s": round(hitung_persentil(all_lats, 0.95), 2),
        "latensi_max_s": round(max(all_lats) if all_lats else 0.0, 2),
        "runs": runs,
        "all_latencies": all_lats
    }

def jalankan_multi20(reps: int = 2) -> Dict[str, Any]:
    print(f"\n=======================================================")
    print(f"--- REGRESI MULTIGILIRAN 20 PESAN | VARIAN B (JALUR PRODUKSI) ({reps} ULANGAN) ---")
    print(f"=======================================================")
    cat = get_active_catalog()
    runs = []
    all_lats = []

    with open("scratch/replay_20_turns_result.json", "r", encoding="utf-8") as f:
        replay_data = json.load(f)

    for rep in range(1, reps + 1):
        session_id = f"p29_multi20_varB_rep{rep}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        print(f"\n[Multi20 | Rep {rep}/{reps}] Sesi: {session_id}")
        turn_list = []

        for item in replay_data:
            idx = item["turn"]
            u_msg = item["user_msg"]

            t0 = time.time()
            res = process_chat_message(
                session_id=session_id,
                user_text=u_msg,
                catatan_pengetahuan_katalog=True,
                produk_terdekat=True,
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
                "foto_tersedia": res.get("foto_tersedia", []),
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
        "suite": "multi20",
        "varian": "B",
        "reps": reps,
        "latensi_median_s": round(hitung_persentil(all_lats, 0.50), 2),
        "latensi_p95_s": round(hitung_persentil(all_lats, 0.95), 2),
        "latensi_max_s": round(max(all_lats) if all_lats else 0.0, 2),
        "runs": runs,
        "all_latencies": all_lats
    }

def jalankan_single27(reps: int = 2) -> Dict[str, Any]:
    print(f"\n=======================================================")
    print(f"--- REGRESI SATU GILIRAN 27 PESAN | VARIAN B ({reps} ULANGAN) ---")
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
            session_id = f"p29_single27_varB_rep{rep}_t{idx}_{int(time.time())}_{uuid.uuid4().hex[:4]}"

            t0 = time.time()
            res = process_chat_message(
                session_id=session_id,
                user_text=u_msg,
                catatan_pengetahuan_katalog=True,
                produk_terdekat=True,
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
                "foto_tersedia": res.get("foto_tersedia", []),
                "foto_dikirim": [],
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
        "varian": "B",
        "reps": reps,
        "latensi_median_s": round(hitung_persentil(all_lats, 0.50), 2),
        "latensi_p95_s": round(hitung_persentil(all_lats, 0.95), 2),
        "latensi_max_s": round(max(all_lats) if all_lats else 0.0, 2),
        "runs": runs,
        "all_latencies": all_lats
    }

def format_argumen_alat(tool_calls_detail: List[Dict[str, Any]]) -> str:
    if not tool_calls_detail:
        return "tidak panggil alat"
    parts = []
    for tc in tool_calls_detail:
        nama = tc.get("nama", "")
        args = tc.get("argumen", {})
        parts.append(f"{nama}({json.dumps(args, ensure_ascii=False)})")
    return "; ".join(parts)

def main():
    print("===============================================================")
    print("=== MEMULAI EKSEKUSI PENGUJIAN LENGKAP PUTARAN 29 BUTIR 5 ===")
    print("===============================================================")
    t_global_start = time.time()

    # 1. Replay Live 37 Varian A (kedua flag False, 3 ulangan)
    res_live37_varA = jalankan_live37(catatan_pengetahuan=False, produk_terdekat=False, reps=3, label_varian="A")
    with open("scratch/uji_p29_live37_varian_a.json", "w", encoding="utf-8") as f:
        json.dump(res_live37_varA, f, ensure_ascii=False, indent=2)

    # 2. Replay Live 37 Varian B (kedua flag True, 3 ulangan)
    res_live37_varB = jalankan_live37(catatan_pengetahuan=True, produk_terdekat=True, reps=3, label_varian="B")
    with open("scratch/uji_p29_live37_varian_b.json", "w", encoding="utf-8") as f:
        json.dump(res_live37_varB, f, ensure_ascii=False, indent=2)

    # 3. Regresi Live 26 Varian B (2 ulangan)
    res_live26 = jalankan_live26(reps=2)
    with open("scratch/uji_p29_regresi_live26.json", "w", encoding="utf-8") as f:
        json.dump(res_live26, f, ensure_ascii=False, indent=2)

    # 4. Regresi Multi 20 Varian B (2 ulangan, jalur produksi)
    res_multi20 = jalankan_multi20(reps=2)
    with open("scratch/uji_p29_regresi_multi20.json", "w", encoding="utf-8") as f:
        json.dump(res_multi20, f, ensure_ascii=False, indent=2)

    # 5. Regresi Single 27 Varian B (2 ulangan)
    res_single27 = jalankan_single27(reps=2)
    with open("scratch/uji_p29_regresi_single27.json", "w", encoding="utf-8") as f:
        json.dump(res_single27, f, ensure_ascii=False, indent=2)

    # Ekstrak Tabel 10 Giliran Khusus untuk Laporan
    tabel_10 = []
    target_set = set(SEPULUH_GILIRAN_TARGET)

    # Susun per giliran target, lalu per varian (A lalu B), lalu per ulangan (1, 2, 3)
    for target_msg in SEPULUH_GILIRAN_TARGET:
        for var_label, res_var in [("A", res_live37_varA), ("B", res_live37_varB)]:
            for r in res_var["runs"]:
                rep_num = r["rep"]
                for t in r["turns"]:
                    if t["user_msg"] == target_msg:
                        tabel_10.append({
                            "pesan_user": target_msg,
                            "turn_index": t["turn"],
                            "varian": f"Varian {var_label}",
                            "ulangan": rep_num,
                            "argumen_alat": format_argumen_alat(t["tool_calls_detail"]),
                            "kode_foto_terkirim": t["foto_dikirim"],
                            "balasan_verbatim": t["balasan_verbatim"]
                        })

    with open("scratch/uji_p29_tabel_10_turns.json", "w", encoding="utf-8") as f:
        json.dump(tabel_10, f, ensure_ascii=False, indent=2)

    # Ekstrak SEMUA giliran dari SEMUA uji yang balasannya memuat kata "foto" atau "gambar"
    semua_foto_turns = []
    regex_foto = re.compile(r"\b(foto|gambar)\b", re.IGNORECASE)

    all_suites_data = [
        ("live37_varian_a", res_live37_varA),
        ("live37_varian_b", res_live37_varB),
        ("regresi_live26", res_live26),
        ("regresi_multi20", res_multi20),
        ("regresi_single27", res_single27),
    ]

    for suite_name, suite_dict in all_suites_data:
        var_label = suite_dict.get("varian", "B")
        for r in suite_dict.get("runs", []):
            rep_num = r.get("rep", 1)
            turns_or_results = r.get("turns") or r.get("results") or []
            for item in turns_or_results:
                reply = item.get("balasan_verbatim", "")
                if regex_foto.search(reply):
                    semua_foto_turns.append({
                        "suite": suite_name,
                        "varian": var_label,
                        "rep": rep_num,
                        "turn": item.get("turn") or item.get("idx"),
                        "user_msg": item.get("user_msg") or item.get("pesan"),
                        "argumen_alat": format_argumen_alat(item.get("tool_calls_detail", [])),
                        "kode_foto_terkirim": item.get("foto_dikirim", []),
                        "balasan_verbatim": reply
                    })

    with open("scratch/uji_p29_semua_foto_turns.json", "w", encoding="utf-8") as f:
        json.dump(semua_foto_turns, f, ensure_ascii=False, indent=2)

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
        res_live37_varA["all_latencies"]
        + res_live37_varB["all_latencies"]
        + res_live26["all_latencies"]
        + res_multi20["all_latencies"]
        + res_single27["all_latencies"]
    )

    ringkasan = {
        "live37_varian_a": {
            "median_s": res_live37_varA["latensi_median_s"],
            "p95_s": res_live37_varA["latensi_p95_s"],
            "max_s": res_live37_varA["latensi_max_s"]
        },
        "live37_varian_b": {
            "median_s": res_live37_varB["latensi_median_s"],
            "p95_s": res_live37_varB["latensi_p95_s"],
            "max_s": res_live37_varB["latensi_max_s"]
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

    with open("scratch/uji_p29_ringkasan.json", "w", encoding="utf-8") as f:
        json.dump(ringkasan, f, ensure_ascii=False, indent=2)

    print("\n===============================================================")
    print("=== SELESAI PENGUJIAN LENGKAP PUTARAN 29 ===")
    print(f"Total giliran: {len(all_total_lats)}")
    print(f"Total durasi: {ringkasan['keseluruhan']['total_durasi_menit']} menit")
    print(f"Latensi Keseluruhan: Median={ringkasan['keseluruhan']['median_s']}s, P95={ringkasan['keseluruhan']['p95_s']}s, Max={ringkasan['keseluruhan']['max_s']}s")
    print(f"Multi20 Multigiliran: {ringkasan['regresi_multi20']['multigiliran_perlu_alat']}")
    print(f"Single27 Rep 1: dipanggil saat perlu {ringkasan['regresi_single27']['rep1_dipanggil_saat_perlu']}, salah panggil {ringkasan['regresi_single27']['rep1_salah_panggil']}")
    print(f"Single27 Rep 2: dipanggil saat perlu {ringkasan['regresi_single27']['rep2_dipanggil_saat_perlu']}, salah panggil {ringkasan['regresi_single27']['rep2_salah_panggil']}")
    print(f"Total giliran ber-kata foto/gambar: {len(semua_foto_turns)}")
    print("===============================================================")

if __name__ == "__main__":
    main()
