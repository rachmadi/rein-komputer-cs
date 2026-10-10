# -*- coding: utf-8 -*-
"""
tests/test_putaran12_synthetic.py
Tes unit sintetis untuk Putaran 12:
- Kategori tak dikenal ditolak
- Ganti kategori mereset merek
- Pesan majemuk menjalankan pencarian
- Klaim ketiadaan tanpa lookup dicegah
(Semua contoh sintetis buatan sendiri, tanpa teks nyata dari log/laporan)
"""
import pytest
from unittest.mock import MagicMock

from services.schema_actions import (
    ParserOutput, ActionEnum, ActionArguments, StateUpdate, SlotEnum, JenisPerbaikanEnum
)
from services.validator import validate_parser_output
from services.session_pipeline import SessionPipeline
from services.action_engine import ActionEngine
from services.grounding_checker import GroundingChecker


@pytest.fixture
def action_engine():
    return ActionEngine()


@pytest.fixture
def session_pipeline():
    return SessionPipeline()


def test_kategori_tak_dikenal_ditolak():
    """B1: Validator menolak pembaruan state kategori yang tidak ada di nilai katalog."""
    raw_output = {
        "aksi": "minta_rekomendasi",
        "argumen": {
            "kategori": "alat_dapur",  # kategori sintetis tak dikenal
            "kebutuhan_teks": "desain grafis sintetis"
        },
        "pembaruan_state": {
            "kategori": "alat_dapur"
        }
    }
    validated, is_valid = validate_parser_output(raw_output)
    assert is_valid is True
    # Kategori tak dikenal harus dihapus / di-None-kan oleh validator
    assert validated.argumen.kategori is None
    assert validated.pembaruan_state.kategori is None


def test_ganti_kategori_mereset_merek(action_engine, session_pipeline):
    """B2: Saat kategori berganti, merek lama di-reset jika tidak disebut eksplisit di pesan baru."""
    # State awal diisi kategori printer dan merek Epson
    state = {
        "kategori": "printer",
        "merek": "epson",
        "kebutuhan_teks": "cetak dokumen skripsi",
        "budget": 3000000,
        "produk_tampil": [{"kode": "KB-P02", "nama": "Epson Printer Sintetis"}],
        "kriteria_pelanggan": {"kategori": "printer", "merek": "epson"}
    }

    # Pelanggan berganti haluan menanyakan kategori laptop secara umum tanpa sebut merek
    pesan = "Apakah ada perangkat laptop untuk tugas kuliah?"
    
    # Jalankan melalui pipeline logic kategori switch
    mock_parsed = ParserOutput(
        aksi=ActionEnum.CARI_PRODUK,
        argumen=ActionArguments(kategori="laptop"),
        pembaruan_state=StateUpdate(kategori="laptop")
    )
    
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr("services.session_pipeline.parse_user_message", lambda *args, **kwargs: (mock_parsed, {"latency_ms": 1.0, "json_valid": True}))
        mp.setattr("services.session_pipeline.generate_response", lambda *args, **kwargs: (MagicMock(teks="Berikut rekomendasi laptop untuk Kakak.", pertanyaan_diajukan=None, penilaian=None, tampilkan_kartu=True, produk_dibahas=None), {}))
        
        res, new_state = session_pipeline.process_turn(pesan, session_state=state)

    assert new_state["kategori"] == "laptop"
    # Merek lama epson harus sudah di-reset, bukan terbawa ke kategori laptop
    assert new_state["merek"] is None
    assert "merek" not in new_state.get("kriteria_pelanggan", {})


def test_pesan_majemuk_menjalankan_pencarian(action_engine):
    """C1: Jika ada kriteria produk pada perbaiki_percakapan / keluhan, pencarian tetap dijalankan."""
    parsed = ParserOutput(
        aksi=ActionEnum.PERBAIKI_PERCAKAPAN,
        argumen=ActionArguments(
            jenis=JenisPerbaikanEnum.KELUHAN,
            rujukan="keluhan salah paham",
            kategori="laptop",
            merek="acer"
        ),
        pembaruan_state=StateUpdate(kategori="laptop", merek="acer")
    )
    state = {
        "kategori": "printer",
        "produk_tampil": []
    }

    res = action_engine.execute(parsed, session_state=state)
    assert res.aksi == ActionEnum.PERBAIKI_PERCAKAPAN
    assert res.fakta.get("ada_keluhan") is True
    assert res.fakta.get("nada") == "keluhan"
    # Pencarian katalog harus tetap menghasilkan produk, bukan daftar kosong
    assert len(res.produk_list) > 0
    assert any("acer" in p.get("nama", "").lower() for p in res.produk_list)


def test_klaim_ketiadaan_tanpa_lookup_dicegah():
    """D1: GroundingChecker mencegah generator mengklaim ketiadaan/keberadaan jika belum_dicari bernilai True."""
    checker = GroundingChecker()
    fakta_belum_dicari = {
        "status": "sapaan",
        "belum_dicari": True
    }
    
    # Respons yang mengklaim stok ada tanpa pencarian
    teks_klaim_ada = "Halo Kak! Kami punya stok laptop Asus yang siap dibeli hari ini."
    is_valid_ada, viol_ada = checker.check(teks_klaim_ada, fakta_belum_dicari)
    assert is_valid_ada is False
    assert any("belum_dicari" in v for v in viol_ada)

    # Respons yang mengklaim stok kosong tanpa pencarian
    teks_klaim_kosong = "Halo Kak! Sayang sekali stok laptop Acer di toko kami habis."
    is_valid_kosong, viol_kosong = checker.check(teks_klaim_kosong, fakta_belum_dicari)
    assert is_valid_kosong is False
    assert any("belum_dicari" in v for v in viol_kosong)


def test_trace_a2_printer_canon_kebutuhan(action_engine, capsys):
    """Trace A2: Menelusuri jalur jawab_pertanyaan_bot untuk printer Canon dengan kebutuhan cetak dokumen."""
    from services.action_engine import get_product_brand
    from services.knowledge_service import get_usage_requirements, get_profile_by_id
    from services.catalog_search import apply_filters

    state = {
        "kategori": "printer",
        "merek": "canon",
        "kebutuhan_teks": "cetak dokumen hemat tinta"
    }
    args = ActionArguments(slot=SlotEnum.KEBUTUHAN, nilai="cetak dokumen hemat tinta")

    # Tahap 1: Ambang RAG
    reqs = get_usage_requirements("cetak dokumen hemat tinta")
    pls = reqs.get("profil", [])
    print(f"\n[TRACE A2] Tahap 1 - Ambang RAG: Ditemukan {len(pls)} profil: {[p.get('profil_id') for p in pls]}")

    # Tahap 2: Filter Kategori
    kategori = state["kategori"]
    cands_cat = [p for p in action_engine.catalog.products if p.get("kategori", "").lower() == kategori.lower()]
    print(f"[TRACE A2] Tahap 2 - Filter Kategori ({kategori}): {len(cands_cat)} kandidat")

    # Tahap 3: Filter Merek
    merek = state["merek"]
    cands_merek = [p for p in cands_cat if merek == get_product_brand(p) or merek in str(p.get("nama", "")).lower()]
    print(f"[TRACE A2] Tahap 3 - Filter Merek ({merek}): {len(cands_merek)} kandidat ({[p.get('nama') for p in cands_merek]})")

    # Tahap 4: Filter Profil (apply_filters)
    prof_id = pls[0]["profil_id"] if pls else None
    prof_data = get_profile_by_id(prof_id)
    filters = prof_data.get("filter", [])
    print(f"[TRACE A2] Tahap 4 - Profil {prof_id} ({prof_data.get('judul')}) filter: {filters}")

    cands_passed = []
    gugur = []
    for p in cands_merek:
        passed, reason, penalty, report = apply_filters(p, filters)
        if passed:
            cands_passed.append(p)
        else:
            gugur.append((p.get("nama"), reason, report.get("tidak_terpenuhi")))
        print(f"  Produk {p.get('nama')}: passed={passed}, alasan={reason}")

    print(f"[TRACE A2] Kandidat lolos apply_filters: {len(cands_passed)}, gugur: {len(gugur)}")

    # Eksekusi riil lewat _handle_jawab_pertanyaan_bot
    res = action_engine._handle_jawab_pertanyaan_bot(args, state)
    print(f"[TRACE A2] Status fakta akhir: {res.fakta.get('status')}")

    # Bukti diagnostik:
    # 1. Kandidat masih ada sampai tahap merek (2 unit)
    assert len(cands_merek) == 2
    # 2. Tahap profil/apply_filters menghabiskan seluruh kandidat karena printer tidak punya spek PC (ram/ssd/cpu)
    assert len(cands_passed) == 0
    assert len(gugur) == 2
    # 3. Status akhir adalah 'belum_ada_yang_memenuhi'
    assert res.fakta.get("status") == "belum_ada_yang_memenuhi"

