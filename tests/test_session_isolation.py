# -*- coding: utf-8 -*-
"""
tests/test_session_isolation.py
Membuktikan isolasi penuh antar sesi (Poin 3):
- Sesi A melakukan pencarian / rekomendasi profil P11 dan menampilkan produk.
- Sesi B yang baru langsung meminta "murahin dikit" -> harus menjawab belum ada hasil sebelumnya,
  tanpa ada kebocoran produk maupun profil dari Sesi A.
"""
import pytest
from services.chat_service import get_session_manager, process_chat_message
from services.schema_actions import ParserOutput, ActionEnum, ActionArguments, JenisEnum
from services.action_engine import ActionEngine
from services.session_pipeline import SessionPipeline


def test_two_sessions_isolation_via_action_engine():
    """Uji deterministik langsung pada ActionEngine untuk membuktikan isolasi state."""
    engine = ActionEngine()

    # Sesi A: minta rekomendasi P11
    parsed_a = ParserOutput(
        aksi=ActionEnum.MINTA_REKOMENDASI,
        argumen=ActionArguments(kebutuhan_teks="resep dan youtube", kategori="laptop")
    )
    state_a = {}
    res_a = engine.execute(parsed_a, session_state=state_a)
    assert res_a.profil_id == "P11"
    assert len(res_a.produk_list) > 0
    state_a["produk_tampil"] = res_a.produk_list
    state_a["profil_aktif"] = res_a.profil_id

    # Sesi B: sesi baru tanpa produk_tampil, user minta "murahin dikit" (lanjutan_hasil)
    parsed_b = ParserOutput(
        aksi=ActionEnum.LANJUTAN_HASIL,
        argumen=ActionArguments(jenis=JenisEnum.LEBIH_MURAH)
    )
    state_b = {}  # Sesi B bersih total
    res_b = engine.execute(parsed_b, session_state=state_b)

    # Fakta sesi B harus melaporkan belum_ada_hasil, produk kosong, tanpa produk A
    assert res_b.fakta["status"] == "belum_ada_hasil"
    assert res_b.fakta["total_ditemukan"] == 0
    assert len(res_b.produk_list) == 0

    # Pastikan state A tetap tidak terganggu
    assert len(state_a["produk_tampil"]) > 0
    assert state_a["profil_aktif"] == "P11"


def test_two_sessions_isolation_via_session_manager():
    """Uji isolasi antar session_id pada SessionManager."""
    sm = get_session_manager()

    sid_a = "test_sess_iso_A"
    sid_b = "test_sess_iso_B"

    sm.reset_session(sid_a)
    sm.reset_session(sid_b)

    sess_a = sm.get_session(sid_a)
    sess_b = sm.get_session(sid_b)

    # Isi state di Sesi A
    sess_a["state"]["profil_aktif"] = "P11"
    sess_a["state"]["produk_tampil"] = [{"kode": "KB-L01", "nama": "Acer Aspire Lite 14", "harga": 5199000}]
    sm.add_message(sid_a, "user", "laptop buat cari resep")
    sm.add_message(sid_a, "bot", "Berikut rekomendasi laptop Acer")

    # Pastikan Sesi B tetap kosong dan bersih
    assert sess_b["state"].get("profil_aktif") is None
    assert sess_b["state"].get("produk_tampil") in (None, [])
    assert len(sess_b["messages"]) == 1  # hanya salam pembuka default
