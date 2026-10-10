# -*- coding: utf-8 -*-
"""
services/schema_actions.py
Definisi skema Pydantic dan JSON Schema tertutup untuk 12 aksi parser Antigravity v2.
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
    TANYA_SPESIFIKASI = "tanya_spesifikasi"
    BANDINGKAN = "bandingkan"
    LANJUTAN_HASIL = "lanjutan_hasil"
    TANYA_INFO_TOKO = "tanya_info_toko"
    PERBAIKI_PERCAKAPAN = "perbaiki_percakapan"
    BASA_BASI = "basa_basi"
    TIDAK_JELAS = "tidak_jelas"


class SlotEnum(str, Enum):
    KEBUTUHAN = "kebutuhan"
    AKTIVITAS = "aktivitas"
    BUDGET = "budget"
    KATEGORI = "kategori"
    MEREK = "merek"
    PERSONA = "persona"


class JenisLanjutanEnum(str, Enum):
    LEBIH_MURAH = "lebih_murah"
    TERMURAH_DARI_TAMPIL = "termurah_dari_tampil"
    LEBIH_MAHAL = "lebih_mahal"
    YANG_LAIN = "yang_lain"
    FILTER_TAMBAHAN = "filter_tambahan"


class JenisPerbaikanEnum(str, Enum):
    SALAH_PAHAM = "salah_paham"
    KELUHAN = "keluhan"
    KOREKSI = "koreksi"


class JenisBasaBasiEnum(str, Enum):
    TERIMA_KASIH = "terima_kasih"
    PAMIT = "pamit"
    LAINNYA = "lainnya"


class JenisEnum(str, Enum):
    # lanjutan_hasil
    LEBIH_MURAH = "lebih_murah"
    TERMURAH_DARI_TAMPIL = "termurah_dari_tampil"
    LEBIH_MAHAL = "lebih_mahal"
    YANG_LAIN = "yang_lain"
    FILTER_TAMBAHAN = "filter_tambahan"
    # perbaiki_percakapan
    SALAH_PAHAM = "salah_paham"
    KELUHAN = "keluhan"
    KOREKSI = "koreksi"
    # basa_basi
    TERIMA_KASIH = "terima_kasih"
    PAMIT = "pamit"
    LAINNYA = "lainnya"


class TokoTopikEnum(str, Enum):
    GARANSI = "garansi"
    SERVIS = "servis"
    PEMBAYARAN = "pembayaran"
    PENGIRIMAN = "pengiriman"
    JAM_BUKA = "jam_buka"
    ALAMAT = "alamat"
    LAINNYA = "lainnya"


class AtributSpesifikasiEnum(str, Enum):
    RAM = "ram"
    STORAGE = "storage"
    CPU = "cpu"
    GPU = "gpu"
    LAYAR = "layar"
    BATERAI = "baterai"
    PORT = "port"
    BOBOT = "bobot"
    KEYBOARD = "keyboard"
    KAMERA = "kamera"
    HARGA = "harga"
    LAINNYA = "lainnya"


class AlasanTidakJelasEnum(str, Enum):
    TIDAK_DIPAHAMI = "tidak_dipahami"
    RUJUKAN_TIDAK_ADA = "rujukan_tidak_ada"
    BERTENTANGAN = "bertentangan"
    SISTEM_ERROR = "sistem_error"


class ActionArguments(BaseModel):
    # cari_produk
    kategori: Optional[str] = None
    merek: Optional[str] = None
    merek_kecuali: Optional[str] = None
    nama_model: Optional[str] = None
    gpu: Optional[str] = None
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
    slot: Optional[SlotEnum] = None
    nilai: Optional[Union[str, int, float, None]] = None

    # evaluasi_kecocokan, tanya_spesifikasi, & bandingkan
    rujukan_produk: Optional[List[Union[int, str]]] = None  # nomor urut (1, 2, dll) atau nama dari produk_tampil
    produk: Optional[List[str]] = None                      # kode produk hasil resolusi validator
    produk_luar_katalog: Optional[List[str]] = None         # rujukan produk yang tidak ada di katalog ReIn Komputer
    atribut: Optional[AtributSpesifikasiEnum] = None

    # lanjutan_hasil, perbaiki_percakapan, basa_basi
    jenis: Optional[JenisEnum] = None
    jenis_lanjutan: Optional[Union[JenisEnum, str, None]] = None
    filter: Optional[Dict[str, Any]] = None

    # tanya_info_toko
    topik: Optional[TokoTopikEnum] = None

    # perbaiki_percakapan
    rujukan: Optional[str] = None

    # tidak_jelas (HANYA salah satu dari 4 nilai tertutup B12)
    alasan: Optional[AlasanTidakJelasEnum] = None

    model_config = {
        "extra": "ignore"
    }


class StateUpdate(BaseModel):
    persona: Optional[str] = None
    sebutan: Optional[str] = None  # ibu, bapak, kakak, mama, dsb.
    kebutuhan_teks: Optional[str] = None
    budget: Optional[int] = None
    kategori: Optional[str] = None
    merek: Optional[str] = None

    model_config = {
        "extra": "ignore"
    }


class ParserOutput(BaseModel):
    aksi: ActionEnum
    argumen: ActionArguments = Field(default_factory=ActionArguments)
    pembaruan_state: StateUpdate = Field(default_factory=StateUpdate)
    kontrak_intent: Optional[dict] = None

    model_config = {
        "extra": "ignore"
    }


def get_parser_json_schema(allowed_actions: Optional[List[ActionEnum]] = None) -> dict:
    """Mengembalikan JSON schema dictionary tertutup untuk Ollama structured output."""
    schema = ParserOutput.model_json_schema()
    if "properties" in schema and "kontrak_intent" in schema["properties"]:
        del schema["properties"]["kontrak_intent"]
    if "required" in schema and "kontrak_intent" in schema["required"]:
        schema["required"].remove("kontrak_intent")
    if allowed_actions is not None:
        allowed_vals = [a.value if hasattr(a, "value") else str(a) for a in allowed_actions]
        if "$defs" in schema and "ActionEnum" in schema["$defs"]:
            schema["$defs"]["ActionEnum"]["enum"] = allowed_vals
    return schema
