# -*- coding: utf-8 -*-
"""
services/validator.py
Validator deterministik keluaran Parser LLM untuk Antigravity v2.

Prinsip:
- R2: Hanya memvalidasi skema, tipe, enum, rentang, dan keberadaan di katalog.
- R3: Tidak menimpa aksi parser dengan aturan bahasa/regex. Jika tidak valid atau ragu,
      hasilnya diubah menjadi `tidak_jelas` dengan alasan eksplisit.
"""
from __future__ import annotations

import os
import sqlite3
import logging
from typing import Any, List, Dict
from pydantic import ValidationError

from services.schema_actions import ParserOutput, ActionEnum, ActionArguments, StateUpdate

logger = logging.getLogger(__name__)


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
    produk_refs: List[str] | None,
    produk_tampil: List[Dict[str, Any]] | None
) -> List[str]:
    """
    Menyelesaikan rujukan produk ordinal ('1', 'kedua', 'yang kedua', dsb.)
    menjadi kode produk katalog berdasarkan produk_tampil di state percakapan.
    """
    if not produk_tampil:
        return produk_refs or []

    ordinal_map = {
        "1": 0, "pertama": 0, "yang pertama": 0, "kesatu": 0, "no 1": 0, "no. 1": 0,
        "2": 1, "kedua": 1, "yang kedua": 1, "no 2": 1, "no. 2": 1,
        "3": 2, "ketiga": 2, "yang ketiga": 2, "no 3": 2, "no. 3": 2,
    }

    # Jika produk_refs kosong tapi ada produk tampil dan aksi membutuhkan rujukan produk
    if not produk_refs:
        # Default: ambil semua kode produk yang sedang tampil
        return [p.get("kode") for p in produk_tampil if p.get("kode")]

    resolved = []
    for ref in produk_refs:
        ref_clean = str(ref).lower().strip()
        matched = False
        for ord_key, idx in ordinal_map.items():
            if ref_clean == ord_key or f"yang {ord_key}" in ref_clean:
                if idx < len(produk_tampil) and produk_tampil[idx].get("kode"):
                    resolved.append(produk_tampil[idx]["kode"])
                    matched = True
                    break
        if not matched:
            # Periksa apakah ref cocok langsung dengan kode produk di katalog atau nama
            for p in produk_tampil:
                p_kode = str(p.get("kode", "")).lower()
                p_nama = str(p.get("nama", "")).lower()
                if ref_clean in p_kode or ref_clean in p_nama:
                    resolved.append(p.get("kode"))
                    matched = True
                    break
            if not matched:
                resolved.append(ref)

    return resolved


def validate_parser_output(
    raw_output: dict | Any,
    session_state: dict | None = None,
    db_path: str | None = None
) -> ParserOutput:
    """
    Memvalidasi keluaran parser LLM.
    - Menjamin format Pydantic / ActionEnum valid.
    - Memverifikasi rentang numerik budget (harus non-negatif).
    - Memvalidasi konsistensi rujukan produk terhadap session_state.
    - Menormalkan kategori/merek sesuai data katalog tanpa menimpa aksi.
    - Jika format rusak atau tidak valid: kembalikan `tidak_jelas`.
    """
    state = session_state or {}

    # 1. Validasi struktur JSON ke Pydantic
    if not isinstance(raw_output, dict):
        return ParserOutput(
            aksi=ActionEnum.TIDAK_JELAS,
            argumen=ActionArguments(alasan="Format keluaran bukan objek JSON"),
            pembaruan_state=StateUpdate()
        )

    try:
        parsed = ParserOutput.model_validate(raw_output)
    except ValidationError as ve:
        logger.warning(f"Validasi skema parser gagal: {ve}")
        return ParserOutput(
            aksi=ActionEnum.TIDAK_JELAS,
            argumen=ActionArguments(alasan=f"Skema tidak valid: {ve.errors()[0].get('msg', 'error')}"),
            pembaruan_state=StateUpdate()
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

    # 4. Validasi & resolusi rujukan produk untuk evaluasi_kecocokan dan bandingkan
    if parsed.aksi in (ActionEnum.EVALUASI_KECOCOKAN, ActionEnum.BANDINGKAN):
        produk_tampil = state.get("produk_tampil", [])
        args.produk = resolve_product_references(args.produk, produk_tampil)

    # 5. Normalisasi persona & sebutan di state_update
    if state_up.sebutan:
        state_up.sebutan = state_up.sebutan.strip()
    if state_up.persona:
        state_up.persona = state_up.persona.strip().lower()

    return parsed
