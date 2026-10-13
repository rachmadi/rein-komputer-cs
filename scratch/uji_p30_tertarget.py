# -*- coding: utf-8 -*-
"""
scratch/uji_p30_tertarget.py
Pengujian Putaran 30:
Replay tertarget hanya dua pesan ini dari live37, 3 ulangan tiap pesan, jalur produksi:
1. "Kalo desktop untuk desain 3D, apa rekomendasimu?"
2. "Gak ada yang ram 32 GB?"
Simpan hasil alat penuh (bukan hanya argumen) di JSON seperti P29.
Catat ke logs/uji_history.jsonl (via CHAT_LOG_TARGET=eval, penguji=uji_otomatis).
"""
import sys
import os
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
os.environ["CHAT_LOG_TARGET"] = "eval"
os.environ["LOG_HMAC_KEY"] = "test_hmac_secret_for_test_suite_2026"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True, encoding="utf-8")

from services.chat_service import process_chat_message
from services.agentic_tool_engine import pilih_foto_yang_akan_dikirim
from services.catalog_service import get_active_catalog

PESAN_TERTARGET = [
    "Kalo desktop untuk desain 3D, apa rekomendasimu?",
    "Gak ada yang ram 32 GB?"
]

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
            "latensi_ms": tc.get("latensi_ms", 0.0),
            "pengaman_otomatis": tc.get("pengaman_otomatis", False)
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

def format_argumen_alat_str(tool_calls: List[Dict[str, Any]]) -> str:
    parts = []
    for tc in tool_calls:
        nama = tc.get("nama")
        args = tc.get("argumen", {})
        is_guard = tc.get("pengaman_otomatis", False)
        guard_label = " [pengaman]" if is_guard else ""
        parts.append(f"{nama}({json.dumps(args, ensure_ascii=False)}){guard_label}")
    return " | ".join(parts) if parts else "-"

def main():
    cat = get_active_catalog()
    reps = 3
    runs = []
    tabel_entries = []

    print("=======================================================")
    print("--- REPLAY TERTARGET PUTARAN 30 (JALUR PRODUKSI) ---")
    print(f"Pesan: {PESAN_TERTARGET}")
    print(f"Ulangan: {reps}")
    print("=======================================================\n")

    for rep in range(1, reps + 1):
        session_id = f"p30_tertarget_rep{rep}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        print(f"\n[ULANGAN {rep}/{reps}] Sesi: {session_id}")
        run_turns = []

        for turn_idx, user_msg in enumerate(PESAN_TERTARGET, 1):
            print(f"  Turn {turn_idx}: '{user_msg}'")
            t0 = time.time()
            res = process_chat_message(
                session_id=session_id,
                user_text=user_msg,
                penguji="uji_otomatis"
            )
            latensi = time.time() - t0
            reply = res.get("reply", "").strip()
            tools_called = res.get("tools_called", [])
            tool_calls_detail = ekstrak_tool_calls(res)
            foto_tersedia = res.get("foto_tersedia", [])
            foto_dikirim = hitung_foto_dikirim(res, cat)
            kartu_produk = res.get("offered_products", [])

            print(f"    Tools called: {tools_called}")
            for tc in tool_calls_detail:
                nama = tc.get("nama")
                args = tc.get("argumen")
                guard = " [PENGAMAN]" if tc.get("pengaman_otomatis") else ""
                print(f"      -> {nama}{guard}: {args}")
            print(f"    Foto tersedia: {foto_tersedia} | Dikirim: {foto_dikirim}")
            print(f"    Latensi: {latensi:.2f}s")
            print(f"    Balasan: {reply[:120]}...\n")

            turn_data = {
                "turn": turn_idx,
                "user_msg": user_msg,
                "balasan_verbatim": reply,
                "latensi_s": round(latensi, 2),
                "tools_called": tools_called,
                "tool_calls_detail": tool_calls_detail,
                "foto_tersedia": foto_tersedia,
                "foto_dikirim": foto_dikirim,
                "kartu_produk": kartu_produk
            }
            run_turns.append(turn_data)

            tabel_entries.append({
                "pesan_user": user_msg,
                "turn_index": turn_idx,
                "ulangan": rep,
                "argumen_alat": format_argumen_alat_str(tool_calls_detail),
                "kode_foto_terkirim": foto_dikirim,
                "balasan_verbatim": reply,
                "latensi_s": round(latensi, 2),
                "tool_calls_detail": tool_calls_detail
            })

        runs.append({
            "rep": rep,
            "session_id": session_id,
            "turns": run_turns
        })

    output_file = ROOT_DIR / "scratch" / "uji_p30_tertarget.json"
    data_all = {
        "putaran": 30,
        "deskripsi": "Replay tertarget 2 pesan dari live37 jalur produksi",
        "pesan_tertarget": PESAN_TERTARGET,
        "reps": reps,
        "runs": runs,
        "tabel_hasil": tabel_entries
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data_all, f, indent=2, ensure_ascii=False)

    print(f"\n[SUKSES] Hasil pengujian disimpan ke: {output_file}")

if __name__ == "__main__":
    main()
