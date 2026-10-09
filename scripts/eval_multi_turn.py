# -*- coding: utf-8 -*-
"""
scripts/eval_multi_turn.py
Evaluator multi-turn percakapan SessionPipeline untuk Putaran 8:
- dev_multi_putaran7.jsonl
- dev_multi_putaran7_koreksi.jsonl
- dev_multi_putaran8.jsonl
"""
import os
import sys
import json
import time
import argparse

sys.path.insert(0, os.path.abspath("."))
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from services.session_pipeline import SessionPipeline


def evaluate_dataset(input_file: str, output_eval_json: str, output_results_jsonl: str | None = None):
    if not os.path.exists(input_file):
        print(f"Error: berkas {input_file} tidak ditemukan.")
        return

    with open(input_file, "r", encoding="utf-8") as f:
        conversations = [json.loads(line) for line in f if line.strip()]

    pipeline = SessionPipeline()

    total_turns = 0
    aksi_benar_cnt = 0
    fakta_status_benar_cnt = 0
    asersi_lulus_cnt = 0
    turn_sempurna_cnt = 0
    conv_lulus_cnt = 0
    pelanggaran_checker_cnt = 0
    fallback_cnt = 0
    latencies = []

    results_all = []
    conv_summaries = []

    print(f"\n=== Evaluasi {input_file} ({len(conversations)} percakapan) ===")

    for c_idx, conv in enumerate(conversations, 1):
        conv_id = conv.get("id") or conv.get("conv_id")
        desc = conv.get("fokus") or conv.get("deskripsi", "")
        turns = conv.get("turns") or conv.get("giliran", [])
        print(f"\n[{c_idx}/{len(conversations)}] {conv_id}: {desc}")

        state = {}
        history = []
        conv_all_turns_pass = True

        for turn in turns:
            t_idx = turn.get("t_idx") or turn.get("turn_idx")
            pesan = turn.get("pesan", "")
            aksi_gold = turn.get("aksi_benar")
            status_gold = turn.get("status_fakta_benar")
            asersi = turn.get("asersi") or turn.get("asersi_mekanis", {})

            total_turns += 1

            t0 = time.perf_counter()
            turn_res, new_state = pipeline.process_turn(pesan, session_state=state, history=history)
            dur = (time.perf_counter() - t0) * 1000.0
            latencies.append(dur)

            aksi_pred = turn_res.aksi_terpilih
            status_pred = turn_res.fakta_eksekusi.get("status")

            aksi_match = (aksi_pred.lower().strip() == aksi_gold.lower().strip()) if aksi_gold else True
            if aksi_match:
                aksi_benar_cnt += 1

            status_match = (str(status_pred).lower().strip() == str(status_gold).lower().strip()) if status_gold else True
            if status_match:
                fakta_status_benar_cnt += 1

            # Evaluasi Asersi Mekanis
            asersi_pass = True
            asersi_detail = []

            # 1. kode_produk_wajib
            if asersi.get("kode_produk_wajib"):
                req_codes = asersi["kode_produk_wajib"]
                tampil_codes = [p.get("kode") for p in new_state.get("produk_tampil", [])]
                fakta_prods = turn_res.fakta_eksekusi.get("produk", [])
                if isinstance(fakta_prods, list):
                    for fp in fakta_prods:
                        if isinstance(fp, dict) and fp.get("kode"):
                            tampil_codes.append(fp.get("kode"))
                for rc in req_codes:
                    if rc not in tampil_codes:
                        asersi_pass = False
                        asersi_detail.append(f"missing product {rc}")

            # 2. kategori_wajib
            if asersi.get("kategori_wajib") is not None:
                req_kat = str(asersi["kategori_wajib"]).lower()
                cur_kat = (new_state.get("kategori") or "").lower()
                if cur_kat != req_kat:
                    asersi_pass = False
                    asersi_detail.append(f"expected category {req_kat}, got {cur_kat}")

            # 3. batas_harga
            if asersi.get("batas_harga") is not None:
                req_budget = asersi["batas_harga"]
                cur_budget = turn_res.fakta_eksekusi.get("batas_dipakai") or turn_res.fakta_eksekusi.get("budget_pelanggan") or new_state.get("budget")
                if cur_budget != req_budget:
                    asersi_pass = False
                    asersi_detail.append(f"expected budget {req_budget}, got {cur_budget}")

            # 4. nilai_spek_wajib
            if asersi.get("nilai_spek_wajib"):
                fakta_spek = turn_res.fakta_eksekusi.get("spesifikasi", []) or turn_res.fakta_eksekusi.get("spesifikasi_produk", [])
                spek_str = json.dumps(fakta_spek) + " " + (turn_res.teks_jawaban or "")
                for k, v in asersi["nilai_spek_wajib"].items():
                    if str(v).lower() not in spek_str.lower():
                        digits = "".join([c for c in str(v) if c.isdigit()])
                        if digits and digits not in spek_str:
                            asersi_pass = False
                            asersi_detail.append(f"missing spec {k}={v}")

            # 5. teks_wajib_memuat
            if asersi.get("teks_wajib_memuat"):
                text_to_check = (turn_res.teks_jawaban or "") + " " + json.dumps(turn_res.fakta_eksekusi)
                for req_sub in asersi["teks_wajib_memuat"]:
                    if req_sub.lower() not in text_to_check.lower():
                        asersi_pass = False
                        asersi_detail.append(f"missing text '{req_sub}'")

            # 6. teks_dilarang_memuat
            if asersi.get("teks_dilarang_memuat"):
                ans_text = (turn_res.teks_jawaban or "").lower()
                for forb_sub in asersi["teks_dilarang_memuat"]:
                    if forb_sub.lower() in ans_text:
                        asersi_pass = False
                        asersi_detail.append(f"forbidden text '{forb_sub}' present")

            if asersi_pass:
                asersi_lulus_cnt += 1

            turn_ok = bool(aksi_match and status_match and asersi_pass)
            if turn_ok:
                turn_sempurna_cnt += 1
            else:
                conv_all_turns_pass = False

            if turn_res.pelanggaran_pemeriksa:
                pelanggaran_checker_cnt += 1
            if turn_res.is_emergency_fallback:
                fallback_cnt += 1

            turn_log = {
                "conv_id": conv_id,
                "turn_idx": t_idx,
                "pesan": pesan,
                "aksi_gold": aksi_gold,
                "aksi_pred": aksi_pred,
                "aksi_match": aksi_match,
                "status_gold": status_gold,
                "status_pred": status_pred,
                "status_match": status_match,
                "asersi_pass": asersi_pass,
                "asersi_detail": asersi_detail,
                "turn_ok": turn_ok,
                "pelanggaran_checker": turn_res.pelanggaran_pemeriksa,
                "is_fallback": turn_res.is_emergency_fallback,
                "latensi_ms": round(dur, 1),
                "teks_jawaban": turn_res.teks_jawaban
            }
            results_all.append(turn_log)

            match_symbol = "OK" if turn_ok else "MISMATCH"
            print(f"  T{t_idx} [{match_symbol}] Aksi: {aksi_pred} (gold: {aksi_gold}) | Status: {status_pred} | Lat: {dur:.1f}ms")

            history.append({"role": "user", "content": pesan})
            history.append({"role": "assistant", "content": turn_res.teks_jawaban})
            state = new_state

        if conv_all_turns_pass:
            conv_lulus_cnt += 1
        conv_summaries.append({
            "conv_id": conv_id,
            "total_turns": len(turns),
            "all_turns_pass": conv_all_turns_pass
        })

    latencies.sort()
    p50 = latencies[len(latencies) // 2] if latencies else 0.0
    p95_idx = int(len(latencies) * 0.95)
    p95 = latencies[min(p95_idx, len(latencies) - 1)] if latencies else 0.0

    eval_summary = {
        "dataset": input_file,
        "total_conversations": len(conversations),
        "conversations_passed": conv_lulus_cnt,
        "conversation_accuracy_percent": round((conv_lulus_cnt / len(conversations)) * 100.0, 2) if conversations else 0.0,
        "total_turns": total_turns,
        "turns_passed": turn_sempurna_cnt,
        "turn_accuracy_percent": round((turn_sempurna_cnt / total_turns) * 100.0, 2) if total_turns else 0.0,
        "aksi_correct": aksi_benar_cnt,
        "aksi_accuracy_percent": round((aksi_benar_cnt / total_turns) * 100.0, 2) if total_turns else 0.0,
        "status_correct": fakta_status_benar_cnt,
        "status_accuracy_percent": round((fakta_status_benar_cnt / total_turns) * 100.0, 2) if total_turns else 0.0,
        "assertions_passed": asersi_lulus_cnt,
        "assertion_accuracy_percent": round((asersi_lulus_cnt / total_turns) * 100.0, 2) if total_turns else 0.0,
        "checker_violations": pelanggaran_checker_cnt,
        "emergency_fallbacks": fallback_cnt,
        "latency_p50_ms": round(p50, 1),
        "latency_p95_ms": round(p95, 1),
        "conversations": conv_summaries
    }

    with open(output_eval_json, "w", encoding="utf-8") as f:
        json.dump(eval_summary, f, indent=2, ensure_ascii=False)
    print(f"\nRingkasan evaluasi disimpan di: {output_eval_json}")

    if output_results_jsonl:
        with open(output_results_jsonl, "w", encoding="utf-8") as f:
            for r in results_all:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"Detail log giliran disimpan di: {output_results_jsonl}")

    print("------------------------------------------------------------")
    print(f"Akurasi Giliran      : {turn_sempurna_cnt}/{total_turns} ({eval_summary['turn_accuracy_percent']}%)")
    print(f"Akurasi Percakapan  : {conv_lulus_cnt}/{len(conversations)} ({eval_summary['conversation_accuracy_percent']}%)")
    print(f"Latensi p50 / p95    : {p50:.1f}ms / {p95:.1f}ms")
    print("------------------------------------------------------------")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path ke berkas JSONL input")
    parser.add_argument("--output_eval", required=True, help="Path ke berkas JSON evaluasi ringkas")
    parser.add_argument("--output_results", default=None, help="Path ke berkas JSONL detail hasil")
    args = parser.parse_args()

    evaluate_dataset(args.input, args.output_eval, args.output_results)
