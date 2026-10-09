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
    SlotEnum, JenisEnum, TokoTopikEnum, AtributSpesifikasiEnum,
    AlasanTidakJelasEnum, get_parser_json_schema
)
from services.validator import (
    validate_parser_output, check_state_consistency, get_allowed_actions_for_state,
    get_catalog_brands, get_catalog_categories
)

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
PARSER_MODEL = os.getenv("PARSER_MODEL", "gemma4:e4b")

SYSTEM_PARSER_PROMPT = """Kamu adalah NLU Parser untuk customer care ReIn Komputer di Telegram.
Tugas: Memahami pesan pelanggan secara akurat dan mengembalikan JSON terstruktur sesuai skema tertutup.

DEFINISI 12 AKSI:
1. sapa: Menyapa atau membuka percakapan tanpa menyebut produk, kebutuhan, atau pertanyaan spesifik.
2. cari_produk: Mencari produk berdasarkan kriteria teknis eksplisit, menanyakan ketersediaan merek atau lini produk tertentu, atau memfilter spesifikasi perangkat keras dan batas harga, termasuk pengecualian merek ('merek_kecuali'), tanpa mengaitkannya dengan beban aktivitas komputasi tertentu.
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
- Jika pelanggan HANYA menyebut persona (misal dokter, guru, kerabat) atau HANYA menyebut kategori/merek/budget tanpa aktivitas konkret, gunakan 'jawab_pertanyaan_bot' (slot: persona/kategori/merek/budget).
- 'jawab_pertanyaan_bot' HANYA sah jika bot sebelumnya mengajukan pertanyaan ('pending_question' ada di konteks sesi).
- 'lanjutan_hasil' HANYA sah jika ada produk yang sedang tampil di layar ('produk_tampil' tidak kosong).
- Untuk referensi produk pada 'evaluasi_kecocokan', 'tanya_spesifikasi', dan 'bandingkan', keluarkan 'rujukan_produk' berupa nomor urut ([1], [2], [1, 2]) atau nama produk dari daftar yang sedang tampil. JANGAN mengeluarkan kode produk internal katalog.
- Untuk kartu grafis diskrit (misal rtx 4060, rtx 4050, gtx 1650), masukkan ke argumen 'gpu', BUKAN 'nama_model'.
- 'persona' adalah pihak pemakai perangkat (seperti kerabat, profesi, atau rekan kerja), BUKAN lawan bicara. Jangan mengisi 'sebutan' dengan persona tersebut. Lawan bicara tetap disapa 'Kak' kecuali pelanggan menyebut sebutan untuk dirinya sendiri.
- Parser boleh mengekstrak beberapa slot sekaligus dari satu kalimat di 'argumen' dan 'pembaruan_state' (misal: kategori dan persona dapat diisi bersamaan).
- Untuk pengecualian merek pada 'cari_produk' atau 'lanjutan_hasil', masukkan ke 'merek_kecuali'.
- Format 'kebutuhan_teks' harus ringkas berupa kata kunci aktivitas atau software utama (misal: 'edit video 4k', 'desain 3d revit', 'coding python', 'kasir toko kelontong'), BUKAN kalimat panjang bertele-tele.
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
        s.get("kebutuhan_diketahui")
        or s.get("kebutuhan_teks")
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


def _call_ollama_chat(
    messages: list[dict],
    schema: dict,
    model: str,
    ollama_url: str,
    timeout: float
) -> Tuple[dict, bool, str, str | None]:
    req_data = {
        "model": model,
        "messages": messages,
        "format": schema,
        "stream": False,
        "think": False,
        "keep_alive": "30m",
        "options": {
            "temperature": 0,
            "num_predict": 120,
            "num_ctx": 4096
        }
    }
    raw_content = ""
    json_valid = False
    error_msg = None
    prompt_eval_count = 0
    eval_count = 0
    load_duration = 0
    prompt_eval_duration = 0
    eval_duration = 0
    try:
        req = urllib.request.Request(
            f"{ollama_url}/api/chat",
            data=json.dumps(req_data).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_content = data.get("message", {}).get("content", "").strip()
            prompt_eval_count = data.get("prompt_eval_count", 0)
            eval_count = data.get("eval_count", 0)
            load_duration = data.get("load_duration", 0)
            prompt_eval_duration = data.get("prompt_eval_duration", 0)
            eval_duration = data.get("eval_duration", 0)

        raw_json = json.loads(raw_content)
        json_valid = True
    except Exception as e:
        logger.error(f"Gagal memanggil Ollama parser atau parse JSON: {e}")
        raw_json = {"aksi": "tidak_jelas", "argumen": {"alasan": "sistem_error"}}
        error_msg = str(e)

    return (
        raw_json,
        json_valid,
        raw_content,
        error_msg,
        prompt_eval_count,
        eval_count,
        load_duration,
        prompt_eval_duration,
        eval_duration
    )


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
    Jika skema tidak valid (B11) atau tidak konsisten dengan state, meminta parse ulang 1x.
    """
    t0 = time.perf_counter()
    schema = get_parser_json_schema()
    messages = build_parser_messages(pesan, state=state, history=history, few_shots=few_shots)

    res_call = _call_ollama_chat(
        messages, schema, model, ollama_url, timeout
    )
    raw_json = res_call[0]
    json_valid = res_call[1]
    raw_content = res_call[2]
    error_msg = res_call[3]
    p_eval_cnt = res_call[4] if len(res_call) > 4 else 0
    eval_cnt = res_call[5] if len(res_call) > 5 else 0
    load_dur = res_call[6] if len(res_call) > 6 else 0
    p_eval_dur = res_call[7] if len(res_call) > 7 else 0
    eval_dur = res_call[8] if len(res_call) > 8 else 0

    validated_output, is_schema_valid = validate_parser_output(raw_json, session_state=state)
    is_consistent, reason = check_state_consistency(validated_output, session_state=state)
    retried = False

    # B11: Jika skema parser tidak valid / JSON rusak, coba parse ulang 1 KALI dengan pesan kesalahan skema spesifik
    if not is_schema_valid:
        retried = True
        logger.warning(f"Skema JSON parser tidak valid ({error_msg}). Mencoba parse ulang 1x...")
        correction_messages = list(messages) + [{
            "role": "user",
            "content": f"Koreksi kesalahan format sebelumnya: {error_msg}. Pastikan mengembalikan format JSON valid persis sesuai skema tertutup."
        }]
        res_call_sc = _call_ollama_chat(correction_messages, schema, model, ollama_url, timeout)
        validated_output_sc, is_schema_valid_sc = validate_parser_output(res_call_sc[0], session_state=state)
        p_eval_cnt += res_call_sc[4] if len(res_call_sc) > 4 else 0
        eval_cnt += res_call_sc[5] if len(res_call_sc) > 5 else 0
        load_dur += res_call_sc[6] if len(res_call_sc) > 6 else 0
        p_eval_dur += res_call_sc[7] if len(res_call_sc) > 7 else 0
        eval_dur += res_call_sc[8] if len(res_call_sc) > 8 else 0

        if is_schema_valid_sc:
            validated_output = validated_output_sc
            is_schema_valid = True
            json_valid = res_call_sc[1]
            raw_content = res_call_sc[2]
            error_msg = res_call_sc[3]
            is_consistent, reason = check_state_consistency(validated_output, session_state=state)
        else:
            validated_output = ParserOutput(
                aksi=ActionEnum.TIDAK_JELAS,
                argumen=ActionArguments(alasan=AlasanTidakJelasEnum.SISTEM_ERROR),
                pembaruan_state=StateUpdate()
            )

    # Jika aksi tak sah menurut state: minta parse ulang sekali dengan enum aksi dibatasi sesuai state
    if is_schema_valid and not is_consistent and not retried:
        retried = True
        logger.warning(
            f"Aksi '{validated_output.aksi.value}' tidak konsisten dengan state: {reason}. "
            "Melakukan parse ulang 1x dengan enum aksi dibatasi..."
        )
        allowed_actions = get_allowed_actions_for_state(state)
        restricted_schema = get_parser_json_schema(allowed_actions=allowed_actions)

        res_call_2 = _call_ollama_chat(
            messages, restricted_schema, model, ollama_url, timeout
        )
        raw_json_2 = res_call_2[0]
        json_valid_2 = res_call_2[1]
        raw_content_2 = res_call_2[2]
        error_msg_2 = res_call_2[3]
        p_eval_cnt += res_call_2[4] if len(res_call_2) > 4 else 0
        eval_cnt += res_call_2[5] if len(res_call_2) > 5 else 0
        load_dur += res_call_2[6] if len(res_call_2) > 6 else 0
        p_eval_dur += res_call_2[7] if len(res_call_2) > 7 else 0
        eval_dur += res_call_2[8] if len(res_call_2) > 8 else 0

        validated_output_2, is_schema_valid_2 = validate_parser_output(raw_json_2, session_state=state)
        is_consistent_2, reason_2 = check_state_consistency(validated_output_2, session_state=state)

        if is_schema_valid_2 and is_consistent_2:
            validated_output = validated_output_2
            is_schema_valid = is_schema_valid_2
            json_valid = json_valid_2
            raw_content = raw_content_2
            error_msg = error_msg_2
        else:
            # Jika tetap gagal: tidak_jelas dengan alasan enum tertutup B12
            logger.warning(f"Parse ulang tetap tidak konsisten/tidak valid: {reason_2}. Menjadi tidak_jelas.")
            alasan_final = (
                AlasanTidakJelasEnum.RUJUKAN_TIDAK_ADA
                if ("rujukan" in str(reason_2 or reason) or "produk_tampil" in str(reason_2 or reason))
                else AlasanTidakJelasEnum.BERTENTANGAN
            )
            validated_output = ParserOutput(
                aksi=ActionEnum.TIDAK_JELAS,
                argumen=ActionArguments(alasan=alasan_final),
                pembaruan_state=StateUpdate()
            )
            is_schema_valid = False
            json_valid = False

    dt_ms = (time.perf_counter() - t0) * 1000.0
    final_json_valid = json_valid and is_schema_valid

    metrics = {
        "latency_ms": round(dt_ms, 2),
        "json_valid": final_json_valid,
        "schema_valid": is_schema_valid,
        "retried": retried,
        "raw_content": raw_content,
        "error": error_msg,
        "prompt_eval_count": p_eval_cnt,
        "eval_count": eval_cnt,
        "load_duration_ms": round(load_dur / 1e6, 2),
        "prompt_eval_duration_ms": round(p_eval_dur / 1e6, 2),
        "eval_duration_ms": round(eval_dur / 1e6, 2)
    }

    return validated_output, metrics
