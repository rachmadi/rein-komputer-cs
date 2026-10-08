# -*- coding: utf-8 -*-
import pytest
from services.schema_actions import ParserOutput, ActionEnum, ActionArguments, StateUpdate, get_parser_json_schema
from services.validator import validate_parser_output, resolve_product_references, get_catalog_brands, get_catalog_categories


def test_schema_json_generation():
    schema = get_parser_json_schema()
    assert "properties" in schema
    assert "aksi" in schema["properties"]
    assert "argumen" in schema["properties"]
    assert "pembaruan_state" in schema["properties"]


def test_validator_valid_sapa():
    raw = {"aksi": "sapa", "argumen": {}, "pembaruan_state": {}}
    res = validate_parser_output(raw)
    assert res.aksi == ActionEnum.SAPA


def test_validator_valid_cari_produk():
    raw = {
        "aksi": "cari_produk",
        "argumen": {"kategori": "laptop", "merek": "acer", "max_harga": 15000000},
        "pembaruan_state": {"kategori": "laptop"}
    }
    res = validate_parser_output(raw)
    assert res.aksi == ActionEnum.CARI_PRODUK
    assert res.argumen.kategori == "laptop"
    assert res.argumen.merek == "acer"
    assert res.argumen.max_harga == 15000000


def test_validator_invalid_json_type():
    res = validate_parser_output("bukan dict")
    assert res.aksi == ActionEnum.TIDAK_JELAS
    assert "bukan objek" in res.argumen.alasan.lower()


def test_validator_invalid_action_enum():
    raw = {"aksi": "aksi_tidak_ada", "argumen": {}}
    res = validate_parser_output(raw)
    assert res.aksi == ActionEnum.TIDAK_JELAS
    assert "skema tidak valid" in res.argumen.alasan.lower()


def test_validator_negative_prices_sanitized():
    raw = {
        "aksi": "cari_produk",
        "argumen": {"min_harga": -5000, "max_harga": 10000000},
        "pembaruan_state": {"budget": -100}
    }
    res = validate_parser_output(raw)
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
        "argumen": {"produk": ["yang kedua"]},
        "pembaruan_state": {}
    }
    res = validate_parser_output(raw, session_state=state)
    assert res.aksi == ActionEnum.EVALUASI_KECOCOKAN
    assert res.argumen.produk == ["KB-L02"]


def test_validator_resolve_product_all_when_empty():
    state = {
        "produk_tampil": [
            {"no": 1, "kode": "KB-L01", "nama": "Laptop A"},
            {"no": 2, "kode": "KB-L02", "nama": "Laptop B"}
        ]
    }
    raw = {
        "aksi": "evaluasi_kecocokan",
        "argumen": {"produk": []},
        "pembaruan_state": {}
    }
    res = validate_parser_output(raw, session_state=state)
    assert res.argumen.produk == ["KB-L01", "KB-L02"]


def test_validator_catalog_brands_dynamic():
    brands = get_catalog_brands()
    assert isinstance(brands, list)
    assert len(brands) > 0
    assert "lenovo" in brands or "asus" in brands
