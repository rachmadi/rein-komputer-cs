# -*- coding: utf-8 -*-
"""
tests/test_putaran14_synthetic.py
Tes berbasis sifat untuk Putaran 14:
1. Kontrak Intent (Parser -> Validator):
   - Validator tidak menghapus nilai diam-diam: {permintaan_asli, argumen_valid, argumen_ditolak[field, nilai, alasan]}
   - Klasifikasi argumen di luar katalog (tidak_ada_di_katalog)
   - Klasifikasi argumen ambigu (ambigu)
   - Klasifikasi argumen sah (valid)
2. Kontrak Hasil (ActionEngine):
   - Argumen ditolak -> status tidak_dijual, tanpa pencarian, tanpa kartu
   - Menolak substitusi diam-diam ke state lama atau default laptop
3. Kontrak Konteks (Generator):
   - Konteks Toko selalu ada di prompt generator
   - Balasan tidak menyebut kategori/merek di luar katalog
"""
import pytest
from services.schema_actions import ParserOutput, ActionEnum, ActionArguments, StateUpdate
from services.validator import validate_parser_output, get_catalog_categories, get_catalog_brands
from services.action_engine import ActionEngine
from services.session_pipeline import SessionPipeline


@pytest.mark.parametrize("luar_kategori", ["monitor", "tablet", "kamera", "keyboard", "smartwatch"])
def test_butir2_kategori_di_luar_katalog_diklasifikasikan_tidak_ada(luar_kategori):
    """Kategori di luar katalog tidak dihapus diam-diam, melainkan masuk argumen_ditolak: tidak_ada_di_katalog."""
    raw = {
        "aksi": "cari_produk",
        "argumen": {"kategori": luar_kategori},
        "pembaruan_state": {"kategori": luar_kategori}
    }
    out, is_valid = validate_parser_output(raw)
    assert is_valid is True
    assert out.kontrak_intent is not None
    ki = out.kontrak_intent
    assert ki["permintaan_asli"]["argumen"].get("kategori") == luar_kategori
    assert any(
        d["field"] == "kategori" and d["nilai"] == luar_kategori and d["alasan"] == "tidak_ada_di_katalog"
        for d in ki["argumen_ditolak"]
    )


@pytest.mark.parametrize("luar_merek", ["macbook", "apple", "dell", "samsung", "toshiba"])
def test_butir2_merek_di_luar_katalog_diklasifikasikan_tidak_ada(luar_merek):
    """Merek di luar katalog diklasifikasikan ke argumen_ditolak: tidak_ada_di_katalog."""
    raw = {
        "aksi": "cari_produk",
        "argumen": {"merek": luar_merek, "kategori": "laptop"},
        "pembaruan_state": {"merek": luar_merek}
    }
    out, is_valid = validate_parser_output(raw)
    assert is_valid is True
    ki = out.kontrak_intent
    assert ki["permintaan_asli"]["argumen"].get("merek") == luar_merek
    assert any(
        d["field"] == "merek" and d["nilai"] == luar_merek and d["alasan"] == "tidak_ada_di_katalog"
        for d in ki["argumen_ditolak"]
    )
    # Argumen yang valid tetap masuk argumen_valid
    assert ki["argumen_valid"].get("kategori") == "laptop"


@pytest.mark.parametrize("kat_katalog", ["laptop", "desktop", "printer"])
def test_butir2_kategori_katalog_valid(kat_katalog):
    """Kategori yang dijual katalog diklasifikasikan sebagai argumen_valid."""
    raw = {
        "aksi": "cari_produk",
        "argumen": {"kategori": kat_katalog},
        "pembaruan_state": {"kategori": kat_katalog}
    }
    out, is_valid = validate_parser_output(raw)
    assert is_valid is True
    ki = out.kontrak_intent
    assert ki["argumen_valid"].get("kategori") == kat_katalog
    assert not any(d["field"] == "kategori" for d in ki["argumen_ditolak"])


# =============================================================================
# BUTIR 3 — Kontrak Hasil (ActionEngine)
# =============================================================================
@pytest.mark.parametrize("luar_item,field", [
    ("monitor", "kategori"),
    ("tablet", "kategori"),
    ("kamera", "kategori"),
    ("keyboard", "kategori"),
    ("apple", "merek"),
    ("logitech", "merek"),
    ("samsung", "merek"),
])
def test_butir3_argumen_ditolak_status_tidak_dijual(luar_item, field):
    """Jika ada argumen ditolak: status tidak_dijual, tanpa pencarian, tanpa produk_list/kartu."""
    engine = ActionEngine()
    raw = {
        "aksi": "cari_produk",
        "argumen": {field: luar_item},
        "pembaruan_state": {field: luar_item}
    }
    validated, is_valid = validate_parser_output(raw)
    res = engine.execute(validated, session_state={})
    assert res.fakta["status"] == "tidak_dijual"
    assert res.produk_list == []
    assert res.fakta.get("belum_dicari") is True
    assert res.fakta.get("kategori_tersedia") == get_catalog_categories()
    assert res.fakta.get("merek_tersedia") == get_catalog_brands()


def test_butir3_tanpa_substitusi_diam_diam_ke_state_lama_atau_default_laptop():
    """State lama berisi laptop, pelanggan meminta monitor -> tidak boleh jatuh ke laptop atau tampilkan kartu."""
    engine = ActionEngine()
    state = {
        "kategori": "laptop",
        "produk_tampil": [{"kode": "KB-L01", "nama": "Acer Aspire Lite 14", "harga": 5199000}]
    }
    raw = {
        "aksi": "cari_produk",
        "argumen": {"kategori": "monitor"},
        "pembaruan_state": {"kategori": "monitor"}
    }
    validated, is_valid = validate_parser_output(raw, session_state=state)
    res = engine.execute(validated, session_state=state)
    assert res.fakta["status"] == "tidak_dijual"
    assert res.produk_list == []
    # Tidak boleh ada kartu produk laptop atau produk apa pun yang dikembalikan
    assert len(res.produk_list) == 0

