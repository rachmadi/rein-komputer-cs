# -*- coding: utf-8 -*-
"""
tests/test_persona_salutation.py
Uji validasi persona, sebutan lawan bicara, dan ekstraksi multi-slot (Poin 5):
- persona = pengguna perangkat, bukan lawan bicara.
- Lawan bicara selalu disapa "Kak" kecuali menyebut sebutan untuk diri sendiri.
- Generator menerima slot_sudah_diketahui agar tidak menanyakan ulang slot yang sudah terisi.
- Parser / Validator mendukung multi-slot extraction dari satu giliran (misal: kategori + persona).
"""
import pytest
from services.schema_actions import ParserOutput, ActionEnum, ActionArguments, StateUpdate
from services.validator import validate_parser_output
from services.llm_generator import build_generator_messages


def test_persona_does_not_contaminate_sebutan():
    """Jika persona diisi 'mama', sebutan tidak boleh otomatis menjadi 'mama'."""
    raw = {
        "aksi": "cari_produk",
        "argumen": {"kategori": "laptop"},
        "pembaruan_state": {
            "kategori": "laptop",
            "persona": "mama",
            "sebutan": "mama"  # Model keliru menyamakan sebutan dengan persona
        }
    }
    validated, is_valid = validate_parser_output(raw)
    assert is_valid is True
    assert validated.pembaruan_state.persona == "mama"
    # Validator harus membersihkan sebutan agar tidak memanggil pelanggan 'mama'
    assert validated.pembaruan_state.sebutan is None


def test_generator_messages_uses_kak_when_persona_exists():
    """Generator harus menyapa 'Kak' meskipun persona perangkat adalah 'mama'."""
    state = {
        "persona": "mama",
        "kategori": "laptop",
        "sebutan": None
    }
    messages = build_generator_messages(
        aksi="minta_rekomendasi",
        fakta={"status": "sukses", "produk": []},
        state=state
    )
    user_prompt = messages[-1]["content"]
    assert '"sebutan_pelanggan": "Kak"' in user_prompt
    assert '"persona_pengguna_perangkat": "mama"' in user_prompt
    assert '"kategori": "laptop"' in user_prompt
    assert '"persona": "mama"' in user_prompt


def test_generator_respects_explicit_self_sebutan():
    """Jika pelanggan menyebut sebutan untuk dirinya sendiri (misal Dokter), gunakan sebutan itu."""
    state = {
        "persona": "dokter",
        "sebutan": "Dokter",
        "kategori": "laptop"
    }
    messages = build_generator_messages(
        aksi="cari_produk",
        fakta={"status": "sukses"},
        state=state
    )
    user_prompt = messages[-1]["content"]
    assert '"sebutan_pelanggan": "Dokter"' in user_prompt


def test_multi_slot_extraction_validation():
    """Satu kalimat dapat mengisi kategori sekaligus persona tanpa konflik."""
    raw = {
        "aksi": "minta_rekomendasi",
        "argumen": {
            "kategori": "laptop",
            "persona": "mama",
            "kebutuhan_teks": "cari resep masakan"
        },
        "pembaruan_state": {
            "kategori": "laptop",
            "persona": "mama",
            "kebutuhan_teks": "cari resep masakan"
        }
    }
    validated, is_valid = validate_parser_output(raw)
    assert is_valid is True
    assert validated.argumen.kategori == "laptop"
    assert validated.argumen.persona == "mama"
    assert validated.pembaruan_state.kategori == "laptop"
    assert validated.pembaruan_state.persona == "mama"
