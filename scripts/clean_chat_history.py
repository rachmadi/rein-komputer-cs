# -*- coding: utf-8 -*-
"""
Script Pembersih Riwayat Chat Historis
Membuat logs/chat_history.cleaned.jsonl dari logs/chat_history.jsonl tanpa mengubah berkas asli.
1. Menghapus baris residu pengujian (ho_01_coding s.d. ho_09_cheaper jika ada).
2. Menghapus sesi tanpa balasan bot / kosong.
3. Mengisi nilai default kolom format baru (penguji, engine_mode, type).
4. Menjamin session_id mentah telah di-anonimkan dengan HMAC.
"""
import json
import os
import sys

# Tambahkan direktori root ke path agar dapat mengimpor core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.chat_logger import anonymize_id

INPUT_PATH = os.path.join("logs", "chat_history.jsonl")
OUTPUT_PATH = os.path.join("logs", "chat_history.cleaned.jsonl")


def clean_history():
    if not os.path.exists(INPUT_PATH):
        print(f"File tidak ditemukan: {INPUT_PATH}")
        return

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    total_before = len(lines)
    discarded_test_residue = 0
    discarded_empty_reply = 0
    cleaned_records = []

    for idx, line in enumerate(lines, 1):
        try:
            record = json.loads(line)
        except Exception as e:
            print(f"Error parsing baris {idx}: {e}")
            continue

        raw_session = str(record.get("session_id", ""))
        bot_reply = str(record.get("bot_reply", "") or "").strip()

        # 1. Cek residu tes held-out
        if raw_session.startswith("ho_") or "ho_" in raw_session:
            discarded_test_residue += 1
            continue

        # 2. Cek balasan kosong / gagal tanpa pesan error eksplisit
        if not bot_reply:
            discarded_empty_reply += 1
            continue

        # 3. Anonimisasi ID sesi mentah dengan HMAC
        anon_id = anonymize_id(raw_session, penguji="manusia")
        record["session_id"] = anon_id
        record["anon_session_id"] = anon_id

        # 4. Standarisasi kolom format baru
        if "type" not in record:
            record["type"] = "chat_turn"
        if "penguji" not in record or not record["penguji"]:
            record["penguji"] = "manusia"
        if "engine_mode" not in record or not record["engine_mode"]:
            # Riwayat sebelum migrasi v2 berasal dari era chatgpt_hybrid
            record["engine_mode"] = "chatgpt_hybrid"

        cleaned_records.append(record)

    total_after = len(cleaned_records)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for rec in cleaned_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print("=" * 60)
    print("HASIL PEMBERSIHAN RIWAYAT CHAT HISTORIS")
    print("=" * 60)
    print(f"Total baris sebelum                   : {total_before}")
    print(f"Dibuang - Residu uji (ho_*)           : {discarded_test_residue}")
    print(f"Dibuang - Balasan bot kosong / gagal  : {discarded_empty_reply}")
    print(f"Total baris sesudah (dibersihkan)     : {total_after}")
    print(f"Berkas luaran tersimpan di            : {OUTPUT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    clean_history()
