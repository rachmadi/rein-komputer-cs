# -*- coding: utf-8 -*-
"""
services/validator.py
Validator deterministik keluaran Parser LLM untuk Antigravity v2.

Prinsip:
- R2: Hanya memvalidasi skema, tipe, enum tertutup, rentang, dan keberadaan di katalog.
- R3: Tidak menimpa aksi parser dengan aturan bahasa/regex. Jika tidak valid atau di luar enum tertutup,
      hasilnya ditolak dan diubah menjadi `tidak_jelas` dengan alasan eksplisit tertutup (B12).
"""
from __future__ import annotations

import os
import sqlite3
import logging
from typing import Any, List, Dict, Tuple
from pydantic import ValidationError

from services.schema_actions import (
    ParserOutput, ActionEnum, ActionArguments, StateUpdate,
    SlotEnum, JenisEnum, JenisLanjutanEnum, JenisPerbaikanEnum, JenisBasaBasiEnum,
    TokoTopikEnum, AtributSpesifikasiEnum, AlasanTidakJelasEnum
)

logger = logging.getLogger(__name__)

ACTION_JENIS_MAP = {
    ActionEnum.LANJUTAN_HASIL: {e.value for e in JenisLanjutanEnum},
    ActionEnum.PERBAIKI_PERCAKAPAN: {e.value for e in JenisPerbaikanEnum},
    ActionEnum.BASA_BASI: {e.value for e in JenisBasaBasiEnum},
}


def get_catalog_brands(db_path: str | None = None) -> list[str]:
    """Mengambil daftar merek secara dinamis dari database katalog."""
    path = db_path or os.getenv("DB_PATH", "data/catalog.db")
    try:
        if os.path.exists(path):
            conn = sqlite3.connect(path)
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT brand FROM products WHERE brand IS NOT NULL AND brand != ''")
            brands = [r[0].lower().strip() for r in cur.fetchall() if r[0]]
            conn.close()
            if brands:
                return sorted(list(set(brands)))
    except Exception as e:
        logger.warning(f"Gagal memuat merek dinamis: {e}")
    return ["lenovo", "asus", "hp", "acer", "canon", "epson", "brother"]


def get_catalog_categories(db_path: str | None = None) -> list[str]:
    """Mengambil daftar kategori secara dinamis dari database katalog."""
    path = db_path or os.getenv("DB_PATH", "data/catalog.db")
    try:
        if os.path.exists(path):
            conn = sqlite3.connect(path)
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT kategori FROM products WHERE kategori IS NOT NULL AND kategori != ''")
            cats = [r[0].lower().strip() for r in cur.fetchall() if r[0]]
            conn.close()
            if cats:
                return sorted(list(set(cats)))
    except Exception as e:
        logger.warning(f"Gagal memuat kategori dinamis: {e}")
    return ["laptop", "desktop", "printer", "monitor"]


def resolve_product_references(
    produk_refs: List[Any] | None,
    produk_tampil: List[Dict[str, Any]] | None
) -> Tuple[List[str], bool, str | None]:
    """
    Menyelesaikan rujukan_produk (nomor urut, ordinal, harga ekstrim, nama/merek)
    menjadi daftar kode produk katalog dari produk_tampil di state percakapan.

    Mengembalikan: (resolved_codes, is_valid, failed_reference_str)
    Jika rujukan tidak ditemukan atau ambigu, is_valid = False.
    """
    tampil = produk_tampil or []

    if not tampil:
        return [], False, "tidak_ada_produk_tampil"

    # Jika rujukan tidak disertakan tapi aksi produk dipanggil
    if not produk_refs:
        # Default ke seluruh produk yang tampil jika ada
        return [p.get("kode") for p in tampil if p.get("kode")], True, None

    ordinal_map = {
        "1": 0, "pertama": 0, "yang pertama": 0, "kesatu": 0, "no 1": 0, "no. 1": 0, "ke-1": 0,
        "2": 1, "kedua": 1, "yang kedua": 1, "no 2": 1, "no. 2": 1, "ke-2": 1,
        "3": 2, "ketiga": 2, "yang ketiga": 2, "no 3": 2, "no. 3": 2, "ke-3": 2,
    }

    resolved: List[str] = []
    failed_refs: List[str] = []

    for raw_ref in produk_refs:
        if raw_ref is None:
            continue

        # Jika tipe integer (1, 2, 3)
        if isinstance(raw_ref, int):
            idx = raw_ref - 1
            if 0 <= idx < len(tampil) and tampil[idx].get("kode"):
                resolved.append(tampil[idx]["kode"])
                continue
            else:
                failed_refs.append(str(raw_ref))
                continue

        ref_clean = str(raw_ref).lower().strip()

        # 1. Rujukan kata kunci 'semua'
        if ref_clean in ("semua", "semuanya", "tampil", "seluruhnya"):
            resolved.extend([p.get("kode") for p in tampil if p.get("kode")])
            continue

        # 2. Rujukan superlativ harga
        if ref_clean in ("paling murah", "yang paling murah", "termurah", "yang termurah", "murah"):
            cheapest = min(tampil, key=lambda p: int(p.get("harga") or p.get("harga_idr") or 0))
            if cheapest.get("kode"):
                resolved.append(cheapest["kode"])
            continue

        if ref_clean in ("paling mahal", "yang paling mahal", "termahal", "yang termahal", "mahal"):
            priciest = max(tampil, key=lambda p: int(p.get("harga") or p.get("harga_idr") or 0))
            if priciest.get("kode"):
                resolved.append(priciest["kode"])
            continue

        # 3. Rujukan ordinal / nomor digit
        matched = False
        if ref_clean.isdigit():
            idx = int(ref_clean) - 1
            if 0 <= idx < len(tampil) and tampil[idx].get("kode"):
                resolved.append(tampil[idx]["kode"])
                matched = True
        else:
            for ord_key, idx in ordinal_map.items():
                if ref_clean == ord_key or f"yang {ord_key}" in ref_clean:
                    if idx < len(tampil) and tampil[idx].get("kode"):
                        resolved.append(tampil[idx]["kode"])
                        matched = True
                        break

        if matched:
            continue

        # 4. Rujukan nama / merek / kode produk
        search_kw = ref_clean.replace("yang", "").replace("tadi", "").replace("itu", "").strip()
        matched_candidates = []
        for p in tampil:
            p_kode = str(p.get("kode", "")).lower()
            p_nama = str(p.get("nama", "")).lower()
            p_brand = str(p.get("brand", "")).lower()

            if search_kw and (search_kw == p_kode or search_kw == p_brand or search_kw in p_nama):
                matched_candidates.append(p)

        if len(matched_candidates) == 1:
            resolved.append(matched_candidates[0]["kode"])
        elif len(matched_candidates) > 1:
            # Ambigu: ada lebih dari 1 produk yang cocok
            return [], False, "rujukan_ambigu"
        else:
            failed_refs.append(str(raw_ref))

    # Hilangkan duplikasi urut
    seen = set()
    dedup = [x for x in resolved if not (x in seen or seen.add(x))]

    if failed_refs:
        return dedup, False, failed_refs[0] if len(failed_refs) == 1 else "rujukan_tidak_ada"
    if not dedup:
        return [], False, "rujukan_kosong"

    return dedup, True, None


def validate_parser_output(
    raw_output: dict | Any,
    session_state: dict | None = None,
    db_path: str | None = None
) -> Tuple[ParserOutput, bool]:
    """
    Memvalidasi keluaran parser LLM terhadap skema dan enum tertutup (B11, B12).
    Mengembalikan (ParserOutput, is_schema_valid).
    """
    state = session_state or {}
    produk_tampil_list = state.get("produk_tampil", [])

    # 1. Validasi struktur JSON ke Pydantic
    if isinstance(raw_output, ParserOutput):
        parsed = raw_output
    elif isinstance(raw_output, dict):
        try:
            parsed = ParserOutput.model_validate(raw_output)
        except ValidationError as ve:
            logger.warning(f"Validasi skema/enum parser gagal: {ve}")
            return (
                ParserOutput(
                    aksi=ActionEnum.TIDAK_JELAS,
                    argumen=ActionArguments(alasan=AlasanTidakJelasEnum.SISTEM_ERROR),
                    pembaruan_state=StateUpdate()
                ),
                False
            )
    else:
        return (
            ParserOutput(
                aksi=ActionEnum.TIDAK_JELAS,
                argumen=ActionArguments(alasan=AlasanTidakJelasEnum.SISTEM_ERROR),
                pembaruan_state=StateUpdate()
            ),
            False
        )

    args = parsed.argumen
    state_up = parsed.pembaruan_state

    # 2. Validasi rentang harga (harus >= 0)
    for price_field in ["min_harga", "max_harga", "budget_min", "budget_max"]:
        val = getattr(args, price_field, None)
        if val is not None and val < 0:
            setattr(args, price_field, None)

    if state_up.budget is not None and state_up.budget < 0:
        state_up.budget = None

    # 3. Normalisasi kategori & merek terhadap katalog
    catalog_cats = get_catalog_categories(db_path)
    if args.kategori:
        cat_clean = args.kategori.lower().strip()
        if cat_clean in catalog_cats:
            args.kategori = cat_clean
        elif cat_clean in ("all", "semua"):
            args.kategori = None

    if state_up.kategori:
        cat_clean = state_up.kategori.lower().strip()
        if cat_clean in catalog_cats:
            state_up.kategori = cat_clean

    # 3b. Validasi nilai slot: tolak nilai kosong atau negasi -> bertentangan
    if parsed.aksi == ActionEnum.JAWAB_PERTANYAAN_BOT:
        val_str = str(args.nilai).strip().lower() if args.nilai is not None else ""
        negation_set = {
            "", "-", "--", "tidak ada", "ga ada", "gak ada", "nggak ada", "ndak ada",
            "kosong", "belum ada", "none", "null", "n/a", "tdk ada", "tidak"
        }
        if not val_str or val_str in negation_set:
            logger.warning(f"Nilai slot ditolak karena kosong atau negasi: '{args.nilai}'")
            return (
                ParserOutput(
                    aksi=ActionEnum.TIDAK_JELAS,
                    argumen=ActionArguments(alasan=AlasanTidakJelasEnum.BERTENTANGAN),
                    pembaruan_state=StateUpdate()
                ),
                False
            )

    # 4. Validasi lanjutan_hasil saat tidak ada produk tampil (B9)
    if parsed.aksi == ActionEnum.LANJUTAN_HASIL and not produk_tampil_list:
        logger.warning("Aksi lanjutan_hasil dipanggil saat produk_tampil kosong (B9)")
        return (
            ParserOutput(
                aksi=ActionEnum.TIDAK_JELAS,
                argumen=ActionArguments(alasan=AlasanTidakJelasEnum.RUJUKAN_TIDAK_ADA),
                pembaruan_state=StateUpdate()
            ),
            False
        )

    # 4b. Validasi & resolusi rujukan produk untuk evaluasi_kecocokan, tanya_spesifikasi, dan bandingkan
    if (args.rujukan_produk is not None or parsed.aksi in (ActionEnum.EVALUASI_KECOCOKAN, ActionEnum.TANYA_SPESIFIKASI, ActionEnum.BANDINGKAN)) and not produk_tampil_list:
        logger.warning("Rujukan produk diberikan atau aksi berbasis produk saat produk_tampil kosong (B9)")
        return (
            ParserOutput(
                aksi=ActionEnum.TIDAK_JELAS,
                argumen=ActionArguments(alasan=AlasanTidakJelasEnum.RUJUKAN_TIDAK_ADA),
                pembaruan_state=StateUpdate()
            ),
            False
        )

    if parsed.aksi in (ActionEnum.EVALUASI_KECOCOKAN, ActionEnum.TANYA_SPESIFIKASI, ActionEnum.BANDINGKAN):
        raw_refs = args.rujukan_produk if args.rujukan_produk is not None else args.produk
        resolved_codes, is_ref_valid, failed_ref = resolve_product_references(raw_refs, produk_tampil_list)

        if not is_ref_valid:
            if parsed.aksi == ActionEnum.BANDINGKAN:
                failed_list = [failed_ref] if isinstance(failed_ref, str) else list(failed_ref)
                failed_clean = [f for f in failed_list if f not in ("rujukan_kosong", "rujukan_ambigu")]
                args.produk = resolved_codes if resolved_codes else [p.get("kode") for p in produk_tampil_list if p.get("kode")]
                if failed_clean:
                    args.produk_luar_katalog = failed_clean
            else:
                return (
                    ParserOutput(
                        aksi=ActionEnum.TIDAK_JELAS,
                        argumen=ActionArguments(alasan=AlasanTidakJelasEnum.RUJUKAN_TIDAK_ADA),
                        pembaruan_state=StateUpdate()
                    ),
                    False
                )
        else:
            args.produk = resolved_codes

    # 4c. Validasi jenis per-aksi
    if parsed.aksi in ACTION_JENIS_MAP and args.jenis is not None:
        jenis_str = args.jenis.value if hasattr(args.jenis, "value") else str(args.jenis)
        if jenis_str not in ACTION_JENIS_MAP[parsed.aksi]:
            logger.warning(f"Jenis '{jenis_str}' tidak sah untuk aksi '{parsed.aksi.value}'")
            return (
                ParserOutput(
                    aksi=ActionEnum.TIDAK_JELAS,
                    argumen=ActionArguments(alasan=AlasanTidakJelasEnum.BERTENTANGAN),
                    pembaruan_state=StateUpdate()
                ),
                False
            )

    # 4d. Standarisasi alasan tidak_jelas ke enum tertutup (B12)
    if parsed.aksi == ActionEnum.TIDAK_JELAS:
        if not args.alasan or not isinstance(args.alasan, AlasanTidakJelasEnum):
            raw_alasan_str = str(args.alasan or "").lower()
            if "rujuk" in raw_alasan_str or "produk" in raw_alasan_str:
                args.alasan = AlasanTidakJelasEnum.RUJUKAN_TIDAK_ADA
            elif "tangan" in raw_alasan_str or "negasi" in raw_alasan_str or "konflik" in raw_alasan_str:
                args.alasan = AlasanTidakJelasEnum.BERTENTANGAN
            elif "error" in raw_alasan_str or "sistem" in raw_alasan_str or "skema" in raw_alasan_str:
                args.alasan = AlasanTidakJelasEnum.SISTEM_ERROR
            else:
                args.alasan = AlasanTidakJelasEnum.TIDAK_DIPAHAMI

    # 5. Pembersihan deterministik: Hapus argumen yang tidak relevan dengan aksi yang dipilih
    action_allowed_args = {
        ActionEnum.SAPA: set(),
        ActionEnum.CARI_PRODUK: {"kategori", "merek", "merek_kecuali", "nama_model", "gpu", "min_harga", "max_harga", "ram_gb_min", "storage_gb_min", "ukuran_layar"},
        ActionEnum.MINTA_REKOMENDASI: {"kebutuhan_teks", "persona", "kategori", "budget_min", "budget_max"},
        ActionEnum.JAWAB_PERTANYAAN_BOT: {"slot", "nilai"},
        ActionEnum.EVALUASI_KECOCOKAN: {"rujukan_produk", "produk", "kebutuhan_teks"},
        ActionEnum.TANYA_SPESIFIKASI: {"rujukan_produk", "produk", "atribut"},
        ActionEnum.BANDINGKAN: {"rujukan_produk", "produk", "produk_luar_katalog"},
        ActionEnum.LANJUTAN_HASIL: {"jenis", "merek_kecuali", "filter"},
        ActionEnum.TANYA_INFO_TOKO: {"topik"},
        ActionEnum.PERBAIKI_PERCAKAPAN: {"jenis", "rujukan"},
        ActionEnum.BASA_BASI: {"jenis"},
        ActionEnum.TIDAK_JELAS: {"alasan"}
    }
    allowed = action_allowed_args.get(parsed.aksi)
    if allowed is not None:
        for field in ActionArguments.model_fields.keys():
            if field not in allowed and getattr(args, field, None) is not None:
                setattr(args, field, None)

    # 6. Normalisasi persona & sebutan di state_update
    if state_up.persona:
        state_up.persona = state_up.persona.strip().lower()
    if state_up.sebutan:
        state_up.sebutan = state_up.sebutan.strip()
        if state_up.persona and state_up.sebutan.lower() == state_up.persona:
            state_up.sebutan = None

    return parsed, True


def check_state_consistency(parsed: ParserOutput, session_state: dict | None) -> Tuple[bool, str | None]:
    """
    Validasi konsistensi aksi terhadap state percakapan:
    - jawab_pertanyaan_bot hanya sah bila pending_question ada
    - lanjutan_hasil dan rujukan_produk hanya sah bila ada hasil/produk_tampil di sesi
    """
    state = session_state or {}
    has_pending = bool(state.get("pending_question"))
    produk_tampil = state.get("produk_tampil") or []
    has_tampil = len(produk_tampil) > 0

    if parsed.aksi == ActionEnum.JAWAB_PERTANYAAN_BOT and not has_pending:
        return False, "jawab_pertanyaan_bot hanya sah bila pending_question ada"

    if parsed.aksi == ActionEnum.LANJUTAN_HASIL and not has_tampil:
        return False, "lanjutan_hasil hanya sah bila ada hasil/produk_tampil di sesi"

    if parsed.aksi in (ActionEnum.EVALUASI_KECOCOKAN, ActionEnum.TANYA_SPESIFIKASI, ActionEnum.BANDINGKAN) and not has_tampil:
        return False, f"{parsed.aksi.value} hanya sah bila ada hasil/produk_tampil di sesi"

    if parsed.argumen.rujukan_produk and not has_tampil:
        return False, "rujukan_produk hanya sah bila ada hasil/produk_tampil di sesi"

    return True, None


def get_allowed_actions_for_state(session_state: dict | None) -> List[ActionEnum]:
    """
    Mengembalikan daftar aksi yang sah berdasarkan state saat ini.
    Digunakan saat meminta parse ulang dari LLM jika aksi sebelumnya tidak konsisten dengan state.
    """
    state = session_state or {}
    has_pending = bool(state.get("pending_question"))
    produk_tampil = state.get("produk_tampil") or []
    has_tampil = len(produk_tampil) > 0

    disallowed = set()
    if not has_pending:
        disallowed.add(ActionEnum.JAWAB_PERTANYAAN_BOT)
    if not has_tampil:
        disallowed.add(ActionEnum.LANJUTAN_HASIL)
        disallowed.add(ActionEnum.EVALUASI_KECOCOKAN)
        disallowed.add(ActionEnum.TANYA_SPESIFIKASI)
        disallowed.add(ActionEnum.BANDINGKAN)

    return [a for a in ActionEnum if a not in disallowed]
