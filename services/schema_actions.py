# -*- coding: utf-8 -*-
"""
services/schema_actions.py
Definisi skema Pydantic dan JSON Schema untuk 11 aksi parser Antigravity v2.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field


class ActionEnum(str, Enum):
    SAPA = "sapa"
    CARI_PRODUK = "cari_produk"
    MINTA_REKOMENDASI = "minta_rekomendasi"
    JAWAB_PERTANYAAN_BOT = "jawab_pertanyaan_bot"
    EVALUASI_KECOCOKAN = "evaluasi_kecocokan"
    BANDINGKAN = "bandingkan"
    LANJUTAN_HASIL = "lanjutan_hasil"
    TANYA_INFO_TOKO = "tanya_info_toko"
    PERBAIKI_PERCAKAPAN = "perbaiki_percakapan"
    BASA_BASI = "basa_basi"
    TIDAK_JELAS = "tidak_jelas"


class ActionArguments(BaseModel):
    # cari_produk
    kategori: Optional[str] = None
    merek: Optional[str] = None
    nama_model: Optional[str] = None
    min_harga: Optional[int] = None
    max_harga: Optional[int] = None
    ram_gb_min: Optional[int] = None
    storage_gb_min: Optional[int] = None
    ukuran_layar: Optional[float] = None

    # minta_rekomendasi
    kebutuhan_teks: Optional[str] = None
    persona: Optional[str] = None
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None

    # jawab_pertanyaan_bot
    slot: Optional[str] = None
    nilai: Optional[Union[str, int, float, None]] = None

    # evaluasi_kecocokan & bandingkan
    produk: Optional[List[str]] = None

    # lanjutan_hasil
    jenis: Optional[str] = None  # lebih_murah, lebih_mahal, yang_lain, filter_tambahan
    filter: Optional[Dict[str, Any]] = None

    # tanya_info_toko
    topik: Optional[str] = None  # garansi, servis, pembayaran, pengiriman, jam_buka, alamat, lainnya

    # perbaiki_percakapan
    # jenis: salah_paham, keluhan, koreksi
    rujukan: Optional[str] = None

    # tidak_jelas
    alasan: Optional[str] = None

    model_config = {
        "extra": "ignore"
    }


class StateUpdate(BaseModel):
    persona: Optional[str] = None
    sebutan: Optional[str] = None  # ibu, bapak, kakak, mama, dsb.
    kebutuhan_teks: Optional[str] = None
    budget: Optional[int] = None
    kategori: Optional[str] = None

    model_config = {
        "extra": "ignore"
    }


class ParserOutput(BaseModel):
    aksi: ActionEnum
    argumen: ActionArguments = Field(default_factory=ActionArguments)
    pembaruan_state: StateUpdate = Field(default_factory=StateUpdate)

    model_config = {
        "extra": "ignore"
    }


def get_parser_json_schema() -> dict:
    """Mengembalikan JSON schema dictionary untuk Ollama structured output."""
    return ParserOutput.model_json_schema()
