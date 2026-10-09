# -*- coding: utf-8 -*-
"""
services/session_pipeline.py
Orkestrator Sesi Percakapan Antigravity v2 untuk ReIn Komputer.

Menjalankan alur per giliran secara terukur:
Pesan pelanggan
  -> [1 PARSER LLM]        (gemma4:e4b, structured JSON)
  -> [2 VALIDATOR]         (enum tertutup, sanitasi argumen, resolusi rujukan produk)
  -> [3 MESIN DETERMINISTIK] (RAG profil / filter katalog -> Fakta)
  -> [4 GENERATOR LLM]     (gemma4:e4b, teks percakapan maks 3 kalimat)
  -> [5 PEMERIKSA GROUNDING](validasi harga, larangan kode internal, 1x retry jika melanggar)
  -> [6 KARTU PRODUK]      (kartu produk HTML jika ada hasil produk)
"""
from __future__ import annotations

import os
import time
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from services.llm_parser import parse_user_message
from services.validator import validate_parser_output
from services.action_engine import ActionEngine, ActionResult
from services.llm_generator import generate_response, GeneratorOutput, build_deterministic_fallback_text
from services.grounding_checker import GroundingChecker, EMERGENCY_FALLBACK_TEXT
from services.product_card import format_product_cards_message
from services.schema_actions import ParserOutput, ActionEnum

logger = logging.getLogger(__name__)


@dataclass
class TurnExecutionResult:
    # Hasil percakapan
    teks_jawaban: str
    kartu_produk_html: Optional[str] = None
    pertanyaan_diajukan: Optional[str] = None
    
    # Detail aksi & fakta
    aksi_terpilih: str = ""
    fakta_eksekusi: Dict[str, Any] = field(default_factory=dict)
    
    # Metrik & diagnosa
    latensi_parse_ms: float = 0.0
    latensi_mesin_ms: float = 0.0
    latensi_generate_ms: float = 0.0
    latensi_total_ms: float = 0.0
    
    json_valid: bool = True
    pelanggaran_pemeriksa: List[str] = field(default_factory=list)
    is_emergency_fallback: bool = False
    re_parse: bool = False
    prompt_eval_count: int = 0
    eval_count: int = 0
    load_duration_ms: float = 0.0
    prompt_eval_duration_ms: float = 0.0
    eval_duration_ms: float = 0.0
    parsed_output: Optional[Dict[str, Any]] = None
    raw_llm_content: Optional[str] = None


class SessionPipeline:
    def __init__(self, action_engine: ActionEngine | None = None):
        self.action_engine = action_engine or ActionEngine()
        self.grounding_checker = GroundingChecker()

    def process_turn(
        self,
        pesan_pelanggan: str,
        session_state: dict,
        history: list[dict] | None = None
    ) -> Tuple[TurnExecutionResult, dict]:
        """
        Memproses 1 giliran pesan pelanggan secara utuh.
        Mengembalikan (TurnExecutionResult, session_state_terbaru).
        """
        t_start = time.perf_counter()
        state = dict(session_state or {})
        history = history or state.get("history", [])

        # ---------------------------------------------------------------------
        # 1. PARSER LLM & 2. VALIDATOR
        # ---------------------------------------------------------------------
        parsed, parse_metrics = parse_user_message(pesan_pelanggan, state=state, history=history)
        lat_parse = parse_metrics.get("latency_ms", 0.0)

        # ---------------------------------------------------------------------
        # 3. MESIN DETERMINISTIK
        # ---------------------------------------------------------------------
        t_engine_0 = time.perf_counter()
        action_res: ActionResult = self.action_engine.execute(parsed, session_state=state)
        lat_mesin = (time.perf_counter() - t_engine_0) * 1000.0

        # Update state dari argumen & pembaruan_state parser
        if parsed.argumen.merek:
            state["merek"] = parsed.argumen.merek
        if parsed.argumen.kategori:
            state["kategori"] = parsed.argumen.kategori
        if parsed.argumen.persona:
            state["persona"] = parsed.argumen.persona
        if parsed.argumen.slot and parsed.argumen.nilai:
            slot_name = parsed.argumen.slot.value if hasattr(parsed.argumen.slot, "value") else str(parsed.argumen.slot)
            state[slot_name] = parsed.argumen.nilai

        state_up = parsed.pembaruan_state
        if state_up.persona:
            state["persona"] = state_up.persona
        if state_up.sebutan:
            state["sebutan"] = state_up.sebutan
        if state_up.kebutuhan_teks:
            state["kebutuhan_teks"] = state_up.kebutuhan_teks
        if state_up.budget:
            state["budget"] = state_up.budget
        if state_up.kategori:
            state["kategori"] = state_up.kategori
        if action_res.profil_id:
            state["profil_aktif"] = action_res.profil_id

        # Simpan produk yang tampil jika aksi menghasilkan produk
        if action_res.produk_list:
            state["produk_tampil"] = action_res.produk_list

        # ---------------------------------------------------------------------
        # 4. GENERATOR LLM & 5. PEMERIKSA GROUNDING
        # ---------------------------------------------------------------------
        t_gen_0 = time.perf_counter()
        gen_out, gen_metrics = generate_response(
            aksi=parsed.aksi.value,
            fakta=action_res.fakta,
            state=state,
            history=history
        )

        is_valid, violations = self.grounding_checker.check(
            gen_out.teks, action_res.fakta, state=state, penilaian=gen_out.penilaian
        )
        is_fallback = False

        if not is_valid:
            logger.warning(f"Pelanggaran pemeriksa: {violations}. Meminta generator menulis ulang...")
            feedback_note = f"Perbaiki kalimatmu: {'; '.join(violations)}. Jangan sebut hal tersebut."
            # Retry 1 kali
            gen_out_retry, retry_metrics = generate_response(
                aksi=parsed.aksi.value,
                fakta=action_res.fakta,
                state=state,
                history=history,
                feedback_note=feedback_note
            )
            is_valid_retry, violations_retry = self.grounding_checker.check(
                gen_out_retry.teks, action_res.fakta, state=state, penilaian=gen_out_retry.penilaian
            )
            if is_valid_retry:
                gen_out = gen_out_retry
                violations = []
            else:
                logger.error(f"Pemeriksa gagal setelah retry: {violations_retry}. Menggunakan kalimat darurat berbasis fakta.")
                fallback_teks = build_deterministic_fallback_text(parsed.aksi.value, action_res.fakta)
                gen_out = GeneratorOutput(
                    teks=fallback_teks,
                    pertanyaan_diajukan=None
                )
                violations = violations_retry
                is_fallback = True

        lat_gen = (time.perf_counter() - t_gen_0) * 1000.0
        lat_total = (time.perf_counter() - t_start) * 1000.0

        # Update pending_question di state (A5, A6, A10: info murni tidak pernah membuka pertanyaan)
        if parsed.aksi in (ActionEnum.TANYA_SPESIFIKASI, ActionEnum.TANYA_INFO_TOKO, ActionEnum.BANDINGKAN):
            gen_out.pertanyaan_diajukan = None
            state["pending_question"] = None
        else:
            state["pending_question"] = gen_out.pertanyaan_diajukan
            if gen_out.pertanyaan_diajukan:
                state["last_asked_slot"] = gen_out.pertanyaan_diajukan

        # ---------------------------------------------------------------------
        # 6. KARTU PRODUK HTML
        # ---------------------------------------------------------------------
        kartu_html = None
        if action_res.produk_list and parsed.aksi in (ActionEnum.MINTA_REKOMENDASI, ActionEnum.CARI_PRODUK, ActionEnum.LANJUTAN_HASIL):
            judul_rek = (action_res.fakta.get("profil") or {}).get("judul")
            kartu_html = format_product_cards_message(action_res.produk_list, judul_rekomendasi=judul_rek)

        # Update riwayat percakapan (maks 8 pesan)
        new_history = list(history)
        new_history.append({"role": "user", "content": pesan_pelanggan, "text": pesan_pelanggan})
        new_history.append({"role": "assistant", "content": gen_out.teks, "text": gen_out.teks})
        state["history"] = new_history[-8:]

        turn_result = TurnExecutionResult(
            teks_jawaban=gen_out.teks,
            kartu_produk_html=kartu_html,
            pertanyaan_diajukan=gen_out.pertanyaan_diajukan,
            aksi_terpilih=parsed.aksi.value,
            fakta_eksekusi=action_res.fakta,
            latensi_parse_ms=round(lat_parse, 1),
            latensi_mesin_ms=round(lat_mesin, 1),
            latensi_generate_ms=round(lat_gen, 1),
            latensi_total_ms=round(lat_total, 1),
            json_valid=parse_metrics.get("json_valid", True),
            pelanggaran_pemeriksa=violations,
            is_emergency_fallback=is_fallback,
            re_parse=parse_metrics.get("retried", False),
            prompt_eval_count=(parse_metrics.get("prompt_eval_count", 0) or 0) + (gen_metrics.get("prompt_eval_count", 0) or 0),
            eval_count=(parse_metrics.get("eval_count", 0) or 0) + (gen_metrics.get("eval_count", 0) or 0),
            load_duration_ms=round((parse_metrics.get("load_duration_ms", 0.0) or 0.0) + (gen_metrics.get("load_duration_ms", 0.0) or 0.0), 1),
            prompt_eval_duration_ms=round((parse_metrics.get("prompt_eval_duration_ms", 0.0) or 0.0) + (gen_metrics.get("prompt_eval_duration_ms", 0.0) or 0.0), 1),
            eval_duration_ms=round((parse_metrics.get("eval_duration_ms", 0.0) or 0.0) + (gen_metrics.get("eval_duration_ms", 0.0) or 0.0), 1),
            parsed_output=parsed.model_dump(),
            raw_llm_content=parse_metrics.get("raw_content")
        )

        return turn_result, state
