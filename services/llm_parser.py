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

DAFTAR 12 AKSI & ATURAN ENUM TERTUTUP:
1. sapa: Sapaan pembuka tanpa permintaan spesifik (contoh: 'halo', 'selamat siang', termasuk 'p').
2. cari_produk: Mencari produk/spesifikasi eksplisit tanpa menyebut peruntukan orang ('ada asus?', 'pc gaming rtx 4060', 'ram 32gb').
   - Argumen: kategori, merek, merek_kecuali, nama_model, gpu (mis. 'rtx 4060'), min_harga, max_harga, ram_gb_min, storage_gb_min, ukuran_layar.
3. minta_rekomendasi: Kebutuhan atau aktivitas konkret sudah jelas untuk rekomendasi ('cari resep dan nonton youtube', 'buat render blender', 'laptop buat kakek').
   - Argumen: kebutuhan_teks, persona, kategori, budget_min, budget_max.
4. jawab_pertanyaan_bot: Pelanggan menjawab pending_question bot secara singkat/parsial (slot tertutup: 'kebutuhan', 'aktivitas', 'budget', 'kategori', 'merek', 'persona').
5. evaluasi_kecocokan: Menanyakan apakah produk yang tampil cukup/cocok untuk aktivitas ('cukup gak spek segitu?', 'kuat main valorant gak?', 'yang kedua bagus nggak?').
   - Argumen: rujukan_produk (nomor urut seperti [1], [2], atau nama produk, BUKAN kode internal), kebutuhan_teks.
6. tanya_spesifikasi: Menanyakan fakta spesifikasi produk yang tampil ('layarnya udah IPS?', 'ssd nya berapa GB?', 'prosesornya apa?', 'keyboardnya ada lampu?').
   - Argumen: rujukan_produk (nomor urut seperti [1] atau nama produk), atribut (enum tertutup: 'ram', 'storage', 'cpu', 'gpu', 'layar', 'baterai', 'port', 'bobot', 'keyboard', 'kamera', 'lainnya').
7. bandingkan: Membandingkan atau memilih antara beberapa produk yang disebut/tampil ('bagusan nomor 1 apa nomor 2?').
   - Argumen: rujukan_produk (daftar nomor urut seperti [1, 2] atau nama produk).
8. lanjutan_hasil: Menyempitkan/mengubah hasil sebelumnya ('ada yang lebih murah?', 'ada opsi merk lain selain acer?').
   - Argumen: jenis (enum tertutup: 'lebih_murah', 'lebih_mahal', 'yang_lain', 'filter_tambahan'), merek_kecuali.
9. tanya_info_toko: Tanya info toko yang tidak ada di katalog.
   - Argumen: topik (enum tertutup: 'garansi', 'servis', 'pembayaran', 'pengiriman', 'jam_buka', 'alamat', 'lainnya').
10. perbaiki_percakapan: Pelanggan menegur, mengoreksi, atau mengeluh karena bot salah paham ('kok malah...', 'yang tanya HP 14 siapa?', 'kan udah kubilang...', 'bukan itu maksudku').
    - Argumen: jenis (enum tertutup: 'salah_paham', 'keluhan', 'koreksi'), rujukan.
11. basa_basi: Obrolan penutup atau di luar topik.
    - Argumen: jenis (enum tertutup: 'terima_kasih', 'pamit', 'lainnya').
12. tidak_jelas: Teks acak atau maksud tidak bisa dipastikan ('asdfghjkl', 'hmm gimana ya').
    - Argumen: alasan.

KEBIJAKAN PENTING:
- 'minta_rekomendasi' HANYA jika ada aktivitas konkret ('cari resep dan nonton youtube', 'ngetik word office', 'belajar coding python') ATAU jika pelanggan secara eksplisit meminta rekomendasi ('laptop layar 15.6 inch buat kakek').
- Jika pelanggan HANYA menyebut persona ('buat mama', 'untuk ibu saya yang sudah sepuh') atau HANYA menyebut kategori/merek/budget tanpa aktivitas konkret, gunakan 'jawab_pertanyaan_bot' (slot: persona/kategori/merek/budget).
- Untuk referensi produk yang tampil pada 'evaluasi_kecocokan', 'tanya_spesifikasi', dan 'bandingkan', keluarkan 'rujukan_produk' berupa nomor urut ([1], [2], [1, 2]) atau nama produk. JANGAN mengeluarkan kode produk katalog internal.
- Untuk kartu grafis seperti 'rtx 4060', 'rtx 4050', 'gtx 1650', masukkan ke argumen 'gpu', BUKAN 'nama_model'.
- Untuk pengecualian merek ('selain acer'), masukkan ke 'merek_kecuali'.
- DILARANG menggunakan nilai jenis/topik/slot di luar enum yang telah ditentukan.
"""

DEV_FEW_SHOTS = [
    # 1. sapa
    {
        "role": "user",
        "content": "Pesan: \"halo\"\nState: {\"pending_question\": null, \"produk_tampil\": []}"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "sapa",
            "argumen": {},
            "pembaruan_state": {}
        })
    },
    # 2. cari_produk (merek & kategori)
    {
        "role": "user",
        "content": "Pesan: \"jual laptop acer?\"\nState: {\"pending_question\": null, \"produk_tampil\": []}"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "cari_produk",
            "argumen": {"kategori": "laptop", "merek": "acer"},
            "pembaruan_state": {"kategori": "laptop"}
        })
    },
    # 3. cari_produk (spesifikasi gpu)
    {
        "role": "user",
        "content": "Pesan: \"pc dekstop gaming rtx 4060\"\nState: {\"pending_question\": null, \"produk_tampil\": []}"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "cari_produk",
            "argumen": {"kategori": "desktop", "gpu": "rtx 4060"},
            "pembaruan_state": {"kategori": "desktop"}
        })
    },
    # 4. jawab_pertanyaan_bot (persona saja -> jawab_pertanyaan_bot)
    {
        "role": "user",
        "content": "Pesan: \"Buat mama sih bukan buat aku\"\nState: {\"pending_question\": \"kebutuhan\", \"produk_tampil\": []}"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "jawab_pertanyaan_bot",
            "argumen": {"slot": "persona", "nilai": "mama"},
            "pembaruan_state": {"persona": "mama", "sebutan": "mama"}
        })
    },
    # 5. jawab_pertanyaan_bot (persona lanjut)
    {
        "role": "user",
        "content": "Pesan: \"Untuk ibu saya yang sudah sepuh\"\nState: {\"pending_question\": \"kebutuhan\", \"produk_tampil\": []}"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "jawab_pertanyaan_bot",
            "argumen": {"slot": "persona", "nilai": "ibu sepuh"},
            "pembaruan_state": {"persona": "ibu sepuh", "sebutan": "ibu"}
        })
    },
    # 6. minta_rekomendasi (aktivitas konkret)
    {
        "role": "user",
        "content": "Pesan: \"Paling cuma cari resep dan nonton youtube\"\nState: {\"pending_question\": \"aktivitas\", \"slot_diketahui\": {\"persona\": \"mama\"}, \"produk_tampil\": []}"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "minta_rekomendasi",
            "argumen": {"kebutuhan_teks": "cari resep dan nonton YouTube", "persona": "mama"},
            "pembaruan_state": {"kebutuhan_teks": "cari resep dan nonton YouTube"}
        })
    },
    # 7. evaluasi_kecocokan (rujukan semua produk tampil)
    {
        "role": "user",
        "content": "Pesan: \"Emang spek segitu cukup?\"\nState: {\"pending_question\": null, \"produk_tampil\": [{\"no\": 1, \"kode\": \"KB-L01\"}, {\"no\": 2, \"kode\": \"KB-L02\"}, {\"no\": 3, \"kode\": \"KB-L03\"}], \"slot_diketahui\": {\"kebutuhan_teks\": \"cari resep dan nonton YouTube\"}}"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "evaluasi_kecocokan",
            "argumen": {"rujukan_produk": [1, 2, 3], "kebutuhan_teks": "cari resep dan nonton YouTube"},
            "pembaruan_state": {}
        })
    },
    # 8. evaluasi_kecocokan (rujukan nomor urut 2)
    {
        "role": "user",
        "content": "Pesan: \"yang kedua bagus nggak?\"\nState: {\"pending_question\": null, \"produk_tampil\": [{\"no\": 1, \"kode\": \"KB-L01\"}, {\"no\": 2, \"kode\": \"KB-L02\"}]}"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "evaluasi_kecocokan",
            "argumen": {"rujukan_produk": [2]},
            "pembaruan_state": {}
        })
    },
    # 9. tanya_spesifikasi (rujukan nomor urut 1 & atribut layar)
    {
        "role": "user",
        "content": "Pesan: \"layarnya udah ips?\"\nState: {\"pending_question\": null, \"produk_tampil\": [{\"no\": 1, \"kode\": \"KB-L01\"}]}"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "tanya_spesifikasi",
            "argumen": {"rujukan_produk": [1], "atribut": "layar"},
            "pembaruan_state": {}
        })
    },
    # 10. bandingkan (rujukan nomor urut 1 dan 2)
    {
        "role": "user",
        "content": "Pesan: \"bagusan nomor 1 apa nomor 2?\"\nState: {\"pending_question\": null, \"produk_tampil\": [{\"no\": 1, \"kode\": \"KB-L01\"}, {\"no\": 2, \"kode\": \"KB-L02\"}]}"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "bandingkan",
            "argumen": {"rujukan_produk": [1, 2]},
            "pembaruan_state": {}
        })
    },
    # 11. lanjutan_hasil (filter pengecualian merek)
    {
        "role": "user",
        "content": "Pesan: \"ada opsi merk lain ga selain acer?\"\nState: {\"pending_question\": null, \"produk_tampil\": [{\"no\": 1, \"kode\": \"KB-L01\", \"merek\": \"acer\"}]}"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "lanjutan_hasil",
            "argumen": {"jenis": "yang_lain", "merek_kecuali": "acer"},
            "pembaruan_state": {}
        })
    },
    # 12. perbaiki_percakapan (salah_paham)
    {
        "role": "user",
        "content": "Pesan: \"Aku tanya kok malah dikasih spek lain\"\nState: {\"pending_question\": null, \"produk_tampil\": []}"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "perbaiki_percakapan",
            "argumen": {"jenis": "salah_paham", "rujukan": "dikasih spek lain"},
            "pembaruan_state": {}
        })
    },
    # 13. perbaiki_percakapan (keluhan)
    {
        "role": "user",
        "content": "Pesan: \"Yang tanya HP 14 siapa?\"\nState: {\"pending_question\": null, \"produk_tampil\": [{\"kode\": \"KB-L05\", \"nama\": \"HP 14\"}]}"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "perbaiki_percakapan",
            "argumen": {"jenis": "keluhan", "rujukan": "HP 14"},
            "pembaruan_state": {}
        })
    },
    # 14. tanya_info_toko (alamat)
    {
        "role": "user",
        "content": "Pesan: \"tokonya ada di mana ya lokasinya?\"\nState: {\"pending_question\": null, \"produk_tampil\": []}"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "tanya_info_toko",
            "argumen": {"topik": "alamat"},
            "pembaruan_state": {}
        })
    }
]


def build_parser_messages(
    pesan: str,
    state: dict | None = None,
    history: list[dict] | None = None
) -> List[Dict[str, str]]:
    """
    Menyusun messages Ollama dengan struktur:
    1. Instruksi Statis (System Prompt + Merek/Kategori DB) di depan.
    2. Contoh Few-Shot Statis (DEV_FEW_SHOTS) di urutan berikutnya.
    3. State Percakapan, Riwayat, dan Pesan Baru Pelanggan di akhir.
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

    state_summary = {
        "pending_question": s.get("pending_question"),
        "slot_diketahui": s.get("slot_diketahui", {}),
        "produk_tampil": [
            {
                "no": p.get("no", idx + 1),
                "kode": p.get("kode"),
                "nama": p.get("nama"),
                "harga": p.get("harga_idr") or p.get("harga")
            }
            for idx, p in enumerate(s.get("produk_tampil", []))
        ],
        "profil_aktif": s.get("profil_aktif")
    }

    recent_history = []
    if history:
        for h in history[-6:]:
            role = "Pelanggan" if h.get("role") == "user" else "Bot"
            recent_history.append(f"{role}: {h.get('content', '')}")
    history_str = "\n".join(recent_history) if recent_history else "Tidak ada"

    user_dynamic_content = (
        f"Riwayat Pesan Terakhir:\n{history_str}\n\n"
        f"State Percakapan: {json.dumps(state_summary, ensure_ascii=False)}\n\n"
        f"Pesan Baru Pelanggan: \"{pesan}\""
    )

    messages = [
        {"role": "system", "content": system_content},
        *DEV_FEW_SHOTS,
        {"role": "user", "content": user_dynamic_content}
    ]
    return messages


def parse_user_message(
    pesan: str,
    state: dict | None = None,
    history: list[dict] | None = None,
    model: str = PARSER_MODEL,
    ollama_url: str = OLLAMA_BASE_URL,
    timeout: float = 12.0
) -> Tuple[ParserOutput, Dict[str, Any]]:
    """
    Mem-parse pesan pelanggan menjadi aksi terstruktur via Ollama (gemma4:e4b).
    Mengembalikan (ParserOutput_valid, metadata_metrik).
    """
    t0 = time.perf_counter()
    schema = ParserOutput.model_json_schema()
    messages = build_parser_messages(pesan, state=state, history=history)

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
