# -*- coding: utf-8 -*-
"""
tests/test_putaran13_synthetic.py
Tes sintetis terisolasi untuk fitur Putaran 13 (Butir B - G).
Menggunakan murni nama/data fiktif sintetis, tanpa kalimat nyata dari log.
"""
import pytest
from services.schema_actions import (
    ParserOutput, ActionEnum, ActionArguments, StateUpdate,
    SlotEnum, JenisEnum, JenisLanjutanEnum
)
from services.action_engine import ActionEngine, build_lembar_spesifikasi
from services.session_pipeline import SessionPipeline, strip_repeated_opening_interjection
from services.validator import resolve_product_references, is_valid_kebutuhan_teks


@pytest.fixture
def engine():
    return ActionEngine()


@pytest.fixture
def pipeline(engine):
    return SessionPipeline(action_engine=engine)


# 1. B: Fokus tidak tertimpa
def test_fokus_tidak_tertimpa_oleh_pencarian_atau_perbaikan(pipeline):
    """Fokus lama didorong ke produk_dibahas_sebelumnya dan tidak hilang saat fokus baru muncul."""
    state = {
        "produk_dibahas": ["KB-TEST-01"],
        "produk_dibahas_sebelumnya": [],
        "kebutuhan_teks": "desain poster",
        "history": [{"role": "user", "content": "tanya"}, {"role": "assistant", "content": "jawab"}]
    }

    # Jalankan update fokus dengan kode baru
    from services.session_pipeline import update_product_focus
    from services.action_engine import ActionResult

    res = ActionResult(
        aksi=ActionEnum.CARI_PRODUK,
        fakta={"status": "sukses"},
        produk_list=[{"kode": "KB-TEST-02", "nama": "Laptop Alpha"}]
    )

    update_product_focus(state, action_res=res, catalog=pipeline.action_engine.catalog)

    assert state["produk_dibahas"] == ["KB-TEST-02"]
    assert len(state["produk_dibahas_sebelumnya"]) == 1
    assert state["produk_dibahas_sebelumnya"][0]["kode"] == ["KB-TEST-01"]
    assert state["produk_dibahas_sebelumnya"][0]["label_kebutuhan"] == "desain poster"


# 2. B: "boleh/ya" memakai fokus
def test_afirmasi_singkat_memakai_fokus(pipeline):
    """Jawaban singkat 'ya'/'boleh' otomatis merujuk ke produk_dibahas (fokus saat ini)."""
    fokus = ["KB-TEST-01"]
    resolved, is_valid, failed = resolve_product_references(
        produk_refs=["boleh"],
        produk_tampil=[],
        history_tampil=[],
        produk_dibahas=fokus,
        produk_dibahas_sebelumnya=[]
    )
    assert is_valid is True
    assert resolved == ["KB-TEST-01"]


# 3. B: Perbandingan dua nama dari riwayat
def test_perbandingan_dua_nama_dari_riwayat(engine):
    """Dua nama produk dari riwayat/katalog terselesaikan menjadi 2 kode sah untuk perbandingan."""
    prods = engine.catalog.products
    if len(prods) >= 2:
        p1 = prods[0]
        p2 = prods[1]
        resolved, is_valid, failed = resolve_product_references(
            produk_refs=[p1.get("nama"), p2.get("nama")],
            produk_tampil=[],
            history_tampil=[p1, p2],
            produk_dibahas=[],
            produk_dibahas_sebelumnya=[]
        )
        assert is_valid is True
        assert p1.get("kode") in resolved
        assert p2.get("kode") in resolved


# 4. D: Budget + kebutuhan menjalankan rekomendasi
def test_budget_dan_kebutuhan_menjalankan_rekomendasi(engine):
    """Lanjutan hasil lebih_murah disertai angka budget menjalankan ulang rekomendasi."""
    state = {
        "kategori": "laptop",
        "kebutuhan_teks": "kuliah komputasi dasar",
        "produk_tampil": [{"kode": "KB-L01", "nama": "Laptop Standar", "harga": 9000000}],
        "_pesan_pelanggan": "ada yang budget 7 juta?"
    }
    args = ActionArguments(
        jenis=JenisEnum.LEBIH_MURAH,
        max_harga=7000000
    )
    res = engine._handle_lanjutan_hasil(args, state)
    assert state["budget"] == 7000000
    assert res.aksi == ActionEnum.MINTA_REKOMENDASI
    assert res.fakta.get("status") in ("sukses", "belum_ada_yang_memenuhi", "tidak_ada_dalam_anggaran")


# 5. C: Printer punya lembar spesifikasi dari raw_data
def test_printer_punya_lembar_spesifikasi_dari_raw_data(engine):
    """Printer membentuk lembar_spesifikasi dari raw_data (fungsi, teknologi, kecepatan, dsb)."""
    printers = [p for p in engine.catalog.products if str(p.get("kategori")).lower() == "printer"]
    assert len(printers) > 0, "Harus ada printer di katalog"
    pr = printers[0]
    sheet = build_lembar_spesifikasi(pr)
    assert isinstance(sheet, dict)
    assert len(sheet) > 0
    # Memastikan tidak ada kunci internal
    for forbidden in ("kode", "raw_data", "id", "created_at"):
        assert forbidden not in sheet


# 6. C: Produk di bawah minimum tampil dengan catatan
def test_produk_di_bawah_minimum_tampil_dengan_catatan(engine):
    """Produk yang tidak memenuhi syarat minimum profil tetap tampil dengan catatan memenuhi=False."""
    state = {"kategori": "laptop"}
    args = ActionArguments(
        kategori="laptop",
        kebutuhan_teks="machine learning deep learning model training 64gb"
    )
    res = engine._handle_minta_rekomendasi(args, state)
    # Jika ada produk yang di bawah minimum tapi ditampilkan
    if res.produk_list:
        for p in res.produk_list:
            assert "catatan_minimum" in p
            assert "memenuhi" in p["catatan_minimum"]
            assert "alasan" in p["catatan_minimum"]


# 7. B: Ambigu -> konfirmasi
def test_rujukan_ambigu_menandai_fakta_konfirmasi(engine):
    """Dua produk dengan nama/atribut seimbang memicu status ambigu agar dikonfirmasi."""
    tampil = [
        {"kode": "P-A", "nama": "Laptop Studio Pro 14"},
        {"kode": "P-B", "nama": "Laptop Studio Pro 16"}
    ]
    resolved, is_valid, failed = resolve_product_references(
        produk_refs=["Studio Pro"],
        produk_tampil=tampil,
        history_tampil=[],
        produk_dibahas=[],
        produk_dibahas_sebelumnya=[]
    )
    assert is_valid is False
    assert failed in ("ambigu", "rujukan_ambigu")


# 8. E: kebutuhan_teks berisi kata kategori diabaikan
def test_kebutuhan_teks_berisi_kata_kategori_diabaikan():
    """kebutuhan_teks yang hanya berisi kategori atau merek diabaikan pembaruannya."""
    assert is_valid_kebutuhan_teks("laptop") is False
    assert is_valid_kebutuhan_teks("asus") is False
    assert is_valid_kebutuhan_teks("laptop asus") is False
    assert is_valid_kebutuhan_teks("printer canon") is False
    # Kebutuhan riil harus sah
    assert is_valid_kebutuhan_teks("editing video 4k") is True
    assert is_valid_kebutuhan_teks("laptop untuk kuliah") is True
    assert is_valid_kebutuhan_teks("desain grafis") is True


# 9. F: Pertanyaan ke-3 menawarkan pilihan konkret
def test_pertanyaan_ke_3_menawarkan_pilihan_konkret(engine):
    """Pertanyaan budget ke-3 berturut-turut menghasilkan pilihan_konkret di fakta."""
    pipeline = SessionPipeline(action_engine=engine)
    state = {
        "kategori": "laptop",
        "kebutuhan_teks": "kuliah administrasi",
        "tanya_budget_beruntun": 2,  # sudah ditanyakan 2 kali
        "pending_question": "budget",
        "history": []
    }

    # Pelanggan merespons tanpa angka budget
    turn_res, new_state = pipeline.process_turn("apa saja yang tersedia kak?", state)

    assert new_state.get("tanya_budget_beruntun") == 3
    assert "pilihan_konkret" in turn_res.fakta_eksekusi
    pilihan = turn_res.fakta_eksekusi["pilihan_konkret"]
    assert len(pilihan) >= 2
    assert any("juta" in str(opt).lower() or "rp" in str(opt).lower() for opt in pilihan)


# 10. G: Pasca-proses deterministik membuang kata seru pembuka berulang
def test_pasca_proses_kata_seru_berulang():
    """Kata seru yang sama dengan salah satu dari 3 pembuka terakhir dibuang sampai koma pertama."""
    history = [
        {"role": "assistant", "content": "Baik, ada yang bisa dibantu?"},
        {"role": "user", "content": "tanya"},
        {"role": "assistant", "content": "Tentu, ini daftarnya."}
    ]

    # Jawaban baru dimulai dengan 'Baik,' yang sudah pernah dipakai
    reply_1 = "Baik, kami rekomendasikan produk ini untuk kebutuhan Anda."
    cleaned_1 = strip_repeated_opening_interjection(reply_1, history=history)
    assert cleaned_1 == "Kami rekomendasikan produk ini untuk kebutuhan Anda."

    # Jawaban baru dengan kata seru berbeda (misal 'Siap,') dipertahankan
    reply_2 = "Siap, unit ini tersedia di katalog."
    cleaned_2 = strip_repeated_opening_interjection(reply_2, history=history)
    assert cleaned_2 == "Siap, unit ini tersedia di katalog."
