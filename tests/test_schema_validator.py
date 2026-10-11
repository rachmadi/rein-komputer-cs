# -*- coding: utf-8 -*-
import pytest
from services.schema_actions import (
    ParserOutput, ActionEnum, ActionArguments, StateUpdate, get_parser_json_schema,
    SlotEnum, JenisEnum, TokoTopikEnum, AtributSpesifikasiEnum, AlasanTidakJelasEnum
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
    assert res.argumen.alasan == AlasanTidakJelasEnum.SISTEM_ERROR


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
        "argumen": {"rujukan_produk": ["samsung galaxy book"], "atribut": "ram"},
        "pembaruan_state": {}
    }
    res2, is_valid2 = validate_parser_output(raw2, session_state=state)
    assert is_valid2 is False
    assert res2.aksi == ActionEnum.TIDAK_JELAS


def test_validator_separated_jenis_enums():
    # 'pamit' tidak boleh dipakai di lanjutan_hasil (hanya untuk basa_basi)
    raw1 = {"aksi": "lanjutan_hasil", "argumen": {"jenis": "pamit"}}
    res1, is_valid1 = validate_parser_output(raw1, session_state={"produk_tampil": [{"kode": "KB-01"}]})
    assert is_valid1 is False
    assert res1.aksi == ActionEnum.TIDAK_JELAS

    # 'yang_lain' boleh di lanjutan_hasil
    raw2 = {"aksi": "lanjutan_hasil", "argumen": {"jenis": "yang_lain"}}
    res2, is_valid2 = validate_parser_output(raw2, session_state={"produk_tampil": [{"kode": "KB-01"}]})
    assert is_valid2 is True
    assert res2.aksi == ActionEnum.LANJUTAN_HASIL

    # 'yang_lain' tidak boleh di basa_basi
    raw3 = {"aksi": "basa_basi", "argumen": {"jenis": "yang_lain"}}
    res3, is_valid3 = validate_parser_output(raw3)
    assert is_valid3 is False
    assert res3.aksi == ActionEnum.TIDAK_JELAS

    # 'pamit' boleh di basa_basi
    raw4 = {"aksi": "basa_basi", "argumen": {"jenis": "pamit"}}
    res4, is_valid4 = validate_parser_output(raw4)
    assert is_valid4 is True
    assert res4.aksi == ActionEnum.BASA_BASI


def test_state_consistency_checks():
    from services.validator import check_state_consistency, get_allowed_actions_for_state

    # 1. jawab_pertanyaan_bot tanpa pending_question -> tidak sah
    out_jawab = ParserOutput(aksi=ActionEnum.JAWAB_PERTANYAAN_BOT, argumen=ActionArguments(slot=SlotEnum.PERSONA, nilai="dokter"))
    is_ok, reason = check_state_consistency(out_jawab, session_state={})
    assert is_ok is False
    assert "pending_question" in reason

    # dengan pending_question -> sah
    is_ok_pend, _ = check_state_consistency(out_jawab, session_state={"pending_question": "persona"})
    assert is_ok_pend is True

    # 2. lanjutan_hasil tanpa produk_tampil -> tidak sah
    out_lanjut = ParserOutput(aksi=ActionEnum.LANJUTAN_HASIL, argumen=ActionArguments(jenis=JenisEnum.LEBIH_MURAH))
    is_ok2, reason2 = check_state_consistency(out_lanjut, session_state={})
    assert is_ok2 is False
    assert "produk_tampil" in reason2

    # dengan produk_tampil -> sah
    is_ok_tampil, _ = check_state_consistency(out_lanjut, session_state={"produk_tampil": [{"kode": "KB-01"}]})
    assert is_ok_tampil is True

    # 3. get_allowed_actions_for_state
    allowed_empty = get_allowed_actions_for_state({})
    assert ActionEnum.JAWAB_PERTANYAAN_BOT not in allowed_empty
    assert ActionEnum.LANJUTAN_HASIL not in allowed_empty
    assert ActionEnum.EVALUASI_KECOCOKAN not in allowed_empty
    assert ActionEnum.CARI_PRODUK in allowed_empty

    allowed_with_q = get_allowed_actions_for_state({"pending_question": "budget"})
    assert ActionEnum.JAWAB_PERTANYAAN_BOT in allowed_with_q


def test_parser_reparse_on_state_inconsistency(monkeypatch):
    from services.llm_parser import parse_user_message

    calls = []

    def mock_call_ollama(messages, schema, model, ollama_url, timeout):
        calls.append(schema)
        if len(calls) == 1:
            # Panggilan pertama menghasilkan jawab_pertanyaan_bot padahal pending_question kosong
            return {"aksi": "jawab_pertanyaan_bot", "argumen": {"slot": "persona", "nilai": "guru"}}, True, "{}", None
        else:
            # Panggilan kedua (re-parse dengan enum dibatasi) menghasilkan cari_produk
            return {"aksi": "cari_produk", "argumen": {"kategori": "laptop"}}, True, "{}", None

    monkeypatch.setattr("services.llm_parser._call_ollama_chat", mock_call_ollama)

    output, metrics = parse_user_message("saya guru", state={})
    assert len(calls) == 2
    assert metrics["retried"] is True
    assert output.aksi == ActionEnum.CARI_PRODUK


def test_validator_reject_slot_empty_or_negation():
    # 1. Negasi "tidak ada"
    raw1 = {
        "aksi": "jawab_pertanyaan_bot",
        "argumen": {"slot": "kategori", "nilai": "tidak ada"},
        "pembaruan_state": {}
    }
    res1, is_valid1 = validate_parser_output(raw1, session_state={"pending_question": "kategori"})
    assert is_valid1 is False
    assert res1.aksi == ActionEnum.TIDAK_JELAS
    assert res1.argumen.alasan == AlasanTidakJelasEnum.BERTENTANGAN

    # 2. Negasi "-"
    raw2 = {
        "aksi": "jawab_pertanyaan_bot",
        "argumen": {"slot": "budget", "nilai": "-"},
        "pembaruan_state": {}
    }
    res2, is_valid2 = validate_parser_output(raw2, session_state={"pending_question": "budget"})
    assert is_valid2 is False
    assert res2.aksi == ActionEnum.TIDAK_JELAS

    # 3. Nilai kosong None atau ""
    raw3 = {
        "aksi": "jawab_pertanyaan_bot",
        "argumen": {"slot": "persona", "nilai": ""},
        "pembaruan_state": {}
    }
    res3, is_valid3 = validate_parser_output(raw3, session_state={"pending_question": "persona"})
    assert is_valid3 is False
    assert res3.aksi == ActionEnum.TIDAK_JELAS


def test_validator_reject_rujukan_produk_when_produk_tampil_empty():
    # User / parser memberikan rujukan_produk padahal produk_tampil kosong
    raw = {
        "aksi": "evaluasi_kecocokan",
        "argumen": {"rujukan_produk": [1], "kebutuhan_teks": "kuliah"},
        "pembaruan_state": {}
    }
    res, is_valid = validate_parser_output(raw, session_state={"produk_tampil": []})
    assert is_valid is False
    assert res.aksi == ActionEnum.TIDAK_JELAS
    assert res.argumen.alasan == AlasanTidakJelasEnum.RUJUKAN_TIDAK_ADA

