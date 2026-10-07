# -*- coding: utf-8 -*-
"""
Automated Test Suite: 39 Acceptance Tests (A s/d AM)
Berdasarkan Spesifikasi Bobby Computer Customer Care v1.2 §23
"""
import pytest
from core.catalog import Catalog
from core.state import new_state
from core.engine import step

@pytest.fixture
def catalog():
    # Menggunakan catalog sintetis v1.2 untuk regression test historis spesifikasi v1.2
    return Catalog.from_synthetic_v1_2()

def test_A_jawaban_terhadap_pertanyaan_terakhir(catalog):
    s = new_state()
    s, r1, route1 = step(s, "Jual laptop ya?", catalog)
    assert route1 == "ASK"
    s, r2, route2 = step(s, "Untuk kerja", catalog)
    assert route2 == "OFFER"
    assert "NusaTech Student 14" in r2
    assert "AstraBook 14 Core" in r2
    assert "Rp7.999.000" in r2
    assert "Rp9.499.000" in r2

def test_B_budget_belum_diketahui(catalog):
    s = new_state()
    s, _, _ = step(s, "Butuh laptop", catalog)
    s, _, _ = step(s, "Untuk desain", catalog)
    s, r3, route3 = step(s, "Belum tahu budget", catalog)
    assert "AstraBook 15 Pro" in r3
    assert "desain ringan" in r3

def test_C_budget_setelah_offer(catalog):
    s = new_state()
    s, _, _ = step(s, "Butuh laptop", catalog)
    s, _, _ = step(s, "Untuk desain", catalog)
    s, r3, route3 = step(s, "Yang di bawah 12 juta", catalog)
    assert "AstraBook 15 Pro" in r3
    assert "Creator 15" not in r3 or "13.499.000" not in r3

def test_D_pelanggan_menyerahkan_pilihan(catalog):
    s = new_state()
    s, _, _ = step(s, "Untuk desain", catalog)
    s, r2, route2 = step(s, "Terserah.", catalog)
    assert "AstraBook 15 Pro" in r2

def test_E_kebutuhan_berubah(catalog):
    s = new_state()
    s, _, _ = step(s, "Untuk kantor", catalog)
    s, r2, route2 = step(s, "Eh, buat programmer", catalog)
    assert s["needs"] == ["programming"]
    assert "Garuda Gaming G15" not in r2
    assert "NusaTech Student 14" in r2
    assert "AstraBook 14 Core" in r2
    assert "AstraBook 15 Pro" in r2

def test_F_pertanyaan_spesifikasi(catalog):
    s = new_state()
    s, _, _ = step(s, "Saya tawarkan NusaTech Creator 15", catalog)
    s, r2, route2 = step(s, "RAM-nya berapa?", catalog)
    assert route2 == "PRODUCT_Q"
    assert "16 GB DDR5" in r2

def test_G_koreksi(catalog):
    s = new_state()
    s, r, route = step(s, "Aku tanya laptop, bukan harga", catalog)
    assert route == "CORRECTION"

def test_H_ranking_harga(catalog):
    s = new_state()
    s, _, _ = step(s, "Untuk desain", catalog)
    s, r2, route2 = step(s, "Yang paling murah", catalog)
    assert "AstraBook 15 Pro" in r2
    assert "Merapi Monitor Pro 27" not in r2

def test_I_hasil_kosong(catalog):
    s = new_state()
    s, r, route = step(s, "Laptop di bawah 5 juta", catalog)
    assert route == "EMPTY"
    assert "NusaTech Student 14" in r
    assert "7.999.000" in r

def test_J_stok(catalog):
    s = new_state()
    s, r, route = step(s, "Apakah KB-L02 tersedia stoknya?", catalog)
    assert route == "UNAVAILABLE"
    assert "stok" in r.lower()

def test_K_atribut_tidak_ada(catalog):
    s = new_state()
    s, r, route = step(s, "Berapa kapasitas baterai AstraBook 15 Pro?", catalog)
    assert route == "UNAVAILABLE"
    assert "baterai" in r.lower()

def test_L_kategori_tidak_ada(catalog):
    s = new_state()
    s, r1, route1 = step(s, "Ada printer?", catalog)
    assert route1 == "CATEGORY_GUARD"
    s, r2, route2 = step(s, "Ada keyboard?", catalog)
    assert route2 == "CATEGORY_GUARD"

def test_M_perbandingan(catalog):
    s = new_state()
    s, r, route = step(s, "Bedanya AstraBook 15 Pro dan NusaTech Creator 15 apa?", catalog)
    assert route == "COMPARE"
    assert "11.999.000" in r
    assert "13.499.000" in r
    assert "RTX 2050" in r
    assert "RTX 3050" in r

def test_N_desktop(catalog):
    s = new_state()
    s, r, route = step(s, "Butuh desktop untuk programming", catalog)
    assert route == "OFFER"
    assert "Kencana Workstation" in r
    assert "monitor tidak termasuk" in r.lower()

def test_O_ram_gede(catalog):
    s = new_state()
    s, r, route = step(s, "Laptop yang RAM-nya gede", catalog)
    assert "16 GB" in r
    assert "DDR4" in r and "DDR5" in r

def test_P_prosesor_gede(catalog):
    s = new_state()
    s, r, route = step(s, "Yang prosesornya gede", catalog)
    assert "tidak diranking" in r.lower() or "kuantitatif" in r.lower()

def test_Q_referensi_ordinal(catalog):
    s = new_state()
    s, _, _ = step(s, "Untuk kerja", catalog)
    s, r2, route2 = step(s, "Yang kedua RAM-nya berapa?", catalog)
    assert route2 == "PRODUCT_Q"
    assert "AstraBook 14 Core" in r2 or "16 GB DDR4" in r2

def test_R_kategori_belum_ada_kebutuhan_jelas(catalog):
    s = new_state()
    s, r, route = step(s, "Untuk desain", catalog)
    assert route == "OFFER"
    assert "AstraBook 15 Pro" in r
    assert "Merapi Monitor" not in r

def test_S_niat_beli(catalog):
    s = new_state()
    s, _, _ = step(s, "Saya tawarkan NusaTech Creator 15", catalog)
    s, r2, route2 = step(s, "Oke, mau beli yang itu", catalog)
    assert route2 == "PURCHASE"
    assert "pembayaran" in r2.lower()

def test_T_budget_target(catalog):
    s = new_state()
    s, r, route = step(s, "Laptop sekitar 10 juta", catalog)
    assert route == "OFFER"
    assert "AstraBook 14 Core" in r

def test_U_variasi_bahasa_kerja(catalog):
    for ph in ["buat kerja", "kerjaan kantor", "ngetik dokumen", "pekerjaan administrasi"]:
        s = new_state()
        s["category"] = "laptop"
        s, r, route = step(s, ph, catalog)
        assert route == "OFFER"
        assert "NusaTech Student 14" in r

def test_V_mahasiswa_clue(catalog):
    s = new_state()
    s, r, route = step(s, "Saya mahasiswa, cari laptop", catalog)
    assert route == "OFFER"
    assert "NusaTech Student 14" in r

def test_W_urutan_kata(catalog):
    for ph in ["Laptop buat editing video", "laptop untuk video editing"]:
        s = new_state()
        s, r, route = step(s, ph, catalog)
        assert route == "OFFER"
        assert "NusaTech Creator 15" in r

def test_X_normalisasi_level_1(catalog):
    for greeting in ["Halo, Kak!", "Terima kasih.", "Makasih!", "Bye."]:
        s = new_state()
        s, r, route = step(s, greeting, catalog)
        assert route in ("DIRECT", "CANCEL")

def test_Y_atribut_dengan_kata_pembawa(catalog):
    s = new_state()
    s, r, route = step(s, "Prosesor apa untuk programming?", catalog)
    assert "programming" in s["needs"] or route in ("OFFER", "PRODUCT_Q")

def test_Z_referensi_sebelum_atribut(catalog):
    s = new_state()
    s, _, _ = step(s, "Butuh laptop untuk kerja", catalog)
    s, r2, route2 = step(s, "Yang kedua harganya berapa?", catalog)
    assert "9.499.000" in r2

def test_AA_nama_produk_tanpa_kandidat(catalog):
    s = new_state()
    s, r, route = step(s, "Berapa harga AstraBook 15 Pro dan berapa RAM-nya?", catalog)
    assert route == "PRODUCT_Q"
    assert "11.999.000" in r
    assert "16 GB DDR5" in r

def test_AB_gaming_dengan_budget(catalog):
    s = new_state()
    s, r, route = step(s, "Laptop gaming di bawah 12 juta", catalog)
    assert route == "OFFER"
    assert "AstraBook 15 Pro" in r
    assert "menengah" in r.lower()

def test_AC_kata_development(catalog):
    s = new_state()
    s, r, route = step(s, "Laptop buat development", catalog)
    assert route == "ASK"
    assert "Garuda Gaming G15" not in r

def test_AD_terserah_berulang(catalog):
    s = new_state()
    s, _, _ = step(s, "Butuh laptop", catalog)
    s, r2, route2 = step(s, "Terserah.", catalog)
    assert route2 == "SPREAD"
    s, r3, route3 = step(s, "Terserah.", catalog)
    assert route3 == "SPREAD2"

def test_AE_preferensi_dibersihkan_saat_kebutuhan_berganti(catalog):
    s = new_state()
    s, _, _ = step(s, "Laptop untuk desain, yang paling murah", catalog)
    s, r2, route2 = step(s, "Sekarang untuk gaming", catalog)
    assert "cheapest" not in s["preferences"]
    assert route2 == "OFFER"

def test_AF_pertanyaan_produk_tidak_mengunci_filter(catalog):
    s = new_state()
    s, _, _ = step(s, "Butuh laptop untuk kerja", catalog)
    s, _, _ = step(s, "Prosesornya Intel atau AMD?", catalog)
    assert s["constraints"]["vendor"] is None
    s, r3, route3 = step(s, "Ada yang lain?", catalog)
    assert route3 in ("MORE", "OFFER")

def test_AG_komputer(catalog):
    s = new_state()
    s, r, route = step(s, "Komputer untuk kantor", catalog)
    assert route == "OFFER"
    assert "Kencana Office Mini" in r

def test_AH_pembatalan_mereset_state(catalog):
    s = new_state()
    s, _, _ = step(s, "Laptop untuk desain", catalog)
    s, _, _ = step(s, "Nggak jadi", catalog)
    assert s["category"] is None
    s, r3, route3 = step(s, "RAM-nya berapa?", catalog)
    assert "belum ada produk" in r3.lower()

def test_AI_paling_murah_tanpa_kebutuhan(catalog):
    s = new_state()
    s, r, route = step(s, "Laptop yang paling murah", catalog)
    assert route == "OFFER"
    assert "NusaTech Student 14" in r

def test_AJ_jawaban_kebutuhan_tidak_dikenal(catalog):
    def stub_nlu(text, ctx):
        if "skripsi" in text:
            return {"needs": ["student"]}
        return {"needs": []}
        
    s = new_state()
    s, _, _ = step(s, "Jual laptop?", catalog)
    s, r2, route2 = step(s, "Buat ngerjain skripsi", catalog, nlu=stub_nlu)
    assert "NusaTech Student 14" in r2

def test_AK_nol_jaringan_di_level_1(catalog):
    def crash_nlu(text, ctx):
        raise RuntimeError("Jaringan Ollama tidak boleh dipanggil di Level 1!")
    s = new_state()
    s, r, route = step(s, "Halo, Kak!", catalog, nlu=crash_nlu)
    assert route == "DIRECT"

def test_AL_kata_nya_dan_nama(catalog):
    s = new_state()
    s, r, route = step(s, "Harganya AstraBook 15 Pro?", catalog)
    assert route == "PRODUCT_Q"
    assert "11.999.000" in r

def test_AM_atribut_monitor(catalog):
    s = new_state()
    s, r, route = step(s, "Merapi Monitor 24 RAM-nya berapa?", catalog)
    assert route == "PRODUCT_Q"
    assert "tidak berlaku untuk monitor" in r.lower()
    assert "Kak, Kak" not in r
