# -*- coding: utf-8 -*-
"""
tests/test_scenarios_v2.py
Uji skenario komprehensif Antigravity v2 ReIn Komputer mencakup:
- Skenario A1 - A12 (Alur percakapan, multi-turn, info murni, koreksi)
- Aturan Deterministik B1 - B18 (Validasi, isolasi, batas sistem, fallback)
Seluruh pengujian menggunakan data sintetis, stub parser/generator (tanpa LLM live),
menegaskan perilaku deterministik sesuai Tabel Perilaku ReIn Komputer.
"""
import pytest
from unittest.mock import patch, MagicMock

from services.schema_actions import (
    ParserOutput, ActionEnum, ActionArguments, StateUpdate,
    SlotEnum, JenisEnum, TokoTopikEnum, AtributSpesifikasiEnum, AlasanTidakJelasEnum
)
from services.action_engine import ActionEngine, ActionResult
from services.validator import validate_parser_output
from services.grounding_checker import GroundingChecker
from services.llm_generator import build_deterministic_fallback_text, GeneratorOutput
from services.session_pipeline import SessionPipeline
from core.config import KONTAK_STAF


@pytest.fixture
def engine():
    return ActionEngine()


@pytest.fixture
def pipeline():
    return SessionPipeline()


# =============================================================================
# SKENARIO PERCAKAPAN A1 - A12
# =============================================================================

def test_A1_sapa(engine):
    """A1: Sapaan awal membuka percakapan ramah dengan sebutan Kakak/Kak."""
    parsed = ParserOutput(
        aksi=ActionEnum.SAPA,
        argumen=ActionArguments(),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state={})
    assert res.aksi == ActionEnum.SAPA
    assert res.fakta["status"] == "sapaan"
    assert len(res.produk_list) == 0


def test_A2_minta_rekomendasi(engine):
    """A2: Rekomendasi kebutuhan komputasi nyata memetakan ke profil katalog."""
    parsed = ParserOutput(
        aksi=ActionEnum.MINTA_REKOMENDASI,
        argumen=ActionArguments(kebutuhan_teks="kantor excel spreadsheet dan tugas kuliah", kategori="laptop"),
        pembaruan_state=StateUpdate(kebutuhan_teks="kantor excel spreadsheet dan tugas kuliah")
    )
    res = engine.execute(parsed, session_state={})
    assert res.aksi == ActionEnum.MINTA_REKOMENDASI
    assert res.fakta["status"] == "sukses"
    assert res.profil_id is not None
    assert len(res.produk_list) > 0


def test_A3_cari_produk(engine):
    """A3: Pencarian produk eksplisit dengan filter spesifikasi/anggaran."""
    parsed = ParserOutput(
        aksi=ActionEnum.CARI_PRODUK,
        argumen=ActionArguments(kategori="laptop", max_harga=12000000),
        pembaruan_state=StateUpdate(kategori="laptop", budget=12000000)
    )
    res = engine.execute(parsed, session_state={})
    assert res.aksi == ActionEnum.CARI_PRODUK
    assert res.fakta["status"] == "sukses"
    assert len(res.produk_list) > 0
    for p in res.produk_list:
        assert p["harga"] <= 12000000


def test_A4_jawab_pertanyaan_bot(engine):
    """A4: Menjawab pertanyaan bot memperbarui slot state dan mengeksekusi pencarian."""
    state = {
        "pending_question": "kebutuhan",
        "kategori": "laptop"
    }
    parsed = ParserOutput(
        aksi=ActionEnum.JAWAB_PERTANYAAN_BOT,
        argumen=ActionArguments(slot=SlotEnum.KEBUTUHAN, nilai="kantor excel dan ketik skripsi"),
        pembaruan_state=StateUpdate(kebutuhan_teks="kantor excel dan ketik skripsi")
    )
    res = engine.execute(parsed, session_state=state)
    assert res.fakta["status"] == "sukses"
    assert len(res.produk_list) > 0


def test_A5_evaluasi_kecocokan(engine):
    """A5: Evaluasi hardware produk yang tampil terhadap kebutuhan spesifik."""
    state = {
        "produk_tampil": [
            {"kode": "KB-L01", "nama": "Advan Workplus", "kategori": "laptop", "harga": 7299000, "cpu_tier": 2, "ram_gb": 16, "storage_ssd_gb": 512, "vram_gb": 0}
        ],
        "profil_aktif": "P01"
    }
    parsed = ParserOutput(
        aksi=ActionEnum.EVALUASI_KECOCOKAN,
        argumen=ActionArguments(produk=["KB-L01"]),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state=state)
    assert res.aksi == ActionEnum.EVALUASI_KECOCOKAN
    assert res.fakta["status"] == "sukses"
    eval_list = res.fakta.get("evaluasi_produk") or []
    assert len(eval_list) > 0
    assert eval_list[0]["status_kecocokan"] in ("memenuhi_minimum", "memenuhi_rekomendasi", "di_bawah_minimum")


def test_A6_tanya_spesifikasi(engine):
    """A6: Tanya spesifikasi teknis spesifik produk yang tampil (info murni)."""
    state = {
        "produk_tampil": [
            {"kode": "KB-L01", "nama": "Advan Workplus", "kategori": "laptop", "harga": 7299000, "ram": "16 GB LPDDR5"}
        ]
    }
    parsed = ParserOutput(
        aksi=ActionEnum.TANYA_SPESIFIKASI,
        argumen=ActionArguments(produk=["KB-L01"], atribut=AtributSpesifikasiEnum.RAM),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state=state)
    assert res.aksi == ActionEnum.TANYA_SPESIFIKASI
    assert res.fakta["status"] == "sukses"
    assert res.fakta["atribut_ditanya"] == "ram"


def test_A7_bandingkan(engine):
    """A7: Perbandingan spesifikasi berdampingan untuk dua produk (info murni)."""
    state = {
        "produk_tampil": [
            {"kode": "KB-L01", "nama": "Advan Workplus", "kategori": "laptop", "harga": 7299000},
            {"kode": "KB-L02", "nama": "ASUS Vivobook Go 14", "kategori": "laptop", "harga": 6299000}
        ]
    }
    parsed = ParserOutput(
        aksi=ActionEnum.BANDINGKAN,
        argumen=ActionArguments(produk=["KB-L01", "KB-L02"]),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state=state)
    assert res.aksi == ActionEnum.BANDINGKAN
    assert res.fakta["status"] == "sukses"
    assert len(res.fakta.get("perbandingan") or res.fakta.get("produk_dibandingkan") or []) == 2


def test_A8_lanjutan_hasil(engine):
    """A8: Lanjutan hasil memperbarui hasil berdasarkan patokan harga sebelumnya."""
    state = {
        "produk_tampil": [
            {"kode": "KB-L01", "nama": "Advan Workplus", "kategori": "laptop", "harga": 7299000}
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
    assert res.fakta["status"] in ("sukses", "tidak_ada_lebih_murah")


def test_A9_tanya_info_toko(engine):
    """A9: Tanya info operasional toko hanya memberikan kontak staf tanpa janji durasi."""
    parsed = ParserOutput(
        aksi=ActionEnum.TANYA_INFO_TOKO,
        argumen=ActionArguments(topik=TokoTopikEnum.GARANSI),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state={})
    assert res.aksi == ActionEnum.TANYA_INFO_TOKO
    assert res.fakta["data_tersedia"] is False
    assert KONTAK_STAF in res.fakta["kontak_staf"]


def test_A10_perbaiki_percakapan(engine):
    """A10: Koreksi pelanggan memperbarui state yang keliru tanpa berdebat."""
    state = {"kategori": "laptop", "budget": 10000000}
    parsed = ParserOutput(
        aksi=ActionEnum.PERBAIKI_PERCAKAPAN,
        argumen=ActionArguments(jenis=JenisEnum.KOREKSI),
        pembaruan_state=StateUpdate(kategori="desktop")
    )
    res = engine.execute(parsed, session_state=state)
    assert res.aksi == ActionEnum.PERBAIKI_PERCAKAPAN
    assert res.fakta["status"] == "sukses"
    assert res.fakta["jenis"] == "koreksi"


def test_A11_basa_basi(engine):
    """A11: Percakapan penutup / terima kasih / pamit ditanggapi sopan tanpa pencarian."""
    parsed = ParserOutput(
        aksi=ActionEnum.BASA_BASI,
        argumen=ActionArguments(jenis=JenisEnum.TERIMA_KASIH),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state={})
    assert res.aksi == ActionEnum.BASA_BASI
    assert res.fakta["status"] == "basa_basi"
    assert len(res.produk_list) == 0


def test_A12_tidak_jelas(engine):
    """A12: Pesan tidak jelas dibatasi hanya pada 4 enum alasan tertutup."""
    for alasan in [AlasanTidakJelasEnum.TIDAK_DIPAHAMI, AlasanTidakJelasEnum.RUJUKAN_TIDAK_ADA, AlasanTidakJelasEnum.BERTENTANGAN, AlasanTidakJelasEnum.SISTEM_ERROR]:
        parsed = ParserOutput(
            aksi=ActionEnum.TIDAK_JELAS,
            argumen=ActionArguments(alasan=alasan),
            pembaruan_state=StateUpdate()
        )
        res = engine.execute(parsed, session_state={})
        assert res.aksi == ActionEnum.TIDAK_JELAS
        assert res.fakta["alasan"] == alasan.value


# =============================================================================
# ATURAN DETERMINISTIK & BATAS SISTEM B1 - B18
# =============================================================================

def test_B1_persona_saja_tanpa_aktivitas(engine):
    """B1: Pelanggan menyebut persona SAJA -> tanya_kebutuhan, dilarang tampilkan produk."""
    parsed = ParserOutput(
        aksi=ActionEnum.MINTA_REKOMENDASI,
        argumen=ActionArguments(persona="guru sekolah dasar"),
        pembaruan_state=StateUpdate(persona="guru sekolah dasar")
    )
    res = engine.execute(parsed, session_state={})
    assert res.fakta["status"] == "tanya_kebutuhan"
    assert len(res.produk_list) == 0


def test_B2_kategori_atau_merek_saja(engine):
    """B2: Pelanggan menyebut kategori SAJA atau merek SAJA -> cari_produk max 3 dan butuh_persempit."""
    parsed = ParserOutput(
        aksi=ActionEnum.CARI_PRODUK,
        argumen=ActionArguments(merek="lenovo"),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state={})
    assert res.fakta["status"] == "sukses"
    assert res.fakta.get("butuh_persempit") is True
    assert 0 < len(res.produk_list) <= 3


def test_B3_kategori_lanjutan_hasil_dari_produk_tampil(engine):
    """B3: Di lanjutan_hasil, kategori aktif diwarisi dari produk_tampil di sesi."""
    state = {
        "produk_tampil": [
            {"kode": "KB-D01", "nama": "HP All-in-One 24", "kategori": "desktop", "harga": 12499000}
        ],
        "kategori": None
    }
    parsed = ParserOutput(
        aksi=ActionEnum.LANJUTAN_HASIL,
        argumen=ActionArguments(jenis=JenisEnum.LEBIH_MURAH),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state=state)
    assert res.fakta.get("kategori") == "desktop" or res.fakta.get("kategori_dipakai") == "desktop"


def test_B4_profil_tidak_ditemukan_berulang(engine):
    """B4: Profil RAG meleset berulang -> tawarkan kategori/budget atau kontak staf."""
    state = {"consecutive_profile_misses": 1}
    with patch("services.action_engine.get_usage_requirements", return_value={"profil": []}):
        parsed = ParserOutput(
            aksi=ActionEnum.MINTA_REKOMENDASI,
            argumen=ActionArguments(kebutuhan_teks="keperluan observasi satelit cuaca"),
            pembaruan_state=StateUpdate()
        )
        res = engine.execute(parsed, session_state=state)
        assert res.fakta["status"] == "profil_tidak_ditemukan_berulang"
        assert KONTAK_STAF in res.fakta["kontak_staf"]


def test_B5_qdrant_embedding_mati_sistem_error(engine):
    """B5: Qdrant/embedding mati saat minta_rekomendasi -> status sistem_error."""
    with patch("services.action_engine.get_usage_requirements", side_effect=ConnectionError("Qdrant offline")):
        parsed = ParserOutput(
            aksi=ActionEnum.MINTA_REKOMENDASI,
            argumen=ActionArguments(kebutuhan_teks="kuliah arsitektur"),
            pembaruan_state=StateUpdate()
        )
        res = engine.execute(parsed, session_state={})
        assert res.fakta["status"] == "sistem_error"
        assert KONTAK_STAF in res.fakta["kontak_staf"]


def test_B6_tidak_ada_produk_memenuhi_minimum(engine):
    """B6: Tidak ada produk memenuhi spesifikasi minimum -> fakta produk_terdekat & kekurangan."""
    fake_prof = {
        "id": "P99",
        "judul": "Profil Ekstrem",
        "filter": [{"field": "ram_gb", "op": ">=", "value": 128, "mandatory": True}]
    }
    with patch("services.action_engine.get_usage_requirements", return_value={"profil": [{"profil_id": "P99"}]}), \
         patch("services.action_engine.get_profile_by_id", return_value=fake_prof):
        parsed = ParserOutput(
            aksi=ActionEnum.MINTA_REKOMENDASI,
            argumen=ActionArguments(kebutuhan_teks="komputasi super berat"),
            pembaruan_state=StateUpdate()
        )
        res = engine.execute(parsed, session_state={"profil_aktif": "P99"})
        assert res.fakta["status"] == "belum_ada_yang_memenuhi"
        assert "produk_terdekat" in res.fakta
        assert len(res.fakta["produk_terdekat"]["kekurangan"]) > 0


def test_B7_tidak_ada_dalam_anggaran_dan_opsi_termurah(engine):
    """B7: Anggaran di bawah harga terendah katalog -> tidak_ada_dalam_anggaran + harga termurah."""
    parsed = ParserOutput(
        aksi=ActionEnum.CARI_PRODUK,
        argumen=ActionArguments(kategori="laptop", max_harga=2000000),
        pembaruan_state=StateUpdate(budget=2000000)
    )
    res = engine.execute(parsed, session_state={})
    assert res.fakta["status"] == "tidak_ada_dalam_anggaran"
    assert res.fakta["harga_termurah_kategori"] > 2000000


def test_B8_tidak_ada_opsi_lebih_murah_atau_lebih_mahal(engine):
    """B8: Opsi lebih murah / lebih mahal simetris melaporkan batas katalog."""
    state = {
        "produk_tampil": [
            {"kode": "KB-L05", "nama": "Lenovo IdeaPad 1", "kategori": "laptop", "harga": 5199000}
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


def test_B9_rujukan_tidak_ada_tanpa_produk_tampil():
    """B9: lanjutan_hasil tanpa produk_tampil di sesi ditolak validator -> rujukan_tidak_ada."""
    raw = {
        "aksi": "lanjutan_hasil",
        "argumen": {"jenis": "lebih_murah"},
        "pembaruan_state": {}
    }
    out, valid = validate_parser_output(raw, session_state={})
    assert out.aksi == ActionEnum.TIDAK_JELAS
    assert out.argumen.alasan == AlasanTidakJelasEnum.RUJUKAN_TIDAK_ADA


def test_B10_ollama_error_timeout_sistem_error_tanpa_retry():
    """B10: Ollama timeout / network error di parser -> permintaan maaf sistem_error tanpa retry."""
    from services.llm_parser import parse_user_message
    with patch("services.llm_parser._call_ollama_chat", return_value=({"aksi": "tidak_jelas", "argumen": {"alasan": "sistem_error"}}, False, "", "timeout", 0, 0, 0, 0, 0)):
        out, meta = parse_user_message("halo bot", state={})
        assert out.aksi == ActionEnum.TIDAK_JELAS
        assert out.argumen.alasan == AlasanTidakJelasEnum.SISTEM_ERROR
        # Tidak boleh retry pada timeout
        assert meta.get("retried") is False or meta.get("re_parse") is False


def test_B11_rusak_sekali_reparse_satu_kali_baru_tidak_jelas():
    """B11: JSON rusak pertama kali -> coba reparse 1 KALI dengan pesan kesalahan skema."""
    from services.llm_parser import parse_user_message
    call_count = 0
    def mock_ollama(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ({}, False, "bukan json", "json rusak", 0, 0, 0, 0, 0)
        return ({"aksi": "sapa", "argumen": {}, "pembaruan_state": {}}, True, "{}", None, 0, 0, 0, 0, 0)

    with patch("services.llm_parser._call_ollama_chat", side_effect=mock_ollama):
        out, meta = parse_user_message("halo", state={})
        assert call_count == 2
        assert out.aksi == ActionEnum.SAPA


def test_B12_alasan_tidak_jelas_hanya_4_enum():
    """B12: Alasan tidak_jelas hanya sah untuk 4 enum tertutup."""
    valid_reasons = {e.value for e in AlasanTidakJelasEnum}
    assert valid_reasons == {"tidak_dipahami", "rujukan_tidak_ada", "bertentangan", "sistem_error"}


def test_B13_emergency_fallback_text_constraints():
    """B13: Teks cadangan darurat <= 420 karakter, netral, hanya kontak staf fiktif."""
    fakta = {"status": "sistem_error", "kontak_staf": KONTAK_STAF}
    text = build_deterministic_fallback_text("tidak_jelas", fakta)
    assert len(text) <= 420
    assert KONTAK_STAF in text
    assert "menghubungkan" not in text.lower()


def test_B14_evaluasi_tanpa_produk_tanpa_profil(engine):
    """B14: evaluasi_kecocokan tanpa produk dan tanpa profil -> status profil_tidak_ditemukan/belum_ada_produk, tidak boleh sukses dengan evaluasi kosong."""
    parsed = ParserOutput(
        aksi=ActionEnum.EVALUASI_KECOCOKAN,
        argumen=ActionArguments(produk=[]),
        pembaruan_state=StateUpdate()
    )
    with patch("services.action_engine.get_usage_requirements", return_value={"profil": []}):
        res = engine.execute(parsed, session_state={})
        # Wajib menolak status 'sukses' jika produk kosong dan profil tidak ditemukan
        assert res.fakta["status"] in ("profil_tidak_ditemukan", "belum_ada_produk")
        assert res.fakta["status"] != "sukses"


def test_B15_tanya_spesifikasi_atribut_harga_dan_tidak_tersedia(engine):
    """B15: tanya_spesifikasi mendukung atribut harga, dan atribut yang tidak tersedia menghasilkan status atribut_tidak_tersedia tanpa fallback acak."""
    state = {
        "produk_tampil": [
            {"kode": "KB-L01", "nama": "Advan Workplus", "kategori": "laptop", "harga": 7299000}
        ]
    }
    # 1. Atribut harga harus didukung
    parsed_harga = ParserOutput(
        aksi=ActionEnum.TANYA_SPESIFIKASI,
        argumen=ActionArguments(produk=["KB-L01"], atribut=AtributSpesifikasiEnum.HARGA),
        pembaruan_state=StateUpdate()
    )
    res_harga = engine.execute(parsed_harga, session_state=state)
    assert res_harga.fakta["status"] == "sukses"
    assert "7.299.000" in str(res_harga.fakta["spesifikasi"][0]["nilai_spesifikasi"]) or "7299000" in str(res_harga.fakta["spesifikasi"][0]["nilai_spesifikasi"])

    # 2. Atribut tidak tersedia (misal webcam pada printer atau produk tanpa info kamera)
    parsed_kamera = ParserOutput(
        aksi=ActionEnum.TANYA_SPESIFIKASI,
        argumen=ActionArguments(produk=["KB-P01"], atribut=AtributSpesifikasiEnum.KAMERA),
        pembaruan_state=StateUpdate()
    )
    res_kamera = engine.execute(parsed_kamera, session_state={"produk_tampil": [{"kode": "KB-P01", "nama": "Epson L3210", "kategori": "printer"}]})
    assert res_kamera.fakta["status"] == "atribut_tidak_tersedia"


def test_B16_evaluasi_dan_spesifikasi_produk_tidak_di_katalog(engine):
    """B16: Evaluasi & spesifikasi untuk produk di luar katalog -> status produk_tidak_di_katalog + padanan_terdekat."""
    parsed = ParserOutput(
        aksi=ActionEnum.EVALUASI_KECOCOKAN,
        argumen=ActionArguments(produk=["MacBook Air M2"]),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state={"profil_aktif": "P01"})
    assert res.fakta["status"] == "produk_tidak_di_katalog"
    assert "padanan_terdekat" in res.fakta


def test_B17_json_rusak_dua_kali_tidak_jelas_tidak_dipahami():
    """B17: JSON rusak 2 kali -> tidak_jelas dengan alasan tidak_dipahami (bukan sistem_error)."""
    from services.llm_parser import parse_user_message
    with patch("services.llm_parser._call_ollama_chat", return_value=({}, False, "bukan json", "parse error", 0, 0, 0, 0, 0)):
        out, meta = parse_user_message("pesan acak", state={})
        assert out.aksi == ActionEnum.TIDAK_JELAS
        assert out.argumen.alasan == AlasanTidakJelasEnum.TIDAK_DIPAHAMI


def test_B18_kartu_produk_dikirim_setiap_aksi_daftar_produk(pipeline):
    """B18: Kartu produk dikirim untuk SETIAP aksi yang menghasilkan produk_list, bukan hanya 3 aksi."""
    fake_prod = [{"kode": "KB-L01", "nama": "Advan Workplus", "harga": 7299000, "kategori": "laptop"}]
    with patch("services.session_pipeline.parse_user_message", return_value=(
             ParserOutput(aksi=ActionEnum.JAWAB_PERTANYAAN_BOT, argumen=ActionArguments(slot=SlotEnum.KATEGORI, nilai="laptop"), pembaruan_state=StateUpdate()),
             {}
         )), \
         patch.object(pipeline.action_engine, "execute", return_value=ActionResult(
             aksi=ActionEnum.JAWAB_PERTANYAAN_BOT,
             fakta={"status": "sukses", "produk": fake_prod},
             produk_list=fake_prod
         )), \
         patch("services.session_pipeline.generate_response", return_value=(GeneratorOutput(teks="Ini produknya Kak."), {})):
        turn_res, new_state = pipeline.process_turn("laptop", session_state={})
        assert turn_res.kartu_produk_html is not None
        assert "KB-L01" in turn_res.kartu_produk_html
