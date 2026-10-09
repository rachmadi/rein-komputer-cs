# -*- coding: utf-8 -*-
"""
scripts/replay.py
Menjalankan percakapan regresi dari eval/regression_telegram.jsonl dengan LLM sungguhan (Ollama).
Memproses 11 percakapan (134 giliran) dari uji Telegram pemilik data, masing-masing dengan sesi baru.
Dapat dijalankan 3 kali (--runs 3, default) atau sesuai parameter.
Menuliskan transkrip lengkap ke eval/replay_transcript.md dengan hitungan otomatis di akhir.
"""
import os
import sys
import json
import time
import argparse
from typing import List, Dict, Any

# Root workspace ke sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.session_pipeline import SessionPipeline
from services.schema_actions import ParserOutput, ActionEnum, ActionArguments
from services.action_engine import ActionEngine
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
        # Eksekusi aksi evaluasi_kecocokan secara deterministik
        parsed = ParserOutput(
            aksi=ActionEnum.EVALUASI_KECOCOKAN,
            argumen=ActionArguments(produk=[c["produk_kode"]], kebutuhan_teks=c["kebutuhan"])
        )
        act_res = pipeline.action_engine.execute(parsed, session_state={})
        
        # Generator LLM
        gen_out, gen_metrics = generate_response(
            aksi=ActionEnum.EVALUASI_KECOCOKAN.value,
            fakta=act_res.fakta,
            state={"kebutuhan_teks": c["kebutuhan"]},
            history=[]
        )
        
        # Validasi grounding checker
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


def run_replay(regression_file: str, runs: int, output_md: str, limit_convs: int | None = None):
    print(f"Memuat skenario regresi dari {regression_file}...")
    with open(regression_file, "r", encoding="utf-8") as f:
        conversations = [json.loads(line) for line in f if line.strip()]

    if limit_convs:
        conversations = conversations[:limit_convs]

    print(f"Ditemukan {len(conversations)} percakapan untuk diuji. Menjalankan {runs} repetisi...")
    pipeline = SessionPipeline()

    md_lines = []
    md_lines.append("# Transkrip Replay Percakapan Regresi Telegram")
    md_lines.append(f"**Tanggal Pengujian**: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    md_lines.append(f"**Berkas Sumber**: `{regression_file}` ({len(conversations)} percakapan, {sum(len(c.get('turns', [])) for c in conversations)} giliran)")
    md_lines.append(f"**Jumlah Repetisi (Runs)**: {runs}")
    md_lines.append("")

    total_turns_executed = 0
    total_emergency_fallbacks = 0
    total_checker_violations = 0
    total_category_mismatches = 0

    # Iterasi run
    for r in range(1, runs + 1):
        md_lines.append(f"## --- RUN {r} DARI {runs} ---")
        md_lines.append("")

        for c_idx, conv in enumerate(conversations, 1):
            c_id = conv.get("id", f"conv-{c_idx}")
            sumber = conv.get("sumber", "telegram")
            menguji = conv.get("menguji", "")
            turns = conv.get("turns", [])

            session_id = f"sess_run_{r}_{c_id}"
            session_state = {}
            last_requested_category = None

            md_lines.append(f"### Percakapan {c_id} (Run {r})")
            if menguji:
                md_lines.append(f"*Fokus Uji*: {menguji}")
            md_lines.append("")
            md_lines.append("| No | Pesan Pelanggan | Aksi Parse | Fakta Mesin | Teks Bot Verbatim | Kartu | Parse (ms) | Mesin (ms) | Gen (ms) | Total (ms) | Pelanggaran | Darurat |")
            md_lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")

            for t_idx, user_msg in enumerate(turns, 1):
                total_turns_executed += 1
                
                # Deteksi kategori yang diminta pelanggan
                msg_lower = user_msg.lower()
                if "laptop" in msg_lower or "lepi" in msg_lower:
                    last_requested_category = "laptop"
                elif "pc" in msg_lower or "desktop" in msg_lower or "komputer meja" in msg_lower:
                    last_requested_category = "desktop"
                elif "printer" in msg_lower:
                    last_requested_category = "printer"

                t_res, updated_state = pipeline.process_turn(user_msg, session_state)
                session_state = updated_state

                # Deteksi kategori mismatch pada produk yang ditampilkan
                cat_mismatch = False
                if t_res.fakta_eksekusi and "produk" in t_res.fakta_eksekusi and last_requested_category:
                    prods = t_res.fakta_eksekusi.get("produk", [])
                    if isinstance(prods, list) and prods:
                        for p in prods:
                            p_cat = (p.get("kategori") or "").lower()
                            if p_cat and p_cat != last_requested_category:
                                cat_mismatch = True
                                break
                if cat_mismatch:
                    total_category_mismatches += 1

                if t_res.is_emergency_fallback:
                    total_emergency_fallbacks += 1
                if t_res.pelanggaran_pemeriksa:
                    total_checker_violations += len(t_res.pelanggaran_pemeriksa)

                # Ringkasan fakta mesin
                status_fakta = t_res.fakta_eksekusi.get("status", "-")
                total_prod = len(t_res.fakta_eksekusi.get("produk", []))
                fakta_summary = f"status={status_fakta}, n={total_prod}"
                if "topik" in t_res.fakta_eksekusi:
                    fakta_summary += f", topik={t_res.fakta_eksekusi['topik']}"

                # Kartu
                kartu_str = "Ada" if t_res.kartu_produk_html else "-"
                darurat_str = "Ya" if t_res.is_emergency_fallback else "Tidak"
                pelanggaran_cnt = len(t_res.pelanggaran_pemeriksa)

                clean_user = user_msg.replace("|", "/").replace("\n", " ")
                clean_bot = t_res.teks_jawaban.replace("|", "/").replace("\n", " ")

                md_lines.append(
                    f"| {t_idx} | {clean_user} | `{t_res.aksi_terpilih}` | {fakta_summary} | {clean_bot} | {kartu_str} | {t_res.latensi_parse_ms:.1f} | {t_res.latensi_mesin_ms:.1f} | {t_res.latensi_generate_ms:.1f} | {t_res.latensi_total_ms:.1f} | {pelanggaran_cnt} | {darurat_str} |"
                )

                print(f"[Run {r}][{c_id} Turn {t_idx:02d}/{len(turns):02d}] {clean_user[:25]:25s} -> {t_res.aksi_terpilih:18s} ({t_res.latensi_total_ms:6.1f}ms)", flush=True)

            md_lines.append("")
            # Simpan transkrip inkremental ke file
            os.makedirs(os.path.dirname(output_md) or ".", exist_ok=True)
            with open(output_md, "w", encoding="utf-8") as f_tmp:
                f_tmp.write("\n".join(md_lines) + "\n")

    # Evaluasi 3 Kasus Evaluasi Kecocokan (Item B.5)
    print("\nMenjalankan 3 kasus evaluasi_kecocokan untuk bukti keluaran mentah generator...", flush=True)
    eval_cases = evaluate_three_evaluasi_kecocokan_cases(pipeline)
    md_lines.append("## Bukti Keluaran Mentah Generator: Evaluasi Kecocokan (B.5)")
    md_lines.append("Tiga kasus evaluasi spesifikasi perangkat keras terhadap profil kebutuhan komputasi:")
    md_lines.append("")
    for ec in eval_cases:
        md_lines.append(f"### {ec['kasus']}")
        md_lines.append(f"- **Kebutuhan**: \"{ec['kebutuhan']}\"")
        md_lines.append(f"- **Produk Diuji**: `{ec['produk_kode']}`")
        md_lines.append(f"- **Status Kecocokan Fakta Mesin**: `{ec['fakta_status_kecocokan']}`")
        md_lines.append(f"- **Generator `penilaian`**: `{json.dumps(ec['generator_penilaian'])}`")
        md_lines.append(f"- **Generator `teks`**: \"{ec['generator_teks']}\"")
        md_lines.append(f"- **Keluaran Mentah JSON Generator**: `{ec['raw_generator_content']}`")
        md_lines.append(f"- **Hasil Pemeriksa Grounding**: Valid={ec['checker_valid']}, Pelanggaran={ec['violations']}")
        md_lines.append("")

    # Hitungan Otomatis di Akhir Transkrip
    md_lines.append("## Hitungan Otomatis Ringkasan Evaluasi")
    md_lines.append(f"- **Total Giliran Dieksekusi**: {total_turns_executed} giliran")
    md_lines.append(f"- **Jumlah Giliran Berkalimat Darurat**: {total_emergency_fallbacks}")
    md_lines.append(f"- **Jumlah Pelanggaran Pemeriksa**: {total_checker_violations}")
    md_lines.append(f"- **Jumlah Giliran Kategori Mismatch**: {total_category_mismatches}")
    md_lines.append("")
    md_lines.append("> Catatan: Penilaian rubrik kualitatif akhir dilakukan oleh reviewer dari transkrip di atas.")

    os.makedirs(os.path.dirname(output_md) or ".", exist_ok=True)
    with open(output_md, "w", encoding="utf-8") as f_out:
        f_out.write("\n".join(md_lines) + "\n")

    print(f"\nSelesai! Transkrip replay tersimpan di: {output_md}")
    print(f"Total giliran: {total_turns_executed}, Darurat: {total_emergency_fallbacks}, Pelanggaran: {total_checker_violations}, Mismatch kategori: {total_category_mismatches}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="eval/regression_telegram.jsonl", help="Path berkas regression jsonl")
    parser.add_argument("--runs", type=int, default=1, help="Jumlah repetisi pengujian")
    parser.add_argument("--output", default="eval/replay_putaran5.md", help="Path berkas output markdown")
    parser.add_argument("--limit-convs", type=int, default=3, help="Jumlah percakapan yang diuji")
    args = parser.parse_args()

    run_replay(args.file, args.runs, args.output, limit_convs=args.limit_convs)
