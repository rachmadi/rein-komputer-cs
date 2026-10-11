# -*- coding: utf-8 -*-
"""
tests/test_putaran15b_synthetic.py
Pengujian sintetis untuk PUTARAN 15b:
- Butir 1: Regresi kategori & proteksi merek saat evaluasi/perbandingan
- Butir 4: Pertanyaan spesifikasi berbasis data (kolom terisi dan raw_data lengkap)
"""
import pytest
from services.session_pipeline import SessionPipeline
from services.schema_actions import (
    ParserOutput, ActionEnum, ActionArguments, StateUpdate,
    AlasanTidakJelasEnum, AtributSpesifikasiEnum
)
from services.validator import validate_parser_output


def test_butir1_kategori_tetap_laptop_saat_pesan_profil_desktop_ideal():
    """
    Tes Butir 1: State awal laptop dengan kebutuhan.
    Pesan pelanggan memuat kata kunci profil 'desktop ideal' ('AI lokal' / 'bikin model bisnis menggunakan AI lokal').
    Kategori harus tetap 'laptop' dan kebutuhan_teks harus tetap ada (tidak ter-reset).
    """
    pipeline = SessionPipeline()
    state = {
        "kategori": "laptop",
        "kebutuhan_teks": "cari artikel ilmiah",
        "produk_tampil": ["KB-L11", "KB-L12"]
    }

    # Pesan yang memicu profil P13 ("desktop (ideal)") tanpa menyebut kata "desktop"
    res, updated_state = pipeline.process_turn(
        "aku juga mau bikin model bisnis menggunakan AI lokal",
        session_state=state
    )

    assert updated_state["kategori"] == "laptop", f"Kategori seharusnya tetap laptop, didapat: {updated_state['kategori']}"
    assert updated_state.get("kebutuhan_teks") is not None, "Kebutuhan_teks tidak boleh di-reset menjadi None"
    assert "ai" in updated_state["kebutuhan_teks"].lower() or "artikel" in updated_state["kebutuhan_teks"].lower() or "model bisnis" in updated_state["kebutuhan_teks"].lower()


def test_butir1_kategori_hanya_berganti_jika_disebut_eksplisit():
    """
    Kategori hanya boleh berganti jika pelanggan menyebut kategori baru secara eksplisit di pesan.
    """
    pipeline = SessionPipeline()
    state = {
        "kategori": "laptop",
        "kebutuhan_teks": "coding python"
    }

    # Pelanggan menyebut eksplisit "desktop"
    res, updated_state = pipeline.process_turn(
        "Tolong ganti tampilkan komputer desktop saja",
        session_state=state
    )

    assert updated_state["kategori"] == "desktop", f"Kategori seharusnya berganti ke desktop, didapat: {updated_state['kategori']}"


def test_butir1_rujukan_produk_bandingkan_tidak_mengubah_merek_state():
    """
    Tes Butir 1: Giliran membandingkan dua produk dari merek berbeda (Asus TUF vs Acer Nitro)
    tidak boleh mengubah atau mengunci merek di state menjadi salah satunya.
    """
    pipeline = SessionPipeline()
    state = {
        "kategori": "laptop",
        "merek": None,
        "kebutuhan_teks": "AI lokal",
        "produk_tampil": ["KB-L25", "KB-L24"]
    }

    # Pelanggan menanyakan perbandingan dua merek
    res, updated_state = pipeline.process_turn(
        "Apa kelebihannya Asus TUF dibanding Acer Nitro yang ditawarkan itu kalau AI lokal?",
        session_state=state
    )

    assert updated_state.get("merek") is None, f"Merek di state seharusnya tetap None, bukan {updated_state.get('merek')}"


def test_butir1_validator_menolak_merek_pada_aksi_bandingkan_dan_evaluasi():
    """
    Validator harus membersihkan args.merek dan state_up.merek saat aksi adalah BANDINGKAN atau EVALUASI_KECOCOKAN.
    """
    parsed = ParserOutput(
        aksi=ActionEnum.BANDINGKAN,
        argumen=ActionArguments(
            produk=["KB-L25", "KB-L24"],
            merek="acer"  # LLM parser keliru menyertakan merek dari nama produk pembanding
        ),
        pembaruan_state=StateUpdate(
            merek="acer"
        )
    )

    validated, ok = validate_parser_output(parsed, session_state={"produk_tampil": ["KB-L25", "KB-L24"]})
    assert ok is True
    assert validated.argumen.merek is None
    assert validated.pembaruan_state.merek is None
    kontrak = getattr(validated, "kontrak_intent", {})
    assert "merek" not in kontrak.get("argumen_valid", {})
