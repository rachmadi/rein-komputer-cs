# -*- coding: utf-8 -*-
"""
scratch/uji_p25_butir4.py
Pengujian Putaran 25 Butir 4: Aturan Nama Reni (R2 vs R3)
Semua pengujian dijalankan lewat jalur produksi (process_chat_message) dengan session_id unik per ulangan.

Tiga Pengujian:
1. Replay 26 pesan pelanggan sesi live 12 Okt 19:54–20:14 (urutan asli), 2 ulangan per varian
2. Uji multigiliran 20 pesan replay (scratch/replay_20_turns_result.json), 2 ulangan per varian
3. Uji satu giliran 27 pesan (eval/uji_alat.csv), 1 ulangan per varian (sesi baru per pesan)

Metrik yang dihitung per varian:
- Balasan pertama memperkenalkan Reni (/ulangan)
- Balasan lain yang memuat nama "Reni" (beserta pesan pelanggannya)
- Panggil saat perlu /20, salah panggil /7 (dari uji satu giliran 27 pesan)
- Perlu dipanggil /28 (dari uji multigiliran 20 pesan, 14 slot x 2 ulangan)
- Latensi maksimum
"""
import sys
import os
import json
import csv
import time
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# Tambahkan root proyek ke sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.chat_service import process_chat_message, get_session_manager
from core.catalog import Catalog
from services.catalog_service import get_active_catalog

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

RENI_PATTERN = re.compile(r"\breni\b", re.IGNORECASE)

def cek_kenalkan_reni(teks: str) -> bool:
    """Mengecek apakah balasan memperkenalkan diri sebagai Reni."""
    t = teks.lower()
    if "saya reni" in t or "namaku reni" or "nama saya reni" in t or "reni dari rein komputer" in t or "perkenalkan, saya reni" in t:
        return bool(RENI_PATTERN.search(t))
    return bool(RENI_PATTERN.search(t))


def jalankan_suite_live26(variant: str, reps: int = 2) -> Dict[str, Any]:
    print(f"\n=======================================================")
    print(f"--- SUITE 1: REPLAY LIVE 26 PESAN | VARIAN {variant} ({reps} ULANGAN) ---")
    print(f"=======================================================")
    is_r3 = (variant == "R3")
    runs = []
    max_lat = 0.0

    for rep in range(1, reps + 1):
        session_id = f"p25_live26_{variant}_rep{rep}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        print(f"\n[Live26 | {variant} | Rep {rep}/{reps}] Sesi: {session_id}")
        turn_list = []

        for idx, u_msg in enumerate(PESAN_LIVE_26, 1):
            t0 = time.time()
            res = process_chat_message(
                session_id=session_id,
                user_text=u_msg,
                persona_nama_r3=is_r3,
                varian="V4"
            )
            dur = time.time() - t0
            max_lat = max(max_lat, dur)
            reply = res.get("reply", "").strip()
            tools_called = res.get("tools_called", [])
            has_reni = bool(RENI_PATTERN.search(reply))
            kenalkan_g1 = bool(idx == 1 and has_reni)

            print(f"  [T{idx:02d}] ({dur:4.1f}s) tools={tools_called} reni={has_reni} | {u_msg[:30]}")

            turn_list.append({
                "turn": idx,
                "user_msg": u_msg,
                "balasan_verbatim": reply,
                "latensi_s": round(dur, 2),
                "tools_called": tools_called,
                "memuat_reni": has_reni,
                "kenalkan_g1": kenalkan_g1
            })

        runs.append({
            "rep": rep,
            "session_id": session_id,
            "turns": turn_list
        })

    return {
        "suite": "live26",
        "variant": variant,
        "reps": reps,
        "max_latensi_s": round(max_lat, 2),
        "runs": runs
    }


def jalankan_suite_multi20(variant: str, reps: int = 2) -> Dict[str, Any]:
    print(f"\n=======================================================")
    print(f"--- SUITE 2: MULTIGILIRAN 20 PESAN | VARIAN {variant} ({reps} ULANGAN) ---")
    print(f"=======================================================")
    is_r3 = (variant == "R3")
    runs = []
    max_lat = 0.0

    with open("scratch/replay_20_turns_result.json", "r", encoding="utf-8") as f:
        replay_data = json.load(f)

    for rep in range(1, reps + 1):
        session_id = f"p25_multi20_{variant}_rep{rep}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        print(f"\n[Multi20 | {variant} | Rep {rep}/{reps}] Sesi: {session_id}")
        turn_list = []

        for item in replay_data:
            idx = item["turn"]
            u_msg = item["user_msg"]

            t0 = time.time()
            res = process_chat_message(
                session_id=session_id,
                user_text=u_msg,
                persona_nama_r3=is_r3,
                varian="V4"
            )
            dur = time.time() - t0
            max_lat = max(max_lat, dur)
            reply = res.get("reply", "").strip()
            tools_called = res.get("tools_called", [])
            has_reni = bool(RENI_PATTERN.search(reply))
            kenalkan_g1 = bool(idx == 1 and has_reni)

            print(f"  [T{idx:02d}] ({dur:4.1f}s) tools={tools_called} reni={has_reni} | {u_msg[:30]}")

            turn_list.append({
                "turn": idx,
                "user_msg": u_msg,
                "balasan_verbatim": reply,
                "latensi_s": round(dur, 2),
                "tools_called": tools_called,
                "memuat_reni": has_reni,
                "kenalkan_g1": kenalkan_g1
            })

        runs.append({
            "rep": rep,
            "session_id": session_id,
            "turns": turn_list
        })

    return {
        "suite": "multi20",
        "variant": variant,
        "reps": reps,
        "max_latensi_s": round(max_lat, 2),
        "runs": runs
    }


def jalankan_suite_satugiliran27(variant: str) -> Dict[str, Any]:
    print(f"\n=======================================================")
    print(f"--- SUITE 3: SATU GILIRAN 27 PESAN | VARIAN {variant} (1 ULANGAN) ---")
    print(f"=======================================================")
    is_r3 = (variant == "R3")
    max_lat = 0.0

    cases = []
    with open("eval/uji_alat.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cases.append({
                "pesan": row["pesan"].strip(),
                "alat_diharapkan": row["alat_diharapkan"].strip()
            })

    results = []
    for idx, c in enumerate(cases, 1):
        u_msg = c["pesan"]
        exp_tool = c["alat_diharapkan"]
        session_id = f"p25_single27_{variant}_t{idx}_{int(time.time())}_{uuid.uuid4().hex[:4]}"

        t0 = time.time()
        res = process_chat_message(
            session_id=session_id,
            user_text=u_msg,
            persona_nama_r3=is_r3,
            varian="V4"
        )
        dur = time.time() - t0
        max_lat = max(max_lat, dur)
        reply = res.get("reply", "").strip()
        tools_called = res.get("tools_called", [])
        has_reni = bool(RENI_PATTERN.search(reply))

        perlu_alat = (exp_tool != "tidak_ada")
        ada_alat = (len(tools_called) > 0)
        panggil_benar = (ada_alat if perlu_alat else not ada_alat)

        print(f"  [{idx:02d}/27] ({dur:4.1f}s) exp={exp_tool:<10} act={tools_called} reni={has_reni} | {u_msg[:30]}")

        results.append({
            "idx": idx,
            "pesan": u_msg,
            "alat_diharapkan": exp_tool,
            "tools_called": tools_called,
            "balasan_verbatim": reply,
            "latensi_s": round(dur, 2),
            "memuat_reni": has_reni,
            "panggil_benar": panggil_benar
        })

    return {
        "suite": "satugiliran27",
        "variant": variant,
        "max_latensi_s": round(max_lat, 2),
        "results": results
    }


def evaluasi_dan_simpan(
    hasil_live26_r2: Dict[str, Any],
    hasil_live26_r3: Dict[str, Any],
    hasil_multi20_r2: Dict[str, Any],
    hasil_multi20_r3: Dict[str, Any],
    hasil_single27_r2: Dict[str, Any],
    hasil_single27_r3: Dict[str, Any],
):
    def hitung_metrik(live: Dict[str, Any], multi: Dict[str, Any], single: Dict[str, Any]) -> Dict[str, Any]:
        # 1. Balasan pertama memperkenalkan Reni (/ulangan)
        # Total ulangan: 2 (live) + 2 (multi) = 4 ulangan percakapan
        g1_live_reni = sum(1 for r in live["runs"] if r["turns"][0]["kenalkan_g1"])
        g1_multi_reni = sum(1 for r in multi["runs"] if r["turns"][0]["kenalkan_g1"])
        total_g1_reps = len(live["runs"]) + len(multi["runs"])
        total_g1_reni = g1_live_reni + g1_multi_reni

        # 2. Balasan lain yang memuat nama "Reni" (beserta pesan pelanggannya)
        balasan_lain_reni = []
        for r in live["runs"]:
            rep_no = r["rep"]
            for t in r["turns"][1:]:  # turn 2 onwards
                if t["memuat_reni"]:
                    balasan_lain_reni.append({
                        "sumber": f"live26_rep{rep_no}",
                        "turn": t["turn"],
                        "user_msg": t["user_msg"],
                        "balasan_verbatim": t["balasan_verbatim"]
                    })
        for r in multi["runs"]:
            rep_no = r["rep"]
            for t in r["turns"][1:]:
                if t["memuat_reni"]:
                    balasan_lain_reni.append({
                        "sumber": f"multi20_rep{rep_no}",
                        "turn": t["turn"],
                        "user_msg": t["user_msg"],
                        "balasan_verbatim": t["balasan_verbatim"]
                    })

        # 3. Panggil saat perlu /20, salah panggil /7 (dari uji satu giliran)
        panggil_saat_perlu = 0
        salah_panggil = 0
        for item in single["results"]:
            exp = item["alat_diharapkan"]
            has_tool = len(item["tools_called"]) > 0
            if exp != "tidak_ada":
                if has_tool:
                    panggil_saat_perlu += 1
            else:
                if has_tool:
                    salah_panggil += 1

        # 4. Perlu dipanggil /28 (dari multi20, 14 slot x 2 ulangan)
        perlu_dipanggil_28 = 0
        for r in multi["runs"]:
            for t in r["turns"]:
                if t["turn"] in PERLU_ALAT_TURNS_20:
                    if len(t["tools_called"]) > 0:
                        perlu_dipanggil_28 += 1

        # 5. Latensi maksimum
        all_lats = []
        for r in live["runs"]:
            for t in r["turns"]:
                all_lats.append(t["latensi_s"])
        for r in multi["runs"]:
            for t in r["turns"]:
                all_lats.append(t["latensi_s"])
        for item in single["results"]:
            all_lats.append(item["latensi_s"])

        max_lat = max(all_lats) if all_lats else 0.0

        return {
            "g1_kenalkan_reni": f"{total_g1_reni}/{total_g1_reps}",
            "g1_live": f"{g1_live_reni}/{len(live['runs'])}",
            "g1_multi": f"{g1_multi_reni}/{len(multi['runs'])}",
            "jumlah_balasan_lain_reni": len(balasan_lain_reni),
            "detail_balasan_lain_reni": balasan_lain_reni,
            "panggil_saat_perlu": f"{panggil_saat_perlu}/20",
            "salah_panggil": f"{salah_panggil}/7",
            "perlu_dipanggil_28": f"{perlu_dipanggil_28}/28",
            "latensi_maksimum_s": round(max_lat, 2)
        }

    metrik_r2 = hitung_metrik(hasil_live26_r2, hasil_multi20_r2, hasil_single27_r2)
    metrik_r3 = hitung_metrik(hasil_live26_r3, hasil_multi20_r3, hasil_single27_r3)

    ringkasan = {
        "timestamp": datetime.now().isoformat(),
        "R2": metrik_r2,
        "R3": metrik_r3
    }

    # Simpan semua berkas JSON
    with open("scratch/uji_p25_live26.json", "w", encoding="utf-8") as f:
        json.dump({"R2": hasil_live26_r2, "R3": hasil_live26_r3}, f, ensure_ascii=False, indent=2)

    with open("scratch/uji_p25_multi20.json", "w", encoding="utf-8") as f:
        json.dump({"R2": hasil_multi20_r2, "R3": hasil_multi20_r3}, f, ensure_ascii=False, indent=2)

    with open("scratch/uji_p25_satugiliran27.json", "w", encoding="utf-8") as f:
        json.dump({"R2": hasil_single27_r2, "R3": hasil_single27_r3}, f, ensure_ascii=False, indent=2)

    with open("scratch/uji_p25_ringkasan.json", "w", encoding="utf-8") as f:
        json.dump(ringkasan, f, ensure_ascii=False, indent=2)

    # Simpan CSV ringkasan perbandingan
    with open("scratch/uji_p25_perbandingan_r2_r3.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Metrik", "R2 (Bawaan)", "R3"])
        writer.writerow(["Balasan pertama memperkenalkan Reni", metrik_r2["g1_kenalkan_reni"], metrik_r3["g1_kenalkan_reni"]])
        writer.writerow(["Balasan lain yang memuat nama Reni", metrik_r2["jumlah_balasan_lain_reni"], metrik_r3["jumlah_balasan_lain_reni"]])
        writer.writerow(["Panggil saat perlu (/20)", metrik_r2["panggil_saat_perlu"], metrik_r3["panggil_saat_perlu"]])
        writer.writerow(["Salah panggil (/7)", metrik_r2["salah_panggil"], metrik_r3["salah_panggil"]])
        writer.writerow(["Perlu dipanggil (/28)", metrik_r2["perlu_dipanggil_28"], metrik_r3["perlu_dipanggil_28"]])
        writer.writerow(["Latensi maksimum (detik)", metrik_r2["latensi_maksimum_s"], metrik_r3["latensi_maksimum_s"]])

    print("\n" + "=" * 80)
    print("### HASIL PERBANDINGAN R2 VS R3 (PUTARAN 25 BUTIR 4)")
    print("=" * 80)
    print(f"{'Metrik':<38} | {'R2 (Bawaan)':<15} | {'R3':<15}")
    print("-" * 80)
    print(f"{'Balasan pertama memperkenalkan Reni':<38} | {metrik_r2['g1_kenalkan_reni']:<15} | {metrik_r3['g1_kenalkan_reni']:<15}")
    print(f"{'Balasan lain yang memuat nama Reni':<38} | {metrik_r2['jumlah_balasan_lain_reni']:<15} | {metrik_r3['jumlah_balasan_lain_reni']:<15}")
    print(f"{'Panggil saat perlu (/20)':<38} | {metrik_r2['panggil_saat_perlu']:<15} | {metrik_r3['panggil_saat_perlu']:<15}")
    print(f"{'Salah panggil (/7)':<38} | {metrik_r2['salah_panggil']:<15} | {metrik_r3['salah_panggil']:<15}")
    print(f"{'Perlu dipanggil (/28)':<38} | {metrik_r2['perlu_dipanggil_28']:<15} | {metrik_r3['perlu_dipanggil_28']:<15}")
    print(f"{'Latensi maksimum (detik)':<38} | {metrik_r2['latensi_maksimum_s']:<15} | {metrik_r3['latensi_maksimum_s']:<15}")
    print("=" * 80)

    print("\nDetail balasan lain yang memuat nama 'Reni' pada R2:")
    for b in metrik_r2["detail_balasan_lain_reni"]:
        print(f"  [{b['sumber']} G{b['turn']}] Pelanggan: '{b['user_msg']}'")
        print(f"    Balasan: {b['balasan_verbatim']}")

    print("\nDetail balasan lain yang memuat nama 'Reni' pada R3:")
    for b in metrik_r3["detail_balasan_lain_reni"]:
        print(f"  [{b['sumber']} G{b['turn']}] Pelanggan: '{b['user_msg']}'")
        print(f"    Balasan: {b['balasan_verbatim']}")


if __name__ == "__main__":
    from datetime import datetime
    t_start_all = time.time()

    # Jalankan Suite 1: Live 26
    res_live_r2 = jalankan_suite_live26("R2", reps=2)
    res_live_r3 = jalankan_suite_live26("R3", reps=2)

    # Jalankan Suite 2: Multi 20
    res_multi_r2 = jalankan_suite_multi20("R2", reps=2)
    res_multi_r3 = jalankan_suite_multi20("R3", reps=2)

    # Jalankan Suite 3: Satu Giliran 27
    res_single_r2 = jalankan_suite_satugiliran27("R2")
    res_single_r3 = jalankan_suite_satugiliran27("R3")

    # Evaluasi agregat dan simpan
    evaluasi_dan_simpan(
        res_live_r2, res_live_r3,
        res_multi_r2, res_multi_r3,
        res_single_r2, res_single_r3
    )

    total_s = time.time() - t_start_all
    print(f"\nPengujian selesai dalam {total_s:.1f} detik ({total_s/60:.2f} menit).")
