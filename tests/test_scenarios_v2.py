# -*- coding: utf-8 -*-
"""
tests/test_scenarios_v2.py
Uji skenario komprehensif Antigravity v2 mencakup seluruh aturan Tabel Perilaku ReIn Komputer:
- Skenario A1 - A12 (Alur percakapan, multi-turn, info murni, koreksi)
- Skenario B1 - B13 (Aturan deterministik, batas katalog, fallback, validasi skema)
Semua skenario dan kalimat pengujian menggunakan kalimat rekaan sintetis murni.
"""
import pytest
from services.schema_actions import (
    ParserOutput, ActionEnum, ActionArguments, StateUpdate,
    SlotEnum, JenisEnum, TokoTopikEnum, AtributSpesifikasiEnum, AlasanTidakJelasEnum
)
from services.action_engine import ActionEngine
from services.validator import validate_parser_output
from services.grounding_checker import GroundingChecker, EMERGENCY_FALLBACK_TEXT
from services.llm_generator import build_deterministic_fallback_text, GeneratorOutput


@pytest.fixture
def engine():
    return ActionEngine()


# =============================================================================
# SKENARIO A1 - A12
# =============================================================================

def test_skenario_a1_sapa(engine):
    """A1: Sapaan awal membuka percakapan secara ramah."""
    parsed = ParserOutput(
        aksi=ActionEnum.SAPA,
        argumen=ActionArguments(),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state={})
    assert res.aksi == ActionEnum.SAPA
    assert res.fakta["status"] == "sapaan"
    assert len(res.produk_list) == 0


def test_skenario_a2_cari_produk_berparameter(engine):
    """A2: Pencarian produk dengan filter parameter eksplisit (kategori, budget)."""
    parsed = ParserOutput(
        aksi=ActionEnum.CARI_PRODUK,
        argumen=ActionArguments(kategori="laptop", max_harga=15000000),
        pembaruan_state=StateUpdate(kategori="laptop", budget=15000000)
    )
    res = engine.execute(parsed, session_state={})
    assert res.aksi == ActionEnum.CARI_PRODUK
    assert res.fakta["status"] == "sukses"
    assert len(res.produk_list) > 0
    for p in res.produk_list:
        assert p["harga"] <= 15000000


def test_skenario_a3_minta_rekomendasi_aktivitas(engine):
    """A3: Rekomendasi kebutuhan komputasi nyata memetakan ke profil katalog."""
    parsed = ParserOutput(
        aksi=ActionEnum.MINTA_REKOMENDASI,
        argumen=ActionArguments(kebutuhan_teks="edit video 4k", kategori="laptop"),
        pembaruan_state=StateUpdate(kebutuhan_teks="edit video 4k")
    )
    res = engine.execute(parsed, session_state={})
    assert res.aksi == ActionEnum.MINTA_REKOMENDASI
    assert res.fakta["status"] == "sukses"
    assert res.profil_id is not None
    assert len(res.produk_list) > 0


def test_skenario_a4_a7_jawab_pertanyaan_bot_update_state(engine):
    """A4 & A7: Jawab pertanyaan bot memperbarui slot state dan melanjutkan eksekusi."""
    state = {"pending_question": "kategori", "kebutuhan_teks": "koding python"}
    parsed = ParserOutput(
        aksi=ActionEnum.JAWAB_PERTANYAAN_BOT,
        argumen=ActionArguments(slot=SlotEnum.KATEGORI, nilai="laptop"),
        pembaruan_state=StateUpdate(kategori="laptop")
    )
    res = engine.execute(parsed, session_state=state)
    assert state.get("pending_question") is None
    assert state.get("kategori") == "laptop"
    assert res.aksi == ActionEnum.MINTA_REKOMENDASI
    assert len(res.produk_list) > 0


def test_skenario_a5_tanya_spesifikasi_info_murni(engine):
    """A5: Tanya spesifikasi adalah info murni dari produk yang sedang tampil."""
    state = {
        "produk_tampil": [
            {"kode": "KB-L01", "nama": "Acer Aspire Lite 14", "kategori": "laptop", "harga": 5199000}
        ]
    }
    parsed = ParserOutput(
        aksi=ActionEnum.TANYA_SPESIFIKASI,
        argumen=ActionArguments(rujukan_produk=["KB-L01"], atribut=AtributSpesifikasiEnum.RAM),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state=state)
    assert res.aksi == ActionEnum.TANYA_SPESIFIKASI
    assert res.fakta["status"] == "sukses"
    assert len(res.fakta["spesifikasi"]) == 1
    assert res.fakta["spesifikasi"][0]["atribut"] == "ram"


def test_skenario_a6_bandingkan_info_murni(engine):
    """A6: Bandingkan produk adalah giliran info murni tanpa pertanyaan penutup."""
    state = {
        "produk_tampil": [
            {"kode": "KB-L01", "nama": "Acer Aspire Lite 14", "kategori": "laptop", "harga": 5199000},
            {"kode": "KB-L02", "nama": "Lenovo IdeaPad Slim 3", "kategori": "laptop", "harga": 6499000}
        ]
    }
    parsed = ParserOutput(
        aksi=ActionEnum.BANDINGKAN,
        argumen=ActionArguments(rujukan_produk=["KB-L01", "KB-L02"]),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state=state)
    assert res.aksi == ActionEnum.BANDINGKAN
    assert res.fakta["status"] == "sukses"
    assert len(res.fakta["perbandingan"]) == 2


def test_skenario_a8_evaluasi_kecocokan(engine):
    """A8: Evaluasi kecocokan menilai pemenuhan hardware terhadap profil kebutuhan."""
    state = {
        "produk_tampil": [
            {"kode": "KB-L01", "nama": "Acer Aspire Lite 14", "kategori": "laptop", "harga": 5199000}
        ],
        "profil_aktif": "P05",  # gaming berat (butuh spek tinggi)
        "kebutuhan_teks": "main game berat"
    }
    parsed = ParserOutput(
        aksi=ActionEnum.EVALUASI_KECOCOKAN,
        argumen=ActionArguments(rujukan_produk=["KB-L01"]),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state=state)
    assert res.aksi == ActionEnum.EVALUASI_KECOCOKAN
    assert res.fakta["status"] == "sukses"
    assert len(res.fakta["evaluasi_produk"]) == 1
    # KB-L01 tanpa dedicated GPU harus di bawah minimum untuk P05
    assert res.fakta["evaluasi_produk"][0]["status_kecocokan"] == "di_bawah_minimum"


def test_skenario_a9_tanya_info_toko_hanya_kontak_staf(engine):
    """A9: Tanya info toko mengarahkan ke staf tanpa estimasi janji respons."""
    parsed = ParserOutput(
        aksi=ActionEnum.TANYA_INFO_TOKO,
        argumen=ActionArguments(topik=TokoTopikEnum.GARANSI),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state={})
    assert res.aksi == ActionEnum.TANYA_INFO_TOKO
    assert res.fakta["status"] == "info_toko"
    assert "kontak_staf" in res.fakta


def test_skenario_a10_basa_basi(engine):
    """A10: Percakapan santai / ucapan terima kasih."""
    parsed = ParserOutput(
        aksi=ActionEnum.BASA_BASI,
        argumen=ActionArguments(jenis=JenisEnum.TERIMA_KASIH),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state={})
    assert res.aksi == ActionEnum.BASA_BASI
    assert res.fakta["status"] == "basa_basi"


def test_skenario_a11_perbaiki_percakapan(engine):
    """A11: Koreksi pelanggan diperbarui di state dan dicatat faktanya."""
    state = {"kategori": "desktop"}
    parsed = ParserOutput(
        aksi=ActionEnum.PERBAIKI_PERCAKAPAN,
        argumen=ActionArguments(jenis=JenisEnum.KOREKSI, rujukan="saya minta laptop bukan desktop"),
        pembaruan_state=StateUpdate(kategori="laptop")
    )
    res = engine.execute(parsed, session_state=state)
    assert res.aksi == ActionEnum.PERBAIKI_PERCAKAPAN
    assert res.fakta["status"] == "sukses"
    assert state.get("kategori") == "laptop"


def test_skenario_a12_tidak_jelas(engine):
    """A12: Pesan tidak jelas mengembalikan alasan tertutup."""
    parsed = ParserOutput(
        aksi=ActionEnum.TIDAK_JELAS,
        argumen=ActionArguments(alasan=AlasanTidakJelasEnum.TIDAK_DIPAHAMI),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state={})
    assert res.aksi == ActionEnum.TIDAK_JELAS
    assert res.fakta["status"] == "tidak_jelas"
    assert res.fakta["alasan"] == "tidak_dipahami"


# =============================================================================
# SKENARIO B1 - B13
# =============================================================================

def test_skenario_b1_persona_saja(engine):
    """B1: Persona saja tanpa aktivitas konkret -> tanya_kebutuhan, tanpa produk."""
    parsed = ParserOutput(
        aksi=ActionEnum.MINTA_REKOMENDASI,
        argumen=ActionArguments(persona="guru sekolah dasar"),
        pembaruan_state=StateUpdate(persona="guru sekolah dasar")
    )
    res = engine.execute(parsed, session_state={})
    assert res.fakta["status"] == "tanya_kebutuhan"
    assert len(res.produk_list) == 0


def test_skenario_b2_kategori_atau_merek_saja(engine):
    """B2: Kategori saja atau merek saja -> max 3 produk dan butuh_persempit."""
    parsed = ParserOutput(
        aksi=ActionEnum.CARI_PRODUK,
        argumen=ActionArguments(kategori="desktop"),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state={})
    assert res.fakta["status"] == "sukses"
    assert res.fakta["butuh_persempit"] is True
    assert 0 < len(res.produk_list) <= 3


def test_skenario_b3_kategori_lanjutan_dari_produk_tampil(engine):
    """B3: Lanjutan hasil mempertahankan kategori aktif dari produk_tampil sebelumnya."""
    state = {
        "produk_tampil": [
            {"kode": "KB-D01", "nama": "HP All-in-One 24", "kategori": "desktop", "harga": 12499000}
        ]
    }
    parsed = ParserOutput(
        aksi=ActionEnum.LANJUTAN_HASIL,
        argumen=ActionArguments(jenis=JenisEnum.LEBIH_MURAH),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state=state)
    assert res.aksi == ActionEnum.LANJUTAN_HASIL
    for p in res.produk_list:
        assert p["kategori"] == "desktop"


def test_skenario_b4_profil_tidak_ditemukan_berulang(engine):
    """B4: Profil tidak ditemukan via RAG menaikkan counter dan menawarkan kontak staf pada pengulangan."""
    state = {"consecutive_profile_misses": 0}
    parsed = ParserOutput(
        aksi=ActionEnum.MINTA_REKOMENDASI,
        argumen=ActionArguments(kebutuhan_teks="aktivitas_antariksa_eksotis_xyz_999"),
        pembaruan_state=StateUpdate()
    )
    # Putaran 1
    res1 = engine.execute(parsed, session_state=state)
    assert res1.fakta["status"] == "profil_tidak_ditemukan"
    assert state["consecutive_profile_misses"] == 1
    # Putaran 2
    res2 = engine.execute(parsed, session_state=state)
    assert res2.fakta["status"] == "profil_tidak_ditemukan_berulang"
    assert "kontak_staf" in res2.fakta


def test_skenario_b6_tidak_ada_produk_memenuhi_minimum(engine):
    """B6: Spek minimum terlalu tinggi mengembalikan produk_terdekat dan kekurangannya."""
    parsed = ParserOutput(
        aksi=ActionEnum.MINTA_REKOMENDASI,
        argumen=ActionArguments(kategori="laptop", budget_max=9000000),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state={"profil_aktif": "P05"})
    assert res.fakta["status"] == "belum_ada_yang_memenuhi"
    assert "produk_terdekat" in res.fakta
    assert len(res.produk_list) == 0


def test_skenario_b7_anggaran_di_bawah_katalog(engine):
    """B7: Budget di bawah harga termurah katalog -> tidak_ada_dalam_anggaran."""
    parsed = ParserOutput(
        aksi=ActionEnum.CARI_PRODUK,
        argumen=ActionArguments(kategori="laptop", max_harga=2000000),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state={})
    assert res.fakta["status"] == "tidak_ada_dalam_anggaran"
    assert len(res.produk_list) == 0


def test_skenario_b8_tidak_ada_opsi_lebih_murah(engine):
    """B8: Menolak pencarian lebih murah jika produk yang tampil sudah termurah."""
    state = {
        "produk_tampil": [
            {"kode": "KB-L01", "nama": "Acer Aspire Lite 14", "kategori": "laptop", "harga": 5199000}
        ],
        "kategori": "laptop"
    }
    parsed = ParserOutput(
        aksi=ActionEnum.LANJUTAN_HASIL,
        argumen=ActionArguments(jenis=JenisEnum.LEBIH_MURAH),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state=state)
    assert res.fakta["status"] == "tidak_ada_lebih_murah"


def test_skenario_b9_lanjutan_hasil_tanpa_produk_tampil_ditolak():
    """B9: Validator menolak lanjutan_hasil tanpa produk_tampil menjadi tidak_jelas (rujukan_tidak_ada)."""
    raw = {
        "aksi": "lanjutan_hasil",
        "argumen": {"jenis": "lebih_murah"},
        "pembaruan_state": {}
    }
    res, is_valid = validate_parser_output(raw, session_state={"produk_tampil": []})
    assert is_valid is False
    assert res.aksi == ActionEnum.TIDAK_JELAS
    assert res.argumen.alasan == AlasanTidakJelasEnum.RUJUKAN_TIDAK_ADA


def test_skenario_b10_deterministic_fallback():
    """B10: Deterministic fallback text builder menghasilkan teks terstruktur berbasis fakta."""
    fakta = {
        "status": "tidak_ada_dalam_anggaran",
        "harga_termurah_kategori_formatted": "Rp5.199.000"
    }
    teks = build_deterministic_fallback_text("cari_produk", fakta)
    assert "Rp5.199.000" in teks
    assert len(teks) <= 420


def test_skenario_b12_alasan_tidak_jelas_empat_enum():
    """B12: Alasan tidak_jelas dibatasi pada 4 enum tertutup."""
    allowed = {e.value for e in AlasanTidakJelasEnum}
    assert allowed == {"tidak_dipahami", "rujukan_tidak_ada", "bertentangan", "sistem_error"}


def test_skenario_b13_emergency_fallback_constraints():
    """B13: Teks cadangan darurat <= 420 karakter, netral, tanpa janji 'menghubungkan'."""
    assert len(EMERGENCY_FALLBACK_TEXT) <= 420
    assert "menghubungkan" not in EMERGENCY_FALLBACK_TEXT.lower()
