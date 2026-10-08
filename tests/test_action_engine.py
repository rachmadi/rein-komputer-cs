# -*- coding: utf-8 -*-
import pytest
from services.schema_actions import (
    ParserOutput, ActionEnum, ActionArguments, StateUpdate,
    AtributSpesifikasiEnum, JenisEnum, TokoTopikEnum
)
from services.action_engine import ActionEngine


@pytest.fixture
def engine():
    return ActionEngine()


def test_action_engine_sapa(engine):
    parsed = ParserOutput(aksi=ActionEnum.SAPA, argumen=ActionArguments(), pembaruan_state=StateUpdate())
    res = engine.execute(parsed, session_state={"sebutan": "kakak"})
    assert res.aksi == ActionEnum.SAPA
    assert res.fakta["status"] == "sapaan"
    assert res.fakta["sebutan"] == "kakak"


def test_action_engine_cari_produk_brand(engine):
    parsed = ParserOutput(
        aksi=ActionEnum.CARI_PRODUK,
        argumen=ActionArguments(merek="asus", kategori="laptop"),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state={})
    assert res.aksi == ActionEnum.CARI_PRODUK
    assert res.fakta["status"] == "sukses"
    assert len(res.produk_list) > 0
    for p in res.produk_list:
        assert "asus" in p["nama"].lower()


def test_action_engine_cari_produk_exception(engine):
    parsed = ParserOutput(
        aksi=ActionEnum.CARI_PRODUK,
        argumen=ActionArguments(kategori="laptop", merek_kecuali="acer"),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state={})
    assert res.fakta["status"] == "sukses"
    for p in res.produk_list:
        assert "acer" not in p["nama"].lower()


def test_action_engine_minta_rekomendasi(engine):
    parsed = ParserOutput(
        aksi=ActionEnum.MINTA_REKOMENDASI,
        argumen=ActionArguments(kebutuhan_teks="editing video youtube 4k premiere pro"),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state={})
    assert res.aksi == ActionEnum.MINTA_REKOMENDASI
    assert res.fakta["status"] == "sukses"
    assert "profil" in res.fakta
    assert len(res.produk_list) > 0
    # Match report harus ada
    assert "match_report" in res.produk_list[0]


def test_action_engine_evaluasi_kecocokan(engine):
    state = {
        "profil_aktif": "P01",
        "produk_tampil": [{"no": 1, "kode": "KB-L01"}]
    }
    parsed = ParserOutput(
        aksi=ActionEnum.EVALUASI_KECOCOKAN,
        argumen=ActionArguments(produk=["KB-L01"]),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state=state)
    assert res.aksi == ActionEnum.EVALUASI_KECOCOKAN
    assert res.fakta["status"] == "sukses"
    assert len(res.fakta["evaluasi_produk"]) == 1
    eval_p = res.fakta["evaluasi_produk"][0]
    assert eval_p["kode"] == "KB-L01"
    assert "lolos" in eval_p
    assert "terpenuhi" in eval_p


def test_action_engine_tanya_spesifikasi(engine):
    parsed = ParserOutput(
        aksi=ActionEnum.TANYA_SPESIFIKASI,
        argumen=ActionArguments(produk=["KB-L01"], atribut=AtributSpesifikasiEnum.RAM),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state={})
    assert res.aksi == ActionEnum.TANYA_SPESIFIKASI
    assert res.fakta["status"] == "sukses"
    assert len(res.fakta["spesifikasi"]) == 1
    item = res.fakta["spesifikasi"][0]
    assert item["kode"] == "KB-L01"
    assert "8" in item["nilai_spesifikasi"] or "DDR" in item["nilai_spesifikasi"]


def test_action_engine_bandingkan(engine):
    parsed = ParserOutput(
        aksi=ActionEnum.BANDINGKAN,
        argumen=ActionArguments(produk=["KB-L01", "KB-L02"]),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state={})
    assert res.aksi == ActionEnum.BANDINGKAN
    assert res.fakta["status"] == "sukses"
    assert len(res.fakta["perbandingan"]) == 2


def test_action_engine_lanjutan_hasil_lebih_murah(engine):
    state = {
        "produk_tampil": [
            {"kode": "KB-L03", "harga": 8799000}
        ],
        "kategori": "laptop"
    }
    parsed = ParserOutput(
        aksi=ActionEnum.LANJUTAN_HASIL,
        argumen=ActionArguments(jenis=JenisEnum.LEBIH_MURAH),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state=state)
    assert res.aksi == ActionEnum.LANJUTAN_HASIL
    assert res.fakta["status"] == "sukses"
    for p in res.produk_list:
        assert p["harga"] < 8799000


def test_action_engine_tanya_info_toko(engine):
    parsed = ParserOutput(
        aksi=ActionEnum.TANYA_INFO_TOKO,
        argumen=ActionArguments(topik=TokoTopikEnum.GARANSI),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state={})
    assert res.aksi == ActionEnum.TANYA_INFO_TOKO
    assert res.fakta["data_tersedia"] is False
    assert "@cs_bobbycomputer" in res.fakta["kontak_staf"]
