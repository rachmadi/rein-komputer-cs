# -*- coding: utf-8 -*-
"""
tests/test_putaran15c_synthetic.py
Pengujian sintetis untuk Putaran 15c ReIn Komputer.
- Butir 3: Perbaikan regresi "speknya kosong" (tanya_spesifikasi menghasilkan lembar lengkap, bukan atribut_tidak_tersedia).
- Butir 4: Perbaikan resolusi referensi posisional ("3 pilihan tadi") dan nama pendek substring ("Nitro").
"""
import pytest
from services.action_engine import ActionEngine, is_general_spec_query
from services.schema_actions import ParserOutput, ActionEnum, ActionArguments, StateUpdate


def test_butir3_is_general_spec_query_detection():
    """Memastikan deteksi permintaan spesifikasi umum/komplain spek kosong bekerja secara data-driven."""
    # Frasa umum & komplain spek kosong harus True
    assert is_general_spec_query(None) is True
    assert is_general_spec_query("") is True
    assert is_general_spec_query("kosong") is True
    assert is_general_spec_query("speknya kosong") is True
    assert is_general_spec_query("spesifikasi lengkap") is True
    assert is_general_spec_query("spek lengkap") is True
    assert is_general_spec_query("mana speknya") is True
    assert is_general_spec_query("detail") is True
    assert is_general_spec_query("spesifikasi") is True

    # Atribut teknis spesifik harus False
    assert is_general_spec_query("ram") is False
    assert is_general_spec_query("gpu") is False
    assert is_general_spec_query("cpu") is False
    assert is_general_spec_query("layar") is False
    assert is_general_spec_query("cetak foto") is False
    assert is_general_spec_query("tabung tinta") is False
    assert is_general_spec_query("kamera") is False


def test_butir3_tanya_spesifikasi_spek_kosong_sukses_lembar_lengkap():
    """
    Butir 3:
    Ketika pelanggan menanyakan 'speknya kosong' atau 'spesifikasi lengkap',
    ActionEngine harus mengembalikan status 'sukses' dengan tipe_jawaban 'ringkasan_spesifikasi'
    dan lembar_spesifikasi terisi penuh, bukan 'atribut_tidak_tersedia'.
    """
    engine = ActionEngine(db_path="data/test_catalog.db")
    state = {
        "produk_tampil": [{"kode": "KB-L09", "nama": "ASUS TUF Gaming A15", "harga": 16999000}],
        "produk_terakhir_dibahas": "KB-L09",
        "produk_dibahas": ["KB-L09"]
    }

    # 1. Atribut 'kosong'
    p_kosong = ParserOutput(
        aksi=ActionEnum.TANYA_SPESIFIKASI,
        argumen=ActionArguments(produk=["KB-L09"], atribut="kosong")
    )
    res_kosong = engine.execute(p_kosong, session_state=state)
    assert res_kosong.fakta["status"] == "sukses"
    assert res_kosong.fakta.get("tipe_jawaban") == "ringkasan_spesifikasi"
    assert "lembar_spesifikasi" in res_kosong.fakta
    lembar = res_kosong.fakta["lembar_spesifikasi"]
    assert "prosesor" in lembar or "cpu" in lembar
    assert "ram" in lembar

    # 2. Atribut 'spesifikasi lengkap'
    p_lengkap = ParserOutput(
        aksi=ActionEnum.TANYA_SPESIFIKASI,
        argumen=ActionArguments(produk=["KB-L09"], atribut="spesifikasi lengkap")
    )
    res_lengkap = engine.execute(p_lengkap, session_state=state)
    assert res_lengkap.fakta["status"] == "sukses"
    assert res_lengkap.fakta.get("tipe_jawaban") == "ringkasan_spesifikasi"
    assert "lembar_spesifikasi" in res_lengkap.fakta

    # 3. Atribut non-eksisten pada printer tetap 'atribut_tidak_tersedia' (tidak ada regresi)
    p_kamera = ParserOutput(
        aksi=ActionEnum.TANYA_SPESIFIKASI,
        argumen=ActionArguments(produk=["KB-P10"], atribut="kamera")
    )
    res_kamera = engine.execute(p_kamera, session_state={})
    assert res_kamera.fakta["status"] == "atribut_tidak_tersedia"


def test_butir4_resolve_positional_set_reference():
    """
    Butir 4:
    Rujukan posisional himpunan ('3 pilihan tadi', 'pilihan tadi', '3 opsi tadi')
    harus diresolusi ke seluruh produk tampil/riwayat yang relevan.
    """
    from services.validator import resolve_product_references

    tampil = [
        {"kode": "KB-L24", "nama": "Acer Nitro V 15", "harga": 14000000},
        {"kode": "KB-L25", "nama": "ASUS TUF Gaming A15", "harga": 16500000},
        {"kode": "KB-L29", "nama": "Lenovo Legion Pro 5i", "harga": 22000000}
    ]

    # 1. '3 pilihan tadi'
    codes, ok, fail = resolve_product_references(["3 pilihan tadi"], tampil, tampil)
    assert ok is True
    assert codes == ["KB-L24", "KB-L25", "KB-L29"]

    # 2. 'pilihan tadi'
    codes, ok, fail = resolve_product_references(["pilihan tadi"], tampil, tampil)
    assert ok is True
    assert codes == ["KB-L24", "KB-L25", "KB-L29"]

    # 3. '2 opsi tadi'
    codes, ok, fail = resolve_product_references(["2 opsi tadi"], tampil, tampil)
    assert ok is True
    assert codes == ["KB-L24", "KB-L25"]


def test_butir4_resolve_model_name_substring():
    """
    Butir 4:
    Rujukan sebagian nama model (substring case-insensitive) seperti 'Nitro', 'TUF', 'Swift'
    harus berhasil diselesaikan ke produk yang sesuai di history_tampil atau katalog luas,
    bahkan jika produk_tampil saat itu berisi produk lain.
    """
    from services.validator import extract_model_substring_reference, validate_parser_output
    from services.schema_actions import ParserOutput, ActionEnum, ActionArguments, StateUpdate

    # Produk tampil saat itu adalah laptop spek rendah hasil reset
    tampil_rendah = [
        {"kode": "KB-L01", "nama": "Acer Aspire Lite 14", "harga": 5199000},
        {"kode": "KB-L02", "nama": "Advan Soulmate", "harga": 2499000},
        {"kode": "KB-L03", "nama": "Axioo MyBook 14F", "harga": 3499000}
    ]
    # Riwayat tampil memuat pilihan laptop AI lokal sebelumnya
    history_lengkap = [
        {"kode": "KB-L24", "nama": "Acer Nitro V 15 ANV15-51", "harga": 14000000},
        {"kode": "KB-L25", "nama": "ASUS TUF Gaming A15 FA507NU", "harga": 16500000},
        {"kode": "KB-L29", "nama": "Lenovo Legion Pro 5i 16IRX8", "harga": 22000000}
    ] + tampil_rendah

    # 1. extract_model_substring_reference untuk 'Nitro bisa untuk AI lokal?'
    m_nitro = extract_model_substring_reference(
        "Nitro bisa untuk AI lokal?",
        produk_tampil=tampil_rendah,
        history_tampil=history_lengkap,
        db_path="data/test_catalog.db"
    )
    assert "KB-L24" in m_nitro

    # 2. validate_parser_output override rujukan_produk jika user menyebut nama model eksplisit
    state_eval = {
        "_pesan_pelanggan": "Nitro bisa untuk AI lokal?",
        "kategori": "laptop",
        "kebutuhan_teks": "AI lokal",
        "produk_tampil": tampil_rendah,
        "history_produk_tampil": history_lengkap
    }
    raw_parser_out = {
        "aksi": "evaluasi_kecocokan",
        "argumen": {
            "rujukan_produk": [1, 2, 3],  # Parser LLM salah mengirim [1, 2, 3]
            "kebutuhan_teks": "AI lokal"
        },
        "pembaruan_state": {}
    }
    validated, is_valid = validate_parser_output(raw_parser_out, session_state=state_eval, db_path="data/test_catalog.db")
    assert is_valid is True
    # Validator harus mengoreksi rujukan ke Acer Nitro (KB-L24), bukan KB-L01!
    assert validated.argumen.rujukan_produk == ["KB-L24"]
    assert validated.argumen.produk == ["KB-L24"]


def test_butir4_turn56_termurah_dari_tampil_handling():
    """
    Butir 4:
    Pertanyaan giliran 56 'Tadi, kamu nawarin 3 pilihan yang bisa AI lokal. Yang paling murah kan masih di bawah 15 juta?'
    harus dieksekusi sebagai jenis termurah_dari_tampil, mengembalikan status sukses dan unit termurah
    tanpa mereset produk_tampil.
    """
    engine = ActionEngine(db_path="data/test_catalog.db")
    tampil_ai = [
        {"kode": "KB-L24", "nama": "Acer Nitro V 15 ANV15-51", "harga": 14000000},
        {"kode": "KB-L25", "nama": "ASUS TUF Gaming A15 FA507NU", "harga": 16500000},
        {"kode": "KB-L29", "nama": "Lenovo Legion Pro 5i 16IRX8", "harga": 22000000}
    ]
    state_turn56 = {
        "kategori": "laptop",
        "kebutuhan_teks": "bikin model bisnis pakai AI lokal",
        "produk_tampil": tampil_ai,
        "history_produk_tampil": tampil_ai,
        "_pesan_pelanggan": "Tadi, kamu nawarin 3 pilihan yang bisa AI lokal. Yang paling murah kan masih di bawah 15 juta?"
    }

    from services.schema_actions import JenisEnum
    p_turn56 = ParserOutput(
        aksi=ActionEnum.LANJUTAN_HASIL,
        argumen=ActionArguments(jenis=JenisEnum.TERMURAH_DARI_TAMPIL),
        kontrak_intent={
            "permintaan_asli": {"aksi": "lanjutan_hasil", "argumen": {"jenis": "termurah_dari_tampil"}},
            "argumen_valid": {"jenis": JenisEnum.TERMURAH_DARI_TAMPIL},
            "argumen_ditolak": []
        }
    )
    res = engine.execute(p_turn56, session_state=state_turn56)
    assert res.fakta["status"] == "sukses"
    assert res.fakta["jenis_lanjutan"] == "termurah_dari_tampil"
    assert res.fakta["produk_termurah"]["kode"] == "KB-L24"
    assert res.fakta["produk_termurah"]["harga"] <= 15000000
