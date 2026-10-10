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
import re
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


from core.db import get_catalog_inventory


def get_catalog_brands(db_path: str | None = None) -> list[str]:
    """Mengambil daftar merek secara dinamis dari catalog.db via satu sumber kebenaran."""
    return get_catalog_inventory(db_path)["merek"]


def get_catalog_categories(db_path: str | None = None) -> list[str]:
    """Mengambil daftar kategori secara dinamis dari catalog.db via satu sumber kebenaran."""
    return get_catalog_inventory(db_path)["kategori"]


def is_valid_kebutuhan_teks(text: str | None, db_path: str | None = None) -> bool:
    """
    Putaran 13 Butir E:
    kebutuhan_teks tidak boleh hanya berisi kata kategori atau merek yang ada di katalog
    (bandingkan token dengan nilai katalog dinamis, bukan regex bahasa);
    jika setelah dibuang kosong -> abaikan pembaruan (return False).
    """
    if not text or not str(text).strip():
        return False
    raw_tokens = [re.sub(r"^[^\w]+|[^\w]+$", "", t.lower()) for t in str(text).split()]
    tokens = [t for t in raw_tokens if t]
    if not tokens:
        return False

    catalog_cats = set(get_catalog_categories(db_path))
    catalog_brands = set(get_catalog_brands(db_path))
    catalog_words = {c.lower() for c in catalog_cats} | {b.lower() for b in catalog_brands}

    remaining_tokens = [t for t in tokens if t not in catalog_words]
    return len(remaining_tokens) > 0



def resolve_product_references(
    produk_refs: List[Any] | None,
    produk_tampil: List[Dict[str, Any]] | None,
    history_tampil: List[Dict[str, Any]] | None = None,
    produk_dibahas: List[str] | None = None,
    produk_dibahas_sebelumnya: List[Dict[str, Any]] | None = None
) -> Tuple[List[str], bool, str | None]:
    """
    Menyelesaikan rujukan_produk (nomor urut, ordinal, harga ekstrim, nama/merek,
    afirmasi singkat, fokus saat ini, atau riwayat sesi)
    menjadi daftar kode produk katalog.
    Urutan resolusi: fokus (produk_dibahas) -> sebelumnya (produk_dibahas_sebelumnya)
    -> riwayat set (tampil/hist) -> katalog menurut nama.

    Mengembalikan: (resolved_codes, is_valid, failed_reference_str)
    Jika rujukan tidak ditemukan atau ambigu, is_valid = False.
    """
    tampil = produk_tampil or []
    hist = history_tampil or []
    fokus = produk_dibahas or []
    prev_stack = produk_dibahas_sebelumnya or []

    if not tampil and not hist and not fokus and not prev_stack:
        return [], False, "tidak_ada_produk_tampil"

    # Jika rujukan tidak disertakan tapi aksi produk dipanggil
    if not produk_refs:
        if fokus:
            return [c for c in fokus if c], True, None
        if prev_stack:
            first_c = prev_stack[0].get("kode", [])
            if first_c:
                return [c for c in first_c if c], True, None
        # Default ke seluruh produk yang tampil jika ada
        return [p.get("kode") for p in tampil if p.get("kode")], True, None

    ordinal_map = {
        "pertama": 0, "yang pertama": 0, "kesatu": 0, "no 1": 0, "no. 1": 0, "ke-1": 0,
        "kedua": 1, "yang kedua": 1, "no 2": 1, "no. 2": 1, "ke-2": 1,
        "ketiga": 2, "yang ketiga": 2, "no 3": 2, "no. 3": 2, "ke-3": 2,
    }

    norm_tampil = []
    for idx, p in enumerate(tampil or []):
        if isinstance(p, dict):
            norm_tampil.append(p)
        elif isinstance(p, str):
            norm_tampil.append({"kode": p, "nama": p})
    tampil = norm_tampil

    norm_hist = []
    for idx, p in enumerate(hist):
        if isinstance(p, dict):
            norm_hist.append(p)
        elif isinstance(p, str):
            norm_hist.append({"kode": p, "nama": p})
    hist = norm_hist

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
            elif hist and 0 <= idx < len(hist) and hist[idx].get("kode"):
                resolved.append(hist[idx]["kode"])
                continue
            else:
                failed_refs.append(str(raw_ref))
                continue

        ref_clean = str(raw_ref).lower().strip()
        is_prev = bool(re.search(r"\b(sebelumnya|tadi|kemarin|lalu|riwayat|dulu)\b", ref_clean))

        # 0. Rujukan pendek afirmatif / demonstratif ("boleh", "ya", "itu", "tadi", "mau", dll.)
        if re.search(r"^(?:ya|iya|boleh|mau|ok|oke|siap|tampilkan|mau\s+lihat|itu|ini|yang\s+itu|tadi|yang\s+tadi|produk\s+tadi|laptop\s+tadi|printer\s+tadi)$", ref_clean):
            if fokus:
                resolved.extend([c for c in fokus if c])
                continue
            elif prev_stack:
                first_c = prev_stack[0].get("kode", [])
                if first_c:
                    resolved.extend([c for c in first_c if c])
                    continue
            elif tampil:
                if tampil[0].get("kode"):
                    resolved.append(tampil[0]["kode"])
                    continue

        # 1. Rujukan kata kunci 'semua'
        if ref_clean in ("semua", "semuanya", "tampil", "seluruhnya"):
            resolved.extend([p.get("kode") for p in tampil if p.get("kode")])
            continue

        # 2. Rujukan superlativ harga
        if any(k in ref_clean for k in ("paling murah", "termurah", "paling terjangkau", "murah")):
            target_list = hist if (is_prev and hist) else (tampil or hist)
            cheapest = min(target_list, key=lambda p: int(p.get("harga") or p.get("harga_idr") or 0)) if target_list else {}
            if cheapest.get("kode"):
                resolved.append(cheapest["kode"])
            continue

        if any(k in ref_clean for k in ("paling mahal", "termahal", "mahal")):
            target_list = hist if (is_prev and hist) else (tampil or hist)
            priciest = max(target_list, key=lambda p: int(p.get("harga") or p.get("harga_idr") or 0)) if target_list else {}
            if priciest.get("kode"):
                resolved.append(priciest["kode"])
            continue

        # 3. Rujukan ordinal / nomor digit (misal: '1', 'opsi 1', 'opsi 1 sebelumnya')
        matched = False
        m_digit = re.match(r"^(?:produk\s+|unit\s+|opsi\s+|no\.?\s*|nomor\s+|pilihan\s+|#)?\[?(\d+)\]?(?:\s+(?:ini|itu|tadi|sebelumnya))?$", ref_clean)
        if m_digit:
            idx = int(m_digit.group(1)) - 1
            if is_prev and hist and 0 <= idx < len(hist) and hist[idx].get("kode"):
                resolved.append(hist[idx]["kode"])
                matched = True
            elif not is_prev and 0 <= idx < len(tampil) and tampil[idx].get("kode"):
                resolved.append(tampil[idx]["kode"])
                matched = True
            elif hist and 0 <= idx < len(hist) and hist[idx].get("kode"):
                resolved.append(hist[idx]["kode"])
                matched = True
            else:
                failed_refs.append(str(raw_ref))
                matched = True
        else:
            for ord_key, idx in ordinal_map.items():
                if re.search(rf"\b{re.escape(ord_key)}\b", ref_clean):
                    if is_prev and hist and 0 <= idx < len(hist) and hist[idx].get("kode"):
                        resolved.append(hist[idx]["kode"])
                        matched = True
                        break
                    elif not is_prev and 0 <= idx < len(tampil) and tampil[idx].get("kode"):
                        resolved.append(tampil[idx]["kode"])
                        matched = True
                        break
                    elif hist and 0 <= idx < len(hist) and hist[idx].get("kode"):
                        resolved.append(hist[idx]["kode"])
                        matched = True
                        break
                    else:
                        failed_refs.append(str(raw_ref))
                        matched = True
                        break

        if matched:
            continue

        # 4. Rujukan nama / merek / kode produk
        search_kw = ref_clean.replace("yang", "").replace("tadi", "").replace("itu", "").strip()

        # 4a. Cek fokus saat ini
        if fokus:
            fokus_matches = []
            for fc in fokus:
                if str(fc).lower() == search_kw:
                    fokus_matches.append(fc)
                else:
                    for pt in tampil + hist:
                        if pt.get("kode", "").lower() == str(fc).lower():
                            pt_nama = str(pt.get("nama", "")).lower()
                            pt_brand = str(pt.get("brand", "")).lower()
                            if search_kw in pt_nama or search_kw == pt_brand:
                                fokus_matches.append(fc)
                                break
            if len(fokus_matches) == 1:
                resolved.append(fokus_matches[0])
                continue
            elif len(fokus_matches) > 1:
                return [], False, "rujukan_ambigu"

        # 4b. Cek tumpukan fokus sebelumnya (produk_dibahas_sebelumnya)
        if prev_stack:
            prev_matches = []
            for entry in prev_stack:
                e_codes = entry.get("kode", []) if isinstance(entry, dict) else [entry]
                e_label = str(entry.get("label_kebutuhan", "")).lower() if isinstance(entry, dict) else ""
                label_matched = bool(e_label and (search_kw in e_label or e_label in search_kw))
                for ec in e_codes:
                    if label_matched or str(ec).lower() == search_kw:
                        if ec not in prev_matches:
                            prev_matches.append(ec)
                    else:
                        for pt in tampil + hist:
                            if pt.get("kode", "").lower() == str(ec).lower():
                                pt_nama = str(pt.get("nama", "")).lower()
                                pt_brand = str(pt.get("brand", "")).lower()
                                if search_kw in pt_nama or search_kw == pt_brand:
                                    if ec not in prev_matches:
                                        prev_matches.append(ec)
                                    break
                if prev_matches:
                    break
            if len(prev_matches) == 1:
                resolved.append(prev_matches[0])
                continue
            elif len(prev_matches) > 1:
                return [], False, "rujukan_ambigu"

        # 4c. Cek produk_tampil lalu history_tampil
        search_targets = (hist if is_prev else tampil) or []
        fallback_targets = (tampil if is_prev else hist) or []
        matched_candidates = []

        def _match_list(cand_list):
            m = []
            for p in cand_list:
                p_kode = str(p.get("kode", "")).lower()
                p_nama = str(p.get("nama", "")).lower()
                p_brand = str(p.get("brand", "")).lower()
                p_cat_nama = ""
                if p_kode:
                    try:
                        from services.catalog_service import get_active_catalog
                        cat = get_active_catalog()
                        full_p = cat.by_code.get(p_kode.upper()) or cat.by_code.get(p_kode)
                        if full_p:
                            p_cat_nama = str(full_p.get("nama", "")).lower()
                            if not p_brand:
                                p_brand = str(full_p.get("brand", "")).lower()
                    except Exception:
                        pass
                p_tokens = [t for t in re.split(r"\s+", search_kw) if len(t) >= 2]
                if search_kw and (
                    search_kw == p_kode or search_kw == p_brand or
                    search_kw in p_nama or (p_brand and p_brand in search_kw) or
                    (p_cat_nama and search_kw in p_cat_nama) or
                    (p_tokens and (all(tok in p_nama or tok in p_brand for tok in p_tokens) or (p_cat_nama and all(tok in p_cat_nama or tok in p_brand for tok in p_tokens))))
                ):
                    if p not in m:
                        m.append(p)
            return m

        matched_candidates = _match_list(search_targets)
        if not matched_candidates and fallback_targets:
            matched_candidates = _match_list(fallback_targets)

        if len(matched_candidates) == 1:
            resolved.append(matched_candidates[0]["kode"])
            continue
        elif len(matched_candidates) > 1:
            # Ambigu: ada lebih dari 1 produk yang cocok
            return [], False, "rujukan_ambigu"

        # 5. Cek apakah rujukan cocok dengan produk di seluruh katalog (E7: ASUS D500, dll)
        cat_matches = []
        try:
            from services.catalog_service import get_active_catalog
            cat = get_active_catalog()
            clean_search = re.sub(r"\b(desktop|laptop|komputer|pc|unit|seri|tipe|model|printer)\b", "", search_kw, flags=re.IGNORECASE).strip()
            tokens = [t for t in re.split(r"\s+", clean_search) if len(t) >= 2]
            for p_cat in cat.products:
                p_c_kode = str(p_cat.get("kode", "")).lower()
                p_c_nama = str(p_cat.get("nama", "")).lower()
                p_c_brand = str(p_cat.get("brand", "")).lower()
                if search_kw == p_c_kode or clean_search == p_c_kode:
                    if p_cat not in cat_matches:
                        cat_matches.append(p_cat)
                    break
                if tokens and all((tok in p_c_nama or tok in p_c_brand) for tok in tokens):
                    if p_cat not in cat_matches:
                        cat_matches.append(p_cat)
        except Exception as e:
            logger.warning(f"Gagal cek katalog pada resolve_product_references: {e}")

        if len(cat_matches) == 1:
            resolved.append(cat_matches[0]["kode"])
        elif len(cat_matches) > 1:
            return [], False, "rujukan_ambigu"
        else:
            failed_refs.append(str(raw_ref))

    # Hilangkan duplikasi urut
    seen = set()
    dedup = [x for x in resolved if not (x in seen or seen.add(x))]

    if failed_refs:
        first_fail = failed_refs[0]
        if re.match(r"^(?:produk\s+|unit\s+|opsi\s+|no\.?\s*|nomor\s+|#)?\[?(\d+)\]?$", first_fail.strip().lower()):
            first_fail = "rujukan_tidak_ada"
        return dedup, False, first_fail if len(failed_refs) == 1 else "rujukan_tidak_ada"
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
        raw_copy = dict(raw_output)
        from services.catalog_search import parse_budget_from_text
        if "argumen" in raw_copy and isinstance(raw_copy["argumen"], dict):
            raw_arg = dict(raw_copy["argumen"])
            for bf in ("max_harga", "budget_max", "min_harga", "budget_min"):
                if bf in raw_arg and isinstance(raw_arg[bf], str):
                    raw_arg[bf] = parse_budget_from_text(raw_arg[bf])
            raw_copy["argumen"] = raw_arg
        if "pembaruan_state" in raw_copy and isinstance(raw_copy["pembaruan_state"], dict):
            raw_su = dict(raw_copy["pembaruan_state"])
            if "budget" in raw_su and isinstance(raw_su["budget"], str):
                raw_su["budget"] = parse_budget_from_text(raw_su["budget"])
            raw_copy["pembaruan_state"] = raw_su
        try:
            parsed = ParserOutput.model_validate(raw_copy)
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

    # Kontrak Intent (Putaran 14 Butir 2):
    # Validator tidak boleh menghapus atau mengganti nilai dari parser diam-diam.
    # Setiap argumen diklasifikasikan: valid, tidak_ada_di_katalog, atau ambigu.
    raw_args_original = {}
    if isinstance(raw_output, dict) and "argumen" in raw_output and isinstance(raw_output["argumen"], dict):
        raw_args_original = dict(raw_output["argumen"])
    elif isinstance(raw_output, ParserOutput):
        raw_args_original = {k: v for k, v in raw_output.argumen.model_dump().items() if v is not None}

    permintaan_asli = {
        "aksi": parsed.aksi.value if hasattr(parsed.aksi, "value") else str(parsed.aksi),
        "argumen": dict(raw_args_original)
    }
    argumen_valid = {}
    argumen_ditolak = []

    # 2. Validasi rentang harga (harus >= 0)
    for price_field in ["min_harga", "max_harga", "budget_min", "budget_max"]:
        val = getattr(args, price_field, None)
        if val is not None:
            if isinstance(val, (int, float)) and val >= 0:
                argumen_valid[price_field] = int(val)
            else:
                argumen_ditolak.append({"field": price_field, "nilai": val, "alasan": "ambigu"})
                setattr(args, price_field, None)

    if state_up.budget is not None and state_up.budget < 0:
        state_up.budget = None

    # 3. Normalisasi kategori & merek terhadap katalog
    catalog_cats = get_catalog_categories(db_path)
    catalog_brands = get_catalog_brands(db_path)

    # Klasifikasi argumen kategori
    raw_cat = raw_args_original.get("kategori") or args.kategori
    if raw_cat:
        cat_clean = str(raw_cat).lower().strip()
        if cat_clean in catalog_cats:
            args.kategori = cat_clean
            argumen_valid["kategori"] = cat_clean
        elif cat_clean in ("all", "semua"):
            args.kategori = None
            argumen_valid["kategori"] = "all"
        else:
            logger.warning(f"B1/Butir 2: Kategori tidak ada di katalog ditolak: '{raw_cat}'")
            argumen_ditolak.append({
                "field": "kategori",
                "nilai": raw_cat,
                "alasan": "tidak_ada_di_katalog"
            })
            args.kategori = None

    if state_up.kategori:
        cat_clean = str(state_up.kategori).lower().strip()
        if cat_clean in catalog_cats:
            state_up.kategori = cat_clean
        else:
            logger.warning(f"B1/Butir 2: Pembaruan state kategori tak dikenal ditolak: '{state_up.kategori}'")
            if not any(d["field"] == "kategori" for d in argumen_ditolak):
                argumen_ditolak.append({
                    "field": "kategori",
                    "nilai": state_up.kategori,
                    "alasan": "tidak_ada_di_katalog"
                })
            state_up.kategori = None

    # Klasifikasi argumen merek
    raw_merek = raw_args_original.get("merek") or args.merek
    if raw_merek:
        m_clean = str(raw_merek).lower().strip()
        if m_clean in catalog_brands:
            args.merek = m_clean
            argumen_valid["merek"] = m_clean
        else:
            logger.warning(f"B1/Butir 2: Merek tidak ada di katalog ditolak: '{raw_merek}'")
            argumen_ditolak.append({
                "field": "merek",
                "nilai": raw_merek,
                "alasan": "tidak_ada_di_katalog"
            })
            args.merek = None

    if state_up.merek:
        m_clean = str(state_up.merek).lower().strip()
        if m_clean in catalog_brands:
            state_up.merek = m_clean
        else:
            logger.warning(f"B1/Butir 2: Pembaruan state merek tak dikenal ditolak: '{state_up.merek}'")
            if not any(d["field"] == "merek" for d in argumen_ditolak):
                argumen_ditolak.append({
                    "field": "merek",
                    "nilai": state_up.merek,
                    "alasan": "tidak_ada_di_katalog"
                })
            state_up.merek = None

    # 3a. Normalisasi merek_kecuali jika terisi nama GPU/chipmaker
    if args.merek_kecuali:
        mk_val = str(args.merek_kecuali).lower()
        gpu_chipmakers = ["nvidia", "geforce", "rtx", "gtx", "radeon"]
        if any(chip in mk_val for chip in gpu_chipmakers):
            if not args.gpu:
                args.gpu = args.merek_kecuali
            args.merek_kecuali = None

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

        slot_key = args.slot.value if hasattr(args.slot, "value") else str(args.slot).lower()
        if slot_key in ("kategori", "category"):
            if val_str not in catalog_cats:
                logger.warning(f"B1: Nilai slot kategori tak dikenal diabaikan: '{args.nilai}'")
                args.nilai = None
        elif slot_key in ("merek", "brand"):
            if val_str not in catalog_brands:
                logger.warning(f"B1: Nilai slot merek tak dikenal diabaikan: '{args.nilai}'")
                args.nilai = None
        elif slot_key in ("kebutuhan", "aktivitas"):
            if not is_valid_kebutuhan_teks(val_str, db_path):
                logger.warning(f"E: Nilai slot kebutuhan hanya berisi kategori/merek katalog diabaikan: '{args.nilai}'")
                args.nilai = None

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

    # Putaran 13 Butir E & Putaran 14 Butir 2: Validasi kebersihan kebutuhan_teks
    if args.kebutuhan_teks:
        if is_valid_kebutuhan_teks(args.kebutuhan_teks, db_path):
            argumen_valid["kebutuhan_teks"] = args.kebutuhan_teks
        else:
            logger.warning(f"E/Butir 2: Argumen kebutuhan_teks '{args.kebutuhan_teks}' hanya berisi kategori/merek katalog, ditolak sebagai ambigu.")
            argumen_ditolak.append({
                "field": "kebutuhan_teks",
                "nilai": args.kebutuhan_teks,
                "alasan": "ambigu"
            })
            args.kebutuhan_teks = None

    if parsed.pembaruan_state.kebutuhan_teks and not is_valid_kebutuhan_teks(parsed.pembaruan_state.kebutuhan_teks, db_path):
        logger.warning(f"E: Pembaruan state kebutuhan_teks '{parsed.pembaruan_state.kebutuhan_teks}' hanya berisi kategori/merek katalog, diabaikan.")
        parsed.pembaruan_state.kebutuhan_teks = None

    # Sinkronisasi kebutuhan_teks antara pembaruan_state dan argumen
    if parsed.pembaruan_state.kebutuhan_teks and not args.kebutuhan_teks:
        args.kebutuhan_teks = parsed.pembaruan_state.kebutuhan_teks
    elif args.kebutuhan_teks and not parsed.pembaruan_state.kebutuhan_teks:
        parsed.pembaruan_state.kebutuhan_teks = args.kebutuhan_teks

    # 4b. Validasi & resolusi rujukan produk untuk evaluasi_kecocokan, tanya_spesifikasi, dan bandingkan
    history_tampil_list = state.get("history_produk_tampil", [])
    fokus_list = state.get("produk_dibahas", [])
    prev_stack_list = state.get("produk_dibahas_sebelumnya", [])
    if (args.rujukan_produk is not None or parsed.aksi in (ActionEnum.EVALUASI_KECOCOKAN, ActionEnum.TANYA_SPESIFIKASI, ActionEnum.BANDINGKAN)) and not produk_tampil_list and not history_tampil_list and not fokus_list and not prev_stack_list:
        logger.warning("Rujukan produk diberikan atau aksi berbasis produk saat produk_tampil, fokus, dan riwayat kosong (B9)")
        argumen_ditolak.append({
            "field": "rujukan_produk",
            "nilai": args.rujukan_produk or args.produk,
            "alasan": "tidak_ada_di_katalog"
        })
        return (
            ParserOutput(
                aksi=ActionEnum.TIDAK_JELAS,
                argumen=ActionArguments(alasan=AlasanTidakJelasEnum.RUJUKAN_TIDAK_ADA),
                pembaruan_state=StateUpdate(),
                kontrak_intent={
                    "permintaan_asli": permintaan_asli,
                    "argumen_valid": argumen_valid,
                    "argumen_ditolak": argumen_ditolak
                }
            ),
            False
        )

    if parsed.aksi in (ActionEnum.EVALUASI_KECOCOKAN, ActionEnum.TANYA_SPESIFIKASI, ActionEnum.BANDINGKAN):
        raw_refs = args.rujukan_produk if args.rujukan_produk is not None else args.produk
        if not raw_refs:
            if fokus_list:
                raw_refs = [c for c in fokus_list if c]
            elif prev_stack_list and isinstance(prev_stack_list, list) and prev_stack_list[0].get("kode"):
                raw_refs = [c for c in prev_stack_list[0].get("kode") if c]
            elif produk_tampil_list:
                ptd = state.get("produk_terakhir_dibahas")
                if ptd:
                    if isinstance(ptd, list):
                        raw_refs = [x.get("kode") if isinstance(x, dict) else str(x) for x in ptd]
                    elif isinstance(ptd, dict):
                        raw_refs = [ptd.get("kode")] if ptd.get("kode") else []
                    else:
                        raw_refs = [str(ptd)]
                else:
                    raw_refs = [p.get("kode") for p in produk_tampil_list if p.get("kode")]

        resolved_codes, is_ref_valid, failed_ref = resolve_product_references(
            raw_refs, produk_tampil_list, history_tampil=history_tampil_list,
            produk_dibahas=fokus_list, produk_dibahas_sebelumnya=prev_stack_list
        )

        if not is_ref_valid:
            if parsed.aksi == ActionEnum.BANDINGKAN:
                failed_list = [failed_ref] if isinstance(failed_ref, str) else list(failed_ref)
                failed_clean = [f for f in failed_list if f not in ("rujukan_kosong", "rujukan_ambigu", "rujukan_tidak_ada")]
                args.produk = resolved_codes if resolved_codes else []
                if failed_clean:
                    args.produk_luar_katalog = failed_clean
                    for fc in failed_clean:
                        argumen_ditolak.append({"field": "produk", "nilai": fc, "alasan": "tidak_ada_di_katalog"})
            else:
                argumen_ditolak.append({
                    "field": "rujukan_produk",
                    "nilai": raw_refs,
                    "alasan": "ambigu" if failed_ref in ("rujukan_ambigu", "ambigu") else "tidak_ada_di_katalog"
                })
                return (
                    ParserOutput(
                        aksi=ActionEnum.TIDAK_JELAS,
                        argumen=ActionArguments(alasan=AlasanTidakJelasEnum.RUJUKAN_TIDAK_ADA),
                        pembaruan_state=StateUpdate(),
                        kontrak_intent={
                            "permintaan_asli": permintaan_asli,
                            "argumen_valid": argumen_valid,
                            "argumen_ditolak": argumen_ditolak
                        }
                    ),
                    False
                )
        else:
            args.produk = resolved_codes
            argumen_valid["produk"] = resolved_codes

        if args.produk_luar_katalog:
            still_outside = []
            for luar_item in args.produk_luar_katalog:
                res_codes, ok, _ = resolve_product_references(
                    [luar_item], produk_tampil_list, history_tampil=history_tampil_list,
                    produk_dibahas=fokus_list, produk_dibahas_sebelumnya=prev_stack_list
                )
                if ok and res_codes:
                    if not args.produk:
                        args.produk = []
                    for c in res_codes:
                        if c not in args.produk:
                            args.produk.append(c)
                else:
                    still_outside.append(luar_item)
            args.produk_luar_katalog = still_outside or None

    # 4c. Validasi jenis per-aksi
    if parsed.aksi in ACTION_JENIS_MAP and args.jenis is not None:
        jenis_str = args.jenis.value if hasattr(args.jenis, "value") else str(args.jenis).lower()
        if parsed.aksi == ActionEnum.LANJUTAN_HASIL:
            if jenis_str in ("lainnya", "merek_lain", "yang_setara", "setara", "alternatif", "varian_lain"):
                args.jenis = JenisEnum.YANG_LAIN
                jenis_str = JenisEnum.YANG_LAIN.value
            elif jenis_str in ("termurah", "paling_murah", "paling_rendah", "termurah_dari_tampil"):
                args.jenis = JenisEnum.TERMURAH_DARI_TAMPIL
                jenis_str = JenisEnum.TERMURAH_DARI_TAMPIL.value
            elif jenis_str in ("di_bawah_itu", "murah", "lebih_hemat"):
                args.jenis = JenisEnum.LEBIH_MURAH
                jenis_str = JenisEnum.LEBIH_MURAH.value
            elif jenis_str in ("di_atas_itu", "mahal", "premium", "tinggi"):
                args.jenis = JenisEnum.LEBIH_MAHAL
                jenis_str = JenisEnum.LEBIH_MAHAL.value

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
        ActionEnum.LANJUTAN_HASIL: {"jenis", "merek_kecuali", "filter", "max_harga", "min_harga"},
        ActionEnum.TANYA_INFO_TOKO: {"topik"},
        ActionEnum.PERBAIKI_PERCAKAPAN: {"jenis", "rujukan", "kategori", "merek", "kebutuhan_teks", "persona", "max_harga", "min_harga", "budget_max", "budget_min", "ram_gb_min", "storage_gb_min", "gpu"},
        ActionEnum.BASA_BASI: {"jenis"},
        ActionEnum.TIDAK_JELAS: {"alasan"}
    }
    allowed = action_allowed_args.get(parsed.aksi)
    if allowed is not None:
        for field in ActionArguments.model_fields.keys():
            if field not in allowed and getattr(args, field, None) is not None:
                setattr(args, field, None)

    # Sanitasi CPU salah masuk ke field GPU
    if args.gpu:
        raw_gpu = str(args.gpu).lower()
        if any(cpu_kw in raw_gpu for cpu_kw in ["core i", "ryzen", "intel core", "processor n", "celeron", "pentium", "snapdragon"]):
            args.gpu = None

    # 6. Normalisasi persona & sebutan di state_update
    if state_up.persona:
        state_up.persona = state_up.persona.strip().lower()
    if state_up.sebutan:
        state_up.sebutan = state_up.sebutan.strip()
        if state_up.persona and state_up.sebutan.lower() == state_up.persona:
            state_up.sebutan = None

    for f in ActionArguments.model_fields.keys():
        val = getattr(args, f, None)
        if val is not None and f not in argumen_valid and not any(d["field"] == f for d in argumen_ditolak):
            argumen_valid[f] = val

    parsed.kontrak_intent = {
        "permintaan_asli": permintaan_asli,
        "argumen_valid": argumen_valid,
        "argumen_ditolak": argumen_ditolak
    }

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
