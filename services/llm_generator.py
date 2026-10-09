# -*- coding: utf-8 -*-
"""
services/llm_generator.py
Generator Bahasa Alami (LLM) untuk Bobby Computer di Telegram.

Sesuai Antigravity v2:
- Model: gemma4:e4b
- Temperature: 0.4, num_predict: 160, think: False
- Structured Output: JSON {teks: str, pertanyaan_diajukan: str | None}
- Menghasilkan maksimal 3 kalimat, ramah, santai, dan berpijak murni pada FAKTA.
"""
from __future__ import annotations

import os
import json
import time
import urllib.request
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
GENERATOR_MODEL = os.getenv("GENERATOR_MODEL", "gemma4:e4b")

GENERATOR_SYSTEM_PROMPT = """Kamu adalah customer care ReIn Komputer di Telegram.
Tugasmu adalah menjawab pesan pelanggan dengan ramah, santai, dan sopan dalam bahasa Indonesia.
Selalu panggil pelanggan dengan 'Kak' atau 'Kakak' kecuali pelanggan secara eksplisit menyebutkan sebutan untuk dirinya sendiri (misal Bapak, Ibu, Dokter).
JANGAN PERNAH memanggil pelanggan dengan nama persona pengguna perangkat (misal jika laptop untuk 'mama', 'ibu', 'anak', atau 'kakek', jangan panggil pelanggan 'Mama' atau 'Kakek', tetap panggil pelanggan 'Kak').

ATURAN UTAMA (BATASAN RESPONS C):
1. Jawab maksimal 3 kalimat dan maksimal 420 karakter, langsung ke inti pesan pelanggan.
2. Kamu menerima: AKSI, FAKTA hasil sistem deterministik, state, dan riwayat obrolan.
3. HANYA gunakan angka dan informasi yang ada di FAKTA. Jangan mengarang harga, spesifikasi, atau model fiktif.
4. Jangan menulis ulang daftar produk atau harga secara panjang; kartu produk resmi akan dikirim oleh sistem terpisah.
5. Kamu boleh bernalar dari FAKTA (misal: menjelaskan apakah laptop tersebut cukup/kuat untuk kebutuhan pelanggan) dengan jujur.
6. ATURAN SLOT: Jangan pernah menanyakan ulang slot yang sudah terisi di 'slot_sudah_diketahui' (misal jika kategori sudah diketahui, jangan tanyakan kategori; jika persona atau kebutuhan/aktivitas sudah diketahui, jangan tanyakan hal tersebut). Jika ada slot penting yang belum diketahui, tanyakan MAKSIMAL SATU slot saja di 'pertanyaan_diajukan' dan teksmu.
7. Jika pelanggan menegur, mengoreksi, atau komplain, akui dan minta maaf secukupnya secara sopan, lalu fokus ke kebutuhan pelanggan.
8. JANGAN mengulang salam jika percakapan sudah berjalan.
9. JANGAN menyebut kode internal produk (seperti 'KB-L01', 'P01'), nama kolom database, atau istilah sistem internal seperti kata 'tier', 'cpu_tier', atau 'selisih'. Gunakan deskripsi spesifikasi yang ramah pelanggan (misal sebutkan nama seri prosesor seperti Core i5 atau Ryzen 5, kapasitas RAM dan SSD).
10. Untuk garansi, servis, pembayaran, dan info toko yang datanya tidak ada, arahkan pelanggan untuk berkonsultasi langsung dengan staf toko kami tanpa membuat janji palsu.
11. Jika status fakta adalah 'sebagian_tidak_di_katalog' atau terdapat 'produk_luar_katalog', jelaskan secara jujur dan ramah bahwa produk tersebut tidak tersedia di katalog ReIn Komputer, lalu sampaikan perbandingan dengan spesifikasi produk katalog yang tersedia.
12. Giliran informasi murni (tanya_spesifikasi, tanya_info_toko, bandingkan) DILARANG mengajukan pertanyaan di akhir pesan.

Kembalikan format JSON persis sesuai skema:
{
  "teks": "<kalimat jawaban untuk pelanggan>",
  "pertanyaan_diajukan": "<slot yang ditanyakan: 'kebutuhan' | 'budget' | 'kategori' | null>",
  "penilaian": {
    "<kode_produk>": "di_bawah_minimum" | "memenuhi_minimum" | "memenuhi_rekomendasi"
  }
}
Catatan untuk penilaian:
- Khusus aksi evaluasi_kecocokan, isi 'penilaian' dengan status kecocokan tiap produk yang dievaluasi ('di_bawah_minimum', 'memenuhi_minimum', atau 'memenuhi_rekomendasi') sesuai fakta.
- Untuk aksi selain evaluasi_kecocokan, isi 'penilaian' dengan null.
"""


KONTAK_STAF = os.getenv("KONTAK_STAF", "@cs_reinkomputer")
EMERGENCY_FALLBACK_TEXT = (
    f"Sistem kami sedang mengalami kendala teknis sementara. "
    f"Untuk bantuan langsung, silakan hubungi tim kami di {KONTAK_STAF}. "
    f"Anda juga bisa mencoba mengulang pesan Anda."
)


def build_deterministic_fallback_text(aksi: str, fakta: dict) -> str:
    """Merakit teks cadangan terstruktur langsung dari fakta_eksekusi secara deterministik (B10, B13)."""
    status = fakta.get("status")

    if status == "tidak_ada_dalam_anggaran":
        min_p = fakta.get("harga_termurah_kategori_formatted") or f"Rp{fakta.get('harga_termurah_kategori', 0):,}".replace(",", ".")
        return f"Belum ada produk dalam rentang anggaran tersebut, Kak. Pilihan paling terjangkau di katalog kami saat ini mulai dari {min_p}."

    if status == "belum_ada_yang_memenuhi":
        p_close = fakta.get("produk_terdekat", {})
        nama = p_close.get("nama", "perangkat terdekat")
        kekurangan = ", ".join(p_close.get("kekurangan", []))
        return f"Saat ini belum ada produk yang memenuhi seluruh spesifikasi minimum yang dibutuhkan, Kak. Pilihan terdekat kami adalah {nama} ({kekurangan})."

    if status == "tidak_ada_lebih_murah":
        min_p = fakta.get("harga_termurah_saat_ini_formatted") or "harga tersebut"
        return f"Produk yang ditampilkan sebelumnya sudah merupakan opsi paling terjangkau di katalog kami ({min_p}), Kak."

    if status == "tidak_ada_lebih_mahal":
        return "Produk yang ditampilkan sebelumnya sudah merupakan opsi spesifikasi tertinggi di katalog kami, Kak."

    if status == "tanya_kebutuhan":
        persona = fakta.get("persona", "pengguna")
        return f"Baik Kak, kebutuhan untuk {persona} sudah dicatat. Boleh tahu biasanya akan lebih sering dipakai untuk aktivitas apa saja?"

    if status == "profil_tidak_ditemukan":
        return "Kami belum dapat memetakan kebutuhan tersebut ke rekomendasi spesifik, Kak. Boleh ceritakan aktivitas atau software utama yang akan sering digunakan?"

    if status == "profil_tidak_ditemukan_berulang":
        return f"Kebutuhan tersebut belum teridentifikasi di sistem kami, Kak. Kakak bisa menyebutkan kategori dan anggaran langsung, atau berkonsultasi ke staf di {KONTAK_STAF}."

    if status == "info_toko":
        return f"Untuk informasi operasional toko, silakan langsung hubungi tim kami di {KONTAK_STAF}, Kak."

    if status == "rujukan_tidak_ada":
        return "Produk yang dirujuk tidak ditemukan di daftar yang sedang tampil, Kak. Silakan sebutkan kebutuhan atau perangkat yang dicari."

    prods = fakta.get("produk", [])
    if prods:
        nama_list = [p.get("nama") for p in prods[:3] if p.get("nama")]
        if nama_list:
            return f"Berikut beberapa pilihan yang sesuai di katalog kami: {', '.join(nama_list)}. Apakah ada model yang ingin Kakak ketahui lebih detail?"

    return EMERGENCY_FALLBACK_TEXT


class GeneratorOutput(BaseModel):
    teks: str = Field(description="Jawaban percakapan untuk pelanggan, maksimal 3 kalimat.")
    pertanyaan_diajukan: Optional[str] = Field(default=None, description="Slot yang ditanyakan bot jika ada, misal 'kebutuhan', 'budget', atau null.")
    penilaian: Optional[Dict[str, str]] = Field(default=None, description="Untuk evaluasi_kecocokan: mapping kode produk ke status kecocokan ('di_bawah_minimum', 'memenuhi_minimum', 'memenuhi_rekomendasi').")

    model_config = {
        "extra": "ignore"
    }


def build_generator_messages(
    aksi: str,
    fakta: dict,
    state: dict,
    history: list[dict] | None = None,
    feedback_note: str | None = None
) -> List[Dict[str, str]]:
    messages = [
        {"role": "system", "content": GENERATOR_SYSTEM_PROMPT}
    ]

    # Format ringkas riwayat
    if history:
        hist_text = "\n".join([f"- {h.get('role', 'user')}: {h.get('content') or h.get('text') or ''}" for h in history[-4:]])
        messages.append({
            "role": "user",
            "content": f"Riwayat percakapan terakhir:\n{hist_text}"
        })

    # Konteks giliran ini: sebutan lawan bicara selalu 'Kak' kecuali pelanggan menyebut sebutan untuk diri sendiri
    sebutan = state.get("sebutan") or "Kak"

    # Slot yang sudah terisi agar tidak ditanyakan ulang oleh generator
    slot_terisi = {}
    for slot_name in ["kategori", "persona", "kebutuhan_teks", "budget", "merek"]:
        val = state.get(slot_name)
        if val:
            slot_terisi[slot_name] = val

    context_data = {
        "aksi": aksi,
        "fakta": fakta,
        "sebutan_pelanggan": sebutan,
        "persona_pengguna_perangkat": state.get("persona"),
        "slot_sudah_diketahui": slot_terisi,
        "pending_question_sebelumnya": state.get("pending_question")
    }

    turn_prompt = f"Konteks giliran ini:\n{json.dumps(context_data, ensure_ascii=False, indent=2)}"
    if feedback_note:
        turn_prompt += f"\n\nCATATAN PERBAIKAN DARI PEMERIKSA (Wajib diperbaiki):\n{feedback_note}"

    messages.append({
        "role": "user",
        "content": turn_prompt
    })

    return messages


def generate_response(
    aksi: str,
    fakta: dict,
    state: dict,
    history: list[dict] | None = None,
    feedback_note: str | None = None,
    model: str = GENERATOR_MODEL,
    ollama_url: str = OLLAMA_BASE_URL,
    timeout: float = 25.0
) -> Tuple[GeneratorOutput, Dict[str, Any]]:
    """
    Menghasilkan jawaban percakapan via Ollama gemma4:e4b.
    Mengembalikan (GeneratorOutput, metrics_dict).
    """
    t0 = time.perf_counter()
    messages = build_generator_messages(aksi, fakta, state, history=history, feedback_note=feedback_note)
    schema = GeneratorOutput.model_json_schema()

    req_data = {
        "model": model,
        "messages": messages,
        "format": schema,
        "stream": False,
        "think": False,
        "keep_alive": "30m",
        "options": {
            "temperature": 0.4,
            "num_predict": 256,
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

        parsed_json = json.loads(raw_content)
        out = GeneratorOutput.model_validate(parsed_json)
        json_valid = True
    except Exception as e:
        logger.error(f"Gagal generate respons via Ollama: {e}")
        error_msg = str(e)
        fallback_teks = build_deterministic_fallback_text(aksi, fakta)
        out = GeneratorOutput(
            teks=fallback_teks,
            pertanyaan_diajukan=None
        )

    # Batasan Respons C (maksimal 3 kalimat, maksimal 420 karakter, tanpa pertanyaan pada info murni):
    if aksi in ("tanya_spesifikasi", "tanya_info_toko", "bandingkan"):
        out.pertanyaan_diajukan = None
        if out.teks and out.teks.rstrip().endswith("?"):
            parts = re.split(r"(?<=[.!?])\s+", out.teks.strip())
            if len(parts) > 1 and parts[-1].endswith("?"):
                out.teks = " ".join(parts[:-1]).strip()

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", out.teks.strip()) if s.strip()]
    if len(sentences) > 3:
        out.teks = " ".join(sentences[:3]).strip()

    if len(out.teks) > 420:
        truncated = out.teks[:420]
        last_punct = max(truncated.rfind("."), truncated.rfind("?"), truncated.rfind("!"))
        if last_punct > 120:
            out.teks = truncated[:last_punct + 1].strip()
        else:
            out.teks = truncated.rstrip()

    dt_ms = (time.perf_counter() - t0) * 1000.0
    metrics = {
        "latency_ms": round(dt_ms, 2),
        "json_valid": json_valid,
        "error": error_msg,
        "raw_content": raw_content,
        "prompt_eval_count": prompt_eval_count,
        "eval_count": eval_count,
        "load_duration_ms": round(load_duration / 1e6, 2),
        "prompt_eval_duration_ms": round(prompt_eval_duration / 1e6, 2),
        "eval_duration_ms": round(eval_duration / 1e6, 2)
    }
    return out, metrics
