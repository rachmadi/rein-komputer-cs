# -*- coding: utf-8 -*-
"""
services/llm_parser.py
LLM-based Natural Language Understanding (NLU) Parser untuk Bobby Computer.

Sesuai Antigravity v2:
- Model: gemma4:e4b
- Structured Output: JSON schema Pydantic dengan ENUM TERTUTUP KETAT
- Temperature: 0, num_predict: 120, think: False
- Susunan Prompt: Instruksi dan contoh statis di depan, state dan pesan di akhir
- Few-shots: HANYA dari set pengembangan (dev)
- Validasi deterministik: skema, enum tertutup, rentang, dan resolusi rujukan produk.
"""
from __future__ import annotations

import os
import json
import time
import urllib.request
import logging
from typing import Any, Dict, List, Tuple

from services.schema_actions import (
    ParserOutput, ActionEnum, ActionArguments, StateUpdate,
    SlotEnum, JenisEnum, TokoTopikEnum, AtributSpesifikasiEnum
)
from services.validator import validate_parser_output, get_catalog_brands, get_catalog_categories

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
PARSER_MODEL = os.getenv("PARSER_MODEL", "gemma4:e4b")

SYSTEM_PARSER_PROMPT = """Kamu adalah NLU Parser untuk customer care Bobby Computer di Telegram.
Tugas: Memahami pesan pelanggan secara akurat dan mengembalikan JSON terstruktur sesuai skema tertutup.

DEFINISI 12 AKSI:
1. sapa: Menyapa atau membuka percakapan tanpa menyebut produk, kebutuhan, atau pertanyaan spesifik.
2. cari_produk: Mencari produk berdasarkan kriteria teknis eksplisit seperti kategori, merek, spesifikasi perangkat keras, atau batas harga tanpa mengaitkannya dengan beban aktivitas komputasi tertentu.
3. minta_rekomendasi: Meminta saran produk berdasarkan aktivitas konkret, beban kerja komputasi, atau skenario penggunaan nyata yang membutuhkan penalaran kelayakan perangkat.
4. jawab_pertanyaan_bot: Menjawab pertanyaan atau slot yang sebelumnya diajukan oleh bot, seperti menyebutkan persona, kategori, merek, atau budget secara tunggal tanpa aktivitas penggunaan.
5. evaluasi_kecocokan: Menanyakan kelayakan atau kecukupan spesifikasi produk yang sedang tampil di layar untuk menjalankan kebutuhan atau beban kerja tertentu.
6. tanya_spesifikasi: Menanyakan fakta spesifikasi teknis tunggal dari produk yang sedang tampil di layar tanpa menilai kecukupan untuk suatu aktivitas.
7. bandingkan: Membandingkan perbedaan spesifikasi teknis atau keunggulan antara dua atau lebih produk yang sedang tampil atau disebutkan.
8. lanjutan_hasil: Meminta alternatif lain, variasi produk, atau penyesuaian kriteria terhadap hasil pencarian yang sudah ditampilkan sebelumnya.
9. tanya_info_toko: Menanyakan informasi operasional toko seperti garansi, kebijakan servis, metode pembayaran, pengiriman, alamat fisik, atau jam buka toko.
10. perbaiki_percakapan: Menyampaikan koreksi, teguran, atau keluhan karena bot salah memahami maksud pelanggan atau keluar dari konteks percakapan.
11. basa_basi: Menyampaikan ucapan penutup, terima kasih, pamit, atau obrolan santai yang tidak memerlukan tindakan katalog.
12. tidak_jelas: Pesan yang tidak memiliki makna yang dapat diidentifikasi atau informasinya saling bertentangan sehingga membutuhkan klarifikasi lebih lanjut.

KEBIJAKAN BATAS AKSI:
- 'minta_rekomendasi' HANYA jika ada aktivitas komputasi konkret atau skenario kerja nyata.
- Jika pelanggan HANYA menyebut persona (misal dokter, guru, kakek) atau HANYA menyebut kategori/merek/budget tanpa aktivitas konkret, gunakan 'jawab_pertanyaan_bot' (slot: persona/kategori/merek/budget).
- Untuk referensi produk pada 'evaluasi_kecocokan', 'tanya_spesifikasi', dan 'bandingkan', keluarkan 'rujukan_produk' berupa nomor urut ([1], [2], [1, 2]) atau nama produk. JANGAN mengeluarkan kode produk internal katalog.
- Untuk kartu grafis diskrit (misal rtx 4060, rtx 4050, gtx 1650), masukkan ke argumen 'gpu', BUKAN 'nama_model'.
- Untuk pengecualian merek, masukkan ke 'merek_kecuali'.
- DILARANG menggunakan nilai jenis/topik/slot di luar enum skema yang ditentukan.
"""

# 8 CONTOH SINTETIS DAN BERAGAM YANG MENGGAMBARKAN BATAS ANTAR AKSI
# (Tidak menggunakan kalimat dari percakapan nyata, tangkapan layar, log, atau held-out)
SYNTHETIC_8_BOUNDARY_FEW_SHOTS = [
    # 1. Batas: Persona Saja (jawab_pertanyaan_bot) vs Aktivitas Konkret
    {
        "role": "user",
        "content": (
            "Konteks Sesi: {\"teks_pesan_terakhir_bot\": \"Untuk siapa perangkat ini akan digunakan?\", \"kebutuhan_diketahui\": null, \"produk_tampil\": [], \"pending_question\": \"persona\"}\n"
            "Pesan Pelanggan: \"Saya dokter spesialis anak di klinik swasta\""
        )
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "jawab_pertanyaan_bot",
            "argumen": {"slot": "persona", "nilai": "dokter anak"},
            "pembaruan_state": {"persona": "dokter anak", "sebutan": "dokter"}
        })
    },
    # 2. Batas: Aktivitas Konkret (minta_rekomendasi) vs Pencarian Spesifikasi
    {
        "role": "user",
        "content": (
            "Konteks Sesi: {\"teks_pesan_terakhir_bot\": null, \"kebutuhan_diketahui\": null, \"produk_tampil\": [], \"pending_question\": null}\n"
            "Pesan Pelanggan: \"Perlu perangkat untuk rekaman multi-track 24 channel dan mixing audio di studio\""
        )
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "minta_rekomendasi",
            "argumen": {"kebutuhan_teks": "rekaman multi-track dan mixing audio", "kategori": "desktop"},
            "pembaruan_state": {"kebutuhan_teks": "rekaman multi-track dan mixing audio", "kategori": "desktop"}
        })
    },
    # 3. Batas: Evaluasi Kecocokan (evaluasi_kecocokan) vs Tanya Spesifikasi
    {
        "role": "user",
        "content": (
            "Konteks Sesi: {\"teks_pesan_terakhir_bot\": \"Berikut unit yang tersedia\", \"kebutuhan_diketahui\": \"rendering 3D Revit\", \"produk_tampil\": [{\"no\": 1, \"nama\": \"Workstation Alpha\", \"harga\": 18500000}], \"pending_question\": null}\n"
            "Pesan Pelanggan: \"Apakah unit pertama ini sanggup memproses render interior yang berat?\""
        )
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "evaluasi_kecocokan",
            "argumen": {"rujukan_produk": [1], "kebutuhan_teks": "rendering 3D Revit"},
            "pembaruan_state": {}
        })
    },
    # 4. Batas: Tanya Spesifikasi (tanya_spesifikasi) vs Evaluasi Kecocokan
    {
        "role": "user",
        "content": (
            "Konteks Sesi: {\"teks_pesan_terakhir_bot\": null, \"kebutuhan_diketahui\": null, \"produk_tampil\": [{\"no\": 1, \"nama\": \"Laptop Creator 16\", \"harga\": 14200000}], \"pending_question\": null}\n"
            "Pesan Pelanggan: \"Slot kartu grafis pada unit tersebut memakai seri apa?\""
        )
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "tanya_spesifikasi",
            "argumen": {"rujukan_produk": [1], "atribut": "gpu"},
            "pembaruan_state": {}
        })
    },
    # 5. Batas: Perbaikan Percakapan (perbaiki_percakapan) vs Pencarian Baru
    {
        "role": "user",
        "content": (
            "Konteks Sesi: {\"teks_pesan_terakhir_bot\": \"Berikut rekomendasi desktop tower untuk Anda\", \"kebutuhan_diketahui\": null, \"produk_tampil\": [{\"no\": 1, \"nama\": \"Tower Pro\", \"harga\": 12000000}], \"pending_question\": null}\n"
            "Pesan Pelanggan: \"Saya minta komputer jinjing portabel, bukan komputer meja\""
        )
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "perbaiki_percakapan",
            "argumen": {"jenis": "koreksi", "rujukan": "komputer jinjing portabel bukan meja"},
            "pembaruan_state": {"kategori": "laptop"}
        })
    },
    # 6. Batas: Pencarian Baru Berparameter (cari_produk) vs Rekomendasi Kebutuhan
    {
        "role": "user",
        "content": (
            "Konteks Sesi: {\"teks_pesan_terakhir_bot\": null, \"kebutuhan_diketahui\": null, \"produk_tampil\": [], \"pending_question\": null}\n"
            "Pesan Pelanggan: \"Carikan laptop dell dengan prosesor intel i7 batas dana 15 juta\""
        )
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "cari_produk",
            "argumen": {"kategori": "laptop", "merek": "dell", "max_harga": 15000000},
            "pembaruan_state": {"kategori": "laptop", "budget": 15000000}
        })
    },
    # 7. Batas: Lanjutan Hasil (lanjutan_hasil) vs Pencarian Baru
    {
        "role": "user",
        "content": (
            "Konteks Sesi: {\"teks_pesan_terakhir_bot\": \"Pilihan tersedia saat ini\", \"kebutuhan_diketahui\": null, \"produk_tampil\": [{\"no\": 1, \"nama\": \"Model Pro A\", \"harga\": 11000000}, {\"no\": 2, \"nama\": \"Model Pro B\", \"harga\": 13500000}], \"pending_question\": null}\n"
            "Pesan Pelanggan: \"Berikan opsi alternatif lain yang harganya lebih terjangkau dari daftar itu\""
        )
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "lanjutan_hasil",
            "argumen": {"jenis": "lebih_murah"},
            "pembaruan_state": {}
        })
    },
    # 8. Batas: Info Toko (tanya_info_toko) vs Pertanyaan Katalog
    {
        "role": "user",
        "content": (
            "Konteks Sesi: {\"teks_pesan_terakhir_bot\": null, \"kebutuhan_diketahui\": null, \"produk_tampil\": [], \"pending_question\": null}\n"
            "Pesan Pelanggan: \"Bagaimana prosedur klaim perbaikan jika perangkat mengalami kerusakan masa pakai?\""
        )
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "tanya_info_toko",
            "argumen": {"topik": "garansi"},
            "pembaruan_state": {}
        })
    }
]

# 14 CONTOH LAMA (Dipertahankan khusus untuk studi ablasi kondisi c)
OLD_14_FEW_SHOTS = [
    {"role": "user", "content": "Pesan: \"halo\"\nState: {\"pending_question\": null, \"produk_tampil\": []}"},
    {"role": "assistant", "content": json.dumps({"aksi": "sapa", "argumen": {}, "pembaruan_state": {}})},
    {"role": "user", "content": "Pesan: \"jual laptop acer?\"\nState: {\"pending_question\": null, \"produk_tampil\": []}"},
    {"role": "assistant", "content": json.dumps({"aksi": "cari_produk", "argumen": {"kategori": "laptop", "merek": "acer"}, "pembaruan_state": {"kategori": "laptop"}})},
    {"role": "user", "content": "Pesan: \"pc dekstop gaming rtx 4060\"\nState: {\"pending_question\": null, \"produk_tampil\": []}"},
    {"role": "assistant", "content": json.dumps({"aksi": "cari_produk", "argumen": {"kategori": "desktop", "gpu": "rtx 4060"}, "pembaruan_state": {"kategori": "desktop"}})},
    {"role": "user", "content": "Pesan: \"Buat mama sih bukan buat aku\"\nState: {\"pending_question\": \"kebutuhan\", \"produk_tampil\": []}"},
    {"role": "assistant", "content": json.dumps({"aksi": "jawab_pertanyaan_bot", "argumen": {"slot": "persona", "nilai": "mama"}, "pembaruan_state": {"persona": "mama", "sebutan": "mama"}})},
    {"role": "user", "content": "Pesan: \"Untuk ibu saya yang sudah sepuh\"\nState: {\"pending_question\": \"kebutuhan\", \"produk_tampil\": []}"},
    {"role": "assistant", "content": json.dumps({"aksi": "jawab_pertanyaan_bot", "argumen": {"slot": "persona", "nilai": "ibu sepuh"}, "pembaruan_state": {"persona": "ibu sepuh", "sebutan": "ibu"}})},
    {"role": "user", "content": "Pesan: \"Paling cuma cari resep dan nonton youtube\"\nState: {\"pending_question\": \"aktivitas\", \"slot_diketahui\": {\"persona\": \"mama\"}, \"produk_tampil\": []}"},
    {"role": "assistant", "content": json.dumps({"aksi": "minta_rekomendasi", "argumen": {"kebutuhan_teks": "cari resep dan nonton YouTube", "persona": "mama"}, "pembaruan_state": {"kebutuhan_teks": "cari resep dan nonton YouTube"}})},
    {"role": "user", "content": "Pesan: \"Emang spek segitu cukup?\"\nState: {\"pending_question\": null, \"produk_tampil\": [{\"no\": 1, \"kode\": \"KB-L01\"}, {\"no\": 2, \"kode\": \"KB-L02\"}, {\"no\": 3, \"kode\": \"KB-L03\"}], \"slot_diketahui\": {\"kebutuhan_teks\": \"cari resep dan nonton YouTube\"}}"},
    {"role": "assistant", "content": json.dumps({"aksi": "evaluasi_kecocokan", "argumen": {"rujukan_produk": [1, 2, 3], "kebutuhan_teks": "cari resep dan nonton YouTube"}, "pembaruan_state": {}})},
    {"role": "user", "content": "Pesan: \"yang kedua bagus nggak?\"\nState: {\"pending_question\": null, \"produk_tampil\": [{\"no\": 1, \"kode\": \"KB-L01\"}, {\"no\": 2, \"kode\": \"KB-L02\"}]}"},
    {"role": "assistant", "content": json.dumps({"aksi": "evaluasi_kecocokan", "argumen": {"rujukan_produk": [2]}, "pembaruan_state": {}})},
    {"role": "user", "content": "Pesan: \"layarnya udah ips?\"\nState: {\"pending_question\": null, \"produk_tampil\": [{\"no\": 1, \"kode\": \"KB-L01\"}]}"},
    {"role": "assistant", "content": json.dumps({"aksi": "tanya_spesifikasi", "argumen": {"rujukan_produk": [1], "atribut": "layar"}, "pembaruan_state": {}})},
    {"role": "user", "content": "Pesan: \"bagusan nomor 1 apa nomor 2?\"\nState: {\"pending_question\": null, \"produk_tampil\": [{\"no\": 1, \"kode\": \"KB-L01\"}, {\"no\": 2, \"kode\": \"KB-L02\"}]}"},
    {"role": "assistant", "content": json.dumps({"aksi": "bandingkan", "argumen": {"rujukan_produk": [1, 2]}, "pembaruan_state": {}})},
    {"role": "user", "content": "Pesan: \"ada opsi merk lain ga selain acer?\"\nState: {\"pending_question\": null, \"produk_tampil\": [{\"no\": 1, \"kode\": \"KB-L01\", \"merek\": \"acer\"}]}"},
    {"role": "assistant", "content": json.dumps({"aksi": "lanjutan_hasil", "argumen": {"jenis": "yang_lain", "merek_kecuali": "acer"}, "pembaruan_state": {}})},
    {"role": "user", "content": "Pesan: \"Aku tanya kok malah dikasih spek lain\"\nState: {\"pending_question\": null, \"produk_tampil\": []}"},
    {"role": "assistant", "content": json.dumps({"aksi": "perbaiki_percakapan", "argumen": {"jenis": "salah_paham", "rujukan": "dikasih spek lain"}, "pembaruan_state": {}})},
    {"role": "user", "content": "Pesan: \"Yang tanya HP 14 siapa?\"\nState: {\"pending_question\": null, \"produk_tampil\": [{\"kode\": \"KB-L05\", \"nama\": \"HP 14\"}]}"},
    {"role": "assistant", "content": json.dumps({"aksi": "perbaiki_percakapan", "argumen": {"jenis": "keluhan", "rujukan": "HP 14"}, "pembaruan_state": {}})},
    {"role": "user", "content": "Pesan: \"tokonya ada di mana ya lokasinya?\"\nState: {\"pending_question\": null, \"produk_tampil\": []}"},
    {"role": "assistant", "content": json.dumps({"aksi": "tanya_info_toko", "argumen": {"topik": "alamat"}, "pembaruan_state": {}})}
]

CURRENT_FEW_SHOTS = SYNTHETIC_8_BOUNDARY_FEW_SHOTS


def build_parser_messages(
    pesan: str,
    state: dict | None = None,
    history: list[dict] | None = None,
    few_shots: list[dict] | None = None
) -> List[Dict[str, str]]:
    """
    Menyusun messages Ollama dengan struktur:
    1. Instruksi Statis (System Prompt + Merek/Kategori DB) di depan.
    2. Contoh Few-Shot Statis (few_shots) di urutan berikutnya.
    3. Input Konteks Parser Sesi dan Pesan Baru Pelanggan di akhir:
       - teks_pesan_terakhir_bot
       - kebutuhan_diketahui
       - produk_tampil
       - pending_question
    Struktur ini memaksimalkan penggunaan KV cache prefix Ollama/llamacpp.
    """
    s = state or {}
    brands = get_catalog_brands()
    cats = get_catalog_categories()

    system_content = (
        f"{SYSTEM_PARSER_PROMPT}\n"
        f"Katalog Merek Tersedia: {', '.join(brands)}\n"
        f"Katalog Kategori Tersedia: {', '.join(cats)}"
    )

    active_few_shots = few_shots if few_shots is not None else CURRENT_FEW_SHOTS

    # Ekstrak teks pesan terakhir bot dari riwayat
    last_bot_msg = None
    if history:
        for h in reversed(history):
            role_h = h.get("role") or h.get("sender")
            if role_h in ("bot", "assistant"):
                last_bot_msg = h.get("content") or h.get("text")
                if last_bot_msg:
                    break

    kebutuhan_diketahui = (
        s.get("kebutuhan_teks")
        or (s.get("slot_diketahui") or {}).get("kebutuhan_teks")
        or s.get("profil_aktif")
    )

    produk_tampil = [
        {
            "no": p.get("no", idx + 1),
            "nama": p.get("nama"),
            "harga": p.get("harga_idr") or p.get("harga")
        }
        for idx, p in enumerate(s.get("produk_tampil", []))
    ]

    context_data = {
        "teks_pesan_terakhir_bot": last_bot_msg,
        "kebutuhan_diketahui": kebutuhan_diketahui,
        "produk_tampil": produk_tampil,
        "pending_question": s.get("pending_question")
    }

    user_dynamic_content = (
        f"Konteks Sesi: {json.dumps(context_data, ensure_ascii=False)}\n"
        f"Pesan Pelanggan: \"{pesan}\""
    )

    messages = [
        {"role": "system", "content": system_content},
        *active_few_shots,
        {"role": "user", "content": user_dynamic_content}
    ]
    return messages


def parse_user_message(
    pesan: str,
    state: dict | None = None,
    history: list[dict] | None = None,
    model: str = PARSER_MODEL,
    ollama_url: str = OLLAMA_BASE_URL,
    timeout: float = 25.0,
    few_shots: list[dict] | None = None
) -> Tuple[ParserOutput, Dict[str, Any]]:
    """
    Mem-parse pesan pelanggan menjadi aksi terstruktur via Ollama (gemma4:e4b).
    Mengembalikan (ParserOutput_valid, metadata_metrik).
    """
    t0 = time.perf_counter()
    schema = ParserOutput.model_json_schema()
    messages = build_parser_messages(pesan, state=state, history=history, few_shots=few_shots)

    req_data = {
        "model": model,
        "messages": messages,
        "format": schema,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0,
            "num_predict": 120
        }
    }

    raw_content = ""
    json_valid = False
    error_msg = None

    try:
        req = urllib.request.Request(
            f"{ollama_url}/api/chat",
            data=json.dumps(req_data).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_content = data.get("message", {}).get("content", "").strip()

        raw_json = json.loads(raw_content)
        json_valid = True
    except Exception as e:
        logger.error(f"Gagal memanggil Ollama parser atau parse JSON: {e}")
        raw_json = {"aksi": "tidak_jelas", "argumen": {"alasan": f"Error: {str(e)}"}}
        error_msg = str(e)

    dt_ms = (time.perf_counter() - t0) * 1000.0

    # Jalankan validator deterministik dengan pengecekan enum tertutup ketat
    validated_output, is_schema_valid = validate_parser_output(raw_json, session_state=state)

    # Nilai di luar enum tertutup dihitung sebagai JSON tidak valid
    final_json_valid = json_valid and is_schema_valid

    metrics = {
        "latency_ms": round(dt_ms, 2),
        "json_valid": final_json_valid,
        "schema_valid": is_schema_valid,
        "raw_content": raw_content,
        "error": error_msg
    }

    return validated_output, metrics
