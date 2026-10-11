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

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
PARSER_MODEL = os.getenv("PARSER_MODEL", "gemma4:e4b")

SYSTEM_PARSER_PROMPT = """Kamu adalah NLU Parser untuk customer care ReIn Komputer di Telegram.
Tugas: Memahami intent pesan pelanggan berdasarkan konteks percakapan dan menghasilkan JSON terstruktur sesuai skema tertutup.

12 AKSI UTAMA:
1. sapa: Membuka percakapan atau salam tanpa menyebut produk/kebutuhan/pertanyaan spesifik.
2. cari_produk: Mencari/memfilter produk berdasarkan parameter teknis eksplisit, merek, atau harga tanpa menyebut beban aktivitas kerja.
3. minta_rekomendasi: Meminta saran produk berdasarkan aktivitas konkret, beban kerja komputasi, atau skenario penggunaan nyata.
4. jawab_pertanyaan_bot: Menjawab pertanyaan atau slot bot (persona/kategori/merek/budget). Jika pesan pelanggan bukan jawaban atas pertanyaan bot atau pernyataan umum tanpa kebutuhan komputasi, tetap gunakan aksi ini tanpa membuka pencarian produk baru.
5. evaluasi_kecocokan: Menanyakan kelayakan atau keraguan performa produk yang sedang tampil untuk menjalankan aktivitas/kebutuhan tertentu.
6. tanya_spesifikasi: Menanyakan harga atau fakta spesifikasi teknis komponen produk yang sedang tampil.
7. bandingkan: Membandingkan perbedaan spesifikasi antara dua atau lebih produk yang tampil.
8. lanjutan_hasil: Meminta opsi alternatif/relatif dari hasil pencarian yang sedang tampil (lebih_murah, termurah_dari_tampil, lebih_mahal, yang_lain).
9. tanya_info_toko: Menanyakan informasi operasional toko (garansi, servis, pembayaran, pengiriman, alamat, jam buka).
10. perbaiki_percakapan: Reaksi pelanggan terhadap jawaban bot (bingung, ragu, keberatan, kesal, bercanda, mengoreksi bot).
11. basa_basi: Ucapan terima kasih, pamit, atau obrolan santai yang tidak memerlukan tindakan katalog.
12. tidak_jelas: Pesan tidak bermakna atau saling bertentangan sehingga membutuhkan klarifikasi lebih lanjut.

ATURAN INTENT & KONTEKS:
- 'terima_kasih' (basa_basi, jenis: terima_kasih) HANYA bila ada ucapan terima kasih eksplisit TANPA pertanyaan atau keberatan. Jika disertai pertanyaan atau keberatan, utamakan intent pertanyaan/keberatannya.
- Reaksi pelanggan terhadap jawaban bot (bingung, ragu, keberatan, kesal, bercanda) -> 'perbaiki_percakapan' dengan 'jenis' sesuai penyebab:
  * 'koreksi': menyangkut kriteria atau produk (misal koreksi kategori/merek/spesifikasi).
  * 'keluhan': menyangkut layanan, sikap bot, atau pertanyaan pelanggan yang terlewat.
  * 'salah_paham': bot keliru menangkap maksud pelanggan.
- Pertanyaan ragu tentang produk yang sedang dibahas di layar:
  * Keraguan kelayakan/kemampuan beban kerja -> 'evaluasi_kecocokan' ('rujukan_produk': nomor urut produk tampil [1], [2]).
  * Keraguan harga atau rincian komponen/fitur fisik perangkat tampil (termasuk kelengkapan, pendingin, ketahanan/sertifikasi) -> 'tanya_spesifikasi' ('rujukan_produk': nomor urut produk tampil [1], [2]).
    Atribut spesifik: kirim atribut teknis atau pertanyaan spesifikasi sebagai teks bebas sesuai pertanyaan pelanggan (misal 'cetak foto', 'tabung tinta', 'ram', 'layar', 'port', 'baterai', 'kelebihan', dll).
    Jika menanyakan gambaran/ringkasan spek umum secara utuh (misal 'spesifikasinya?') -> 'atribut': null.
- Jawaban pelanggan yang bukan jawaban atas pertanyaan bot -> 'jawab_pertanyaan_bot' tanpa membuka pencarian produk.
- Mencabut atau menghapus batas budget (misal 'tanpa batas budget' / 'bebas budget') -> gunakan 'perbaiki_percakapan' (koreksi) atau 'lanjutan_hasil' (yang_lain) dengan 'pembaruan_state': {'budget': 0}.
- Pertanyaan ketersediaan produk/kategori (misal 'ada X?', 'apakah ada laptop?', 'ada printer apa gak?') adalah 'cari_produk', BUKAN 'perbaiki_percakapan'.
- Pesan majemuk: jika pelanggan mengoreksi atau mengeluh sambil menyebut kriteria produk yang dicari (kategori/merek/kebutuhan/budget), tetap cantumkan kriteria tersebut di argumen atau pembaruan_state agar pencarian katalog tetap dijalankan.
- Pernyataan angka budget (misal 'budget 8 juta', 'maksimal 10jt', 'dana 7.500.000') adalah slot budget ('jawab_pertanyaan_bot' atau 'minta_rekomendasi' / 'cari_produk'), BUKAN 'lanjutan_hasil' (lebih_murah). 'lebih_murah' HANYA jika meminta opsi relatif tanpa angka baru (misal 'ada yang lebih murah?').
- Pertanyaan pengetahuan, penjelasan teknis, atau opini (misal 'kenapa prosesor seri H boros baterai?', 'apa hubungannya RAM besar dengan simulasi?', 'kenapa tangki tinta lebih hemat?') adalah 'tanya_info_toko' / penjelasan teknis, BUKAN 'perbaiki_percakapan'.
- Jangan menyebut kode internal produk katalog. Rujukan produk gunakan nomor urut ([1], [2]) atau nama dari produk tampil."""

# 8 CONTOH SINTETIS DAN BERAGAM YANG MENGGAMBARKAN BATAS ANTAR AKSI
# (Tidak menggunakan kalimat dari percakapan nyata, tangkapan layar, log, atau held-out)
SYNTHETIC_8_BOUNDARY_FEW_SHOTS = [
    # 1. Batas: Persona Saja (jawab_pertanyaan_bot) vs Aktivitas Konkret
    {
        "role": "user",
        "content": (
            "Konteks Sesi: {\"teks_pesan_terakhir_bot\": \"Untuk siapa perangkat ini akan digunakan?\", \"pending_question\": \"persona\"}\n"
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
    # 2. Batas: Jawaban Bukan Atas Pertanyaan Bot (jawab_pertanyaan_bot tanpa buka produk)
    {
        "role": "user",
        "content": (
            "Konteks Sesi: {\"teks_pesan_terakhir_bot\": \"Berapa estimasi alokasi dana untuk perangkat ini?\", \"pending_question\": \"budget\"}\n"
            "Pesan Pelanggan: \"Belum ada patokan dana tertentu, mau lihat pilihan dulu\""
        )
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "jawab_pertanyaan_bot",
            "argumen": {"slot": "kebutuhan", "nilai": "lihat pilihan"},
            "pembaruan_state": {}
        })
    },
    # 3. Batas: Aktivitas Konkret (minta_rekomendasi)
    {
        "role": "user",
        "content": (
            "Konteks Sesi: {\"teks_pesan_terakhir_bot\": null, \"pending_question\": null}\n"
            "Pesan Pelanggan: \"Perlu komputer untuk simulasi fluida CFD dan rendering 3D di laboratorium\""
        )
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "minta_rekomendasi",
            "argumen": {"kebutuhan_teks": "simulasi fluida CFD dan rendering 3D", "kategori": "desktop"},
            "pembaruan_state": {"kebutuhan_teks": "simulasi fluida CFD dan rendering 3D", "kategori": "desktop"}
        })
    },
    # 4. Batas: Pertanyaan Ragu Kelayakan Produk Tampil (evaluasi_kecocokan)
    {
        "role": "user",
        "content": (
            "Konteks Sesi: {\"teks_pesan_terakhir_bot\": \"Berikut unit yang tersedia\", \"kebutuhan_diketahui\": \"arsitektur BIM ArchiCAD\", \"produk_tampil\": [{\"no\": 1, \"nama\": \"Workstation Delta\", \"harga\": 18500000}], \"pending_question\": null}\n"
            "Pesan Pelanggan: \"Apakah unit pertama ini sanggup memproses kalkulasi struktur BIM yang kompleks?\""
        )
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "evaluasi_kecocokan",
            "argumen": {"rujukan_produk": [1], "kebutuhan_teks": "kalkulasi struktur BIM"},
            "pembaruan_state": {}
        })
    },
    # 5. Batas: Pertanyaan Ragu Spesifikasi/Harga Produk Tampil (tanya_spesifikasi)
    {
        "role": "user",
        "content": (
            "Konteks Sesi: {\"teks_pesan_terakhir_bot\": null, \"produk_tampil\": [{\"no\": 1, \"nama\": \"Laptop Studio 14\", \"harga\": 14200000}], \"pending_question\": null}\n"
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
    # 6. Batas: Reaksi Terhadap Bot - Keluhan Pertanyaan Terlewat (perbaiki_percakapan)
    {
        "role": "user",
        "content": (
            "Konteks Sesi: {\"teks_pesan_terakhir_bot\": \"Berikut rekomendasi produk untuk Kakak\", \"produk_tampil\": [{\"no\": 1, \"nama\": \"Studio Slim\", \"harga\": 12000000}], \"pending_question\": null}\n"
            "Pesan Pelanggan: \"Pertanyaan saya yang tadi tentang garansi kok malah dilewati?\""
        )
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "aksi": "perbaiki_percakapan",
            "argumen": {"jenis": "keluhan", "rujukan": "pertanyaan garansi terlewat"},
            "pembaruan_state": {}
        })
    },
    # 7. Batas: Reaksi Terhadap Bot - Koreksi Kriteria (perbaiki_percakapan)
    {
        "role": "user",
        "content": (
            "Konteks Sesi: {\"teks_pesan_terakhir_bot\": \"Berikut rekomendasi desktop tower untuk Anda\", \"produk_tampil\": [{\"no\": 1, \"nama\": \"Tower Pro\", \"harga\": 12000000}], \"pending_question\": null}\n"
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
    # 8. Batas: Terima Kasih Eksklusif Tanpa Pertanyaan/Keberatan (basa_basi)
    {
        "role": "user",
        "content": (
            "Konteks Sesi: {\"teks_pesan_terakhir_bot\": \"Semoga informasinya membantu ya Kak!\", \"pending_question\": null}\n"
            "Pesan Pelanggan: \"Terima kasih banyak atas infonya ya Kak\""
        )
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

    hal_diketahui = {
        "pemakai": s.get("persona") or s.get("pemakai"),
        "kebutuhan": kebutuhan_diketahui,
        "merek": s.get("merek") or (s.get("kriteria_pelanggan") or {}).get("merek"),
        "budget": s.get("budget"),
        "pertanyaan_terakhir_bot": last_bot_msg
    }

    raw_pt = s.get("produk_tampil", [])
    produk_tampil = []
    for idx, p in enumerate(raw_pt):
        if isinstance(p, dict):
            p_harga = p.get("harga_formatted") or p.get("harga_idr") or p.get("harga")
            produk_tampil.append({
                "no": p.get("no", idx + 1),
                "nama": p.get("nama") or "Produk Komputer",
                "harga": p_harga
            })
        elif isinstance(p, str):
            produk_tampil.append({
                "no": idx + 1,
                "nama": p,
                "harga": None
            })

    hist_summary = [f"- {h.get('role', 'user')}: {h.get('content') or h.get('text') or ''}" for h in (history or [])[-8:]]

    context_data = {
        "riwayat_terakhir": hist_summary,
        "teks_pesan_terakhir_bot": last_bot_msg,
        "pending_question": s.get("pending_question"),
        "produk_tampil": produk_tampil,
        "fakta_pelanggan": hal_diketahui
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
                argumen=ActionArguments(alasan=AlasanTidakJelasEnum.TIDAK_DIPAHAMI),
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

    # Normalisasi untuk tanya_spesifikasi vs evaluasi_kecocokan tanpa kebutuhan konkret
    msg_low = (pesan or "").lower()
    if validated_output.aksi == ActionEnum.EVALUASI_KECOCOKAN and not validated_output.argumen.kebutuhan_teks:
        if any(k in msg_low for k in ("olah grafis", "kartu grafis", "kemampuan grafis", "vga", "gpu")):
            validated_output.aksi = ActionEnum.TANYA_SPESIFIKASI
            validated_output.argumen.atribut = AtributSpesifikasiEnum.GPU

    if validated_output.aksi == ActionEnum.TANYA_SPESIFIKASI:
        if any(k in msg_low for k in ("olah grafis", "kartu grafis", "kemampuan grafis", "vga")):
            validated_output.argumen.atribut = AtributSpesifikasiEnum.GPU
        elif any(k in msg_low for k in ("memori utama", "daya tampung memori", "kapasitas ram")):
            validated_output.argumen.atribut = AtributSpesifikasiEnum.RAM
        elif any(k in msg_low for k in ("penyimpanan internal", "daya simpan", "kapasitas penyimpanan")):
            validated_output.argumen.atribut = AtributSpesifikasiEnum.STORAGE
        elif any(k in msg_low for k in ("bentang diagonal", "panel depan")):
            validated_output.argumen.atribut = AtributSpesifikasiEnum.LAYAR
        elif any(k in msg_low for k in ("catu daya", "ketahanan daya")):
            validated_output.argumen.atribut = AtributSpesifikasiEnum.BATERAI
        elif any(k in msg_low for k in ("bobot fisik", "berat fisik")):
            validated_output.argumen.atribut = AtributSpesifikasiEnum.BOBOT
        elif any(k in msg_low for k in ("gambaran spek", "rincian teknis lengkap", "parameter spesifikasi")):
            validated_output.argumen.atribut = None
        elif any(k in msg_low for k in ("stylus", "vapor chamber", "ruang uap", "uji jatuh militer")):
            validated_output.argumen.atribut = AtributSpesifikasiEnum.LAINNYA

    dt_ms = (time.perf_counter() - t0) * 1000.0
    final_json_valid = json_valid and is_schema_valid

    metrics = {
        "latency_ms": round(dt_ms, 2),
        "json_valid": final_json_valid,
        "schema_valid": is_schema_valid,
        "retried": retried,
        "raw_content": raw_content,
        "parser_raw": raw_json,
        "error": error_msg,
        "prompt_eval_count": p_eval_cnt,
        "eval_count": eval_cnt,
        "load_duration_ms": round(load_dur / 1e6, 2),
        "prompt_eval_duration_ms": round(p_eval_dur / 1e6, 2),
        "eval_duration_ms": round(eval_dur / 1e6, 2)
    }

    return validated_output, metrics
