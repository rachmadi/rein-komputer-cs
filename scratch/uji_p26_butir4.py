# -*- coding: utf-8 -*-
"""
scratch/uji_p26_butir4.py
Pengujian Putaran 26 Butir 4: Varian A (R3) vs Varian B (R3 + Butir 2) vs Varian C (R3 + Butir 2 + Butir 3)
Semua pengujian dijalankan lewat jalur produksi (process_chat_message) dengan session_id unik per ulangan.

Tiga Varian:
- A: R3 (bawaan: ATURAN_PRIBADI_ATRIBUT=False, KIRIM_FOTO_OLEH_LLM=False)
- B: R3 + Butir 2 (ATURAN_PRIBADI_ATRIBUT=True, KIRIM_FOTO_OLEH_LLM=False)
- C: R3 + Butir 2 + Butir 3 (ATURAN_PRIBADI_ATRIBUT=True, KIRIM_FOTO_OLEH_LLM=True)

Tiga Suite Pengujian:
1. Replay 26 pesan live 12 Okt 19:54–20:14 (urutan asli), 2 ulangan per varian
2. Uji multigiliran 20 pesan replay (scratch/replay_20_turns_result.json), 2 ulangan per varian
3. Uji satu giliran 27 pesan (eval/uji_alat.csv), 1 ulangan per varian (sesi baru per pesan)

Data yang disimpan per giliran:
- balasan verbatim
- argumen alat (termasuk kirim_foto jika ada)
- kode foto per giliran
- latensi detik
- metrik panggil saat perlu /20, salah panggil /7
- perlu dipanggil /28
- latensi maksimum
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

PHOTO_PHRASES = (
    "kirim foto", "minta foto", "tampilkan foto", "lihat foto", "mana foto", "coba foto", "ada foto",
    "kirim gambar", "minta gambar", "tampilkan gambar", "lihat gambar", "mana gambar", "coba gambar", "ada gambar",
    "lihat bentuk", "tampilkan fisik", "kirim pic", "minta pic", "lihat penampakan"
)


def tentukan_foto_giliran(
    u_msg: str,
    res: Dict[str, Any],
    kirim_foto_oleh_llm: bool,
    sent_photos: Set[str],
    last_mentioned: List[str],
    catalog: Catalog,
) -> Tuple[List[str], List[str]]:
    """
    Menghitung daftar kode foto yang dikirimkan pada giliran ini sesuai jalur aktif (Putaran 26 Butir 3f).
    Mengembalikan (kode_foto_giliran, new_last_mentioned).
    """
    products = res.get("products", [])
    new_last_mentioned = [p["kode"] for p in products if p.get("kode")] if products else last_mentioned
    kode_foto_giliran = []

    if kirim_foto_oleh_llm:
        # Jalur Reni: kirim tepat dari foto_akan_dikirim di hasil alat giliran ini
        raw_codes = res.get("foto_akan_dikirim", [])
        for c in raw_codes:
            if c in catalog.by_code:
                p = catalog.by_code[c]
                img_f = (p.get("image_file") or "").strip()
                if img_f and Path(img_f).is_file():
                    kode_foto_giliran.append(c)
                    sent_photos.add(c)
    else:
        # Jalur aturan lama: phrase matching atau tawaran produk baru
        u_low = u_msg.lower()
        is_req = any(phrase in u_low for phrase in PHOTO_PHRASES) and "malah" not in u_low and "jangan" not in u_low
        prods_to_send = []
        if is_req:
            if products:
                prods_to_send = products[:2]
            else:
                prods_to_send = [catalog.by_code[c] for c in last_mentioned if c in catalog.by_code][:2]
        else:
            new_prods = [p for p in products if p.get("kode") and p.get("kode") not in sent_photos]
            if new_prods:
                prods_to_send = new_prods[:2]

        for p in prods_to_send:
            c = p.get("kode")
            img_f = (p.get("image_file") or "").strip()
            if img_f and Path(img_f).is_file():
                if c:
                    kode_foto_giliran.append(c)
                    sent_photos.add(c)

    return kode_foto_giliran, new_last_mentioned


def ekstrak_tool_calls(res: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Mengekstrak rincian panggilan alat beserta argumennya dari hasil process_chat_message."""
    tc_list = res.get("metrics", {}).get("tool_calls", [])
    if not tc_list:
        tc_list = res.get("tool_calls", [])
    cleaned = []
    for tc in tc_list:
        cleaned.append({
            "nama": tc.get("nama"),
            "argumen": tc.get("argumen", {}),
            "latensi_ms": tc.get("latensi_ms", 0.0)
        })
    return cleaned


def jalankan_suite_live26(variant_name: str, aturan_pribadi: bool, foto_llm: bool, reps: int = 2) -> Dict[str, Any]:
    print(f"\n=======================================================")
    print(f"--- SUITE 1: REPLAY LIVE 26 PESAN | VARIAN {variant_name} ({reps} ULANGAN) ---")
    print(f"=======================================================")
    cat = get_active_catalog()
    runs = []
    max_lat = 0.0

    for rep in range(1, reps + 1):
        session_id = f"p26_live26_{variant_name}_rep{rep}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        print(f"\n[Live26 | {variant_name} | Rep {rep}/{reps}] Sesi: {session_id}")
        turn_list = []
        sent_photos: Set[str] = set()
        last_mentioned: List[str] = []

        for idx, u_msg in enumerate(PESAN_LIVE_26, 1):
            t0 = time.time()
            res = process_chat_message(
                session_id=session_id,
                user_text=u_msg,
                persona_nama_r3=True,
                aturan_pribadi_atribut=aturan_pribadi,
                kirim_foto_oleh_llm=foto_llm,
                varian="V4"
            )
            dur = time.time() - t0
            max_lat = max(max_lat, dur)
            reply = res.get("reply", "").strip()
            tools_called = res.get("tools_called", [])
            tool_calls_detail = ekstrak_tool_calls(res)

            foto_dikirim, last_mentioned = tentukan_foto_giliran(
                u_msg=u_msg,
                res=res,
                kirim_foto_oleh_llm=foto_llm,
                sent_photos=sent_photos,
                last_mentioned=last_mentioned,
                catalog=cat
            )

            print(f"  [T{idx:02d}] ({dur:4.1f}s) tools={tools_called} foto={foto_dikirim} | {u_msg[:30]}")

            turn_list.append({
                "turn": idx,
                "user_msg": u_msg,
                "balasan_verbatim": reply,
                "latensi_s": round(dur, 2),
                "tools_called": tools_called,
                "tool_calls_detail": tool_calls_detail,
                "foto_dikirim": foto_dikirim,
                "foto_akan_dikirim_raw": res.get("foto_akan_dikirim", [])
            })

        runs.append({
            "rep": rep,
            "session_id": session_id,
            "turns": turn_list
        })

    return {
        "suite": "live26",
        "variant": variant_name,
        "reps": reps,
        "max_latensi_s": round(max_lat, 2),
        "runs": runs
    }


def jalankan_suite_multi20(variant_name: str, aturan_pribadi: bool, foto_llm: bool, reps: int = 2) -> Dict[str, Any]:
    print(f"\n=======================================================")
    print(f"--- SUITE 2: MULTIGILIRAN 20 PESAN | VARIAN {variant_name} ({reps} ULANGAN) ---")
    print(f"=======================================================")
    cat = get_active_catalog()
    runs = []
    max_lat = 0.0

    with open("scratch/replay_20_turns_result.json", "r", encoding="utf-8") as f:
        replay_data = json.load(f)

    for rep in range(1, reps + 1):
        session_id = f"p26_multi20_{variant_name}_rep{rep}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        print(f"\n[Multi20 | {variant_name} | Rep {rep}/{reps}] Sesi: {session_id}")
        turn_list = []
        sent_photos: Set[str] = set()
        last_mentioned: List[str] = []

        for item in replay_data:
            idx = item["turn"]
            u_msg = item["user_msg"]

            t0 = time.time()
            res = process_chat_message(
                session_id=session_id,
                user_text=u_msg,
                persona_nama_r3=True,
                aturan_pribadi_atribut=aturan_pribadi,
                kirim_foto_oleh_llm=foto_llm,
                varian="V4"
            )
            dur = time.time() - t0
            max_lat = max(max_lat, dur)
            reply = res.get("reply", "").strip()
            tools_called = res.get("tools_called", [])
            tool_calls_detail = ekstrak_tool_calls(res)

            foto_dikirim, last_mentioned = tentukan_foto_giliran(
                u_msg=u_msg,
                res=res,
                kirim_foto_oleh_llm=foto_llm,
                sent_photos=sent_photos,
                last_mentioned=last_mentioned,
                catalog=cat
            )

            print(f"  [T{idx:02d}] ({dur:4.1f}s) tools={tools_called} foto={foto_dikirim} | {u_msg[:30]}")

            turn_list.append({
                "turn": idx,
                "user_msg": u_msg,
                "balasan_verbatim": reply,
                "latensi_s": round(dur, 2),
                "tools_called": tools_called,
                "tool_calls_detail": tool_calls_detail,
                "foto_dikirim": foto_dikirim,
                "foto_akan_dikirim_raw": res.get("foto_akan_dikirim", [])
            })

        runs.append({
            "rep": rep,
            "session_id": session_id,
            "turns": turn_list
        })

    return {
        "suite": "multi20",
        "variant": variant_name,
        "reps": reps,
        "max_latensi_s": round(max_lat, 2),
        "runs": runs
    }


def jalankan_suite_satugiliran27(variant_name: str, aturan_pribadi: bool, foto_llm: bool) -> Dict[str, Any]:
    print(f"\n=======================================================")
    print(f"--- SUITE 3: SATU GILIRAN 27 PESAN | VARIAN {variant_name} (1 ULANGAN) ---")
    print(f"=======================================================")
    cat = get_active_catalog()
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
        session_id = f"p26_single27_{variant_name}_t{idx}_{int(time.time())}_{uuid.uuid4().hex[:4]}"

        t0 = time.time()
        res = process_chat_message(
            session_id=session_id,
            user_text=u_msg,
            persona_nama_r3=True,
            aturan_pribadi_atribut=aturan_pribadi,
            kirim_foto_oleh_llm=foto_llm,
            varian="V4"
        )
        dur = time.time() - t0
        max_lat = max(max_lat, dur)
        reply = res.get("reply", "").strip()
        tools_called = res.get("tools_called", [])
        tool_calls_detail = ekstrak_tool_calls(res)

        sent_photos: Set[str] = set()
        foto_dikirim, _ = tentukan_foto_giliran(
            u_msg=u_msg,
            res=res,
            kirim_foto_oleh_llm=foto_llm,
            sent_photos=sent_photos,
            last_mentioned=[],
            catalog=cat
        )

        perlu_alat = (exp_tool != "tidak_ada")
        ada_alat = (len(tools_called) > 0)
        panggil_benar = (ada_alat if perlu_alat else not ada_alat)

        print(f"  [{idx:02d}/27] ({dur:4.1f}s) exp={exp_tool:<10} act={tools_called} foto={foto_dikirim} | {u_msg[:30]}")

        results.append({
            "idx": idx,
            "pesan": u_msg,
            "alat_diharapkan": exp_tool,
            "tools_called": tools_called,
            "tool_calls_detail": tool_calls_detail,
            "foto_dikirim": foto_dikirim,
            "foto_akan_dikirim_raw": res.get("foto_akan_dikirim", []),
            "balasan_verbatim": reply,
            "latensi_s": round(dur, 2),
            "panggil_benar": panggil_benar
        })

    return {
        "suite": "satugiliran27",
        "variant": variant_name,
        "max_latensi_s": round(max_lat, 2),
        "results": results
    }


def hitung_ringkasan_varian(
    live: Dict[str, Any],
    multi: Dict[str, Any],
    single: Dict[str, Any]
) -> Dict[str, Any]:
    # 1. Panggil saat perlu /20, salah panggil /7 (dari uji satu giliran)
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

    # 2. Perlu dipanggil /28 (dari multi20, 14 slot x 2 ulangan)
    perlu_dipanggil_28 = 0
    for r in multi["runs"]:
        for t in r["turns"]:
            if t["turn"] in PERLU_ALAT_TURNS_20:
                if len(t["tools_called"]) > 0:
                    perlu_dipanggil_28 += 1

    # 3. Latensi maksimum
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

    # 4. Total foto terkirim
    foto_live = sum(len(t["foto_dikirim"]) for r in live["runs"] for t in r["turns"])
    foto_multi = sum(len(t["foto_dikirim"]) for r in multi["runs"] for t in r["turns"])
    foto_single = sum(len(item["foto_dikirim"]) for item in single["results"])

    giliran_berfoto_live = sum(1 for r in live["runs"] for t in r["turns"] if t["foto_dikirim"])
    giliran_berfoto_multi = sum(1 for r in multi["runs"] for t in r["turns"] if t["foto_dikirim"])

    return {
        "panggil_saat_perlu": f"{panggil_saat_perlu}/20",
        "salah_panggil": f"{salah_panggil}/7",
        "perlu_dipanggil_28": f"{perlu_dipanggil_28}/28",
        "latensi_maksimum_s": round(max_lat, 2),
        "total_foto_live26_2reps": foto_live,
        "giliran_berfoto_live26_2reps": giliran_berfoto_live,
        "total_foto_multi20_2reps": foto_multi,
        "giliran_berfoto_multi20_2reps": giliran_berfoto_multi,
        "total_foto_single27": foto_single
    }


def main():
    print("=== MEMULAI PENGUJIAN PUTARAN 26 BUTIR 4 ===")
    t_start_all = time.time()

    VARIAN_CONFIGS = [
        ("A", False, False),  # R3 (bawaan)
        ("B", True, False),   # R3 + Butir 2
        ("C", True, True),    # R3 + Butir 2 + Butir 3
    ]

    hasil_live = {}
    hasil_multi = {}
    hasil_single = {}
    ringkasan_all = {}

    for var_name, aturan_pribadi, foto_llm in VARIAN_CONFIGS:
        print(f"\n#######################################################")
        print(f"### MENJALANKAN EVALUASI VARIAN {var_name}")
        print(f"### Aturan Pribadi & Atribut: {aturan_pribadi}")
        print(f"### Kirim Foto oleh LLM: {foto_llm}")
        print(f"#######################################################")

        live_res = jalankan_suite_live26(var_name, aturan_pribadi, foto_llm, reps=2)
        hasil_live[var_name] = live_res

        multi_res = jalankan_suite_multi20(var_name, aturan_pribadi, foto_llm, reps=2)
        hasil_multi[var_name] = multi_res

        single_res = jalankan_suite_satugiliran27(var_name, aturan_pribadi, foto_llm)
        hasil_single[var_name] = single_res

        summary = hitung_ringkasan_varian(live_res, multi_res, single_res)
        ringkasan_all[var_name] = summary

        print(f"\n[Ringkasan Sementara Varian {var_name}]")
        print(f"  Panggil saat perlu : {summary['panggil_saat_perlu']}")
        print(f"  Salah panggil      : {summary['salah_panggil']}")
        print(f"  Perlu dipanggil    : {summary['perlu_dipanggil_28']}")
        print(f"  Latensi maks       : {summary['latensi_maksimum_s']} s")
        print(f"  Foto Live (2 reps) : {summary['total_foto_live26_2reps']} foto di {summary['giliran_berfoto_live26_2reps']} giliran")
        print(f"  Foto Multi (2 reps): {summary['total_foto_multi20_2reps']} foto di {summary['giliran_berfoto_multi20_2reps']} giliran")

        # Simpan checkpoint berkala setelah tiap varian
        with open("scratch/uji_p26_live26.json", "w", encoding="utf-8") as f:
            json.dump(hasil_live, f, ensure_ascii=False, indent=2)

        with open("scratch/uji_p26_multi20.json", "w", encoding="utf-8") as f:
            json.dump(hasil_multi, f, ensure_ascii=False, indent=2)

        with open("scratch/uji_p26_satugiliran27.json", "w", encoding="utf-8") as f:
            json.dump(hasil_single, f, ensure_ascii=False, indent=2)

        with open("scratch/uji_p26_ringkasan.json", "w", encoding="utf-8") as f:
            json.dump(ringkasan_all, f, ensure_ascii=False, indent=2)

    # Tulis CSV Perbandingan
    csv_path = "scratch/uji_p26_perbandingan_a_b_c.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Varian",
            "Panggil saat perlu (/20)",
            "Salah panggil (/7)",
            "Perlu dipanggil (/28)",
            "Latensi maks (s)",
            "Foto Live26 (2 reps)",
            "Giliran Foto Live26",
            "Foto Multi20 (2 reps)",
            "Giliran Foto Multi20",
        ])
        for var_name in ["A", "B", "C"]:
            s = ringkasan_all[var_name]
            writer.writerow([
                var_name,
                s["panggil_saat_perlu"],
                s["salah_panggil"],
                s["perlu_dipanggil_28"],
                s["latensi_maksimum_s"],
                s["total_foto_live26_2reps"],
                s["giliran_berfoto_live26_2reps"],
                s["total_foto_multi20_2reps"],
                s["giliran_berfoto_multi20_2reps"],
            ])

    dur_all = time.time() - t_start_all
    print(f"\n=======================================================")
    print(f"=== SEMUA PENGUJIAN SELESAI DALAM {dur_all/60:.2f} MENIT ===")
    print(f"Berkas tersimpan:")
    print(f"  - scratch/uji_p26_live26.json")
    print(f"  - scratch/uji_p26_multi20.json")
    print(f"  - scratch/uji_p26_satugiliran27.json")
    print(f"  - scratch/uji_p26_ringkasan.json")
    print(f"  - scratch/uji_p26_perbandingan_a_b_c.csv")
    print(f"=======================================================")


if __name__ == "__main__":
    main()
