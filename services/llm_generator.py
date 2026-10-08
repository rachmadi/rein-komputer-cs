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
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
GENERATOR_MODEL = os.getenv("GENERATOR_MODEL", "gemma4:e4b")

GENERATOR_SYSTEM_PROMPT = """Kamu adalah customer care Bobby Computer di Telegram.
Tugasmu adalah menjawab pesan pelanggan dengan ramah, santai, dan sopan dalam bahasa Indonesia.
Gunakan sebutan yang disukai pelanggan jika ada (kakak, ibu, bapak, mama).

ATURAN UTAMA:
1. Jawab maksimal 3 kalimat dan langsung ke inti pertanyaan pelanggan.
2. Kamu menerima: AKSI, FAKTA hasil sistem deterministik, state, dan riwayat obrolan.
3. HANYA gunakan angka dan informasi yang ada di FAKTA. Jangan mengarang harga atau spesifikasi.
4. Jangan menulis ulang daftar produk atau harga secara panjang; kartu produk resmi akan dikirim oleh sistem terpisah.
5. Kamu boleh bernalar dari FAKTA (misal: menjelaskan apakah laptop tersebut cukup/kuat untuk kebutuhan pelanggan) dengan jujur.
6. Jika kebutuhan atau budget belum diketahui dan relevan ditanyakan, tanyakan SATU hal saja di 'pertanyaan_diajukan' dan teksmu.
7. Jika pelanggan menegur, mengoreksi, atau komplain, akui dan minta maaf secukupnya secara sopan, lalu fokus ke kebutuhan pelanggan.
8. JANGAN mengulang salam jika percakapan sudah berjalan.
9. JANGAN menyebut kode internal produk (seperti 'KB-L01', 'P01'), nama kolom database, atau istilah sistem internal.
10. Untuk garansi, servis, pembayaran, dan info toko yang datanya tidak ada, arahkan pelanggan menghubungi staf di @cs_bobbycomputer.

Kembalikan format JSON persis sesuai skema:
{
  "teks": "<kalimat jawaban untuk pelanggan>",
  "pertanyaan_diajukan": "<slot yang ditanyakan: 'kebutuhan' | 'budget' | 'kategori' | null>"
}
"""


class GeneratorOutput(BaseModel):
    teks: str = Field(description="Jawaban percakapan untuk pelanggan, maksimal 3 kalimat.")
    pertanyaan_diajukan: Optional[str] = Field(default=None, description="Slot yang ditanyakan bot jika ada, misal 'kebutuhan', 'budget', atau null.")

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

    # Konteks giliran ini
    sebutan = state.get("sebutan") or state.get("persona") or "Kakak"
    context_data = {
        "aksi": aksi,
        "fakta": fakta,
        "sebutan_pelanggan": sebutan,
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
        "options": {
            "temperature": 0.4,
            "num_predict": 160
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

        parsed_json = json.loads(raw_content)
        out = GeneratorOutput.model_validate(parsed_json)
        json_valid = True
    except Exception as e:
        logger.error(f"Gagal generate respons via Ollama: {e}")
        error_msg = str(e)
        out = GeneratorOutput(
            teks="Halo Kak, ada yang bisa kami bantu seputar produk laptop atau komputer hari ini?",
            pertanyaan_diajukan=None
        )

    dt_ms = (time.perf_counter() - t0) * 1000.0
    metrics = {
        "latency_ms": round(dt_ms, 2),
        "json_valid": json_valid,
        "error": error_msg,
        "raw_content": raw_content
    }
    return out, metrics
