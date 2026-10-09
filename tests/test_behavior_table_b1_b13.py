# -*- coding: utf-8 -*-
"""
tests/test_behavior_table_b1_b13.py
Uji unit komprehensif untuk aturan Tabel Perilaku ReIn Komputer B1-B13 dan A5-A10.
Semua kalimat dan skenario menggunakan teks sintetis murni.
"""
import json
import pytest
from services.schema_actions import (
    ParserOutput, ActionEnum, ActionArguments, StateUpdate,
    AlasanTidakJelasEnum, JenisEnum, TokoTopikEnum
)
from services.action_engine import ActionEngine
from services.validator import validate_parser_output, resolve_product_references
from services.grounding_checker import EMERGENCY_FALLBACK_TEXT
from services.llm_generator import build_deterministic_fallback_text, EMERGENCY_FALLBACK_TEXT as GEN_FALLBACK_TEXT


@pytest.fixture
def engine():
    return ActionEngine()


def test_b1_persona_saja_tanpa_aktivitas(engine):
    """B1: Pelanggan menyebut persona SAJA (tanpa aktivitas konkret)."""
    parsed = ParserOutput(
        aksi=ActionEnum.MINTA_REKOMENDASI,
        argumen=ActionArguments(persona="mahasiswa baru"),
        pembaruan_state=StateUpdate(persona="mahasiswa baru")
    )
    res = engine.execute(parsed, session_state={})
    assert res.fakta["status"] == "tanya_kebutuhan"
    assert res.fakta["persona"] == "mahasiswa baru"
    assert len(res.produk_list) == 0, "Dilarang menampilkan kartu produk saat persona saja"


def test_b2_kategori_atau_merek_saja(engine):
    """B2: Pelanggan menyebut kategori SAJA atau merek SAJA -> cari_produk max 3 dan butuh_persempit."""
    parsed = ParserOutput(
        aksi=ActionEnum.CARI_PRODUK,
        argumen=ActionArguments(merek="asus"),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state={})
    assert res.fakta["status"] == "sukses"
    assert res.fakta.get("butuh_persempit") is True
    assert 0 < len(res.produk_list) <= 3


def test_b3_kategori_lanjutan_hasil_dari_produk_tampil(engine):
    """B3: Di lanjutan_hasil, kategori aktif diambil dari produk_tampil di sesi."""
    state = {
        "produk_tampil": [
            {"kode": "KB-D01", "nama": "HP All-in-One 24", "kategori": "desktop", "harga": 12499000}
        ],
        "kategori": None  # tidak ada kategori awal di state
    }
    parsed = ParserOutput(
        aksi=ActionEnum.LANJUTAN_HASIL,
        argumen=ActionArguments(jenis=JenisEnum.LEBIH_MURAH),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state=state)
    assert res.aksi == ActionEnum.LANJUTAN_HASIL
    # Semua produk yang dihasilkan harus berkategori desktop, bukan default laptop
    for p in res.produk_list:
        assert p["kategori"] == "desktop"


def test_b4_profil_tidak_ditemukan_berulang(engine):
    """B4: Profil tidak ditemukan di RAG, consecutive counter, tawarkan kategori/kontak staf."""
    state = {"consecutive_profile_misses": 0}
    parsed = ParserOutput(
        aksi=ActionEnum.MINTA_REKOMENDASI,
        argumen=ActionArguments(kebutuhan_teks="aktivitas antariksa gravitasi nol planet mars"),
        pembaruan_state=StateUpdate()
    )
    res1 = engine.execute(parsed, session_state=state)
    assert res1.fakta["status"] == "profil_tidak_ditemukan"
    assert state["consecutive_profile_misses"] == 1

    # Percobaan kedua gagal berturut-turut
    res2 = engine.execute(parsed, session_state=state)
    assert res2.fakta["status"] == "profil_tidak_ditemukan_berulang"
    assert "kontak_staf" in res2.fakta
    assert state["consecutive_profile_misses"] == 2


def test_b6_tidak_ada_produk_memenuhi_minimum(engine):
    """B6: Tidak ada produk memenuhi spesifikasi minimum -> fakta produk terdekat dan kekurangan."""
    # Profil coding berat atau arsitektur dengan syarat spek sangat tinggi yang tidak ada di dummy
    parsed = ParserOutput(
        aksi=ActionEnum.MINTA_REKOMENDASI,
        argumen=ActionArguments(kebutuhan_teks="kuliah arsitektur desain render 3D sketchup autocad", budget_max=5000000),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state={})
    # Anggaran 5 jt untuk render 3D arsitektur akan terpicu tidak_ada_dalam_anggaran atau belum_ada_yang_memenuhi
    assert res.fakta["status"] in ("tidak_ada_dalam_anggaran", "belum_ada_yang_memenuhi")
    assert len(res.produk_list) == 0


def test_b7_anggaran_di_bawah_harga_terendah_katalog(engine):
    """B7: Anggaran di bawah produk termurah di kategori tersebut."""
    parsed = ParserOutput(
        aksi=ActionEnum.CARI_PRODUK,
        argumen=ActionArguments(kategori="laptop", max_harga=2000000),  # 2 juta
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state={})
    assert res.fakta["status"] == "tidak_ada_dalam_anggaran"
    assert res.fakta["budget_pelanggan"] == 2000000
    assert res.fakta["harga_termurah_kategori"] > 2000000
    assert len(res.produk_list) == 0


def test_b8_tidak_ada_opsi_lebih_murah_atau_lebih_mahal(engine):
    """B8: lanjutan_hasil lebih_murah jika sudah termurah -> tidak_ada_lebih_murah."""
    state = {
        "produk_tampil": [
            {"kode": "KB-L01", "nama": "Acer Aspire Lite 14", "kategori": "laptop", "harga": 5199000}
        ],
        "kategori": "laptop"
    }
    # KB-L01 adalah laptop termurah (5.199.000)
    parsed = ParserOutput(
        aksi=ActionEnum.LANJUTAN_HASIL,
        argumen=ActionArguments(jenis=JenisEnum.LEBIH_MURAH),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state=state)
    assert res.fakta["status"] == "tidak_ada_lebih_murah"
    assert len(res.produk_list) == 0


def test_b9_lanjutan_hasil_tanpa_produk_tampil_ditolak():
    """B9: Minta opsi lanjutan tapi belum ada produk yang tampil -> rujukan_tidak_ada."""
    raw = {
        "aksi": "lanjutan_hasil",
        "argumen": {"jenis": "lebih_murah"},
        "pembaruan_state": {}
    }
    res, is_valid = validate_parser_output(raw, session_state={"produk_tampil": []})
    assert is_valid is False
    assert res.aksi == ActionEnum.TIDAK_JELAS
    assert res.argumen.alasan == AlasanTidakJelasEnum.RUJUKAN_TIDAK_ADA


def test_b10_deterministic_fallback_builder():
    """B10: Teks cadangan dirakit langsung dari fakta_eksekusi terstruktur."""
    fakta_budget = {
        "status": "tidak_ada_dalam_anggaran",
        "harga_termurah_kategori_formatted": "Rp5.199.000"
    }
    txt = build_deterministic_fallback_text("minta_rekomendasi", fakta_budget)
    assert "Rp5.199.000" in txt
    assert len(txt) <= 420


def test_b12_alasan_tidak_jelas_hanya_4_enum():
    """B12: Alasan tidak_jelas hanya salah satu dari 4 enum tertutup."""
    allowed = {"tidak_dipahami", "rujukan_tidak_ada", "bertentangan", "sistem_error"}
    for val in AlasanTidakJelasEnum:
        assert val.value in allowed

    # Validasi bahwa string ad-hoc dinormalisasi ke salah satu dari 4 enum
    raw = {"aksi": "tidak_jelas", "argumen": {"alasan": "kalimat ad-hoc aneh"}}
    res, _ = validate_parser_output(raw)
    assert res.argumen.alasan in [
        AlasanTidakJelasEnum.TIDAK_DIPAHAMI,
        AlasanTidakJelasEnum.RUJUKAN_TIDAK_ADA,
        AlasanTidakJelasEnum.BERTENTANGAN,
        AlasanTidakJelasEnum.SISTEM_ERROR
    ]


def test_b13_emergency_fallback_text_constraints():
    """B13: Teks cadangan darurat <= 420 karakter, netral, tanpa janji 'menghubungkan'."""
    assert len(EMERGENCY_FALLBACK_TEXT) <= 420
    assert len(GEN_FALLBACK_TEXT) <= 420
    assert "menghubungkan" not in EMERGENCY_FALLBACK_TEXT.lower()
    assert "mohon maaf atas ketidaknyamanannya" not in EMERGENCY_FALLBACK_TEXT.lower()


def test_a9_tanya_info_toko_hanya_kontak_staf(engine):
    """A9: tanya_info_toko memberikan kontak staf tanpa menyebut janji respons waktu."""
    parsed = ParserOutput(
        aksi=ActionEnum.TANYA_INFO_TOKO,
        argumen=ActionArguments(topik=TokoTopikEnum.GARANSI),
        pembaruan_state=StateUpdate()
    )
    res = engine.execute(parsed, session_state={})
    assert res.fakta["status"] == "info_toko"
    assert "kontak_staf" in res.fakta
    assert "5 menit" not in str(res.fakta).lower()
    assert "segera" not in str(res.fakta).lower()


def test_fase3_synthetic_few_shots_clean():
    """Fase 3: Few-shot parser tepat 8 contoh sintetis dan beragam batas aksi."""
    from services.llm_parser import SYNTHETIC_8_BOUNDARY_FEW_SHOTS
    # 8 pasang user-assistant = 16 pesan
    assert len(SYNTHETIC_8_BOUNDARY_FEW_SHOTS) == 16
    user_turns = [m for m in SYNTHETIC_8_BOUNDARY_FEW_SHOTS if m["role"] == "user"]
    assert len(user_turns) == 8


def test_fase3_generator_rule_c_constraints():
    """Fase 3: Generator mematuhi Batasan Respons C (<=3 kalimat, <=420 char, info murni tanpa pertanyaan)."""
    from services.llm_generator import generate_response
    from unittest.mock import patch

    # Mock raw response yang melebihi 3 kalimat dan mengandung pertanyaan di info murni
    long_raw = {
        "teks": "Laptop ini menggunakan GPU RTX 4060. Kapasitas VRAM sebesar 8GB GDDR6. Performa grafis sangat baik untuk rendering. Apakah Kakak mau membelinya?",
        "pertanyaan_diajukan": "kebutuhan",
        "penilaian": None
    }
    with patch("services.llm_generator.urllib.request.urlopen") as mock_url:
        import io
        mock_resp = io.BytesIO(f'{{"message": {{"content": {json.dumps(json.dumps(long_raw))}}}}}'.encode("utf-8"))
        mock_url.return_value.__enter__.return_value.read.return_value = mock_resp.getvalue()

        out, _ = generate_response(
            aksi="tanya_spesifikasi",
            fakta={"status": "sukses", "spesifikasi": []},
            state={}
        )
        assert len(out.teks) <= 420
        assert out.pertanyaan_diajukan is None
        # Kalimat <= 3
        import re
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", out.teks.strip()) if s]
        assert len(sentences) <= 3


def test_fase5_reject_hardware_specs_on_non_product_turns():
    """Fase 5: Menolak halusinasi spesifikasi hardware (harga, GB, model) pada giliran non-produk."""
    from services.grounding_checker import GroundingChecker
    checker = GroundingChecker()

    # 1. Sapaan menyebut harga
    valid, errs = checker.check("Halo Kak! Ada laptop seharga 7 juta rupiah.", fakta={"status": "sapaan"})
    assert valid is False
    assert any("non-produk" in e.lower() for e in errs)

    # 2. Basa-basi menyebut spesifikasi GB
    valid, errs = checker.check("Terima kasih Kak, perangkat ini punya 16GB RAM.", fakta={"status": "basa_basi"})
    assert valid is False
    assert any("non-produk" in e.lower() for e in errs)

    # 3. Profil tidak ditemukan menyebut nama model laptop
    valid, errs = checker.check("Kami belum menemukan kebutuhan Kakak, tapi ada Vivobook bagus.", fakta={"status": "profil_tidak_ditemukan"})
    assert valid is False
    assert any("non-produk" in e.lower() for e in errs)


def test_fase5_reject_internal_system_terms_leak():
    """Fase 5: Menolak teks respons yang membocorkan istilah skema internal (tier, selisih, fakta, score)."""
    from services.grounding_checker import GroundingChecker
    checker = GroundingChecker()

    valid1, errs1 = checker.check("Laptop ini masuk cpu_tier 3 dengan performa tinggi.", fakta={"status": "sukses"})
    assert valid1 is False
    assert any("internal" in e.lower() for e in errs1)

    valid2, errs2 = checker.check("Berdasarkan fakta dan selisih spesifikasi, unit ini cocok.", fakta={"status": "sukses"})
    assert valid2 is False
    assert any("internal" in e.lower() for e in errs2)


