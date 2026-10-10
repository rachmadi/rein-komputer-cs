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
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from services.llm_parser import parse_user_message
from services.validator import validate_parser_output
from services.action_engine import ActionEngine, ActionResult, parse_int_safe
from services.llm_generator import generate_response, GeneratorOutput, build_deterministic_fallback_text
from services.grounding_checker import GroundingChecker, EMERGENCY_FALLBACK_TEXT
from services.product_card import format_product_cards_message
from services.schema_actions import ParserOutput, ActionEnum, ActionArguments, AlasanTidakJelasEnum

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
    jalur: str = "model"
    aksi_parser: Optional[str] = None
    jenis: Optional[str] = None


def match_rule_greeting(pesan_pelanggan: str) -> Optional[Tuple[str, str, str]]:
    """
    Memeriksa apakah pesan sepenuhnya merupakan sapaan atau terima kasih berdasarkan daftar kata tertutup.
    Mengembalikan (route, reply_text, fakta_status) jika cocok, atau None jika tidak.
    """
    if not pesan_pelanggan:
        return None
    # Normalisasi pesan: huruf kecil, buang tanda baca/emoji, rapikan spasi
    text_clean = re.sub(r"[^\w\s]|_", " ", pesan_pelanggan.lower())
    words = text_clean.split()
    if not words:
        return None

    # Himpunan kata sapaan yang diizinkan
    sapaan_words = {"halo", "hai", "hi", "hello", "pagi", "siang", "sore", "malam", "selamat", "assalamualaikum", "kak", "kakak"}
    greeting_roots = {"halo", "hai", "hi", "hello", "pagi", "siang", "sore", "malam", "assalamualaikum"}

    # Himpunan kata terima kasih yang diizinkan
    terima_kasih_words = {"terima", "kasih", "makasih", "thanks", "banyak", "kak", "kakak"}

    # 1. Cek apakah SELURUH kata termasuk dalam sapaan
    if all(w in sapaan_words for w in words) and any(w in greeting_roots for w in words):
        if "pagi" in words:
            reply = "Selamat pagi, Kak! Selamat datang di ReIn Komputer. Ada kebutuhan komputer atau laptop yang bisa kami bantu carikan hari ini?"
        elif "siang" in words:
            reply = "Selamat siang, Kak! Selamat datang di ReIn Komputer. Ada kebutuhan komputer atau laptop yang bisa kami bantu carikan hari ini?"
        elif "sore" in words:
            reply = "Selamat sore, Kak! Selamat datang di ReIn Komputer. Ada kebutuhan komputer atau laptop yang bisa kami bantu carikan hari ini?"
        elif "malam" in words:
            reply = "Selamat malam, Kak! Selamat datang di ReIn Komputer. Ada kebutuhan komputer atau laptop yang bisa kami bantu carikan hari ini?"
        elif "assalamualaikum" in words:
            reply = "Waalaikumsalam, Kak! Selamat datang di ReIn Komputer. Ada kebutuhan komputer atau laptop yang bisa kami bantu carikan hari ini?"
        else:
            reply = "Halo, Kak! Selamat datang di ReIn Komputer. Ada kebutuhan komputer atau laptop yang bisa kami bantu carikan hari ini?"
        return ("sapa", reply, "sapaan")

    # 2. Cek apakah SELURUH kata termasuk dalam terima kasih
    cleaned_phrase = " ".join(words)
    has_tk_root = "makasih" in words or "thanks" in words or "terima kasih" in cleaned_phrase
    if all(w in terima_kasih_words for w in words) and has_tk_root:
        reply = "Sama-sama, Kak! Senang bisa membantu di ReIn Komputer. Silakan beri tahu jika ada kebutuhan komputer atau laptop lain yang ingin dicari."
        return ("basa_basi", reply, "terima_kasih")

    return None


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
        # 0. JALUR ATURAN SAPAAN & TERIMA KASIH (tanpa memanggil model)
        # ---------------------------------------------------------------------
        rule_match = match_rule_greeting(pesan_pelanggan)
        if rule_match is not None:
            r_aksi, r_reply, r_status = rule_match
            lat_total = (time.perf_counter() - t_start) * 1000.0
            new_history = list(history)
            new_history.append({"role": "user", "content": pesan_pelanggan, "text": pesan_pelanggan})
            new_history.append({"role": "assistant", "content": r_reply, "text": r_reply})
            state["history"] = new_history[-8:]

            turn_result = TurnExecutionResult(
                teks_jawaban=r_reply,
                kartu_produk_html=None,
                pertanyaan_diajukan=None,
                aksi_terpilih=r_aksi,
                fakta_eksekusi={"status": r_status},
                latensi_parse_ms=0.0,
                latensi_mesin_ms=0.0,
                latensi_generate_ms=0.0,
                latensi_total_ms=round(lat_total, 1),
                jalur="aturan",
                aksi_parser=r_aksi,
                jenis=None
            )
            return turn_result, state

        # ---------------------------------------------------------------------
        # 1. PARSER LLM & 2. VALIDATOR
        # ---------------------------------------------------------------------
        try:
            parsed, parse_metrics = parse_user_message(pesan_pelanggan, state=state, history=history)
            lat_parse = parse_metrics.get("latency_ms", 0.0)
        except Exception as exc:
            logger.error(f"Kegagalan parser LLM: {exc}")
            parsed = ParserOutput(
                aksi=ActionEnum.TIDAK_JELAS,
                argumen=ActionArguments(alasan=AlasanTidakJelasEnum.SISTEM_ERROR)
            )
            parse_metrics = {"latency_ms": 0.0, "json_valid": False}
            lat_parse = 0.0

        # D6: Pergantian kategori mereset slot anggaran, merek, profil aktif, dan produk tampil
        if parsed.argumen.kategori:
            new_kat_str = str(parsed.argumen.kategori).strip().lower()
            old_kat_str = str(state.get("kategori", "")).strip().lower() if state.get("kategori") else None
            if old_kat_str and new_kat_str != old_kat_str:
                state["kategori"] = new_kat_str
                state["budget"] = None
                state["merek"] = None
                state["profil_aktif"] = None
                state["kebutuhan_teks"] = None
                state["produk_tampil"] = []
                state["produk_terakhir_dibahas"] = None
                state["history_produk_tampil"] = []
                state["kriteria_pelanggan"] = {"kategori": new_kat_str}
                state["batas_bot"] = {}

        # Deteksi kategori jika belum terisi di argumen maupun state
        if not parsed.argumen.kategori and not state.get("kategori"):
            if re.search(r"\b(laptop|notebook|komputer jinjing)\b", pesan_pelanggan, re.IGNORECASE):
                parsed.argumen.kategori = "laptop"
                state["kategori"] = "laptop"
            elif re.search(r"\b(desktop|pc|komputer meja)\b", pesan_pelanggan, re.IGNORECASE):
                parsed.argumen.kategori = "desktop"
                state["kategori"] = "desktop"
            elif re.search(r"\b(printer)\b", pesan_pelanggan, re.IGNORECASE):
                parsed.argumen.kategori = "printer"
                state["kategori"] = "printer"

        # E3: Deteksi jika pesan pelanggan membawa kebutuhan komputasi baru yang belum terisi di argumen
        if not parsed.argumen.kebutuhan_teks and parsed.aksi in (ActionEnum.EVALUASI_KECOCOKAN, ActionEnum.MINTA_REKOMENDASI):
            m_keb = re.search(r"(?:dipakai|buat|untuk|kebutuhan)\s+([a-zA-Z0-9\s\+\#]{4,40}?)(?:\s+apakah|\s+bisa|\s+kuat|\?|$)", pesan_pelanggan, re.IGNORECASE)
            if m_keb:
                extracted_keb = m_keb.group(1).strip()
                if len(extracted_keb) >= 4:
                    parsed.argumen.kebutuhan_teks = extracted_keb
                    parsed.pembaruan_state.kebutuhan_teks = extracted_keb

        # E4: Ekstrak batas anggaran jika ada pada lanjutan_hasil
        if parsed.aksi == ActionEnum.LANJUTAN_HASIL and not parsed.argumen.max_harga:
            from services.catalog_search import parse_budget_from_text
            b_text = parse_budget_from_text(pesan_pelanggan)
            if b_text:
                parsed.argumen.max_harga = b_text
                state["budget"] = b_text

        # Update kriteria_pelanggan & batas_bot terpisah di state (F1)
        if "kriteria_pelanggan" not in state or not isinstance(state["kriteria_pelanggan"], dict):
            state["kriteria_pelanggan"] = {}
        if "batas_bot" not in state or not isinstance(state["batas_bot"], dict):
            state["batas_bot"] = {}

        if parsed.argumen.max_harga is not None:
            state["kriteria_pelanggan"]["max_harga"] = parse_int_safe(parsed.argumen.max_harga)
        elif parsed.pembaruan_state.budget is not None:
            state["kriteria_pelanggan"]["max_harga"] = parsed.pembaruan_state.budget

        if parsed.argumen.merek:
            state["kriteria_pelanggan"]["merek"] = parsed.argumen.merek
        if parsed.argumen.kategori:
            state["kriteria_pelanggan"]["kategori"] = parsed.argumen.kategori
        if parsed.argumen.kebutuhan_teks:
            state["kriteria_pelanggan"]["kebutuhan_teks"] = parsed.argumen.kebutuhan_teks
        if parsed.argumen.ram_gb_min:
            state["kriteria_pelanggan"]["ram_gb_min"] = parsed.argumen.ram_gb_min

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
        if parsed.argumen.max_harga is not None:
            state["budget"] = parse_int_safe(parsed.argumen.max_harga)
        if parsed.argumen.persona:
            state["persona"] = parsed.argumen.persona
        if parsed.argumen.kebutuhan_teks:
            state["kebutuhan_teks"] = parsed.argumen.kebutuhan_teks
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
            if "history_produk_tampil" not in state or not isinstance(state["history_produk_tampil"], list):
                state["history_produk_tampil"] = []
            hist_codes = {p.get("kode") for p in state["history_produk_tampil"] if isinstance(p, dict) and p.get("kode")}
            for p in action_res.produk_list:
                if isinstance(p, dict) and p.get("kode") and p.get("kode") not in hist_codes:
                    state["history_produk_tampil"].append(p)
                    hist_codes.add(p.get("kode"))

            if len(action_res.produk_list) == 1:
                state["produk_terakhir_dibahas"] = action_res.produk_list[0].get("kode")
        elif action_res.fakta.get("rujukan_dipakai"):
            rujukan_list = action_res.fakta.get("rujukan_dipakai")
            if rujukan_list and len(rujukan_list) == 1:
                state["produk_terakhir_dibahas"] = rujukan_list[0]

        # ---------------------------------------------------------------------
        # 4. GENERATOR LLM & 5. PEMERIKSA GROUNDING
        # ---------------------------------------------------------------------
        # Siapkan riwayat yang SUDAH memuat pesan giliran ini (maks 8 entri)
        current_history = list(history)
        current_history.append({"role": "user", "content": pesan_pelanggan, "text": pesan_pelanggan})
        history_8 = current_history[-8:]

        t_gen_0 = time.perf_counter()
        gen_out, gen_metrics = generate_response(
            aksi=parsed.aksi.value,
            fakta=action_res.fakta,
            state=state,
            history=history_8,
            pesan_pelanggan=pesan_pelanggan
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
                history=history_8,
                pesan_pelanggan=pesan_pelanggan,
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
        if action_res.produk_list:
            judul_rek = (action_res.fakta.get("profil") or {}).get("judul")
            kartu_html = format_product_cards_message(action_res.produk_list, judul_rekomendasi=judul_rek)

        # Update riwayat percakapan (maks 8 pesan)
        current_history.append({"role": "assistant", "content": gen_out.teks, "text": gen_out.teks})
        state["history"] = current_history[-8:]

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
            raw_llm_content=parse_metrics.get("raw_content"),
            jalur="model",
            aksi_parser=parsed.aksi.value,
            jenis=(parsed.argumen.jenis.value if hasattr(parsed.argumen.jenis, "value") else str(parsed.argumen.jenis)) if getattr(parsed.argumen, "jenis", None) is not None else None
        )

        return turn_result, state
