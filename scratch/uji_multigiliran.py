# -*- coding: utf-8 -*-
"""
scratch/uji_multigiliran.py
Pengujian Alur Multi-Giliran 20 Pesan Replay (Putaran 23 Butir 4).

Menguji varian B1 dan B1F dengan 20 pesan replay (3 ulangan per varian).
Semua varian menggunakan C1 (Qdrant teks penuh) dan KB baru.
  - B1  : V4 + C1 + berpikir hanya di panggilan pertama
  - B1F : B1 + pengingat format (satu paragraf, maks 4 kalimat, tanpa daftar & baris baru)

Label kebutuhan alat:
  - Perlu alat (14 giliran): 2, 3, 4, 5, 6, 9, 10, 11, 13, 14, 15, 16, 18, 19 (total 42 slot untuk 3 ulangan)
  - Tidak perlu alat (1 giliran): 1
  - Tidak dinilai: 7, 8, 12, 17, 20

Metrik Putaran 23:
  - Perlu dipanggil /42
  - Janji tanpa aksi
  - Balasan > 4 kalimat (kalimat dipisah oleh . ! ? diikuti spasi, baris baru, atau akhir teks)
  - Baris baru (\n)
  - Bintang (*)
  - Awalan "Reni:"
  - Latensi maksimum
  - Jumlah giliran > 60 detik
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from statistics import median
from typing import Any, Dict, List, Set

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.agentic_tool_engine import run_agentic_tool
from core.catalog import Catalog
from services.catalog_service import get_active_catalog

PERLU_ALAT_TURNS: Set[int] = {2, 3, 4, 5, 6, 9, 10, 11, 13, 14, 15, 16, 18, 19}
TIDAK_PERLU_ALAT_TURNS: Set[int] = {1}
JANJI_POLA = re.compile(r"\b(cek|periksa|carikan|cari dulu|lihat dulu|saya cari|saya carikan)\b", re.IGNORECASE)
BOCOR_WORDS_PATTERN = r"\b(alat|katalog|pengetahuan|sistem|database)\b"
BOCOR_PHRASES = ["cek bagian", "cek halaman", "cek kebijakan", "cek sendiri", "cek langsung"]

VARIANT_CONFIGS: Dict[str, Dict[str, Any]] = {
    "TOPK3": {"pemeriksaan_ulang_janji": False, "mode_berpikir": False, "mode_berpikir_sebagian": True, "prompt_varian": "V4", "pengurai_alat_mentah": True, "top_k": 3},
    "TOPK5": {"pemeriksaan_ulang_janji": False, "mode_berpikir": False, "mode_berpikir_sebagian": True, "prompt_varian": "V4", "pengurai_alat_mentah": True, "top_k": 5},
    "B1_TOPK3": {"pemeriksaan_ulang_janji": False, "mode_berpikir": False, "mode_berpikir_sebagian": True, "prompt_varian": "V4", "pengurai_alat_mentah": True, "top_k": 3},
    "B1_TOPK5": {"pemeriksaan_ulang_janji": False, "mode_berpikir": False, "mode_berpikir_sebagian": True, "prompt_varian": "V4", "pengurai_alat_mentah": True, "top_k": 5},
    "B1": {"pemeriksaan_ulang_janji": False, "mode_berpikir": False, "mode_berpikir_sebagian": True, "prompt_varian": "V4", "pengurai_alat_mentah": True, "top_k": 3},
    "B1F": {"pemeriksaan_ulang_janji": False, "mode_berpikir": False, "mode_berpikir_sebagian": True, "prompt_varian": "B1F", "pengurai_alat_mentah": True, "top_k": 3},
    # Putaran 25: Varian persona R2 vs R3
    "R2": {"pemeriksaan_ulang_janji": False, "mode_berpikir": False, "mode_berpikir_sebagian": True, "prompt_varian": "V4", "pengurai_alat_mentah": True, "top_k": 3, "persona_nama_r3": False},
    "R3": {"pemeriksaan_ulang_janji": False, "mode_berpikir": False, "mode_berpikir_sebagian": True, "prompt_varian": "V4", "pengurai_alat_mentah": True, "top_k": 3, "persona_nama_r3": True},
    # Kompatibilitas mundur
    "B": {"pemeriksaan_ulang_janji": False, "mode_berpikir": True, "mode_berpikir_sebagian": False, "prompt_varian": "V4", "pengurai_alat_mentah": True, "top_k": 3},
    "P": {"pemeriksaan_ulang_janji": False, "mode_berpikir": False, "mode_berpikir_sebagian": False, "prompt_varian": "P", "pengurai_alat_mentah": False, "top_k": 3},
    "PB1": {"pemeriksaan_ulang_janji": False, "mode_berpikir": False, "mode_berpikir_sebagian": True, "prompt_varian": "PB1", "pengurai_alat_mentah": True, "top_k": 3},
}


def calc_p90(values: List[float]) -> float:
    """Menghitung p90 dengan interpolasi linier."""
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * 0.9
    f = int(k)
    c = f + 1
    if c < len(s):
        return s[f] + (k - f) * (s[c] - s[f])
    return s[f]


def count_sentences(text: str) -> int:
    """
    Menghitung jumlah kalimat berdasarkan pemisah .!? diikuti spasi, baris baru, atau akhir teks
    (Putaran 23 Butir 4a).
    """
    cleaned = text.strip()
    parts = re.split(r'[.!?]+(?:\s+|\n+|$)', cleaned)
    sentences = [p.strip() for p in parts if p.strip()]
    return len(sentences)


def check_lebih_4_kalimat(reply: str) -> bool:
    """Mengecek apakah balasan lebih dari 4 kalimat."""
    return count_sentences(reply) > 4


def check_baris_baru(reply: str) -> bool:
    """Mengecek apakah balasan memuat karakter baris baru (\n) (Putaran 23 Butir 4a)."""
    return "\n" in reply


def check_ada_bintang(reply: str) -> bool:
    """Mengecek apakah balasan memuat tanda bintang (*) (Putaran 23 Butir 4a)."""
    return "*" in reply


def check_awalan_reni(reply: str) -> bool:
    """Mengecek apakah balasan diawali dengan 'Reni:' (Putaran 23 Butir 4d)."""
    return bool(re.match(r"^reni\s*:", reply.strip(), re.IGNORECASE))


def check_reni_g2_20(turn: int, reply: str) -> bool:
    """Mengecek apakah balasan memuat kata 'Reni' di giliran 2–20."""
    if 2 <= turn <= 20:
        return bool(re.search(r"\breni\b", reply, re.IGNORECASE))
    return False


def load_replay_turns(path: str = "scratch/replay_20_turns_result.json") -> List[Dict[str, Any]]:
    """Memuat 20 user_msg dari log replay 18e apa adanya."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Berkas replay tidak ditemukan: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def check_janji_tanpa_aksi(reply: str, tools_called: List[str]) -> bool:
    """Mengecek apakah balasan akhir tanpa alat memuat janji periksa."""
    if tools_called:
        return False
    return bool(JANJI_POLA.search(reply.lower()))


def check_sebut_bot(reply: str) -> bool:
    """Mengecek apakah balasan menyebut diri chatbot, bot, AI, atau asisten virtual."""
    pattern = r"\b(chatbot|bot|ai|asisten virtual)\b"
    return bool(re.search(pattern, reply, re.IGNORECASE))


def check_bocor(reply: str) -> bool:
    """Mengecek kebocoran internal: kata utuh alat, katalog, pengetahuan, sistem, database atau frasa cek bagian/halaman/kebijakan/sendiri/langsung."""
    low = reply.lower()
    if re.search(BOCOR_WORDS_PATTERN, low, re.IGNORECASE):
        return True
    return any(p in low for p in BOCOR_PHRASES)


def run_single_conversation(
    variant: str,
    rep: int,
    replay_data: List[Dict[str, Any]],
    catalog: Catalog,
    jalur_produksi: bool = False,
) -> List[Dict[str, Any]]:
    """Menjalankan 1 alur percakapan replay dengan session_state bersih."""
    import uuid
    history: List[Dict[str, Any]] = []
    state: Dict[str, Any] = {}
    turn_results: List[Dict[str, Any]] = []

    session_id = f"eval_{variant}_rep{rep}_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    cfg = VARIANT_CONFIGS.get(variant, {
        "pemeriksaan_ulang_janji": False,
        "mode_berpikir": False,
        "mode_berpikir_sebagian": True,
        "prompt_varian": variant,
        "pengurai_alat_mentah": True,
        "top_k": 3
    })

    # Konfigurasi top_k pengetahuan untuk varian ini
    import services.agent_tools as agent_tools
    top_k_val = cfg.get("top_k", 3)
    agent_tools.PENGETAHUAN_TOPK = top_k_val
    os.environ["PENGETAHUAN_TOPK"] = str(top_k_val)

    mode_info = f" | jalur_produksi (sesi: {session_id})" if jalur_produksi else ""
    print(f"\n>>> [VARIAN {variant} (top_k={top_k_val}){mode_info} | ULANGAN {rep}] Memulai {len(replay_data)} giliran percakapan...", flush=True)

    for item in replay_data:
        t_num = item["turn"]
        u_msg = item["user_msg"]

        t0 = time.perf_counter()
        if jalur_produksi:
            from services.chat_service import process_chat_message
            res = process_chat_message(
                session_id=session_id,
                user_text=u_msg,
                persona_nama_r3=cfg.get("persona_nama_r3"),
                varian=cfg["prompt_varian"],
                pemeriksaan_ulang_janji=cfg["pemeriksaan_ulang_janji"],
                mode_berpikir=cfg["mode_berpikir"],
                mode_berpikir_sebagian=cfg.get("mode_berpikir_sebagian", True),
                pengurai_alat_mentah=cfg.get("pengurai_alat_mentah", True),
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000

            reply = res.get("reply", "")
            metrics = res.get("metrics", {})
            tool_calls = metrics.get("tool_calls", [])
            tools_called = res.get("tools_called", [])
            products_rendered = [p.get("kode") for p in res.get("products", [])]
            this_turn_hasil_alat = res.get("hasil_alat_giliran", [])
            error_darurat = res.get("error_darurat")
            alat_mentah_events = res.get("alat_mentah_events", [])
        else:
            res = run_agentic_tool(
                user_text=u_msg,
                history=history,
                catalog=catalog,
                session_state=state,
                varian=cfg["prompt_varian"],
                pemeriksaan_ulang_janji=cfg["pemeriksaan_ulang_janji"],
                mode_berpikir=cfg["mode_berpikir"],
                mode_berpikir_sebagian=cfg.get("mode_berpikir_sebagian", True),
                pengurai_alat_mentah=cfg.get("pengurai_alat_mentah", True),
                persona_nama_r3=cfg.get("persona_nama_r3"),
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000

            reply = res.get("reply", "")
            tool_calls = res.get("tool_calls", [])
            tools_called = res.get("tools_called", [])
            products_rendered = [p.get("kode") for p in res.get("products", [])]
            this_turn_hasil_alat = res.get("hasil_alat_giliran", [])
            error_darurat = res.get("error_darurat")
            alat_mentah_events = res.get("alat_mentah_events", [])

            # Perbarui riwayat chat dan state
            history.append({"role": "user", "content": u_msg})
            history.append({"role": "assistant", "content": reply})
            if "mentioned_products" in res:
                state["mentioned_products"] = res["mentioned_products"]

        # Deteksi metrik
        is_janji = check_janji_tanpa_aksi(reply, tools_called)
        is_bot = check_sebut_bot(reply)
        is_bocor = check_bocor(reply)
        sebut_reni = bool(t_num == 1 and "reni" in reply.lower())

        # Metrik Putaran 23 / 24
        lebih_4_kalimat = check_lebih_4_kalimat(reply)
        baris_baru = check_baris_baru(reply)
        ada_bintang = check_ada_bintang(reply)
        awalan_reni = check_awalan_reni(reply)
        reni_g2_20 = check_reni_g2_20(t_num, reply)
        durasi_s = elapsed_ms / 1000.0
        lebih_60s = durasi_s > 60.0

        log_item = {
            "turn": t_num,
            "user_msg": u_msg,
            "balasan": reply,  # Verbatim tidak dipotong
            "tools_called": tools_called,
            "tool_calls": [
                {
                    "nama": tc.get("nama"),
                    "argumen": tc.get("argumen"),
                    "sumber": tc.get("sumber"),
                    "alasan_cadangan": tc.get("alasan_cadangan"),
                }
                for tc in tool_calls
            ],
            "hasil_alat": this_turn_hasil_alat,
            "error_darurat": error_darurat,
            "kode_kartu": products_rendered,
            "latensi_ms": round(elapsed_ms, 2),
            "latensi_s": round(durasi_s, 2),
            "is_janji_tanpa_aksi": is_janji,
            "is_sebut_bot": is_bot,
            "is_bocor": is_bocor,
            "sebut_reni": sebut_reni,
            "lebih_4_kalimat": lebih_4_kalimat,
            "baris_baru": baris_baru,
            "ada_bintang": ada_bintang,
            "awalan_reni": awalan_reni,
            "reni_g2_20": reni_g2_20,
            "lebih_60s": lebih_60s,
            "pemeriksaan_ulang": bool(res.get("pemeriksaan_ulang")),
            "balasan_sebelum_periksa": res.get("balasan_sebelum_periksa"),
            "alat_mentah_events": alat_mentah_events,
            "llm_calls": res.get("llm_calls", []),
        }
        turn_results.append(log_item)

        tool_str = ", ".join(tools_called) if tools_called else "-"
        pu_str = " [PU]" if res.get("pemeriksaan_ulang") else ""
        print(f"  [G{t_num:02d}] Tools: {tool_str:<20}{pu_str} | {elapsed_ms/1000:.2f}s | Msg: {u_msg[:35]}", flush=True)

    return turn_results


def evaluate_variant_results(all_runs: Dict[str, List[List[Dict[str, Any]]]]) -> Dict[str, Any]:
    """Menghitung metrik agregat per varian sesuai Putaran 23 dan Putaran 24 Butir 4."""
    summary: Dict[str, Any] = {}

    for var, reps_data in all_runs.items():
        total_reps = len(reps_data)
        perlu_called_count = 0
        salah_g1_count = 0
        janji_tanpa_aksi_count = 0
        bocor_count = 0
        g1_reni_count = 0
        sebut_bot_count = 0
        error_darurat_count = 0
        pemeriksaan_ulang_count = 0
        done_reason_length_count = 0
        lebih_4_kalimat_count = 0
        baris_baru_count = 0
        bintang_count = 0
        awalan_reni_count = 0
        reni_g2_20_count = 0
        lebih_60s_count = 0
        alat_mentah_diurai_count = 0
        alat_mentah_gagal_count = 0
        latencies = []

        total_perlu_slots = len(PERLU_ALAT_TURNS) * total_reps  # 14 * reps = 42
        total_g1_slots = len(TIDAK_PERLU_ALAT_TURNS) * total_reps  # 1 * reps = 3

        for rep_turns in reps_data:
            for t in rep_turns:
                t_num = t["turn"]
                has_tool = len(t["tools_called"]) > 0
                latencies.append(t["latensi_ms"])

                if t_num in PERLU_ALAT_TURNS and has_tool:
                    perlu_called_count += 1
                if t_num == 1 and has_tool:
                    salah_g1_count += 1
                if t["is_janji_tanpa_aksi"]:
                    janji_tanpa_aksi_count += 1
                if t.get("is_bocor"):
                    bocor_count += 1
                if t_num == 1 and t["sebut_reni"]:
                    g1_reni_count += 1
                if t["is_sebut_bot"]:
                    sebut_bot_count += 1
                if t.get("error_darurat"):
                    error_darurat_count += 1
                if t.get("pemeriksaan_ulang"):
                    pemeriksaan_ulang_count += 1

                if t.get("lebih_4_kalimat"):
                    lebih_4_kalimat_count += 1
                if t.get("baris_baru"):
                    baris_baru_count += 1
                if t.get("ada_bintang"):
                    bintang_count += 1
                if t.get("awalan_reni"):
                    awalan_reni_count += 1
                if t.get("reni_g2_20"):
                    reni_g2_20_count += 1
                if t.get("lebih_60s"):
                    lebih_60s_count += 1

                for ev in t.get("alat_mentah_events", []):
                    if ev == "alat_mentah_diurai":
                        alat_mentah_diurai_count += 1
                    elif ev == "alat_mentah_gagal":
                        alat_mentah_gagal_count += 1

                for lc in t.get("llm_calls", []):
                    if lc.get("done_reason") == "length":
                        done_reason_length_count += 1

        lat_s = [lat / 1000.0 for lat in latencies]
        med_lat_s = round(median(lat_s), 2) if lat_s else 0.0
        p90_lat_s = round(calc_p90(lat_s), 2) if lat_s else 0.0
        max_lat_s = round(max(lat_s), 2) if lat_s else 0.0

        summary[var] = {
            "total_reps": total_reps,
            "panggil_perlu": f"{perlu_called_count}/{total_perlu_slots}",
            "panggil_perlu_num": perlu_called_count,
            "panggil_perlu_total": total_perlu_slots,
            "panggil_perlu_pct": round((perlu_called_count / total_perlu_slots) * 100, 1) if total_perlu_slots else 0.0,
            "max_latensi_s": max_lat_s,
            "lebih_60s": lebih_60s_count,
            "alat_mentah_diurai": alat_mentah_diurai_count,
            "alat_mentah_gagal": alat_mentah_gagal_count,
            "error_darurat": error_darurat_count,
            "janji_tanpa_aksi": janji_tanpa_aksi_count,
            "lebih_4_kalimat": lebih_4_kalimat_count,
            "baris_baru": baris_baru_count,
            "bintang": bintang_count,
            "awalan_reni": awalan_reni_count,
            "bocor": bocor_count,
            "jumlah_pemeriksaan_ulang": pemeriksaan_ulang_count,
            "done_reason_length": done_reason_length_count,
            "g1_reni": f"{g1_reni_count}/{total_g1_slots}",
            "sebut_bot": sebut_bot_count,
            "salah_g1": f"{salah_g1_count}/{total_g1_slots}",
            "reni_g2_20": reni_g2_20_count,
            "median_latensi_s": med_lat_s,
            "p90_latensi_s": p90_lat_s,
        }

    return summary


def main():
    parser = argparse.ArgumentParser(description="Uji Multi-Giliran 20 Pesan Replay (Putaran 24)")
    parser.add_argument("--variants", default="TOPK3,TOPK5", help="Daftar varian (default: TOPK3,TOPK5)")
    parser.add_argument("--reps", type=int, default=3, help="Jumlah ulangan per varian (default: 3)")
    parser.add_argument("--replay-file", default="scratch/replay_20_turns_result.json", help="Berkas replay JSON")
    parser.add_argument(
        "--jalur-produksi", "--jalur_produksi",
        dest="jalur_produksi",
        action="store_true",
        help="Setiap pesan dikirim lewat process_chat_message dengan id sesi baru per ulangan (Putaran 25 Butir 4c)"
    )
    args = parser.parse_args()

    variants = [v.strip().upper() for v in args.variants.split(",") if v.strip()]
    replay_data = load_replay_turns(args.replay_file)
    cat = get_active_catalog()

    mode_label = " (JALUR PRODUKSI)" if args.jalur_produksi else ""
    print(f"=== UJI MULTI-GILIRAN PUTARAN 24/25{mode_label} ===")
    print(f"Varian: {variants} | Ulangan: {args.reps} | Pesan replay: {len(replay_data)}")
    print(f"Katalog aktif: {len(cat.by_code)} produk")

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = f"scratch/uji_multigiliran_{timestamp_str}.json"
    csv_file = f"scratch/uji_multigiliran_{timestamp_str}.csv"

    all_data: Dict[str, List[List[Dict[str, Any]]]] = {}

    for var in variants:
        all_data[var] = []
        for rep in range(1, args.reps + 1):
            rep_res = run_single_conversation(var, rep, replay_data, cat, jalur_produksi=args.jalur_produksi)
            all_data[var].append(rep_res)

    summary = evaluate_variant_results(all_data)

    output_payload = {
        "timestamp": timestamp_str,
        "variants": variants,
        "reps": args.reps,
        "summary": summary,
        "runs": all_data
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2, ensure_ascii=False)

    # Simpan ringkasan CSV
    with open(csv_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "varian", "panggil_perlu", "panggil_perlu_pct", "max_latensi_s", "lebih_60s",
            "alat_mentah_diurai", "alat_mentah_gagal", "error_darurat",
            "janji_tanpa_aksi", "median_latensi_s"
        ])
        for var, s in summary.items():
            writer.writerow([
                var, s["panggil_perlu"], s["panggil_perlu_pct"], s["max_latensi_s"], s["lebih_60s"],
                s["alat_mentah_diurai"], s["alat_mentah_gagal"], s["error_darurat"],
                s["janji_tanpa_aksi"], s["median_latensi_s"]
            ])

    print("\n" + "=" * 110)
    print("### HASIL PERBANDINGAN VARIAN MULTI-GILIRAN (PUTARAN 24)")
    print("=" * 110)
    header = (
        f"{'Varian':<10} | {'Perlu Dipanggil (/42)':<22} | {'Max Lat (s)':<12} | {'Giliran >60s':<13} | "
        f"{'Mentah Diurai':<14} | {'Mentah Gagal':<13} | {'Error Darurat':<13}"
    )
    sep = "-" * 110
    print(header)
    print(sep)
    for var, s in summary.items():
        print(
            f"{var:<10} | {s['panggil_perlu']:<22} | {s['max_latensi_s']:<12} | {s['lebih_60s']:<13} | "
            f"{s['alat_mentah_diurai']:<14} | {s['alat_mentah_gagal']:<13} | {s['error_darurat']:<13}"
        )
    print("=" * 110)
    print(f"Hasil lengkap JSON disimpan ke: {out_file}")
    print(f"Ringkasan CSV disimpan ke: {csv_file}\n")


if __name__ == "__main__":
    main()
