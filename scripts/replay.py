# -*- coding: utf-8 -*-
"""
scripts/replay.py
Menjalankan percakapan regresi dari eval/regression_telegram.jsonl dengan LLM sungguhan (Ollama).
Memproses 11 percakapan (134 giliran) dari uji Telegram pemilik data, masing-masing dengan sesi baru.
Dijalankan 3 kali (--runs 3, default) untuk mengukur stabilitas dan variabilitas antar-run.
Menyimpan transkrip lengkap dan ringkasan metrik di eval/replay_putaran6.md serta data mentah di eval/replay_putaran6.jsonl.
"""
import os
import sys
import json
import time
import argparse
from typing import List, Dict, Any
from collections import Counter

# Set OLLAMA_BASE_URL to IPv4 loopback to prevent IPv6 SYN_SENT delay on Windows
os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

# Root workspace ke sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.session_pipeline import SessionPipeline
from services.schema_actions import ParserOutput, ActionEnum, ActionArguments
from services.llm_generator import generate_response


def evaluate_three_evaluasi_kecocokan_cases(pipeline: SessionPipeline) -> List[Dict[str, Any]]:
    """
    Menjalankan 3 kasus evaluasi_kecocokan setelah perbaikan:
    1. di_bawah_minimum
    2. memenuhi_minimum
    3. memenuhi_rekomendasi
    Mengembalikan keluaran mentah generator (field penilaian dan teks).
    """
    cases = [
        {
            "kasus": "Kasus 1: di_bawah_minimum",
            "kebutuhan": "editing video 4K dan animasi rendering 3D",
            "produk_kode": "KB-L01",  # Acer Aspire Lite (N100, 8GB RAM, iGPU)
            "target": "di_bawah_minimum"
        },
        {
            "kasus": "Kasus 2: memenuhi_minimum",
            "kebutuhan": "kuliah dan ngetik skripsi word excel",
            "produk_kode": "KB-L01",  # Acer Aspire Lite (N100, 8GB RAM, SSD 512GB)
            "target": "memenuhi_minimum"
        },
        {
            "kasus": "Kasus 3: memenuhi_rekomendasi",
            "kebutuhan": "kuliah dan ngetik skripsi word excel",
            "produk_kode": "KB-L03",  # ASUS Vivobook 14 (Core i5, 16GB RAM, SSD 512GB)
            "target": "memenuhi_rekomendasi"
        }
    ]

    results = []
    for c in cases:
        parsed = ParserOutput(
            aksi=ActionEnum.EVALUASI_KECOCOKAN,
            argumen=ActionArguments(produk=[c["produk_kode"]], kebutuhan_teks=c["kebutuhan"])
        )
        act_res = pipeline.action_engine.execute(parsed, session_state={})
        
        gen_out, gen_metrics = generate_response(
            aksi=ActionEnum.EVALUASI_KECOCOKAN.value,
            fakta=act_res.fakta,
            state={"kebutuhan_teks": c["kebutuhan"]},
            history=[]
        )
        
        is_valid, violations = pipeline.grounding_checker.check(
            gen_out.teks, act_res.fakta, state={"kebutuhan_teks": c["kebutuhan"]}, penilaian=gen_out.penilaian
        )
        
        results.append({
            "kasus": c["kasus"],
            "kebutuhan": c["kebutuhan"],
            "produk_kode": c["produk_kode"],
            "fakta_status_kecocokan": act_res.fakta.get("evaluasi_produk", [{}])[0].get("status_kecocokan"),
            "generator_penilaian": gen_out.penilaian,
            "generator_teks": gen_out.teks,
            "raw_generator_content": gen_metrics.get("raw_content"),
            "checker_valid": is_valid,
            "violations": violations
        })
    return results


def percentile(data: List[float], p: float) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    idx = int(len(s) * p)
    return s[min(idx, len(s) - 1)]


def run_replay(regression_file: str, runs: int, output_md: str, output_jsonl: str, limit_convs: int | None = None):
    print(f"Memuat skenario regresi dari {regression_file}...")
    with open(regression_file, "r", encoding="utf-8") as f:
        conversations = [json.loads(line) for line in f if line.strip()]

    if limit_convs:
        conversations = conversations[:limit_convs]

    total_turns_dataset = sum(len(c.get("turns", [])) for c in conversations)
    print(f"Ditemukan {len(conversations)} percakapan ({total_turns_dataset} giliran). Menjalankan {runs} repetisi...")
    
    pipeline = SessionPipeline()

    os.makedirs(os.path.dirname(output_md) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(output_jsonl) or ".", exist_ok=True)
    
    # Buka jsonl untuk streaming output mentah
    f_jsonl = open(output_jsonl, "w", encoding="utf-8")

    all_turn_records = []
    run_records: Dict[int, List[Dict[str, Any]]] = {r: [] for r in range(1, runs + 1)}
    turns_by_key: Dict[str, Dict[int, str]] = {}  # key: (conv_id, t_idx) -> {run_r: aksi}

    md_transcript_lines = []

    for r in range(1, runs + 1):
        print(f"\n==========================================")
        print(f"        MEMULAI RUN {r} DARI {runs}")
        print(f"==========================================")
        md_transcript_lines.append(f"## --- RUN {r} DARI {runs} ---")
        md_transcript_lines.append("")

        for c_idx, conv in enumerate(conversations, 1):
            c_id = conv.get("id", f"conv-{c_idx}")
            sumber = conv.get("sumber", "telegram")
            menguji = conv.get("menguji", "")
            turns = conv.get("turns", [])

            session_id = f"sess_run_{r}_{c_id}"
            session_state = {}
            last_requested_category = None

            md_transcript_lines.append(f"### Percakapan {c_id} (Run {r})")
            if menguji:
                md_transcript_lines.append(f"*Fokus Uji*: {menguji}")
            md_transcript_lines.append("")
            md_transcript_lines.append("| No | Pesan Pelanggan | Aksi Parse | Fakta Mesin | Teks Bot Verbatim | Kartu | Parse (ms) | Mesin (ms) | Gen (ms) | Total (ms) | Pelanggaran | Darurat |")
            md_transcript_lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")

            for t_idx, user_msg in enumerate(turns, 1):
                msg_lower = user_msg.lower()
                if "laptop" in msg_lower or "lepi" in msg_lower:
                    last_requested_category = "laptop"
                elif "pc" in msg_lower or "desktop" in msg_lower or "komputer meja" in msg_lower:
                    last_requested_category = "desktop"
                elif "printer" in msg_lower:
                    last_requested_category = "printer"

                t_res, updated_state = pipeline.process_turn(user_msg, session_state)
                session_state = updated_state

                # Deteksi kategori mismatch
                cat_mismatch = False
                if t_res.fakta_eksekusi and "produk" in t_res.fakta_eksekusi and last_requested_category:
                    prods = t_res.fakta_eksekusi.get("produk", [])
                    if isinstance(prods, list) and prods:
                        for p in prods:
                            p_cat = (p.get("kategori") or "").lower()
                            if p_cat and p_cat != last_requested_category:
                                cat_mismatch = True
                                break

                status_fakta = t_res.fakta_eksekusi.get("status", "-")
                total_prod = len(t_res.fakta_eksekusi.get("produk", []))
                fakta_summary = f"status={status_fakta}, n={total_prod}"
                if "topik" in t_res.fakta_eksekusi:
                    fakta_summary += f", topik={t_res.fakta_eksekusi['topik']}"

                kartu_str = "Ada" if t_res.kartu_produk_html else "-"
                darurat_str = "Ya" if t_res.is_emergency_fallback else "Tidak"
                pelanggaran_cnt = len(t_res.pelanggaran_pemeriksa)

                clean_user = user_msg.replace("|", "/").replace("\n", " ")
                clean_bot = t_res.teks_jawaban.replace("|", "/").replace("\n", " ")

                md_transcript_lines.append(
                    f"| {t_idx} | {clean_user} | `{t_res.aksi_terpilih}` | {fakta_summary} | {clean_bot} | {kartu_str} | {t_res.latensi_parse_ms:.1f} | {t_res.latensi_mesin_ms:.1f} | {t_res.latensi_generate_ms:.1f} | {t_res.latensi_total_ms:.1f} | {pelanggaran_cnt} | {darurat_str} |"
                )

                rec = {
                    "run": r,
                    "conv_id": c_id,
                    "turn_idx": t_idx,
                    "pesan": user_msg,
                    "aksi_terpilih": t_res.aksi_terpilih,
                    "fakta_status": status_fakta,
                    "latensi_parse_ms": round(t_res.latensi_parse_ms, 1),
                    "latensi_mesin_ms": round(t_res.latensi_mesin_ms, 1),
                    "latensi_generate_ms": round(t_res.latensi_generate_ms, 1),
                    "latensi_total_ms": round(t_res.latensi_total_ms, 1),
                    "pelanggaran_checker": t_res.pelanggaran_pemeriksa,
                    "is_emergency_fallback": t_res.is_emergency_fallback,
                    "kategori_mismatch": cat_mismatch,
                    "teks_jawaban": t_res.teks_jawaban
                }
                all_turn_records.append(rec)
                run_records[r].append(rec)

                key = f"{c_id}_T{t_idx}"
                if key not in turns_by_key:
                    turns_by_key[key] = {}
                turns_by_key[key][r] = t_res.aksi_terpilih

                f_jsonl.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f_jsonl.flush()

                print(f"[R{r}][{c_id} T{t_idx:02d}/{len(turns):02d}] {clean_user[:25]:25s} -> {t_res.aksi_terpilih:18s} ({t_res.latensi_total_ms:6.1f}ms)", flush=True)

            md_transcript_lines.append("")

    f_jsonl.close()

    # Evaluasi 3 Kasus Evaluasi Kecocokan (B.5)
    print("\nMenjalankan 3 kasus evaluasi_kecocokan untuk bukti keluaran mentah generator...", flush=True)
    eval_cases = evaluate_three_evaluasi_kecocokan_cases(pipeline)

    # --- PERHITUNGAN METRIK AGREGAT ---
    print("\nMenghitung metrik stabilitas dan latensi...")

    # 1. Latensi per run & gabungan
    latency_summary = {}
    for r in range(1, runs + 1):
        recs = run_records[r]
        p_parse = [x["latensi_parse_ms"] for x in recs]
        p_mesin = [x["latensi_mesin_ms"] for x in recs]
        p_gen = [x["latensi_generate_ms"] for x in recs]
        p_tot = [x["latensi_total_ms"] for x in recs]
        latency_summary[f"Run {r}"] = {
            "parse_p50": percentile(p_parse, 0.50), "parse_p95": percentile(p_parse, 0.95),
            "mesin_p50": percentile(p_mesin, 0.50), "mesin_p95": percentile(p_mesin, 0.95),
            "gen_p50": percentile(p_gen, 0.50),     "gen_p95": percentile(p_gen, 0.95),
            "tot_p50": percentile(p_tot, 0.50),     "tot_p95": percentile(p_tot, 0.95),
            "n": len(recs)
        }

    all_parse = [x["latensi_parse_ms"] for x in all_turn_records]
    all_mesin = [x["latensi_mesin_ms"] for x in all_turn_records]
    all_gen = [x["latensi_generate_ms"] for x in all_turn_records]
    all_tot = [x["latensi_total_ms"] for x in all_turn_records]
    latency_summary["Gabungan"] = {
        "parse_p50": percentile(all_parse, 0.50), "parse_p95": percentile(all_parse, 0.95),
        "mesin_p50": percentile(all_mesin, 0.50), "mesin_p95": percentile(all_mesin, 0.95),
        "gen_p50": percentile(all_gen, 0.50),     "gen_p95": percentile(all_gen, 0.95),
        "tot_p50": percentile(all_tot, 0.50),     "tot_p95": percentile(all_tot, 0.95),
        "n": len(all_turn_records)
    }

    # 2. Frekuensi Aksi A1-A12
    action_counter = Counter(x["aksi_terpilih"] for x in all_turn_records)
    total_recs = len(all_turn_records)

    # 3. Pelanggaran Checker & Emergency Fallback
    all_violations = []
    emergency_count = 0
    cat_mismatch_count = 0
    for x in all_turn_records:
        if x["pelanggaran_checker"]:
            all_violations.extend(x["pelanggaran_checker"])
        if x["is_emergency_fallback"]:
            emergency_count += 1
        if x["kategori_mismatch"]:
            cat_mismatch_count += 1
    violation_counter = Counter(all_violations)

    # 4. Konsistensi Antar-Run
    consistent_count = 0
    diff_keys = []
    for key, run_map in turns_by_key.items():
        actions = list(run_map.values())
        if len(actions) == runs and len(set(actions)) == 1:
            consistent_count += 1
        else:
            diff_keys.append((key, run_map))
    consistency_pct = (consistent_count / total_turns_dataset) * 100.0 if total_turns_dataset else 0.0

    # Susun Dokumen Markdown Final
    final_md = []
    final_md.append("# Laporan Hasil Replay Penuh Putaran 6 (ReIn Komputer)")
    final_md.append(f"**Tanggal Pengujian**: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    final_md.append(f"**Dataset**: `{regression_file}` ({len(conversations)} percakapan, {total_turns_dataset} giliran per run)")
    final_md.append(f"**Jumlah Repetisi (Runs)**: {runs} (Total {total_recs} turn dieksekusi)")
    final_md.append("")

    final_md.append("## 1. Ringkasan Latensi Pipeline (ms)")
    final_md.append("| Metrik | Parse p50 | Parse p95 | Mesin p50 | Mesin p95 | Gen p50 | Gen p95 | Total p50 | Total p95 | n |")
    final_md.append("|---|---|---|---|---|---|---|---|---|---|")
    for name, m in latency_summary.items():
        final_md.append(f"| {name} | {m['parse_p50']:.1f} | {m['parse_p95']:.1f} | {m['mesin_p50']:.1f} | {m['mesin_p95']:.1f} | {m['gen_p50']:.1f} | {m['gen_p95']:.1f} | {m['tot_p50']:.1f} | {m['tot_p95']:.1f} | {m['n']} |")
    final_md.append("")

    final_md.append("## 2. Frekuensi Aksi Terprediksi (Gabungan Seluruh Run)")
    final_md.append("| Kode Aksi | Nama Aksi | Frekuensi (n) | Persentase (%) |")
    final_md.append("|---|---|---|---|")
    for act, cnt in sorted(action_counter.items(), key=lambda x: -x[1]):
        pct = (cnt / total_recs) * 100.0
        final_md.append(f"| - | `{act}` | {cnt} | {pct:.1f}% |")
    final_md.append(f"| **Total** | | **{total_recs}** | **100.0%** |")
    final_md.append("")

    final_md.append("## 3. Pelanggaran GroundingChecker & Fallback Darurat")
    final_md.append(f"- **Total Giliran Dieksekusi**: {total_recs}")
    final_md.append(f"- **Total Pelanggaran Checker**: {len(all_violations)} ({len(all_violations)/total_recs*100:.1f}%)")
    final_md.append(f"- **Total Emergency Fallback**: {emergency_count} ({emergency_count/total_recs*100:.1f}%)")
    final_md.append(f"- **Total Kategori Mismatch**: {cat_mismatch_count} ({cat_mismatch_count/total_recs*100:.1f}%)")
    final_md.append("")
    final_md.append("### Rincian Jenis Pelanggaran Checker:")
    if violation_counter:
        for viol, cnt in violation_counter.items():
            final_md.append(f"- `{viol}`: {cnt} kali")
    else:
        final_md.append("- *Tidak ada pelanggaran GroundingChecker yang terdeteksi.*")
    final_md.append("")

    final_md.append("## 4. Konsistensi Antar-Run (Stabilitas Deterministik)")
    final_md.append(f"- **Turn dengan Aksi Identik di Ketiga Run**: {consistent_count}/{total_turns_dataset} ({consistency_pct:.1f}%)")
    final_md.append(f"- **Turn dengan Variasi Aksi**: {len(diff_keys)}/{total_turns_dataset} ({len(diff_keys)/total_turns_dataset*100:.1f}%)")
    final_md.append("")
    if diff_keys:
        final_md.append("### Contoh Giliran dengan Perbedaan Aksi Antar-Run:")
        for idx, (key, run_map) in enumerate(diff_keys[:5], 1):
            actions_str = ", ".join(f"Run {k}: `{v}`" for k, v in sorted(run_map.items()))
            final_md.append(f"{idx}. **{key}**: {actions_str}")
        final_md.append("")

    final_md.append("## 5. Bukti Keluaran Mentah Generator: Evaluasi Kecocokan (B.5)")
    for ec in eval_cases:
        final_md.append(f"### {ec['kasus']}")
        final_md.append(f"- **Kebutuhan**: \"{ec['kebutuhan']}\"")
        final_md.append(f"- **Produk Diuji**: `{ec['produk_kode']}`")
        final_md.append(f"- **Status Kecocokan Fakta Mesin**: `{ec['fakta_status_kecocokan']}`")
        final_md.append(f"- **Generator `penilaian`**: `{json.dumps(ec['generator_penilaian'])}`")
        final_md.append(f"- **Generator `teks`**: \"{ec['generator_teks']}\"")
        final_md.append(f"- **Keluaran Mentah JSON Generator**: `{ec['raw_generator_content']}`")
        final_md.append(f"- **Hasil Pemeriksa Grounding**: Valid={ec['checker_valid']}, Pelanggaran={ec['violations']}")
        final_md.append("")

    final_md.append("## 6. Transkrip Lengkap Percakapan")
    final_md.extend(md_transcript_lines)

    with open(output_md, "w", encoding="utf-8") as f_out:
        f_out.write("\n".join(final_md) + "\n")

    print(f"\nReplay selesai! Markdown disimpan di: {output_md}")
    print(f"Data mentah disimpan di: {output_jsonl}")
    print(f"Konsistensi antar-run: {consistency_pct:.1f}% ({consistent_count}/{total_turns_dataset})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="eval/regression_telegram.jsonl", help="Path berkas regression jsonl")
    parser.add_argument("--runs", type=int, default=3, help="Jumlah repetisi pengujian")
    parser.add_argument("--output", default="eval/replay_putaran6.md", help="Path berkas output markdown")
    parser.add_argument("--jsonl", default="eval/replay_putaran6.jsonl", help="Path berkas output jsonl")
    parser.add_argument("--limit-convs", type=int, default=None, help="Jumlah percakapan yang diuji (None = semua)")
    args = parser.parse_args()

    run_replay(args.file, args.runs, args.output, args.jsonl, limit_convs=args.limit_convs)
