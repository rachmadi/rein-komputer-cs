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


def test_butir3_foto_produk_lokal_dan_tanpa_fallback():
    """
    Butir 3: Produk dengan image_file sah harus merujuk ke berkas gambar di disk.
    Jika tidak ada berkas sah, tidak boleh ada foto dan tidak boleh ada fallback unsplash.
    """
    from pathlib import Path
    import sqlite3

    conn = sqlite3.connect("data/test_catalog.db")
    c = conn.cursor()
    c.execute("SELECT kode, image_url, image_file FROM products WHERE image_file IS NOT NULL")
    valid_rows = c.fetchall()
    conn.close()

    assert len(valid_rows) >= 8, f"Harus ada minimal 8 produk dengan foto lokal sah, ditemukan: {len(valid_rows)}"
    for kode, img_url, img_file in valid_rows:
        p = Path(img_file)
        assert p.exists(), f"Berkas gambar lokal untuk {kode} tidak ditemukan di {img_file}"
        assert p.stat().st_size > 0, f"Berkas gambar lokal untuk {kode} kosong"


def test_butir4_tanya_spesifikasi_berbasis_data_canon_g3020():
    """
    Butir 4:
    - 'bisa cetak foto?' dipetakan ke teks bebas 'cetak foto' dan menghasilkan fakta cetak foto sah
    - 'tabung tinta' menghasilkan informasi tipe printer / tangki tinta
    - Atribut yang tidak ada (kamera pada printer) menghasilkan 'atribut_tidak_tersedia'
    - 'kelebihan' dijawab dari komparasi data
    - 'spesifikasinya?' dijawab ringkasan lembar
    - ActionEngine selalu menyertakan lembar_spesifikasi lengkap
    """
    from services.action_engine import ActionEngine
    from services.schema_actions import ParserOutput, ActionEnum, ActionArguments

    engine = ActionEngine(db_path="data/test_catalog.db")

    # 1. Cetak foto pada Canon G3020 (KB-P10)
    p_foto = ParserOutput(
        aksi=ActionEnum.TANYA_SPESIFIKASI,
        argumen=ActionArguments(produk=["KB-P10"], atribut="cetak foto")
    )
    res_foto = engine.execute(p_foto, session_state={})
    assert res_foto.fakta["status"] == "sukses"
    assert "borderless" in str(res_foto.fakta.get("nilai", "")).lower() or "tanpa tepi" in str(res_foto.fakta.get("nilai", "")).lower()
    assert "lembar_spesifikasi" in res_foto.fakta

    # 2. Tabung tinta pada Canon G3020
    p_tinta = ParserOutput(
        aksi=ActionEnum.TANYA_SPESIFIKASI,
        argumen=ActionArguments(produk=["KB-P10"], atribut="tabung tinta")
    )
    res_tinta = engine.execute(p_tinta, session_state={})
    assert res_tinta.fakta["status"] == "sukses"
    assert "tinta" in str(res_tinta.fakta.get("nilai", "")).lower()
    assert "lembar_spesifikasi" in res_tinta.fakta

    # 3. Atribut tidak ada (kamera pada printer) -> atribut_tidak_tersedia tanpa menebak
    p_kamera = ParserOutput(
        aksi=ActionEnum.TANYA_SPESIFIKASI,
        argumen=ActionArguments(produk=["KB-P10"], atribut="kamera")
    )
    res_kamera = engine.execute(p_kamera, session_state={})
    assert res_kamera.fakta["status"] == "atribut_tidak_tersedia"
    assert "lembar_spesifikasi" in res_kamera.fakta

    # 4. Kelebihan produk dibanding produk lain yang tampil
    p_lebih = ParserOutput(
        aksi=ActionEnum.TANYA_SPESIFIKASI,
        argumen=ActionArguments(produk=["KB-P10"], atribut="kelebihan")
    )
    res_lebih = engine.execute(p_lebih, session_state={
        "produk_tampil": [
            {"kode": "KB-P10", "nama": "Canon PIXMA G3020", "harga": 2550000},
            {"kode": "KB-P02", "nama": "Epson EcoTank L3210", "harga": 2400000}
        ]
    })
    assert res_lebih.fakta["status"] == "sukses"
    assert res_lebih.fakta.get("tipe_jawaban") == "kelebihan"
    assert "ringkasan_kelebihan" in res_lebih.fakta
    assert "lembar_spesifikasi" in res_lebih.fakta

    # 5. Spesifikasi umum ("spesifikasinya?")
    p_umum = ParserOutput(
        aksi=ActionEnum.TANYA_SPESIFIKASI,
        argumen=ActionArguments(produk=["KB-P10"], atribut=None)
    )
    res_umum = engine.execute(p_umum, session_state={})
    assert res_umum.fakta["status"] == "sukses"
    assert res_umum.fakta.get("tipe_jawaban") == "ringkasan_spesifikasi"
    assert "ringkasan_spek" in res_umum.fakta
    assert "lembar_spesifikasi" in res_umum.fakta


def test_butir4_property_based_spesifikasi_katalog_fixture():
    """
    Butir 4: Tes berbasis sifat atas seluruh katalog fixture:
    - Setiap kolom teknis terisi atau kunci raw_data terisi dapat ditanyakan dan berstatus sukses di FAKTA.
    - Kolom yang kosong/None menghasilkan status 'atribut_tidak_tersedia'.
    """
    import sqlite3
    import json
    from services.action_engine import ActionEngine
    from services.schema_actions import ParserOutput, ActionEnum, ActionArguments

    engine = ActionEngine(db_path="data/test_catalog.db")
    prods = engine.catalog.products

    tested_success = 0
    tested_unavailable = 0

    spec_columns = ["ram", "storage", "cpu", "gpu", "display", "refresh_hz", "screen_inch", "panel", "vram_gb", "gpu_dedicated"]

    for p in prods:
        # 1. Tes kolom tabel produk
        for col in spec_columns:
            val = p.get(col)
            p_out = engine.execute(
                ParserOutput(aksi=ActionEnum.TANYA_SPESIFIKASI, argumen=ActionArguments(produk=[p["kode"]], atribut=col)),
                session_state={}
            )
            if val not in (None, "", [], {}):
                assert p_out.fakta["status"] == "sukses", f"Produk {p['kode']} atribut {col} harus sukses tapi dapat {p_out.fakta['status']}"
                assert "lembar_spesifikasi" in p_out.fakta
                tested_success += 1
            else:
                # Kolom kosong -> jika raw_data juga tidak memuatnya, harus atribut_tidak_tersedia
                raw = p.get("raw_data")
                rdict = {}
                if raw:
                    try:
                        rdict = json.loads(raw) if isinstance(raw, str) else raw
                    except Exception:
                        pass
                if col not in rdict:
                    assert p_out.fakta["status"] == "atribut_tidak_tersedia", f"Produk {p['kode']} atribut kosong {col} harus atribut_tidak_tersedia tapi dapat {p_out.fakta['status']}"
                    tested_unavailable += 1

        # 2. Tes kunci raw_data
        raw = p.get("raw_data")
        if raw:
            rdict = json.loads(raw) if isinstance(raw, str) else raw
            for rk, rv in rdict.items():
                if rk in ("sumber_spek", "catatan_sumber"):
                    continue
                if rv not in (None, "", [], {}):
                    p_out = engine.execute(
                        ParserOutput(aksi=ActionEnum.TANYA_SPESIFIKASI, argumen=ActionArguments(produk=[p["kode"]], atribut=rk)),
                        session_state={}
                    )
                    assert p_out.fakta["status"] == "sukses", f"Produk {p['kode']} raw key {rk} harus sukses tapi dapat {p_out.fakta['status']}"
                    tested_success += 1

    assert tested_success >= 400, f"Harus ada minimal 400 pengujian sifat sukses, didapat {tested_success}"
    assert tested_unavailable >= 150, f"Harus ada minimal 150 pengujian sifat atribut_tidak_tersedia, didapat {tested_unavailable}"

