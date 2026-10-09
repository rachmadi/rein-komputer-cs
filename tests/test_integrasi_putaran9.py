# -*- coding: utf-8 -*-
"""
tests/test_integrasi_putaran9.py
Rangkaian tes integrasi Putaran 9 (ReIn Komputer):
- F1: kriteria_pelanggan vs batas_bot terpisah, filter_dipakai di fakta
- F1b: filter spesifikasi katalog (RAM/DDR/storage/GPU), kriteria_diabaikan_data_tak_ada
- F2: rujukan default produk aktif/terakhir saat atribut ditanyakan tanpa nama produk, rujukan_dipakai
- F3: atribut null = spek umum katalog vs atribut 'lainnya' = B15 atribut_tidak_tersedia
- F4: teks jawaban memuat nilai spesifik fakta, tanpa halusinasi kategori
- F5: fallback deterministik berbasis fakta vs kalimat darurat B13, basa-basi bebas nominal
- F6: rujukan produk di luar layar aktif dipetakan dari riwayat sesi
- Marker live: smoke test parser nyata untuk F2 dan F3 (maks 12 kalimat karangan baru)
"""
import pytest
from services.action_engine import ActionEngine
from services.schema_actions import (
    ParserOutput, ActionEnum, ActionArguments, StateUpdate,
    AtributSpesifikasiEnum, JenisEnum
)
from services.session_pipeline import SessionPipeline


def test_f1_kriteria_pelanggan_vs_batas_bot_terpisah():
    """F1: kriteria_pelanggan (dari user) dan batas_bot (dari sistem) dilacak terpisah."""
    engine = ActionEngine()
    state = {
        "kategori": "laptop",
        "kriteria_pelanggan": {"merek": "asus", "max_harga": 10000000},
        "batas_bot": {"max_harga": 8000000},
        "produk_tampil": [
            {"kode": "KB-L03", "nama": "ASUS Vivobook 14", "kategori": "laptop", "harga": 8499000}
        ]
    }
    # User berganti meminta opsi merek lain (lanjutan_hasil)
    args = ActionArguments(jenis=JenisEnum.YANG_LAIN)
    res = engine.execute(ParserOutput(aksi=ActionEnum.LANJUTAN_HASIL, argumen=args), session_state=state)

    # Fakta wajib memuat field 'filter_dipakai'
    assert "filter_dipakai" in res.fakta, "Fakta harus mencatat filter_dipakai secara eksplisit"
    assert res.fakta["filter_dipakai"].get("max_harga") == 10000000, "Batas harga pelanggan yang harus dipakai, bukan batas bot"


def test_f1b_syarat_spesifikasi_dan_kriteria_diabaikan():
    """F1b: Syarat spesifikasi (mis. DDR5) yang kolomnya tidak ada di katalog dicatat di kriteria_diabaikan_data_tak_ada."""
    engine = ActionEngine()
    state = {"kategori": "laptop"}
    args = ActionArguments(kategori="laptop", ram_gb_min=16, filter={"tipe_ram": "ddr5"})
    res = engine.execute(ParserOutput(aksi=ActionEnum.CARI_PRODUK, argumen=args), session_state=state)

    # Fakta wajib memuat kriteria_diabaikan_data_tak_ada jika data tidak memiliki kolom tipe RAM DDR
    assert "kriteria_diabaikan_data_tak_ada" in res.fakta, "Kriteria tanpa kolom katalog wajib dilaporkan di kriteria_diabaikan_data_tak_ada"
    assert "ddr5" in [str(x).lower() for x in res.fakta["kriteria_diabaikan_data_tak_ada"]]


def test_f2_rujukan_default_produk_terakhir():
    """F2: Pertanyaan atribut tanpa nama produk merujuk produk terakhir dibahas / produk tampil, mencatat rujukan_dipakai."""
    engine = ActionEngine()
    state = {
        "kategori": "laptop",
        "produk_tampil": [
            {"kode": "KB-L01", "nama": "Acer Aspire Lite 14", "kategori": "laptop", "harga": 5199000},
            {"kode": "KB-L02", "nama": "Lenovo IdeaPad Slim 3", "kategori": "laptop", "harga": 7299000}
        ],
        "produk_terakhir_dibahas": "KB-L02"
    }
    # User bertanya ukuran layar tanpa menyebut nama laptop
    args = ActionArguments(atribut=AtributSpesifikasiEnum.LAYAR)
    raw_p = ParserOutput(aksi=ActionEnum.TANYA_SPESIFIKASI, argumen=args)

    # 1. Pastikan validator mengizinkan dan memetakan ke produk terakhir dibahas
    from services.validator import validate_parser_output
    val_out, is_valid = validate_parser_output(raw_p, session_state=state)
    assert is_valid, "Validator harus mengizinkan tanya_spesifikasi tanpa rujukan eksplisit jika ada produk aktif"
    assert val_out.argumen.produk == ["KB-L02"]

    # 2. Pastikan ActionEngine mengeksekusi dengan rujukan_dipakai ke produk terakhir dibahas
    res = engine.execute(val_out, session_state=state)
    assert res.fakta.get("status") == "sukses", "Harus sukses merujuk produk aktif"
    assert "rujukan_dipakai" in res.fakta, "Fakta wajib memuat field rujukan_dipakai"
    assert res.fakta["rujukan_dipakai"] == ["KB-L02"]


def test_f3_spek_umum_vs_atribut_tidak_tersedia():
    """F3: Atribut None = ringkasan spek utama; Atribut LAINNYA = B15 atribut_tidak_tersedia (bukan spek lain)."""
    engine = ActionEngine()
    state = {
        "kategori": "laptop",
        "produk_tampil": [
            {"kode": "KB-L01", "nama": "Acer Aspire Lite 14", "kategori": "laptop", "harga": 5199000}
        ]
    }
    # Kasus A: Atribut None / kosong -> Permintaan spek umum -> Ringkasan spek
    args_umum = ActionArguments(produk=["KB-L01"], atribut=None)
    res_umum = engine.execute(ParserOutput(aksi=ActionEnum.TANYA_SPESIFIKASI, argumen=args_umum), session_state=state)
    assert res_umum.fakta.get("status") == "sukses"
    assert "spesifikasi_ringkas" in res_umum.fakta or "ringkasan_spek" in res_umum.fakta

    # Kasus B: Atribut LAINNYA (atribut tak dikenal) -> Wajib B15 atribut_tidak_tersedia
    args_asing = ActionArguments(produk=["KB-L01"], atribut=AtributSpesifikasiEnum.LAINNYA)
    res_asing = engine.execute(ParserOutput(aksi=ActionEnum.TANYA_SPESIFIKASI, argumen=args_asing), session_state=state)
    assert res_asing.fakta.get("status") == "atribut_tidak_tersedia", "Atribut lainnya wajib berstatus atribut_tidak_tersedia sesuai B15"


def test_f4_teks_memuat_nilai_fakta_spesifik():
    """F4: GroundingChecker wajib menolak teks tanya_spesifikasi yang tidak memuat nilai fakta spesifik yang diminta."""
    from services.grounding_checker import GroundingChecker
    checker = GroundingChecker()
    fakta = {
        "status": "sukses",
        "atribut_ditanya": "ram",
        "spesifikasi_produk": [
            {"kode": "KB-L02", "nama": "Lenovo IdeaPad Slim 3", "atribut": "ram", "nilai": "16 GB DDR4"}
        ]
    }
    # Teks generator melupakan nilai 16 GB DDR4 dan hanya memberi rekomendasi umum
    teks_tanpa_nilai = "Lenovo IdeaPad Slim 3 ini memiliki performa yang handal dan desain ringkas untuk kebutuhan harian."
    is_valid, violations = checker.check(teks_tanpa_nilai, fakta)
    assert not is_valid, "GroundingChecker wajib menolak teks tanya_spesifikasi yang tidak memuat nilai spesifik (16 GB DDR4)"
    assert any("nilai" in v.lower() or "spesifikasi" in v.lower() or "ram" in v.lower() for v in violations)


def test_f5_fallback_deterministik_bebas_nominal():
    """F5: Jika generator gagal pada aksi berfakta, sistem menghasilkan fallback deterministik dari fakta, bukan B13."""
    pipeline = SessionPipeline()
    state = {
        "kategori": "laptop",
        "produk_tampil": [
            {"kode": "KB-L02", "nama": "Lenovo IdeaPad Slim 3", "kategori": "laptop", "harga": 7299000}
        ]
    }
    fakta = {
        "status": "sukses",
        "atribut_ditanya": "ram",
        "spesifikasi_produk": [
            {"kode": "KB-L02", "nama": "Lenovo IdeaPad Slim 3", "atribut": "ram", "nilai": "8 GB DDR4"}
        ]
    }
    # Uji pembentukan fallback deterministik saat generator mengalami penolakan
    fallback_text = pipeline.action_engine.build_deterministic_fallback(ActionEnum.TANYA_SPESIFIKASI, fakta, state)
    assert "8 gb" in fallback_text.lower(), "Fallback deterministik harus menyebut nilai dari fakta"
    assert "kendala sistem" not in fallback_text.lower(), "Bukan kalimat darurat B13"


def test_f6_rujukan_riwayat_produk_pernah_tampil():
    """F6: Rujukan ke pilihan yang sudah tidak di layar dipetakan dari riwayat produk yang pernah tampil di sesi."""
    engine = ActionEngine()
    state = {
        "kategori": "laptop",
        "produk_tampil": [
            {"kode": "KB-L06", "nama": "Acer Nitro V 15", "kategori": "laptop", "harga": 10999000}
        ],
        "history_produk_tampil": [
            {"kode": "KB-L01", "nama": "Acer Aspire Lite 14", "kategori": "laptop", "harga": 5199000},
            {"kode": "KB-L06", "nama": "Acer Nitro V 15", "kategori": "laptop", "harga": 10999000}
        ]
    }
    # Pelanggan merujuk opsi pertama di turn sebelumnya yang sekarang sudah tergeser dari layar
    args = ActionArguments(rujukan_produk=["opsi 1 sebelumnya"], atribut=AtributSpesifikasiEnum.RAM)
    res = engine.execute(ParserOutput(aksi=ActionEnum.TANYA_SPESIFIKASI, argumen=args), session_state=state)
    assert res.fakta.get("status") == "sukses", "Rujukan riwayat harus berhasil diselesaikan"
    assert "KB-L01" in str(res.fakta), "Produk riwayat KB-L01 harus terpilih"


# =============================================================================
# TES SMOKE PARSER NYATA (Marker: live, Max 12 Kalimat Baru, F2 & F3)
# =============================================================================

@pytest.mark.live
@pytest.mark.parametrize("kalimat_uji, expected_attr", [
    ("Berapa kapasitas penyimpanan internalnya?", AtributSpesifikasiEnum.STORAGE),
    ("Berapa daya tampung memori utamanya?", AtributSpesifikasiEnum.RAM),
    ("Bagaimana dengan kemampuan olah grafisnya?", AtributSpesifikasiEnum.GPU),
    ("Apakah ada info mengenai bobot fisiknya?", AtributSpesifikasiEnum.BOBOT),
    ("Berapa lama ketahanan catu dayanya?", AtributSpesifikasiEnum.BATERAI),
    ("Berapa bentang diagonal panel depannya?", AtributSpesifikasiEnum.LAYAR),
])
def test_live_smoke_f2_rujukan_default_tanpa_nama_produk(kalimat_uji, expected_attr):
    """Smoke Test F2: Menanyakan atribut spesifik tanpa menyebutkan nama produk."""
    from services.llm_parser import parse_user_message
    state = {
        "kategori": "laptop",
        "produk_tampil": [{"kode": "KB-L01", "nama": "Acer Aspire Lite 14", "kategori": "laptop"}]
    }
    parsed, _ = parse_user_message(kalimat_uji, state=state)
    assert parsed.aksi == ActionEnum.TANYA_SPESIFIKASI
    assert parsed.argumen.atribut == expected_attr


@pytest.mark.live
@pytest.mark.parametrize("kalimat_uji, is_umum", [
    ("Bisa jelaskan gambaran spek perangkat itu?", True),
    ("Tolong jabarkan rincian teknis lengkapnya dong", True),
    ("Bagaimana parameter spesifikasi barang ini?", True),
    ("Apakah perangkat ini dibekali sensor sidik jari?", False),
    ("Apakah memiliki lapisan pelindung anti air?", False),
    ("Apakah casingnya memakai bahan serat karbon?", False),
])
def test_live_smoke_f3_spek_umum_vs_atribut_asing(kalimat_uji, is_umum):
    """Smoke Test F3: Membedakan permintaan spesifikasi umum (atribut None) vs atribut tak dikenal (atribut lainnya)."""
    from services.llm_parser import parse_user_message
    state = {
        "kategori": "laptop",
        "produk_tampil": [{"kode": "KB-L01", "nama": "Acer Aspire Lite 14", "kategori": "laptop"}]
    }
    parsed, _ = parse_user_message(kalimat_uji, state=state)
    assert parsed.aksi == ActionEnum.TANYA_SPESIFIKASI
    if is_umum:
        assert parsed.argumen.atribut is None
    else:
        assert parsed.argumen.atribut == AtributSpesifikasiEnum.LAINNYA

