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
    produk_tampil: List[Dict[str, Any]] | None,
    history_tampil: List[Dict[str, Any]] | None = None
) -> Tuple[List[str], bool, str | None]:
    """
    Menyelesaikan rujukan_produk (nomor urut, ordinal, harga ekstrim, nama/merek, atau riwayat sesi)
    menjadi daftar kode produk katalog dari produk_tampil atau history_produk_tampil di state percakapan.

    Mengembalikan: (resolved_codes, is_valid, failed_reference_str)
    Jika rujukan tidak ditemukan atau ambigu, is_valid = False.
    """
    tampil = produk_tampil or []
    hist = history_tampil or []

    if not tampil and not hist:
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

        # 1. Rujukan kata kunci 'semua'
        if ref_clean in ("semua", "semuanya", "tampil", "seluruhnya"):
            resolved.extend([p.get("kode") for p in tampil if p.get("kode")])
            continue

        # 2. Rujukan superlativ harga
        if ref_clean in ("paling murah", "yang paling murah", "termurah", "yang termurah", "murah"):
            target_list = hist if (is_prev and hist) else tampil
            cheapest = min(target_list, key=lambda p: int(p.get("harga") or p.get("harga_idr") or 0)) if target_list else {}
            if cheapest.get("kode"):
                resolved.append(cheapest["kode"])
            continue

        if ref_clean in ("paling mahal", "yang paling mahal", "termahal", "yang termahal", "mahal"):
            target_list = hist if (is_prev and hist) else tampil
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
        matched_candidates = []
        for p in tampil:
            p_kode = str(p.get("kode", "")).lower()
            p_nama = str(p.get("nama", "")).lower()
            p_brand = str(p.get("brand", "")).lower()

            # Hidrasi nama dan brand dari katalog jika tampil hanya memuat kode
            if (not p_brand or p_nama == p_kode) and p_kode:
                try:
                    from services.catalog_service import get_active_catalog
                    cat = get_active_catalog()
                    full_p = cat.by_code.get(p_kode.upper()) or cat.by_code.get(p_kode)
                    if full_p:
                        p_nama = str(full_p.get("nama", "")).lower()
                        p_brand = str(full_p.get("brand", "")).lower()
                except Exception:
                    pass

            if search_kw and (search_kw == p_kode or search_kw == p_brand or search_kw in p_nama or (p_brand and p_brand in search_kw)):
                matched_candidates.append(p)

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
                    cat_matches.append(p_cat)
                    break
                if tokens and all((tok in p_c_nama or tok in p_c_brand) for tok in tokens):
                    cat_matches.append(p_cat)
        except Exception as e:
            logger.warning(f"Gagal cek katalog pada resolve_product_references: {e}")

        if cat_matches:
            resolved.append(cat_matches[0]["kode"])
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

    # Sinkronisasi kebutuhan_teks antara pembaruan_state dan argumen
    if parsed.pembaruan_state.kebutuhan_teks and not args.kebutuhan_teks:
        args.kebutuhan_teks = parsed.pembaruan_state.kebutuhan_teks
    elif args.kebutuhan_teks and not parsed.pembaruan_state.kebutuhan_teks:
        parsed.pembaruan_state.kebutuhan_teks = args.kebutuhan_teks

    # 4b. Validasi & resolusi rujukan produk untuk evaluasi_kecocokan, tanya_spesifikasi, dan bandingkan
    history_tampil_list = state.get("history_produk_tampil", [])
    if (args.rujukan_produk is not None or parsed.aksi in (ActionEnum.EVALUASI_KECOCOKAN, ActionEnum.TANYA_SPESIFIKASI, ActionEnum.BANDINGKAN)) and not produk_tampil_list and not history_tampil_list:
        logger.warning("Rujukan produk diberikan atau aksi berbasis produk saat produk_tampil dan riwayat kosong (B9)")
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
        if not raw_refs and produk_tampil_list:
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
            raw_refs, produk_tampil_list, history_tampil=history_tampil_list
        )

        if not is_ref_valid:
            if parsed.aksi == ActionEnum.BANDINGKAN:
                failed_list = [failed_ref] if isinstance(failed_ref, str) else list(failed_ref)
                failed_clean = [f for f in failed_list if f not in ("rujukan_kosong", "rujukan_ambigu", "rujukan_tidak_ada")]
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
        jenis_str = args.jenis.value if hasattr(args.jenis, "value") else str(args.jenis).lower()
        if parsed.aksi == ActionEnum.LANJUTAN_HASIL:
            if jenis_str in ("lainnya", "merek_lain", "yang_setara", "setara", "alternatif", "varian_lain"):
                args.jenis = JenisEnum.YANG_LAIN
                jenis_str = JenisEnum.YANG_LAIN.value
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
        ActionEnum.PERBAIKI_PERCAKAPAN: {"jenis", "rujukan"},
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
