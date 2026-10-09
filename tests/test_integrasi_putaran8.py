# -*- coding: utf-8 -*-
"""
tests/test_integrasi_putaran8.py
Pengujian integrasi dan tes langsung (live) untuk Putaran 8 (E1 s.d. E8).
Tahap 2 (Tes Dulu / HARUS MERAH sebelum perbaikan akar masalah diterapkan).
"""
import pytest
from services.schema_actions import (
    ParserOutput, ActionEnum, ActionArguments, StateUpdate,
    AtributSpesifikasiEnum, AlasanTidakJelasEnum
)
from services.action_engine import ActionEngine
from services.catalog_service import get_active_catalog
from services.session_pipeline import SessionPipeline
from services.llm_parser import parse_user_message


# ==============================================================================
# 2.1 TES LIVE (MARKER LIVE) PADA PARSER LLM NYATA (E1, E2, E3)
# ==============================================================================

@pytest.mark.live
def test_live_e1_lanjutan_murni():
    """E1: Permintaan lanjutan murni relatif terhadap daftar tampil harus menghasilkan lanjutan_hasil."""
    pesan = "Bisa berikan saran pengganti berbiaya lebih hemat?"
    state = {
        "produk_tampil": [
            {"kode": "KB-L03", "nama": "Asus Vivobook 14", "harga": 8799000, "kategori": "laptop"},
            {"kode": "KB-L04", "nama": "HP 14s", "harga": 6499000, "kategori": "laptop"}
        ],
        "kategori": "laptop",
        "merek": "asus"
    }
    out, metrics = parse_user_message(pesan, state=state)
    assert out.aksi == ActionEnum.LANJUTAN_HASIL, f"E1 Harap lanjutan_hasil, dapat {out.aksi}"


@pytest.mark.live
def test_live_e2_tanya_spesifikasi_unit_tersebut():
    """E2: Pertanyaan spesifikasi tentang 'unit tersebut' harus menghasilkan tanya_spesifikasi."""
    pesan = "Berapa banderol harga untuk unit tersebut?"
    state = {
        "produk_tampil": [
            {"kode": "KB-L03", "nama": "Asus Vivobook 14", "harga": 8799000, "kategori": "laptop"}
        ],
        "kategori": "laptop"
    }
    out, metrics = parse_user_message(pesan, state=state)
    assert out.aksi == ActionEnum.TANYA_SPESIFIKASI, f"E2 Harap tanya_spesifikasi, dapat {out.aksi}"
    assert out.argumen.rujukan_produk is not None, "E2 rujukan_produk harus terisi"


@pytest.mark.live
def test_live_e3_kebutuhan_baru():
    """E3: Kebutuhan komputasi baru di tengah percakapan wajib mengisi kebutuhan_teks."""
    pesan = "Saya perlu perangkat yang mumpuni untuk edit video 4K dan animasi blender"
    state = {
        "produk_tampil": [
            {"kode": "KB-L01", "nama": "Acer Aspire Lite 14", "harga": 5199000, "kategori": "laptop"}
        ],
        "kategori": "laptop",
        "profil_aktif": "P01"
    }
    out, metrics = parse_user_message(pesan, state=state)
    assert out.aksi in [ActionEnum.MINTA_REKOMENDASI, ActionEnum.EVALUASI_KECOCOKAN], f"E3 Aksi tidak cocok: {out.aksi}"
    assert out.argumen.kebutuhan_teks, "E3 kebutuhan_teks wajib terisi dengan aktivitas"


# ==============================================================================
# 2.2 TES INTEGRASI PIPELINE & ENGINE (E3 s.d. E8)
# ==============================================================================

def test_integrasi_e3_profil_id_persis():
    """E3: Profil kebutuhan baru di-resolve ulang melalui pipeline, menghasilkan profil persis P03/P04 (bukan P01 basi)."""
    pipeline = SessionPipeline()
    state = {
        "kategori": "laptop",
        "profil_aktif": "P01",  # Profil basi kantor
        "kebutuhan_teks": "tugas kantor administrasi",
        "produk_tampil": [
            {"kode": "KB-L01", "nama": "Acer Aspire Lite 14", "kategori": "laptop", "harga": 5199000}
        ]
    }
    res, new_state = pipeline.process_turn(
        "Kalau misalnya dipakai rendering 3D animasi blender seharian apakah kuat?",
        session_state=state
    )
    # Harus di-resolve ulang ke profil 3D P03/P04, tidak boleh memakai profil basi P01
    assert res.fakta_eksekusi.get("status") == "sukses"
    assert res.fakta_eksekusi.get("profil_id") in ["P03", "P04"], f"Harap profil berat P03/P04, dapat {res.fakta_eksekusi.get('profil_id')}"
    assert res.fakta_eksekusi.get("profil_id") != "P01", "Profil basi P01 tidak boleh dipakai ulang"


def test_integrasi_e3_profil_tidak_ditemukan():
    """E3: Kebutuhan yang tidak ada padanannya harus menghasilkan status profil_tidak_ditemukan."""
    engine = ActionEngine()
    state = {"produk_tampil": [{"kode": "KB-L01", "nama": "Acer Aspire Lite 14", "kategori": "laptop"}]}
    args = ActionArguments(
        rujukan_produk=[1],
        kebutuhan_teks="aktivitas acakxyz123 yang sama sekali tidak ada di profil"
    )
    res = engine._handle_evaluasi_kecocokan(args, state)
    assert res.fakta.get("status") == "profil_tidak_ditemukan", f"Harap status profil_tidak_ditemukan, dapat {res.fakta.get('status')}"


def test_integrasi_e4_batas_dan_merek_dipertahankan():
    """E4: Lanjutan berbatas harga mempertahankan filter merek dan batas harga."""
    engine = ActionEngine()
    state = {
        "kategori": "laptop",
        "merek": "lenovo",
        "produk_tampil": [
            {"kode": "KB-L05", "nama": "Lenovo IdeaPad Slim 5", "kategori": "laptop", "harga": 11499000}
        ]
    }
    # Minta yang lebih murah dengan batas 8 juta
    args = ActionArguments(
        jenis="lebih_murah",
        max_harga=8000000
    )
    res = engine._handle_lanjutan_hasil(args, state)
    assert res.fakta.get("status") == "sukses"
    # Seluruh produk yang ditampilkan wajib bermerek Lenovo dan berharga <= 8.000.000
    for p in res.produk_list:
        assert p.get("brand", "").lower() == "lenovo" or p.get("merek", "").lower() == "lenovo", f"Produk bukan lenovo: {p}"
        assert p.get("harga") <= 8000000, f"Produk melebihi batas 8 juta: {p}"


def test_integrasi_e4_kosong_b7_termurah_merek_tersebut():
    """E4: Jika tidak ada dalam batas harga, B7 harus menyebut harga termurah untuk merek itu."""
    engine = ActionEngine()
    state = {
        "kategori": "laptop",
        "merek": "lenovo",
        "produk_tampil": [
            {"kode": "KB-L02", "nama": "Lenovo IdeaPad Slim 3", "kategori": "laptop", "harga": 7299000}
        ]
    }
    # Minta di bawah 5 juta untuk Lenovo (termurah Lenovo di katalog adalah KB-L02 Rp7.299.000)
    args = ActionArguments(
        jenis="lebih_murah",
        max_harga=5000000
    )
    res = engine._handle_lanjutan_hasil(args, state)
    assert res.fakta.get("status") == "tidak_ada_dalam_anggaran"
    # Harga termurah yang dilaporkan harus harga termurah Lenovo (7.299.000), bukan termurah kategori laptop (Acer 5.199.000)
    assert res.fakta.get("harga_termurah_kategori") == 7299000, f"Harap harga termurah merek Lenovo 7.299.000, dapat {res.fakta.get('harga_termurah_kategori')}"


def test_integrasi_e5_gpu_generik_dedicated():
    """E5: Filter GPU generik ('dedicated'/'kartu grafis') harus menyaring produk ber-GPU diskrit di katalog."""
    engine = ActionEngine()
    args = ActionArguments(
        kategori="laptop",
        gpu="dedicated"
    )
    res = engine._handle_cari_produk(args, {})
    assert res.fakta.get("status") == "sukses"
    assert len(res.produk_list) > 0, "Harus menemukan produk ber-GPU diskrit"
    for p in res.produk_list:
        gpu_str = str(p.get("gpu", "")).lower()
        # Harus memiliki GPU diskrit seperti RTX / GTX, bukan grafik bawaan prosesor
        assert "rtx" in gpu_str or "gtx" in gpu_str or "geforce" in gpu_str, f"GPU bukan diskrit: {gpu_str}"


def test_integrasi_e6_produk_luar_katalog_cari_produk():
    """E6: Merek atau produk di luar katalog harus menghasilkan status produk_tidak_di_katalog + padanan, bukan darurat."""
    engine = ActionEngine()
    args = ActionArguments(
        kategori="laptop",
        merek="macbook"
    )
    res = engine._handle_cari_produk(args, {})
    # Harus eksplisit produk_tidak_di_katalog (B16)
    assert res.fakta.get("status") == "produk_tidak_di_katalog", f"Status harus produk_tidak_di_katalog, dapat {res.fakta.get('status')}"
    assert "padanan_terdekat" in res.fakta, "Wajib menyertakan padanan terdekat deterministik"


def test_integrasi_e7_resolusi_nama_model_sebagian():
    """E7: Token model sebagian seperti 'desktop ASUS D500' harus memetakan ke katalog (KB-D03), tidak dibilang produk luar."""
    pipeline = SessionPipeline()
    state = {
        "produk_tampil": [
            {"kode": "KB-D01", "nama": "Lenovo IdeaCentre 3", "kategori": "desktop", "harga": 6999000}
        ],
        "kategori": "desktop"
    }
    res, new_state = pipeline.process_turn(
        "Bagusan prosesor IdeaCentre ini atau desktop ASUS D500?",
        session_state=state
    )
    assert res.aksi_terpilih == "bandingkan"
    # ASUS D500 ada di katalog (KB-D03 Asus ExpertCenter D500), tidak boleh dinyatakan tidak ada
    assert res.fakta_eksekusi.get("status") == "sukses", f"Harap status sukses, dapat {res.fakta_eksekusi.get('status')}"
    assert not res.fakta_eksekusi.get("produk_luar_katalog"), f"ASUS D500 tidak boleh dianggap luar katalog: {res.fakta_eksekusi.get('produk_luar_katalog')}"


def test_integrasi_e8_rujukan_nomor_di_luar_jangkauan():
    """E8: Rujukan nomor di luar daftar tampil (misal nomor 8 saat tampil 2) harus rujukan_tidak_ada."""
    engine = ActionEngine()
    state = {
        "produk_tampil": [
            {"kode": "KB-L01", "nama": "Acer Aspire Lite 14", "harga": 5199000, "kategori": "laptop"},
            {"kode": "KB-L02", "nama": "Lenovo IdeaPad Slim 3", "harga": 7299000, "kategori": "laptop"}
        ]
    }
    args = ActionArguments(
        rujukan_produk=[8],
        kebutuhan_teks="kantor"
    )
    res = engine._handle_evaluasi_kecocokan(args, state)
    # Harus rujukan_tidak_ada (B9 / B14), BUKAN produk_tidak_di_katalog
    assert res.fakta.get("status") == "rujukan_tidak_ada", f"Harap status rujukan_tidak_ada, dapat {res.fakta.get('status')}"
