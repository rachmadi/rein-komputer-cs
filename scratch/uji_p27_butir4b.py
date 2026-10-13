# -*- coding: utf-8 -*-
"""
scratch/uji_p27_butir4b.py
Pengujian model jalur produksi (process_chat_message) untuk Putaran 27 Butir 4b:
Membandingkan Varian A (KATALOG_SQL=False) vs Varian B (KATALOG_SQL=True), 3 rep per varian.

Dua Prompt Uji:
1. "Kasih aku laptop yang paling murah yang punya GPU dedicated"
   Ground truth catalog.db: HP Victus 15-fb0009AX (KB-L26, Rp10.299.000).
2. "Laptop dengan ram 16 GB, berapa yang paling murah?"
   Ground truth catalog.db: MSI Modern 14 C12M (KB-L21, Rp8.499.000).
"""
import sys
import os
import json
import time
import uuid
from pathlib import Path

# Setup path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.chat_service import process_chat_message
import services.agent_tools as agent_tools

CASES = [
    {
        "id": 1,
        "prompt": "Kasih aku laptop yang paling murah yang punya GPU dedicated",
        "gt_code": "KB-L26",
        "gt_name": "HP Victus 15-fb0009AX",
        "gt_price": 10299000,
        "gt_desc": "HP Victus 15-fb0009AX (KB-L26, Rp10.299.000)"
    },
    {
        "id": 2,
        "prompt": "Laptop dengan ram 16 GB, berapa yang paling murah?",
        "gt_code": "KB-L21",
        "gt_name": "MSI Modern 14 C12M",
        "gt_price": 8499000,
        "gt_desc": "MSI Modern 14 C12M (KB-L21, Rp8.499.000)"
    }
]

def check_gt_mention(reply_text: str, gt_code: str, gt_name: str, gt_price: int) -> bool:
    low = reply_text.lower()
    code_low = gt_code.lower()
    name_tokens = [t.lower() for t in gt_name.split() if len(t) > 2]
    
    # Periksa kode langsung
    if code_low in low:
        return True
    
    # Periksa token nama (misal "victus" atau "msi modern")
    if "victus" in low and ("hp" in low or "15" in low):
        return True
    if "msi" in low and "modern" in low:
        return True
    
    # Periksa angka harga
    price_str = f"{gt_price:,}".replace(",", ".")
    if str(gt_price) in low or price_str in low or "10.299" in low or "8.499" in low:
        return True
        
    return False

def main():
    print("=== MEMULAI PENGUJIAN PUTARAN 27 BUTIR 4b: VARIAN A vs VARIAN B ===")
    
    variants = [
        ("A", False, "Jalur Lama (KATALOG_SQL=False)"),
        ("B", True, "Jalur Baru SQL (KATALOG_SQL=True)")
    ]
    
    all_results = []
    
    for var_code, sql_flag, var_label in variants:
        print(f"\n=======================================================")
        print(f"=== Menjalankan Varian {var_code}: {var_label} ===")
        print(f"=======================================================")
        agent_tools.KATALOG_SQL = sql_flag
        
        for case in CASES:
            print(f"\n--- Kasus {case['id']}: \"{case['prompt']}\" ---")
            print(f"    Ground Truth: {case['gt_desc']}")
            
            for rep in range(1, 4):
                sess_id = f"p27_4b_{var_code}_c{case['id']}_rep{rep}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
                t0 = time.time()
                
                res = process_chat_message(
                    session_id=sess_id,
                    user_text=case["prompt"],
                    penguji="uji_otomatis"
                )
                dur = time.time() - t0
                reply = res.get("reply", "").strip()
                
                # Ekstrak tool calls
                tc_list = res.get("metrics", {}).get("tool_calls", [])
                if not tc_list:
                    tc_list = res.get("tool_calls", [])
                cleaned_tools = []
                for tc in tc_list:
                    cleaned_tools.append({
                        "nama": tc.get("nama") or tc.get("function", {}).get("name"),
                        "argumen": tc.get("argumen") or tc.get("function", {}).get("arguments", {})
                    })
                
                # Cek kebenaran ground truth
                is_correct = check_gt_mention(reply, case["gt_code"], case["gt_name"], case["gt_price"])
                
                print(f"  [Rep {rep}] Latensi: {dur:.2f}s | Benar GT: {is_correct}")
                print(f"        Tool calls: {cleaned_tools}")
                print(f"        Balasan: {reply[:100]}...")
                
                all_results.append({
                    "varian": var_code,
                    "katalog_sql": sql_flag,
                    "kasus_id": case["id"],
                    "prompt": case["prompt"],
                    "rep": rep,
                    "session_id": sess_id,
                    "latensi_s": round(dur, 2),
                    "tool_calls": cleaned_tools,
                    "ground_truth": {
                        "kode": case["gt_code"],
                        "nama": case["gt_name"],
                        "harga_idr": case["gt_price"]
                    },
                    "benar_ground_truth": is_correct,
                    "balasan_verbatim": reply
                })
    
    # Simpan hasil
    out_path = Path("scratch/uji_p27_butir4b_hasil.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n[SUKSES] Hasil pengujian 4b disimpan ke {out_path}")
    
    # Tampilkan tabel ringkasan
    print("\n=== TABEL RINGKASAN HASIL BUTIR 4b ===")
    print(f"{'Varian':<7} | {'Kasus':<7} | {'Rep':<4} | {'Latensi':<8} | {'Benar GT':<9} | {'Tool Args'}")
    print("-" * 75)
    for r in all_results:
        args_str = json.dumps([tc["argumen"] for tc in r["tool_calls"]], ensure_ascii=False)
        print(f"{r['varian']:<7} | K{r['kasus_id']:<6} | R{r['rep']:<3} | {r['latensi_s']:<6.2f}s | {str(r['benar_ground_truth']):<9} | {args_str[:40]}")

if __name__ == "__main__":
    main()
