# -*- coding: utf-8 -*-
import pytest
from services.schema_actions import (
    ParserOutput, ActionEnum, ActionArguments, StateUpdate, get_parser_json_schema,
    SlotEnum, JenisEnum, TokoTopikEnum, AtributSpesifikasiEnum
)
from services.validator import validate_parser_output, resolve_product_references, get_catalog_brands, get_catalog_categories


def test_schema_json_generation():
    schema = get_parser_json_schema()
    assert "properties" in schema
    assert "aksi" in schema["properties"]
    assert "argumen" in schema["properties"]
    assert "pembaruan_state" in schema["properties"]


def test_validator_valid_sapa():
    raw = {"aksi": "sapa", "argumen": {}, "pembaruan_state": {}}
    res, is_valid = validate_parser_output(raw)
    assert is_valid is True
    assert res.aksi == ActionEnum.SAPA


def test_validator_valid_cari_produk_with_gpu_and_merek_kecuali():
    raw = {
        "aksi": "cari_produk",
        "argumen": {
            "kategori": "laptop",
            "merek": "asus",
            "merek_kecuali": "acer",
            "gpu": "rtx 4060",
            "max_harga": 15000000
        },
        "pembaruan_state": {"kategori": "laptop"}
    }
    res, is_valid = validate_parser_output(raw)
    assert is_valid is True
    assert res.aksi == ActionEnum.CARI_PRODUK
    assert res.argumen.gpu == "rtx 4060"
    assert res.argumen.merek_kecuali == "acer"


def test_validator_valid_tanya_spesifikasi():
    state = {
        "produk_tampil": [
            {"no": 1, "kode": "KB-L01", "nama": "Laptop A"}
        ]
    }
    raw = {
        "aksi": "tanya_spesifikasi",
        "argumen": {"produk": ["1"], "atribut": "layar"},
        "pembaruan_state": {}
    }
    res, is_valid = validate_parser_output(raw, session_state=state)
    assert is_valid is True
    assert res.aksi == ActionEnum.TANYA_SPESIFIKASI
    assert res.argumen.produk == ["KB-L01"]
    assert res.argumen.atribut == AtributSpesifikasiEnum.LAYAR


def test_validator_invalid_json_type():
    res, is_valid = validate_parser_output("bukan dict")
    assert is_valid is False
    assert res.aksi == ActionEnum.TIDAK_JELAS
    assert "bukan objek" in res.argumen.alasan.lower()


def test_validator_invalid_action_enum():
    raw = {"aksi": "aksi_tidak_ada", "argumen": {}}
    res, is_valid = validate_parser_output(raw)
    assert is_valid is False
    assert res.aksi == ActionEnum.TIDAK_JELAS


def test_validator_invalid_closed_enum_values_rejected():
    # 'pengingat' bukan bagian dari JenisEnum (hanya salah_paham, keluhan, koreksi, dll)
    raw1 = {"aksi": "perbaiki_percakapan", "argumen": {"jenis": "pengingat"}}
    res1, is_valid1 = validate_parser_output(raw1)
    assert is_valid1 is False
    assert res1.aksi == ActionEnum.TIDAK_JELAS

    # 'klarifikasi' bukan bagian dari JenisEnum
    raw2 = {"aksi": "perbaiki_percakapan", "argumen": {"jenis": "klarifikasi"}}
    res2, is_valid2 = validate_parser_output(raw2)
    assert is_valid2 is False
    assert res2.aksi == ActionEnum.TIDAK_JELAS

    # 'alamat_toko' bukan bagian dari TokoTopikEnum (harus 'alamat')
    raw3 = {"aksi": "tanya_info_toko", "argumen": {"topik": "alamat_toko"}}
    res3, is_valid3 = validate_parser_output(raw3)
    assert is_valid3 is False
    assert res3.aksi == ActionEnum.TIDAK_JELAS


def test_validator_negative_prices_sanitized():
    raw = {
        "aksi": "cari_produk",
        "argumen": {"min_harga": -5000, "max_harga": 10000000},
        "pembaruan_state": {"budget": -100}
    }
    res, is_valid = validate_parser_output(raw)
    assert is_valid is True
    assert res.argumen.min_harga is None
    assert res.argumen.max_harga == 10000000
    assert res.pembaruan_state.budget is None


def test_validator_resolve_product_ordinal():
    state = {
        "produk_tampil": [
            {"no": 1, "kode": "KB-L01", "nama": "Laptop A"},
            {"no": 2, "kode": "KB-L02", "nama": "Laptop B"},
            {"no": 3, "kode": "KB-L03", "nama": "Laptop C"}
        ]
    }
    raw = {
        "aksi": "evaluasi_kecocokan",
        "argumen": {"rujukan_produk": [2]},
        "pembaruan_state": {}
    }
    res, is_valid = validate_parser_output(raw, session_state=state)
    assert is_valid is True
    assert res.aksi == ActionEnum.EVALUASI_KECOCOKAN
    assert res.argumen.produk == ["KB-L02"]


def test_validator_unmatched_product_reference_rejected():
    state = {
        "produk_tampil": [
            {"no": 1, "kode": "KB-L01", "nama": "Laptop A"},
            {"no": 2, "kode": "KB-L02", "nama": "Laptop B"}
        ]
    }
    # User asks about product #5 or "macbook" which is not in produk_tampil
    raw1 = {
        "aksi": "evaluasi_kecocokan",
        "argumen": {"rujukan_produk": [5]},
        "pembaruan_state": {}
    }
    res1, is_valid1 = validate_parser_output(raw1, session_state=state)
    assert is_valid1 is False
    assert res1.aksi == ActionEnum.TIDAK_JELAS

    raw2 = {
        "aksi": "tanya_spesifikasi",
        "argumen": {"rujukan_produk": ["macbook pro"], "atribut": "ram"},
        "pembaruan_state": {}
    }
    res2, is_valid2 = validate_parser_output(raw2, session_state=state)
    assert is_valid2 is False
    assert res2.aksi == ActionEnum.TIDAK_JELAS

