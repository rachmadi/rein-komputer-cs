# -*- coding: utf-8 -*-
"""
Uji Terkontrol Pemanggilan Alat (Putaran 18c) — ReIn Komputer
Mengukur kemampuan tool calling gemma4:e4b pada 4 varian prompt:
A. Prompt produksi Putaran 18b (think: False)
B. Prompt A + paragraf keputusan di awal (think: False)
C. Prompt B + 3 percakapan sintetis (few-shot tool calling) (think: False)
D. Prompt A dengan think: True
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.agentic_tool_engine import build_agent_system_prompt
from services.agent_tools import AGENT_TOOLS_SCHEMA


# =============================================================================
# 1. DEFINISI PROMPT & CONTOH SINTETIS
# =============================================================================

PROMPT_A = build_agent_system_prompt()

PARAGRAF_KEPUTUSAN_AWAL = (
    "Untuk setiap pesan pelanggan, putuskan dulu: jika menyangkut produk, harga, "
    "spesifikasi, ketersediaan, atau jumlah produk, panggil alat katalog; jika "
    "menyangkut penjelasan produk, panduan memilih, atau kebijakan toko, panggil "
    "alat pengetahuan; jika tidak, jawab langsung. Jangan menulis bahwa kamu akan "
    "mengecek; langsung panggil alatnya.\n\n"
)

PROMPT_B = PARAGRAF_KEPUTUSAN_AWAL + PROMPT_A

# Contoh sintetis umum untuk Varian C (tidak memakai kalimat dari dataset uji atau sesi live)
FEW_SHOT_EXAMPLES_C: List[Dict[str, Any]] = [
    # 1. Contoh KATALOG
    {
        "role": "user",
        "content": "Halo Kak, mau tanya harga Acer Swift Go 14 berapa ya?"
    },
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "call_kat_01",
                "type": "function",
                "function": {
                    "name": "katalog",
                    "arguments": {
                        "kata_kunci": "Acer Swift Go 14"
                    }
                }
            }
        ]
    },
    {
        "role": "tool",
        "content": json.dumps({
            "status": "sukses",
            "total_cocok": 1,
            "produk": [
                {
                    "kode": "KB-L19",
                    "nama": "Acer Swift Go 14 SFG14-73",
                    "kategori": "laptop",
                    "harga": "Rp14.000.000",
                    "spek_ringkas": "Core Ultra 5 125H, RAM 16GB, SSD 512GB"
                }
            ]
        }, ensure_ascii=False)
    },
    {
        "role": "assistant",
        "content": "Halo Kak! Acer Swift Go 14 SFG14-73 saat ini harganya Rp14.000.000 dengan prosesor Intel Core Ultra 5 dan RAM 16GB. Ada yang ingin Kakak tanyakan lagi mengenai unit ini?"
    },
    # 2. Contoh PENGETAHUAN
    {
        "role": "user",
        "content": "Kak, prosesor seri U sama seri H bedanya apa sih?"
    },
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "call_peng_01",
                "type": "function",
                "function": {
                    "name": "pengetahuan",
                    "arguments": {
                        "pertanyaan": "beda prosesor seri U dan H"
                    }
                }
            }
        ]
    },
    {
        "role": "tool",
        "content": json.dumps({
            "status": "sukses",
            "total_cocok": 1,
            "pengetahuan": [
                {
                    "id": "G01",
                    "judul": "Panduan Umum: Tingkatan Prosesor (CPU)",
                    "teks": "Akhiran laptop: U atau P berarti hemat daya (cocok kantor dan baterai awet); H, HS, HX berarti performa tinggi (cocok gaming, kreatif, dan teknik, tetapi lebih boros baterai dan lebih panas)."
                }
            ]
        }, ensure_ascii=False)
    },
    {
        "role": "assistant",
        "content": "Bedanya di konsumsi daya dan performa Kak. Seri U dirancang hemat daya sehingga baterai lebih awet dan cocok untuk kantor, sedangkan seri H performanya tinggi untuk gaming atau tugas berat tapi lebih boros baterai."
    },
    # 3. Contoh TANPA ALAT (obrolan langsung)
    {
        "role": "user",
        "content": "Terima kasih banyak infonya ya Kak, nanti saya diskusikan dulu."
    },
    {
        "role": "assistant",
        "content": "Sama-sama Kak! Senang bisa membantu. Jika nanti ada yang ingin ditanyakan lagi seputar komputer, silakan chat kembali ya. Semoga harinya menyenangkan!"
    }
]


# =============================================================================
# 2. CALL OLLAMA CHAT KHUSUS PENGUJIAN
# =============================================================================

def call_ollama_turn1(
    messages: List[Dict[str, Any]],
    think: bool = False,
    model: str = "gemma4:e4b",
    url: str = "http://127.0.0.1:11434",
    num_predict: int = 1024,
    num_ctx: int = 8192,
    temperature: float = 0.2,
    timeout: float = 120.0
) -> Dict[str, Any]:
    """Panggilan putaran pertama LLM ke endpoint Ollama /api/chat."""
    t0 = time.perf_counter()
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": think,
        "options": {
            "num_predict": num_predict,
            "num_ctx": num_ctx,
            "temperature": temperature
        },
        "tools": AGENT_TOOLS_SCHEMA
    }

    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{url.rstrip('/')}/api/chat",
        data=req_data,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            durasi_ms = (time.perf_counter() - t0) * 1000
            data["_latensi_ms"] = durasi_ms
            return data
    except Exception as e:
        durasi_ms = (time.perf_counter() - t0) * 1000
        return {
            "error": str(e),
            "_latensi_ms": durasi_ms,
            "message": {"role": "assistant", "content": f"ERROR: {e}"},
            "eval_count": 0
        }


# =============================================================================
# 3. PERAKITAN PESAN PER VARIAN
# =============================================================================

def build_messages_for_variant(variant: str, user_text: str) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Mengembalikan (messages, think_flag) untuk varian yang dipilih:
    A: Prompt A, riwayat kosong, think False
    B: Prompt B, riwayat kosong, think False
    C: Prompt B + 3 contoh sintetis di messages, think False
    D: Prompt A, riwayat kosong, think True
    """
    if variant in ("V0", "V1", "V2", "V3", "V4", "V5", "V6"):
        prompt_sys = build_agent_system_prompt(varian=variant)
        msgs = [{"role": "system", "content": prompt_sys}]
        from services.agentic_tool_engine import variant_has_reminder, KOMPONEN_P
        if variant_has_reminder(variant):
            msgs.append({"role": "system", "content": KOMPONEN_P})
        msgs.append({"role": "user", "content": user_text})
        return msgs, False
    elif variant in ("PROD", "PRODUKSI"):
        # Diambil langsung dari kode produksi
        prompt_prod = build_agent_system_prompt()
        msgs = [{"role": "system", "content": prompt_prod}]
        from services.agentic_tool_engine import variant_has_reminder, KOMPONEN_P
        if variant_has_reminder():
            msgs.append({"role": "system", "content": KOMPONEN_P})
        msgs.append({"role": "user", "content": user_text})
        return msgs, False
    elif variant == "A":
        return [{"role": "system", "content": PROMPT_A}, {"role": "user", "content": user_text}], False
    elif variant == "B":
        return [{"role": "system", "content": PROMPT_B}, {"role": "user", "content": user_text}], False
    elif variant == "C":
        msgs: List[Dict[str, Any]] = [{"role": "system", "content": PROMPT_B}]
        msgs.extend(FEW_SHOT_EXAMPLES_C)
        msgs.append({"role": "user", "content": user_text})
        return msgs, False
    elif variant == "D":
        return [{"role": "system", "content": PROMPT_A}, {"role": "user", "content": user_text}], True
    else:
        raise ValueError(f"Varian '{variant}' tidak dikenal.")


# =============================================================================
# 4. PARSER DATASET UJI
# =============================================================================

def load_test_dataset(filepath: str = "eval/uji_alat.csv") -> List[Dict[str, str]]:
    if not os.path.exists(filepath):
        print(f"ERROR: Berkas dataset '{filepath}' tidak ditemukan!")
        sys.exit(1)

    items = []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pesan = row.get("pesan", "").strip()
            alat_diharapkan = row.get("alat_diharapkan", "").strip()
            if pesan and alat_diharapkan:
                items.append({
                    "pesan": pesan,
                    "alat_diharapkan": alat_diharapkan
                })
    return items


# =============================================================================
# 5. EKSEKUSI PENGUJIAN
# =============================================================================

def run_experiment(input_csv: str = "eval/uji_alat.csv", variants: Optional[List[str]] = None, reps: int = 3) -> str:
    test_cases = load_test_dataset(input_csv)
    print(f"Loaded {len(test_cases)} test cases dari {input_csv}.")

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_csv = f"scratch/uji_alat_hasil_{timestamp_str}.csv"
    os.makedirs("scratch", exist_ok=True)

    fieldnames = [
        "varian",
        "pesan",
        "alat_diharapkan",
        "ulangan",
        "tool_calls",
        "tools_called",
        "raw_content",
        "eval_count",
        "latensi_ms"
    ]

    results = []
    if not variants:
        variants = ["A", "B", "C", "D"]
    total_runs = len(variants) * len(test_cases) * reps
    run_idx = 0

    print(f"Memulai eksperimen: {len(variants)} varian ({', '.join(variants)}) x {len(test_cases)} kasus uji x {reps} ulangan = {total_runs} panggilan.")

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for var in variants:
            print(f"\n>>> MENJALANKAN VARIAN {var} <<<")
            for tc_idx, tc in enumerate(test_cases, start=1):
                pesan = tc["pesan"]
                alat_diharapkan = tc["alat_diharapkan"]

                for rep in range(1, reps + 1):
                    run_idx += 1
                    msgs, think_mode = build_messages_for_variant(var, pesan)
                    t_start = time.perf_counter()
                    resp = call_ollama_turn1(msgs, think=think_mode)
                    latensi = resp.get("_latensi_ms", (time.perf_counter() - t_start) * 1000)

                    msg_obj = resp.get("message", {})
                    t_calls = msg_obj.get("tool_calls") or []
                    raw_content = msg_obj.get("content", "").strip()
                    eval_count = resp.get("eval_count", 0)

                    tool_names = [call.get("function", {}).get("name") for call in t_calls if call.get("function")]

                    row = {
                        "varian": var,
                        "pesan": pesan,
                        "alat_diharapkan": alat_diharapkan,
                        "ulangan": rep,
                        "tool_calls": json.dumps(t_calls, ensure_ascii=False) if t_calls else "",
                        "tools_called": ",".join(tool_names),
                        "raw_content": raw_content,
                        "eval_count": eval_count,
                        "latensi_ms": round(latensi, 2)
                    }
                    writer.writerow(row)
                    f.flush()
                    results.append(row)

                    tool_str = ",".join(tool_names) if tool_names else "-"
                    print(f"[{run_idx}/{total_runs}] Var {var} | Kasus {tc_idx} Rep {rep} | Expected: {alat_diharapkan} | Calls: {tool_str} | Latency: {latensi:.0f}ms")

    print(f"\nEksperimen selesai. Hasil mentah disimpan di: {output_csv}")
    return output_csv


# =============================================================================
# 6. PERHITUNGAN RINGKASAN METRIK (BUTIR 2)
# =============================================================================

def analyze_results(csv_path: str):
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    variants = sorted(list(set(r["varian"] for r in rows)))

    print("\n" + "=" * 80)
    print("ANALISIS HASIL UJI TERKONTROL PEMANGGILAN ALAT (BUTIR 2)")
    print("=" * 80)

    summary_per_variant = {}

    for var in variants:
        v_rows = [r for r in rows if r["varian"] == var]
        
        # 1. Pesan yang butuh alat: alat_diharapkan in {'katalog', 'pengetahuan', 'keduanya'}
        needy_rows = [r for r in v_rows if r["alat_diharapkan"] in ("katalog", "pengetahuan", "keduanya")]
        # 2. Pesan tidak_ada
        none_rows = [r for r in v_rows if r["alat_diharapkan"] == "tidak_ada"]

        # Tingkat panggil alat pada pesan yang butuh alat
        needy_called = [r for r in needy_rows if r["tools_called"]]
        tingkat_panggil_pct = (len(needy_called) / len(needy_rows) * 100) if needy_rows else 0.0

        # Ketepatan alat
        correct_calls = 0
        for r in v_rows:
            expected = r["alat_diharapkan"]
            called = [x.strip() for x in r["tools_called"].split(",") if x.strip()]
            if expected == "tidak_ada":
                if not called:
                    correct_calls += 1
            elif expected == "katalog":
                if "katalog" in called:
                    correct_calls += 1
            elif expected == "pengetahuan":
                if "pengetahuan" in called:
                    correct_calls += 1
            elif expected == "keduanya":
                if "katalog" in called or "pengetahuan" in called:
                    correct_calls += 1
        ketepatan_pct = (correct_calls / len(v_rows) * 100) if v_rows else 0.0

        # Panggilan salah pada pesan tidak_ada
        none_called = [r for r in none_rows if r["tools_called"]]
        panggilan_salah_pct = (len(none_called) / len(none_rows) * 100) if none_rows else 0.0

        # "Janji tanpa aksi": balasan tanpa panggilan alat yang memuat kata cek, periksa, carikan, atau "saya cari"
        JANJI_KEYWORDS = ["cek", "periksa", "carikan", "saya cari"]
        janji_tanpa_aksi = [
            r for r in v_rows
            if not r["tools_called"] and any(kw in (r.get("raw_content") or "").lower() for kw in JANJI_KEYWORDS)
        ]

        # Latensi median
        latencies = [float(r["latensi_ms"]) for r in v_rows]
        med_latency = median(latencies) if latencies else 0.0

        # Rincian per kategori alat_diharapkan
        kategori_breakdown = {}
        for cat in ["katalog", "pengetahuan", "keduanya", "tidak_ada"]:
            cat_rows = [r for r in v_rows if r["alat_diharapkan"] == cat]
            cat_called = [r for r in cat_rows if r["tools_called"]]
            cat_rate = (len(cat_called) / len(cat_rows) * 100) if cat_rows else 0.0
            kategori_breakdown[cat] = {
                "total": len(cat_rows),
                "called": len(cat_called),
                "rate_pct": round(cat_rate, 1)
            }

        summary_per_variant[var] = {
            "total_runs": len(v_rows),
            "panggil_saat_perlu": f"{len(needy_called)}/{len(needy_rows)}",
            "salah_panggil": f"{len(none_called)}/{len(none_rows)}",
            "tingkat_panggil_alat_pct": round(tingkat_panggil_pct, 1),
            "ketepatan_alat_pct": round(ketepatan_pct, 1),
            "panggilan_salah_pct": round(panggilan_salah_pct, 1),
            "janji_tanpa_aksi_count": len(janji_tanpa_aksi),
            "janji_tanpa_aksi_items": janji_tanpa_aksi,
            "median_latensi_ms": round(med_latency, 1),
            "kategori_breakdown": kategori_breakdown
        }

    # Cetak tabel ringkasan per varian
    print("\n### TABEL RINGKASAN METRIK PER VARIAN")
    print("| Varian | Panggil Saat Perlu (/20) | Salah Panggil (/7) | Janji Tanpa Aksi | Tingkat Panggil (%) | Median Latensi (s) |")
    print("|---|---|---|---|---|---|")
    for var, s in summary_per_variant.items():
        print(f"| {var} | {s['panggil_saat_perlu']} | {s['salah_panggil']} | {s['janji_tanpa_aksi_count']} | {s['tingkat_panggil_alat_pct']}% | {s['median_latensi_ms']/1000:.2f} s |")

    print("\n### RINCIAN TINGKAT PANGGIL ALAT PER KATEGORI ALAT_DIHARAPKAN")
    print("| Varian | Katalog | Pengetahuan | Keduanya | Tidak Ada (Salah Panggil) |")
    print("|---|---|---|---|---|")
    for var, s in summary_per_variant.items():
        kb = s["kategori_breakdown"]
        kat_str = f"{kb['katalog']['called']}/{kb['katalog']['total']} ({kb['katalog']['rate_pct']}%)"
        pen_str = f"{kb['pengetahuan']['called']}/{kb['pengetahuan']['total']} ({kb['pengetahuan']['rate_pct']}%)"
        ked_str = f"{kb['keduanya']['called']}/{kb['keduanya']['total']} ({kb['keduanya']['rate_pct']}%)"
        tid_str = f"{kb['tidak_ada']['called']}/{kb['tidak_ada']['total']} ({kb['tidak_ada']['rate_pct']}%)"
        print(f"| {var} | {kat_str} | {pen_str} | {ked_str} | {tid_str} |")

    json_path = csv_path.replace(".csv", "_ringkasan.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary_per_variant, f, indent=2, ensure_ascii=False)
    print(f"\nRingkasan metrik disimpan ke: {json_path}")

    return summary_per_variant


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Uji Terkontrol Pemanggilan Alat")
    parser.add_argument("--csv", default="eval/uji_alat.csv", help="Path ke berkas CSV dataset")
    parser.add_argument("--variants", default="", help="Daftar varian dipisahkan koma (misal: PRODUKSI atau A,B,C,D)")
    parser.add_argument("--reps", type=int, default=3, help="Jumlah pengulangan per kasus")
    parser.add_argument("--prod", action="store_true", help="Jalankan varian PRODUKSI saja (prompt produksi saat ini)")
    args = parser.parse_args()

    selected_variants = None
    if args.prod:
        selected_variants = ["PRODUKSI"]
    elif args.variants:
        selected_variants = [v.strip() for v in args.variants.split(",") if v.strip()]

    if os.path.exists(args.csv):
        out_csv = run_experiment(args.csv, variants=selected_variants, reps=args.reps)
        summary = analyze_results(out_csv)
    else:
        print(f"Berkas dataset {args.csv} belum ditemukan.")
