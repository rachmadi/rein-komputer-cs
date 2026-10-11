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
from services.catalog_search import clean_specs
from services.knowledge_service import infer_category_from_data
from services.schema_actions import ParserOutput, ActionEnum, ActionArguments, AlasanTidakJelasEnum, JenisEnum
from core.config import KONTAK_STAF

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
    pelanggaran: List[str] = field(default_factory=list)
    is_emergency_fallback: bool = False
    jumlah_retry: int = 0
    kartu_isi: List[Dict[str, Any]] = field(default_factory=list)
    produk_dibahas: Any = None
    produk_dibahas_sebelumnya: List[Dict[str, Any]] = field(default_factory=list)
    catatan_minimum: Any = None
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
    parser_raw: Optional[Any] = None
    kartu_ditampilkan: bool = False
    status_fakta: Optional[str] = None
    state_setelah: Optional[Dict[str, Any]] = None
    permintaan_asli: Optional[Dict[str, Any]] = None
    argumen_ditolak: Optional[List[Dict[str, Any]]] = None
    konteks_toko: Optional[Dict[str, Any]] = None
    fakta_lengkap: Optional[Dict[str, Any]] = None


def match_rule_greeting(pesan_pelanggan: str, history: list[dict] | None = None) -> Optional[Tuple[str, str, str]]:
    """
    Memeriksa apakah pesan sepenuhnya merupakan sapaan atau terima kasih berdasarkan daftar kata tertutup.
    Mengembalikan (route, reply_text, fakta_status) jika cocok, atau None jika tidak.
    Bila riwayat tidak kosong, balasan tanpa 'Selamat datang' dan tanpa salam ulang (cukup tanggapan singkat + ajakan).
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

    has_history = bool(history and len(history) > 0)

    # 1. Cek apakah SELURUH kata termasuk dalam sapaan
    if all(w in sapaan_words for w in words) and any(w in greeting_roots for w in words):
        if has_history:
            if "assalamualaikum" in words:
                reply = "Waalaikumsalam, Kak! Ada yang bisa kami bantu lagi untuk kebutuhan komputer atau laptopnya?"
            else:
                reply = "Iya, Kak! Ada kebutuhan komputer atau laptop yang bisa kami bantu carikan lagi?"
        else:
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


def update_product_focus(state: dict, action_res=None, gen_out=None, catalog=None) -> None:
    """Memperbarui state['produk_dibahas'] dan tumpukan state['produk_dibahas_sebelumnya'] (Putaran 13 Butir B)."""
    new_focus_codes = []

    # 1. Dari keluaran generator (bisa nama produk atau kode)
    if gen_out and gen_out.produk_dibahas:
        raw_db = gen_out.produk_dibahas
        if isinstance(raw_db, str):
            raw_db = [raw_db]
        for item in raw_db:
            if not item:
                continue
            item_str = str(item).strip()
            p = None
            if catalog:
                if hasattr(catalog, "get_by_code"):
                    p = catalog.get_by_code(item_str)
                elif hasattr(catalog, "by_code"):
                    p = catalog.by_code.get(item_str.upper()) or catalog.by_code.get(item_str)
            if p and p.get("kode"):
                if p["kode"] not in new_focus_codes:
                    new_focus_codes.append(p["kode"])
            else:
                matched_c = None
                for pt in state.get("produk_tampil", []):
                    if isinstance(pt, dict) and (item_str.lower() in str(pt.get("nama", "")).lower() or item_str.lower() == str(pt.get("kode", "")).lower()):
                        matched_c = pt.get("kode")
                        break
                if matched_c and matched_c not in new_focus_codes:
                    new_focus_codes.append(matched_c)
                elif catalog:
                    for cp in catalog.products:
                        if item_str.lower() in str(cp.get("nama", "")).lower():
                            if cp.get("kode") not in new_focus_codes:
                                new_focus_codes.append(cp.get("kode"))
                            break

    # 2. Jika belum ada dari generator, cek rujukan_dipakai di fakta atau aksi
    if not new_focus_codes and action_res and getattr(action_res, "fakta", None):
        rujukan = action_res.fakta.get("rujukan_dipakai")
        if rujukan:
            if isinstance(rujukan, list):
                new_focus_codes = [c for c in rujukan if c]
            elif isinstance(rujukan, str):
                new_focus_codes = [rujukan]
        elif action_res.fakta.get("produk_termurah"):
            pt_code = action_res.fakta["produk_termurah"].get("kode")
            if pt_code:
                new_focus_codes = [pt_code]
        elif action_res.fakta.get("kode_produk"):
            new_focus_codes = [action_res.fakta["kode_produk"]]
        elif len(action_res.produk_list or []) == 1:
            one_c = action_res.produk_list[0].get("kode")
            if one_c:
                new_focus_codes = [one_c]

    # Batasi 1-3 kode
    new_focus_codes = [c.upper() for c in new_focus_codes if c][:3]

    current_focus = state.get("produk_dibahas") or []
    if new_focus_codes and new_focus_codes != current_focus:
        if current_focus:
            prev_stack = list(state.get("produk_dibahas_sebelumnya") or [])
            # Dedupe: buang jika entri dengan set kode yang sama sudah ada
            prev_stack = [e for e in prev_stack if set(e.get("kode", [])) != set(current_focus)]
            hist_len = len(state.get("history", []))
            turn_num = (hist_len // 2) + 1
            prev_stack.insert(0, {
                "kode": list(current_focus),
                "label_kebutuhan": state.get("kebutuhan_teks") or "",
                "giliran": turn_num
            })
            state["produk_dibahas_sebelumnya"] = prev_stack[:5]

        state["produk_dibahas"] = new_focus_codes
        state["produk_terakhir_dibahas"] = new_focus_codes[0] if len(new_focus_codes) == 1 else new_focus_codes


def strip_repeated_opening_interjection(reply_text: str, history: list[dict] | None) -> str:
    """
    Putaran 13 Butir G:
    Pasca-proses deterministik: jika balasan dibuka dengan kata seru yang sama dengan salah satu
    dari 3 balasan bot terakhir (pembuka_terakhir), buang kata seru itu sampai koma pertama.
    """
    if not reply_text or not history:
        return reply_text

    bot_replies = [
        h.get("content") or h.get("text") or ""
        for h in history
        if h.get("role") in ("assistant", "bot")
    ]
    last_3 = bot_replies[-3:]
    if not last_3:
        return reply_text

    KATA_SERU = {
        "baik", "tentu", "wah", "siap", "halo", "hai", "oke", "ok",
        "nah", "oh", "ya", "iya", "aduh", "sip", "mantap", "hebat"
    }

    def get_opening_interjection(text: str) -> str | None:
        t = text.strip()
        m = re.match(r"^([a-zA-Z]+)\s*,\s*", t)
        if m:
            w = m.group(1).lower()
            if w in KATA_SERU:
                return w
        return None

    past_openings = set()
    for br in last_3:
        op = get_opening_interjection(br)
        if op:
            past_openings.add(op)

    current_op = get_opening_interjection(reply_text)
    if current_op and current_op in past_openings:
        m = re.match(r"^[a-zA-Z]+\s*,\s*(.*)$", reply_text.strip(), flags=re.DOTALL)
        if m:
            remainder = m.group(1).strip()
            if remainder:
                return remainder[:1].upper() + remainder[1:]

    return reply_text


class SessionPipeline:
    def __init__(self, action_engine: ActionEngine | None = None):
        self.action_engine = action_engine or ActionEngine()
        self.grounding_checker = GroundingChecker()

    @property
    def catalog(self):
        return getattr(self.action_engine, "catalog", None)

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
        rule_match = match_rule_greeting(pesan_pelanggan, history=history)
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
                jenis=None,
                parser_raw=None,
                kartu_ditampilkan=False,
                status_fakta=r_status,
                state_setelah={
                    "kategori": state.get("kategori"),
                    "merek": state.get("merek"),
                    "kebutuhan_teks": state.get("kebutuhan_teks"),
                    "budget": state.get("budget"),
                },
                is_emergency_fallback=False,
                jumlah_retry=0,
                pelanggaran=[],
                kartu_isi=[],
                produk_dibahas=state.get("produk_dibahas"),
                produk_dibahas_sebelumnya=state.get("produk_dibahas_sebelumnya", []),
                catatan_minimum=None,
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

        # B2: Deteksi kategori yang diminta pada giliran ini & reset state saat kategori berganti
        from services.validator import get_catalog_categories, get_catalog_brands, is_valid_kebutuhan_teks
        catalog_cats = set(get_catalog_categories())
        catalog_brands = set(get_catalog_brands())

        kontrak = getattr(parsed, "kontrak_intent", None) or {}
        arg_ditolak = kontrak.get("argumen_ditolak", [])
        has_rejected_kat = any(d.get("field") == "kategori" for d in arg_ditolak)

        detected_kategori = None
        is_sys_err = (parsed.aksi == ActionEnum.TIDAK_JELAS and getattr(parsed.argumen, "alasan", None) == AlasanTidakJelasEnum.SISTEM_ERROR)
        if not is_sys_err and not has_rejected_kat:
            if parsed.argumen.kategori and parsed.argumen.kategori.lower() in catalog_cats:
                detected_kategori = parsed.argumen.kategori.lower()
            elif parsed.pembaruan_state.kategori and parsed.pembaruan_state.kategori.lower() in catalog_cats:
                detected_kategori = parsed.pembaruan_state.kategori.lower()
            else:
                inferred = infer_category_from_data(pesan_pelanggan, self.catalog)
                if inferred and inferred.lower() in catalog_cats:
                    detected_kategori = inferred.lower()

        if detected_kategori:
            parsed.argumen.kategori = detected_kategori
            old_kat_str = str(state.get("kategori", "")).strip().lower() if state.get("kategori") else None

            # Saat kategori berganti, reset merek, kebutuhan_teks, produk_tampil, filter spesifikasi, dan budget
            # (kecuali disebut lagi di pesan yang sama). Merek yang disebut eksplisit menggantikan yang lama.
            if old_kat_str and detected_kategori != old_kat_str:
                state["kategori"] = detected_kategori

                # Merek eksplisit di pesan yang sama
                merek_eksplisit = None
                if parsed.argumen.merek and parsed.argumen.merek.lower() in catalog_brands:
                    merek_eksplisit = parsed.argumen.merek.lower()
                elif parsed.pembaruan_state.merek and parsed.pembaruan_state.merek.lower() in catalog_brands:
                    merek_eksplisit = parsed.pembaruan_state.merek.lower()
                else:
                    for b in catalog_brands:
                        if re.search(r"\b" + re.escape(b) + r"\b", pesan_pelanggan, re.IGNORECASE):
                            merek_eksplisit = b
                            break

                if merek_eksplisit:
                    state["merek"] = merek_eksplisit
                    parsed.argumen.merek = merek_eksplisit
                    if "kriteria_pelanggan" not in state or not isinstance(state["kriteria_pelanggan"], dict):
                        state["kriteria_pelanggan"] = {}
                    state["kriteria_pelanggan"]["merek"] = merek_eksplisit
                else:
                    state["merek"] = None
                    parsed.argumen.merek = None
                    parsed.pembaruan_state.merek = None
                    if "kriteria_pelanggan" in state and isinstance(state["kriteria_pelanggan"], dict):
                        state["kriteria_pelanggan"].pop("merek", None)

                # Budget di pesan yang sama
                from services.catalog_search import parse_budget_from_text
                b_text = parse_budget_from_text(pesan_pelanggan)
                if b_text:
                    state["budget"] = b_text
                    parsed.argumen.max_harga = b_text
                    if "kriteria_pelanggan" not in state or not isinstance(state["kriteria_pelanggan"], dict):
                        state["kriteria_pelanggan"] = {}
                    state["kriteria_pelanggan"]["max_harga"] = b_text
                else:
                    state["budget"] = None
                    parsed.argumen.max_harga = None
                    parsed.pembaruan_state.budget = None
                    if "kriteria_pelanggan" in state and isinstance(state["kriteria_pelanggan"], dict):
                        state["kriteria_pelanggan"].pop("max_harga", None)

                # Kebutuhan di pesan yang sama
                m_keb = re.search(r"(?:dipakai|buat|untuk|kebutuhan)\s+([a-zA-Z0-9\s\+\#]{4,40}?)(?:\s+apakah|\s+bisa|\s+kuat|\?|$)", pesan_pelanggan, re.IGNORECASE)
                if m_keb and len(m_keb.group(1).strip()) >= 4 and is_valid_kebutuhan_teks(m_keb.group(1).strip()):
                    state["kebutuhan_teks"] = m_keb.group(1).strip()
                    parsed.argumen.kebutuhan_teks = state["kebutuhan_teks"]
                else:
                    state["kebutuhan_teks"] = None
                    parsed.argumen.kebutuhan_teks = None
                    parsed.pembaruan_state.kebutuhan_teks = None

                # Reset produk_tampil & filter spesifikasi
                state["produk_tampil"] = []
                state["produk_terakhir_dibahas"] = None
                state["history_produk_tampil"] = []
                state["produk_dibahas"] = []
                state["produk_dibahas_sebelumnya"] = []
                state["profil_aktif"] = None
                state["batas_bot"] = {}
                state["kriteria_pelanggan"] = {
                    k: v for k, v in state.get("kriteria_pelanggan", {}).items()
                    if k in ("kategori", "merek", "max_harga")
                }
                state["kriteria_pelanggan"]["kategori"] = detected_kategori
            else:
                state["kategori"] = detected_kategori

        # C2: Pertanyaan "ada X?" dengan kategori eksplisit = pencarian, bukan perbaikan
        is_tanya_kategori = bool(
            detected_kategori and (
                re.search(r"\b(ada|tersedia|punya|jual|stok|ready)\b", pesan_pelanggan, re.IGNORECASE)
                or re.search(r"\b(apa\s*gak|apa\s*nggak|apa\s*tidak)\b", pesan_pelanggan, re.IGNORECASE)
            )
        )
        if is_tanya_kategori and parsed.aksi == ActionEnum.PERBAIKI_PERCAKAPAN:
            is_keluhan_tone = (
                getattr(parsed.argumen, "jenis", None) in ("keluhan", JenisEnum.KELUHAN)
                or bool(re.search(r"\b(kok|capek|kecewa|kesal|lelet|gimana sih)\b", pesan_pelanggan, re.IGNORECASE))
            )
            parsed.aksi = ActionEnum.CARI_PRODUK
            parsed.argumen.kategori = detected_kategori
            if is_keluhan_tone:
                state["_ada_keluhan_pesan"] = True

        # E3: Deteksi jika pesan pelanggan membawa kebutuhan komputasi baru yang belum terisi di argumen
        if not parsed.argumen.kebutuhan_teks and parsed.aksi in (ActionEnum.EVALUASI_KECOCOKAN, ActionEnum.MINTA_REKOMENDASI):
            m_keb = re.search(r"(?:dipakai|buat|untuk|kebutuhan)\s+([a-zA-Z0-9\s\+\#]{4,40}?)(?:\s+apakah|\s+bisa|\s+kuat|\?|$)", pesan_pelanggan, re.IGNORECASE)
            if m_keb:
                extracted_keb = m_keb.group(1).strip()
                if len(extracted_keb) >= 4 and is_valid_kebutuhan_teks(extracted_keb):
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

        # Deteksi pencabutan batasan budget (Butir 13)
        # Jika pelanggan bilang 'tanpa batas budget', 'bebas budget', 'budget dilepas', dsb.
        # atau parser mengirim budget=0 / -1 untuk mencabut batasan budget
        is_cabut_budget = bool(
            re.search(r"\b(tanpa|bebas|lepas|hilangkan|hapus|nggak\s+pakai|tidak\s+pakai|ga\s+pakai|unlimited)\s+(batas\s+|batasan\s+)?(budget|anggaran|biaya)\b", pesan_pelanggan, re.IGNORECASE)
            or re.search(r"\b(budget|anggaran|biaya)\s+(bebas|tanpa\s+batas|dihapus|dilepas|tidak\s+terbatas|unlimited)\b", pesan_pelanggan, re.IGNORECASE)
            or (parsed.pembaruan_state.budget in (0, -1))
            or (parsed.argumen.max_harga in (0, -1))
            or (parsed.argumen.budget_max in (0, -1))
        )

        if is_cabut_budget:
            state["budget"] = None
            state["_cabut_budget"] = True
            if "kriteria_pelanggan" in state and isinstance(state["kriteria_pelanggan"], dict):
                state["kriteria_pelanggan"].pop("max_harga", None)
            if "batas_bot" in state and isinstance(state["batas_bot"], dict):
                state["batas_bot"].pop("max_harga", None)
            parsed.argumen.max_harga = None
            parsed.argumen.budget_max = None
            parsed.pembaruan_state.budget = None
        else:
            if not parsed.argumen.max_harga and not parsed.pembaruan_state.budget:
                from services.catalog_search import parse_budget_from_text
                b_text = parse_budget_from_text(pesan_pelanggan)
                if b_text:
                    parsed.argumen.max_harga = b_text
                    parsed.argumen.budget_max = b_text
                    parsed.pembaruan_state.budget = b_text

            if parsed.argumen.max_harga is not None:
                state["kriteria_pelanggan"]["max_harga"] = parse_int_safe(parsed.argumen.max_harga)
                state["budget"] = parse_int_safe(parsed.argumen.max_harga)
            elif parsed.pembaruan_state.budget is not None:
                state["kriteria_pelanggan"]["max_harga"] = parsed.pembaruan_state.budget
                state["budget"] = parsed.pembaruan_state.budget

        if parsed.argumen.merek:
            m_clean = str(parsed.argumen.merek).lower().strip()
            if m_clean in catalog_brands:
                state["kriteria_pelanggan"]["merek"] = m_clean
                state["merek"] = m_clean
            else:
                logger.warning(f"B1: Merek tak dikenal diabaikan dari argumen: '{parsed.argumen.merek}'")
        elif parsed.pembaruan_state.merek:
            m_clean = str(parsed.pembaruan_state.merek).lower().strip()
            if m_clean in catalog_brands:
                state["kriteria_pelanggan"]["merek"] = m_clean
                state["merek"] = m_clean
            else:
                logger.warning(f"B1: Merek tak dikenal diabaikan dari pembaruan_state: '{parsed.pembaruan_state.merek}'")
        if parsed.argumen.kategori:
            state["kriteria_pelanggan"]["kategori"] = parsed.argumen.kategori
        if parsed.argumen.kebutuhan_teks:
            if is_valid_kebutuhan_teks(parsed.argumen.kebutuhan_teks):
                state["kriteria_pelanggan"]["kebutuhan_teks"] = parsed.argumen.kebutuhan_teks
            else:
                parsed.argumen.kebutuhan_teks = None
        if parsed.argumen.ram_gb_min:
            state["kriteria_pelanggan"]["ram_gb_min"] = parsed.argumen.ram_gb_min

        # ---------------------------------------------------------------------
        # 3. MESIN DETERMINISTIK
        # ---------------------------------------------------------------------
        state["_pesan_pelanggan"] = pesan_pelanggan
        t_engine_0 = time.perf_counter()
        action_res: ActionResult = self.action_engine.execute(parsed, session_state=state)
        lat_mesin = (time.perf_counter() - t_engine_0) * 1000.0
        state.pop("_pesan_pelanggan", None)
        if state.pop("_ada_keluhan_pesan", None):
            action_res.fakta["ada_keluhan"] = True
            action_res.fakta["nada"] = "keluhan"

        # Update state dari argumen & pembaruan_state parser
        state.pop("_cabut_budget", None)
        if is_cabut_budget:
            state["budget"] = None
            if "kriteria_pelanggan" in state and isinstance(state["kriteria_pelanggan"], dict):
                state["kriteria_pelanggan"].pop("max_harga", None)
            if "batas_bot" in state and isinstance(state["batas_bot"], dict):
                state["batas_bot"].pop("max_harga", None)
        else:
            if parsed.argumen.max_harga is not None:
                state["budget"] = parse_int_safe(parsed.argumen.max_harga)

        if parsed.argumen.merek:
            state["merek"] = parsed.argumen.merek
        if parsed.argumen.kategori:
            state["kategori"] = parsed.argumen.kategori
        if parsed.argumen.persona:
            state["persona"] = parsed.argumen.persona
        if parsed.argumen.kebutuhan_teks:
            if is_valid_kebutuhan_teks(parsed.argumen.kebutuhan_teks):
                state["kebutuhan_teks"] = parsed.argumen.kebutuhan_teks
        if parsed.argumen.slot and parsed.argumen.nilai:
            slot_name = parsed.argumen.slot.value if hasattr(parsed.argumen.slot, "value") else str(parsed.argumen.slot)
            if slot_name in ("kebutuhan", "aktivitas") and not is_valid_kebutuhan_teks(parsed.argumen.nilai):
                pass
            else:
                state[slot_name] = parsed.argumen.nilai

        state_up = parsed.pembaruan_state
        if state_up.persona:
            state["persona"] = state_up.persona
        if state_up.sebutan:
            state["sebutan"] = state_up.sebutan
        if state_up.kebutuhan_teks:
            if is_valid_kebutuhan_teks(state_up.kebutuhan_teks):
                state["kebutuhan_teks"] = state_up.kebutuhan_teks
        if not is_cabut_budget and state_up.budget:
            state["budget"] = state_up.budget
        if state_up.kategori:
            state["kategori"] = state_up.kategori
        if state_up.merek:
            state["merek"] = state_up.merek
        if action_res.profil_id:
            state["profil_aktif"] = action_res.profil_id

        # Putaran 13b Butir 2: Budget sebagai filter keras pada produk_tampil & kartu
        cur_budget = state.get("budget")
        if cur_budget and isinstance(cur_budget, (int, float)) and cur_budget > 0:
            if action_res.produk_list:
                action_res.produk_list = [
                    p for p in action_res.produk_list
                    if (p.get("harga") or p.get("harga_idr") or 0) <= cur_budget
                ]
            if state.get("produk_tampil"):
                state["produk_tampil"] = [
                    p for p in state["produk_tampil"]
                    if (p.get("harga") or p.get("harga_idr") or 0) <= cur_budget
                ]

        # Simpan produk yang tampil jika aksi menghasilkan produk
        if action_res.produk_list:
            if action_res.fakta.get("jenis_lanjutan") != "termurah_dari_tampil":
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

        # Update pelacakan produk dari hasil aksi mesin (Putaran 13 Butir B)
        update_product_focus(state, action_res=action_res, catalog=getattr(self.action_engine, "catalog", None))

        # ---------------------------------------------------------------------
        # 3b. PENGHITUNG KELUHAN & TANYA BERUNTUN (Butir 10)
        # ---------------------------------------------------------------------
        keluhan_beruntun = int(state.get("keluhan_beruntun", 0) or 0)
        tanya_beruntun = int(state.get("tanya_beruntun", 0) or 0)

        is_keluhan = (
            parsed.aksi == ActionEnum.PERBAIKI_PERCAKAPAN
            and (getattr(parsed.argumen, "jenis", None) in ("keluhan", JenisEnum.KELUHAN)
                 or "keluhan" in str(getattr(parsed.argumen, "rujukan", "")).lower())
        )

        has_clear_direction = bool(
            (action_res.produk_list and len(action_res.produk_list) > 0)
            or (parsed.argumen.kebutuhan_teks and len(parsed.argumen.kebutuhan_teks.strip()) >= 4)
            or (parsed.aksi in (ActionEnum.CARI_PRODUK, ActionEnum.MINTA_REKOMENDASI) and (parsed.argumen.merek or parsed.argumen.kategori or parsed.argumen.max_harga))
        )

        if is_keluhan:
            keluhan_beruntun += 1
        elif has_clear_direction:
            keluhan_beruntun = 0

        # Putaran 13 Butir F: Pelacakan pertanyaan slot berulang (budget & kebutuhan)
        tanya_budget_beruntun = int(state.get("tanya_budget_beruntun", 0) or 0)
        tanya_kebutuhan_beruntun = int(state.get("tanya_kebutuhan_beruntun", 0) or 0)

        # Cek apakah budget atau kebutuhan dijawab pada giliran ini
        from services.catalog_search import parse_budget_from_text
        pesan_has_budget = bool(parse_budget_from_text(pesan_pelanggan) is not None or parsed.argumen.max_harga is not None)
        pesan_has_kebutuhan = bool(parsed.argumen.kebutuhan_teks and len(parsed.argumen.kebutuhan_teks.strip()) >= 4)

        if pesan_has_budget or state.get("budget") is not None or state.get("_cabut_budget"):
            tanya_budget_beruntun = 0
        if pesan_has_kebutuhan or (state.get("kebutuhan_teks") and not action_res.fakta.get("status") in ("tanya_kebutuhan", "profil_tidak_ditemukan")):
            tanya_kebutuhan_beruntun = 0

        prev_asked = state.get("pending_question") or state.get("last_asked_slot")

        # Deteksi apakah giliran ini menanyakan budget
        is_asking_budget = (
            (prev_asked == "budget" and not pesan_has_budget)
            or action_res.fakta.get("status") in ("tidak_ada_dalam_anggaran", "tanya_budget")
            or (state.get("kebutuhan_teks") and state.get("budget") is None and not state.get("_cabut_budget") and action_res.aksi in (ActionEnum.MINTA_REKOMENDASI, ActionEnum.CARI_PRODUK))
        )
        if is_asking_budget and not (pesan_has_budget or state.get("_cabut_budget")):
            tanya_budget_beruntun += 1
        else:
            tanya_budget_beruntun = 0

        # Deteksi apakah giliran ini menanyakan kebutuhan
        is_asking_kebutuhan = (
            action_res.fakta.get("status") in ("tanya_kebutuhan", "profil_tidak_ditemukan")
            or (prev_asked in ("kebutuhan", "aktivitas") and not pesan_has_kebutuhan)
            or (not state.get("kebutuhan_teks") and action_res.aksi in (ActionEnum.MINTA_REKOMENDASI, ActionEnum.CARI_PRODUK))
        )
        if is_asking_kebutuhan and not pesan_has_kebutuhan:
            tanya_kebutuhan_beruntun += 1
        else:
            tanya_kebutuhan_beruntun = 0

        # tanya_beruntun umum
        if has_clear_direction:
            tanya_beruntun = 0
        else:
            if action_res.fakta.get("status") in ("tanya_kebutuhan", "profil_tidak_ditemukan", "tidak_jelas") or parsed.aksi in (ActionEnum.JAWAB_PERTANYAAN_BOT, ActionEnum.TIDAK_JELAS):
                tanya_beruntun += 1
            else:
                tanya_beruntun = 0

        # Trigger jika mencapai ambang batas
        if keluhan_beruntun >= 2:
            action_res.fakta["tawarkan_staf"] = True
            action_res.fakta["kontak_staf"] = KONTAK_STAF

        kat_aktif = state.get("kategori")
        if tanya_budget_beruntun >= 3:
            if kat_aktif == "printer":
                action_res.fakta["pilihan_konkret"] = [
                    "Di bawah Rp2 juta",
                    "Rp2 juta - Rp4 juta",
                    "Di atas Rp4 juta"
                ]
            else:
                action_res.fakta["pilihan_konkret"] = [
                    "Di bawah Rp7 juta",
                    "Rp7 juta - Rp12 juta",
                    "Di atas Rp12 juta"
                ]
        elif (tanya_kebutuhan_beruntun >= 3) or (tanya_beruntun >= 2 and not action_res.produk_list):
            if kat_aktif == "printer":
                action_res.fakta["pilihan_konkret"] = [
                    "Cetak Dokumen & Tugas Harian",
                    "Cetak Foto & Stiker Warna",
                    "Cetak Volume Tinggi & Usaha"
                ]
            else:
                profiles_raw = []
                try:
                    from services.knowledge_service import get_all_profiles
                    profiles_raw = get_all_profiles()
                except Exception:
                    pass
                pilihan = []
                for pr in profiles_raw:
                    j = pr.get("judul") or pr.get("nama")
                    if j:
                        j_clean = re.sub(r"^[A-Z]\d{2}\s*[-–—:]\s*", "", str(j)).strip()
                        if j_clean and j_clean not in pilihan:
                            pilihan.append(j_clean)
                        if len(pilihan) >= 3:
                            break
                if not pilihan:
                    pilihan = [
                        "Kantoran, Belajar, dan Penggunaan Harian",
                        "Desain Grafis dan Ilustrasi Digital",
                        "Gaming dan Pemrosesan Grafis Berat"
                    ]
                action_res.fakta["pilihan_konkret"] = pilihan[:3]

        state["keluhan_beruntun"] = keluhan_beruntun
        state["tanya_beruntun"] = tanya_beruntun
        state["tanya_budget_beruntun"] = tanya_budget_beruntun
        state["tanya_kebutuhan_beruntun"] = tanya_kebutuhan_beruntun

        # ---------------------------------------------------------------------
        # 4. GENERATOR LLM & 5. PEMERIKSA GROUNDING
        # ---------------------------------------------------------------------
        # Siapkan riwayat yang SUDAH memuat pesan giliran ini (maks 8 entri)
        current_history = list(history)
        current_history.append({"role": "user", "content": pesan_pelanggan, "text": pesan_pelanggan})
        history_8 = current_history[-8:]

        retried_count = 0
        # B10 & Butir 8: Teks darurat B13 HANYA untuk sistem_error (Ollama gagal)
        if action_res.fakta.get("status") == "sistem_error" or action_res.fakta.get("alasan") == "sistem_error":
            t_gen_0 = time.perf_counter()
            gen_out = GeneratorOutput(teks=EMERGENCY_FALLBACK_TEXT, pertanyaan_diajukan=None)
            gen_metrics = {}
            is_valid, violations = True, []
            is_fallback = True
        else:
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
            retried_count = 1
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

        # Putaran 13 Butir G: Pasca-proses deterministik pembersihan kata seru pembuka berulang
        gen_out.teks = strip_repeated_opening_interjection(gen_out.teks, history=history_8)

        # Putaran 13b Butir 1: Jaring pengaman kebocoran kriteria teknis internal
        LEAK_PATTERNS = ["(got ", ">=", "<=", "cpu_tier", "ram_gb", "storage_ssd_gb", "vram_gb", "gpu_dedicated"]
        if any(p in gen_out.teks for p in LEAK_PATTERNS):
            logger.warning("Jaring pengaman aktif: Kebocoran teks internal terdeteksi pada balasan. Mengganti dengan jawaban deterministik.")
            violations.append("Kebocoran teks internal: mengandung kriteria teknis internal")
            is_fallback = True
            clean_fallback = build_deterministic_fallback_text(parsed.aksi.value, action_res.fakta)
            if any(p in clean_fallback for p in LEAK_PATTERNS):
                clean_fallback = "Saat ini belum ada produk yang memenuhi seluruh spesifikasi minimum yang dibutuhkan, Kak. Silakan konsultasikan kebutuhan Kakak dengan staf kami di kontak berikut."
            gen_out.teks = clean_fallback

        # Update pending_question di state sesuai keluaran generator
        state["pending_question"] = gen_out.pertanyaan_diajukan
        if gen_out.pertanyaan_diajukan:
            state["last_asked_slot"] = gen_out.pertanyaan_diajukan
            if gen_out.pertanyaan_diajukan == "budget":
                state["tanya_budget_beruntun"] = max(1, int(state.get("tanya_budget_beruntun", 0) or 0))
            elif gen_out.pertanyaan_diajukan in ("kebutuhan", "aktivitas"):
                state["tanya_kebutuhan_beruntun"] = max(1, int(state.get("tanya_kebutuhan_beruntun", 0) or 0))

        # ---------------------------------------------------------------------
        # 6. KARTU PRODUK HTML (Butir 4)
        # ---------------------------------------------------------------------
        kartu_html = None
        
        # Ekstrak semua kode produk yang secara sah ada di fakta eksekusi
        fakta_codes = set()
        for p in action_res.fakta.get("produk", []):
            if isinstance(p, dict) and p.get("kode"):
                fakta_codes.add(p["kode"])
            elif isinstance(p, str):
                fakta_codes.add(p)
        for p in action_res.fakta.get("alternatif_cocok", []):
            if isinstance(p, dict) and p.get("kode"):
                fakta_codes.add(p["kode"])
            elif isinstance(p, str):
                fakta_codes.add(p)
        for p in action_res.fakta.get("spesifikasi_produk", []):
            if isinstance(p, dict) and p.get("kode"):
                fakta_codes.add(p["kode"])
        for p in action_res.fakta.get("spesifikasi", []):
            if isinstance(p, dict) and p.get("kode"):
                fakta_codes.add(p["kode"])
        for p in action_res.fakta.get("perbandingan", []):
            if isinstance(p, dict) and p.get("kode"):
                fakta_codes.add(p["kode"])
        if action_res.fakta.get("rujukan_dipakai"):
            for c in action_res.fakta.get("rujukan_dipakai"):
                if c:
                    fakta_codes.add(c)
        if action_res.fakta.get("kode_produk"):
            fakta_codes.add(action_res.fakta["kode_produk"])

        raw_candidates = list(action_res.produk_list or [])
        if action_res.fakta.get("alternatif_cocok"):
            for alt in action_res.fakta["alternatif_cocok"]:
                if alt not in raw_candidates:
                    raw_candidates.append(alt)
        if not raw_candidates and action_res.fakta.get("produk"):
            catalog = getattr(self.action_engine, "catalog", None)
            if catalog:
                for fp in action_res.fakta.get("produk"):
                    c_code = fp.get("kode") if isinstance(fp, dict) else fp
                    p_obj = catalog.get_by_code(c_code)
                    if p_obj:
                        raw_candidates.append(p_obj)

        # Kode merakit kartu HANYA untuk kode yang ada di fakta
        valid_products = [
            p for p in raw_candidates
            if (p.get("kode") in fakta_codes if fakta_codes else True)
        ]
        if cur_budget and isinstance(cur_budget, (int, float)) and cur_budget > 0:
            valid_products = [
                p for p in valid_products
                if (p.get("harga") or p.get("harga_idr") or 0) <= cur_budget
            ]

        aksi_name = parsed.aksi.value if hasattr(parsed.aksi, "value") else str(parsed.aksi)
        should_show_card = False

        if action_res.fakta.get("tampilkan_kartu") is True:
            should_show_card = True
        elif aksi_name in ("tanya_spesifikasi", "bandingkan"):
            should_show_card = True
        elif aksi_name in ("cari_produk", "minta_rekomendasi"):
            if gen_out.tampilkan_kartu is not None:
                should_show_card = bool(gen_out.tampilkan_kartu)
            else:
                should_show_card = bool(valid_products)
        elif action_res.produk_list:
            if gen_out.tampilkan_kartu is not None:
                should_show_card = bool(gen_out.tampilkan_kartu)
            else:
                should_show_card = bool(valid_products)
        else:
            if gen_out.tampilkan_kartu is True:
                should_show_card = True
            else:
                should_show_card = False

        if should_show_card and valid_products:
            prods_to_card = valid_products
            if gen_out.produk_dibahas:
                dibahas_code = gen_out.produk_dibahas
                if isinstance(dibahas_code, str):
                    matched = [p for p in valid_products if p.get("kode") == dibahas_code]
                    if matched:
                        prods_to_card = matched
                elif isinstance(dibahas_code, list):
                    matched = [p for p in valid_products if p.get("kode") in dibahas_code]
                    if matched:
                        prods_to_card = matched

            raw_judul = (action_res.fakta.get("profil") or {}).get("judul")
            judul_rek = None
            if raw_judul:
                judul_rek = re.sub(r"^[A-Z]\d{2}\s*[-–—:]\s*", "", str(raw_judul)).strip()
            kartu_html = format_product_cards_message(prods_to_card, judul_rekomendasi=judul_rek)

        # Update pelacakan produk setelah generator selesai (Putaran 13 Butir B)
        update_product_focus(state, action_res=action_res, gen_out=gen_out, catalog=getattr(self.action_engine, "catalog", None))

        # Update riwayat percakapan (maks 8 pesan)
        current_history.append({"role": "assistant", "content": gen_out.teks, "text": gen_out.teks})
        state["history"] = current_history[-8:]

        # Rangkum kartu_isi jika kartu ditampilkan (kode + atribut tampil)
        kartu_isi_list = []
        if should_show_card and valid_products:
            for p in prods_to_card:
                if isinstance(p, dict):
                    kartu_isi_list.append({
                        "kode": p.get("kode"),
                        "nama": p.get("nama"),
                        "harga": p.get("harga") or p.get("harga_idr"),
                        "spesifikasi": p.get("spesifikasi") or clean_specs(p)
                    })

        # Rangkum catatan_minimum dari fakta
        catatan_min_data = action_res.fakta.get("catatan_minimum")
        if not catatan_min_data:
            c_prods = action_res.fakta.get("produk") or action_res.fakta.get("evaluasi_produk") or []
            if isinstance(c_prods, list) and c_prods:
                catatan_min_data = [
                    {"kode": cp.get("kode"), "catatan_minimum": cp.get("catatan_minimum")}
                    for cp in c_prods if isinstance(cp, dict) and cp.get("catatan_minimum")
                ]

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
            pelanggaran=violations,
            is_emergency_fallback=is_fallback,
            jumlah_retry=retried_count,
            kartu_isi=kartu_isi_list,
            produk_dibahas=state.get("produk_dibahas"),
            produk_dibahas_sebelumnya=state.get("produk_dibahas_sebelumnya", []),
            catatan_minimum=catatan_min_data,
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
            jenis=(parsed.argumen.jenis.value if hasattr(parsed.argumen.jenis, "value") else str(parsed.argumen.jenis)) if getattr(parsed.argumen, "jenis", None) is not None else None,
            parser_raw=parse_metrics.get("parser_raw") or parse_metrics.get("raw_content"),
            kartu_ditampilkan=bool(kartu_html is not None and len(str(kartu_html).strip()) > 0),
            status_fakta=(action_res.fakta.get("status") if action_res and action_res.fakta else None),
            state_setelah={
                "kategori": state.get("kategori"),
                "merek": state.get("merek"),
                "kebutuhan_teks": state.get("kebutuhan_teks"),
                "budget": state.get("budget"),
            },
            permintaan_asli=kontrak.get("permintaan_asli", {}),
            argumen_ditolak=kontrak.get("argumen_ditolak", []),
            konteks_toko={"kategori_dijual": sorted(list(catalog_cats)), "merek_dijual": sorted(list(catalog_brands))},
            fakta_lengkap=action_res.fakta
        )

        return turn_result, state
