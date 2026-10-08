# -*- coding: utf-8 -*-
"""
services/llm_parser.py
LLM-based Natural Language Understanding (NLU) Parser untuk Bobby Computer.

Sesuai Antigravity v2:
- Model: gemma4:e4b
- Structured Output: JSON schema Pydantic
- Temperature: 0, num_predict: 120, think: False
- Few-shots: HANYA dari set pengembangan (dev)
- Validasi deterministik: skema, enum, rentang, dan resolusi rujukan produk.
"""
from __future__ import annotations

import os
import json
import time
import urllib.request
import logging
from typing import Any, Dict, List, Tuple

from services.schema_actions import ParserOutput, ActionEnum, ActionArguments, StateUpdate
from services.validator import validate_parser_output, get_catalog_brands, get_catalog_categories

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
PARSER_MODEL = os.getenv("PARSER_MODEL", "gemma4:e4b")

SYSTEM_PARSER_PROMPT = """Kamu adalah NLU Parser untuk asisten Customer Care Bobby Computer di Telegram.
Tugasmu: memahami pesan pelanggan secara akurat dan menerjemahkannya ke dalam JSON terstruktur.

HIMPUNAN AKSI (11 AKSI):
1. sapa: Sapaan pembuka tanpa permintaan spesifik (contoh: 'halo', 'selamat siang', termasuk sapaan singkat 'p').
2. cari_produk: Mencari produk atau spesifikasi eksplisit tanpa menyebut peruntukan orang ('ada asus?', 'pc gaming rtx 4060', 'ram 32gb').
3. minta_rekomendasi: Kebutuhan atau persona sudah jelas untuk rekomendasi ('laptop buat kakek', 'butuh laptop dkv', 'Paling cuma cari resep dan nonton youtube').
4. jawab_pertanyaan_bot: Pelanggan menjawab pending_question bot secara singkat/parsial (slot: kebutuhan/aktivitas/budget/kategori/merek/persona, nilai).
5. evaluasi_kecocokan: Menanyakan kecocokan atau fitur/spesifikasi produk yang sedang tampil ('cukup gak?', 'yang kedua bagus gak?', 'layarnya udah IPS?', 'bisa main valorant?').
6. bandingkan: Membandingkan atau memilih antara beberapa produk yang disebut atau sedang tampil ('bagusan nomor 1 apa nomor 2?').
7. lanjutan_hasil: Menyempitkan/mengubah hasil sebelumnya ('ada yang lebih murah?', 'ada opsi merk lain?').
8. tanya_info_toko: Pertanyaan garansi, servis, pembayaran, pengiriman, jam buka, alamat toko.
9. perbaiki_percakapan: Pelanggan menegur, mengoreksi, atau mengeluhkan salah paham ('kok malah...', 'yang tanya HP 14 siapa?', 'kan udah kubilang...').
10. basa_basi: Obrolan penutup atau di luar topik (jenis: terima_kasih/pamit/lainnya).
11. tidak_jelas: Teks acak atau maksud tidak bisa dipastikan dengan wajar ('asdfghjkl', 'hmm gimana ya').

ATURAN PARSING:
- Jika pelanggan menjawab aktivitas/kebutuhan secara lengkap untuk direkomendasikan ('Paling cuma cari resep dan nonton youtube'), gunakan `minta_rekomendasi`. Jika jawaban hanya nilai singkat/slot ('Buat hiburan', 'maks 7 juta'), gunakan `jawab_pertanyaan_bot`.
- Jika ada produk yang sedang tampil dan pelanggan menanyakan apakah layarnya IPS, RAM bisa upgrade, atau cukup untuk aktivitasnya, gunakan `evaluasi_kecocokan`.
- Jika pelanggan membandingkan dua opsi ('bagusan no 1 apa no 2?'), gunakan `bandingkan`.
- Jika pelanggan menegur, menyindir, atau mengoreksi bot karena salah paham, gunakan `perbaiki_percakapan`.
- Salin sebutan persona (ibu, bapak, mama, dsb.) persis sesuai kata pelanggan ke `pembaruan_state.sebutan`.
"""

DEV_FEW_SHOTS = [
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
    {
        "role": "user",
        "content": "Pesan: \"p\"\nState: {\"pending_question\": null, \"produk_tampil\": []}"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "sapa",
            "argumen": {},
            "pembaruan_state": {}
        })
    },
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
    {
        "role": "user",
        "content": "Pesan: \"Emang spek segitu cukup?\"\nState: {\"pending_question\": null, \"produk_tampil\": [{\"no\": 1, \"kode\": \"KB-L01\"}, {\"no\": 2, \"kode\": \"KB-L02\"}, {\"no\": 3, \"kode\": \"KB-L03\"}], \"slot_diketahui\": {\"kebutuhan_teks\": \"cari resep dan nonton YouTube\"}}"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "evaluasi_kecocokan",
            "argumen": {"produk": ["KB-L01", "KB-L02", "KB-L03"], "kebutuhan_teks": "cari resep dan nonton YouTube"},
            "pembaruan_state": {}
        })
    },
    {
        "role": "user",
        "content": "Pesan: \"bagusan nomor 1 apa nomor 2?\"\nState: {\"pending_question\": null, \"produk_tampil\": [{\"no\": 1, \"kode\": \"KB-L01\"}, {\"no\": 2, \"kode\": \"KB-L02\"}]}"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "bandingkan",
            "argumen": {"produk": ["1", "2"]},
            "pembaruan_state": {}
        })
    },
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
    {
        "role": "user",
        "content": "Pesan: \"Buat hiburan\"\nState: {\"pending_question\": \"aktivitas\", \"produk_tampil\": []}"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "jawab_pertanyaan_bot",
            "argumen": {"slot": "aktivitas", "nilai": "hiburan (nonton, browsing)"},
            "pembaruan_state": {"kebutuhan_teks": "hiburan"}
        })
    },
    {
        "role": "user",
        "content": "Pesan: \"Mana?\"\nState: {\"pending_question\": null, \"slot_diketahui\": {\"kebutuhan_teks\": \"hiburan\"}, \"produk_tampil\": []}"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "minta_rekomendasi",
            "argumen": {"kebutuhan_teks": "hiburan"},
            "pembaruan_state": {}
        })
    },
    {
        "role": "user",
        "content": "Pesan: \"ada yang lebih murah?\"\nState: {\"pending_question\": null, \"produk_tampil\": [{\"kode\": \"KB-L01\", \"harga\": 8000000}]}"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "lanjutan_hasil",
            "argumen": {"jenis": "lebih_murah"},
            "pembaruan_state": {}
        })
    },
    {
        "role": "user",
        "content": "Pesan: \"garansinya berapa lama?\"\nState: {\"pending_question\": null, \"produk_tampil\": []}"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "tanya_info_toko",
            "argumen": {"topik": "garansi"},
            "pembaruan_state": {}
        })
    },
    {
        "role": "user",
        "content": "Pesan: \"makasih ya\"\nState: {\"pending_question\": null, \"produk_tampil\": []}"
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "basa_basi",
            "argumen": {"jenis": "terima_kasih"},
            "pembaruan_state": {}
        })
    }
]


def build_parser_context(
    pesan: str,
    state: dict | None = None,
    history: list[dict] | None = None
) -> str:
    """Membangun string prompt konteks untuk parser LLM."""
    s = state or {}
    brands = get_catalog_brands()
    cats = get_catalog_categories()

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
        "profil_aktif": s.get("profil_aktif"),
        "merek_tersedia": brands,
        "kategori_tersedia": cats
    }

    # Format 6 riwayat terakhir
    recent_history = []
    if history:
        for h in history[-6:]:
            role = "Pelanggan" if h.get("role") == "user" else "Bot"
            recent_history.append(f"{role}: {h.get('content', '')}")
    history_str = "\n".join(recent_history) if recent_history else "Tidak ada"

    return (
        f"Katalog Merek: {', '.join(brands)}\n"
        f"Katalog Kategori: {', '.join(cats)}\n"
        f"Riwayat Pesan Terakhir:\n{history_str}\n"
        f"State Percakapan: {json.dumps(state_summary, ensure_ascii=False)}\n"
        f"Pesan Baru Pelanggan: \"{pesan}\""
    )


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
    user_context = build_parser_context(pesan, state=state, history=history)

    messages = [
        {"role": "system", "content": SYSTEM_PARSER_PROMPT},
        *DEV_FEW_SHOTS,
        {"role": "user", "content": user_context}
    ]

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

    # Jalankan validator deterministik
    validated_output = validate_parser_output(raw_json, session_state=state)

    metrics = {
        "latency_ms": round(dt_ms, 2),
        "json_valid": json_valid,
        "raw_content": raw_content,
        "error": error_msg
    }

    return validated_output, metrics
