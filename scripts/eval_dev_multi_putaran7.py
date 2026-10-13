# -*- coding: utf-8 -*-
"""
scripts/eval_dev_multi_putaran7.py
Evaluasi set DEV multi-giliran Putaran 7 (12 percakapan, 51 giliran).
Menjalankan alur multi-turn SessionPipeline secara utuh (LLM/parser + validator + engine + generator + checker).
Memverifikasi label pra-eksekusi: aksi_benar, status_fakta_benar, dan asersi mekanis.
"""
import os
import sys
import json
import time

sys.path.insert(0, os.path.abspath("."))
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from services.session_pipeline import SessionPipeline


def evaluate_dev_multi():
    input_file = "eval/dev_multi_putaran7.jsonl"
    output_file = "eval/dev_multi_putaran7_results.jsonl"

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
    total_asersi = 0
    pelanggaran_checker_cnt = 0
    fallback_cnt = 0
    latencies = []

    results_all = []

    print(f"=== Menjalankan Evaluasi Dev Multi-Giliran Putaran 7 ({len(conversations)} percakapan) ===")

    for c_idx, conv in enumerate(conversations, 1):
        conv_id = conv.get("id") or conv.get("conv_id")
        desc = conv.get("fokus") or conv.get("deskripsi", "")
        turns = conv.get("turns") or conv.get("giliran", [])
        print(f"\nPercakapan [{c_idx}/{len(conversations)}] {conv_id}: {desc}")

        state = {}
        history = []

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
                total_asersi += 1
                for rc in req_codes:
                    if rc not in tampil_codes:
                        asersi_pass = False
                        asersi_detail.append(f"missing product {rc}")

            # 2. kategori_wajib
            if asersi.get("kategori_wajib") is not None:
                req_kat = str(asersi["kategori_wajib"]).lower()
                cur_kat = (new_state.get("kategori") or "").lower()
                total_asersi += 1
                if cur_kat != req_kat:
                    asersi_pass = False
                    asersi_detail.append(f"expected category {req_kat}, got {cur_kat}")

            # 3. batas_harga
            if asersi.get("batas_harga") is not None:
                req_budget = asersi["batas_harga"]
                cur_budget = turn_res.fakta_eksekusi.get("batas_dipakai") or turn_res.fakta_eksekusi.get("budget_pelanggan") or new_state.get("budget")
                total_asersi += 1
                if cur_budget != req_budget:
                    asersi_pass = False
                    asersi_detail.append(f"expected budget {req_budget}, got {cur_budget}")

            # 4. nilai_spek_wajib
            if asersi.get("nilai_spek_wajib"):
                total_asersi += 1
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
                total_asersi += 1
                text_to_check = (turn_res.teks_jawaban or "") + " " + json.dumps(turn_res.fakta_eksekusi)
                for req_sub in asersi["teks_wajib_memuat"]:
                    if req_sub.lower() not in text_to_check.lower():
                        asersi_pass = False
                        asersi_detail.append(f"missing text '{req_sub}'")

            # 6. teks_dilarang_memuat
            if asersi.get("teks_dilarang_memuat"):
                total_asersi += 1
                ans_text = (turn_res.teks_jawaban or "").lower()
                for forb_sub in asersi["teks_dilarang_memuat"]:
                    if forb_sub.lower() in ans_text:
                        asersi_pass = False
                        asersi_detail.append(f"forbidden text '{forb_sub}' present")

            if asersi_pass:
                asersi_lulus_cnt += 1

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
                "pelanggaran_checker": turn_res.pelanggaran_pemeriksa,
                "is_fallback": turn_res.is_emergency_fallback,
                "latensi_ms": round(dur, 1),
                "teks_jawaban": turn_res.teks_jawaban
            }
            results_all.append(turn_log)

            match_symbol = "OK" if (aksi_match and status_match and asersi_pass) else "MISMATCH"
            print(f"  Turn {t_idx} | [{match_symbol}] Aksi: {aksi_pred} (gold: {aksi_gold}) | Status: {status_pred} | Lat: {dur:.1f}ms")

            # Update history dan state untuk giliran berikutnya
            history.append({"role": "user", "content": pesan})
            history.append({"role": "assistant", "content": turn_res.teks_jawaban})
            state = new_state

    # Simpan hasil lengkap
    with open(output_file, "w", encoding="utf-8") as f:
        for r in results_all:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    latencies.sort()
    p50 = latencies[len(latencies) // 2] if latencies else 0.0
    p95_idx = int(len(latencies) * 0.95)
    p95 = latencies[min(p95_idx, len(latencies) - 1)] if latencies else 0.0

    print("\n============================================================")
    print("HASIL EVALUASI MULTI-GILIRAN DEV PUTARAN 7 (eval/dev_multi_putaran7.jsonl)")
    print("============================================================")
    print(f"Total Percakapan              : {len(conversations)}")
    print(f"Total Giliran (n)             : {total_turns}")
    print(f"Akurasi Aksi                  : {aksi_benar_cnt}/{total_turns} ({(aksi_benar_cnt/total_turns)*100:.1f}%)")
    print(f"Akurasi Status Fakta          : {fakta_status_benar_cnt}/{total_turns} ({(fakta_status_benar_cnt/total_turns)*100:.1f}%)")
    print(f"Giliran Asersi Mekanis Lolos  : {asersi_lulus_cnt}/{total_turns} ({(asersi_lulus_cnt/total_turns)*100:.1f}%)")
    print(f"Pelanggaran GroundingChecker  : {pelanggaran_checker_cnt}/{total_turns} ({(pelanggaran_checker_cnt/total_turns)*100:.1f}%)")
    print(f"Emergency Fallback            : {fallback_cnt}/{total_turns} ({(fallback_cnt/total_turns)*100:.1f}%)")
    print(f"Latensi Pipeline p50          : {p50:.1f} ms")
    print(f"Latensi Pipeline p95          : {p95:.1f} ms")
    print(f"Detail tersimpan di           : {output_file}")


if __name__ == "__main__":
    evaluate_dev_multi()
