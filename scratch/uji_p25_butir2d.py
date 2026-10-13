# -*- coding: utf-8 -*-
"""
Uji Butir 2d Putaran 25:
Putar ulang 21 pesan pelanggan live sesi 12 Okt,
tandai pesan terakhir tidak terkirim,
kirim 'Kok gak jawab?',
simpan balasan terakhir verbatim untuk 3 ulangan.
"""
import json
import time
import sys
from pathlib import Path

# Tambahkan root proyek ke sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.chat_service import process_chat_message, tandai_pesan_terakhir_tidak_terkirim, get_session_manager

PESAN_21 = [
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
]

def jalankan_uji():
    hasil_ulangan = []
    mgr = get_session_manager()

    for rep in range(1, 4):
        session_id = f"uji_p25_b2d_rep{rep}_{int(time.time())}"
        print(f"\n=== Memulai Ulangan {rep}/3 (Sesi: {session_id}) ===")
        t_start_rep = time.time()

        for idx, user_msg in enumerate(PESAN_21, 1):
            t0 = time.time()
            res = process_chat_message(session_id, user_msg)
            dur = time.time() - t0
            print(f"  [Rep {rep}] Pesan {idx}/21: '{user_msg}' -> ({dur:.1f}s)")

        # Tandai balasan terakhir tidak terkirim
        marked = tandai_pesan_terakhir_tidak_terkirim(session_id)
        print(f"  [Rep {rep}] Tandai balasan terakhir tidak terkirim: {marked}")

        # Kirim 'Kok gak jawab?'
        t0 = time.time()
        res_tanya = process_chat_message(session_id, "Kok gak jawab?")
        dur_tanya = time.time() - t0
        balasan_verbatim = res_tanya.get("reply", "")
        print(f"  [Rep {rep}] 'Kok gak jawab?' ({dur_tanya:.1f}s):")
        print(f"  --> {balasan_verbatim}")

        sess = mgr.get_session(session_id)
        hasil_ulangan.append({
            "ulangan": rep,
            "session_id": session_id,
            "durasi_total_s": round(time.time() - t_start_rep, 2),
            "latensi_jawab_s": round(dur_tanya, 2),
            "balasan_verbatim": balasan_verbatim,
            "tools_called": res_tanya.get("tools_called", []),
        })

    with open("scratch/uji_p25_butir2d_result.json", "w", encoding="utf-8") as f:
        json.dump(hasil_ulangan, f, ensure_ascii=False, indent=2)

    print("\n=== Uji Selesai! Hasil disimpan di scratch/uji_p25_butir2d_result.json ===")

if __name__ == "__main__":
    jalankan_uji()
