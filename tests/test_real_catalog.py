# -*- coding: utf-8 -*-
"""
Automated Test Suite: Pengujian Katalog Riil 20 Produk (10 Laptop, 5 Desktop, 5 Printer)
Memverifikasi:
1. Pemuatan 20 produk riil dari Qdrant & Dummy
2. Respons query kategori Printer, Laptop, Desktop
3. Rekomendasi printer berdasarkan kebutuhan (kantor, cetak tugas, scan & fotokopi)
4. Komparasi produk printer dan spesifikasi teknisnya
5. Query anggaran / budget untuk printer dan laptop
6. Pencarian laptop dan desktop spesifikasi nyata (RTX 4060, SSD 1 TB, dsb.)
"""
import pytest
from core.catalog import Catalog
from core.state import new_state
from core.engine import step

@pytest.fixture
def catalog():
    return Catalog.load(source="qdrant")

def test_katalog_counts_and_categories(catalog):
    assert len(catalog.products) == 20
    laptops = [p for p in catalog.products if p["kategori"] == "laptop"]
    desktops = [p for p in catalog.products if p["kategori"] == "desktop"]
    printers = [p for p in catalog.products if p["kategori"] == "printer"]
    assert len(laptops) == 10
    assert len(desktops) == 5
    assert len(printers) == 5

def test_toko_jual_apa(catalog):
    s = new_state()
    s, reply, route = step(s, "Jual apa aja?", catalog)
    assert route == "DIRECT"
    assert "laptop (10 produk)" in reply
    assert "desktop (5 produk)" in reply
    assert "printer (5 produk)" in reply

def test_printer_kebutuhan_kantor_dan_fotokopi(catalog):
    s = new_state()
    s, reply, route = step(s, "Cari printer buat kantor yang bisa scan sama fotokopi", catalog)
    assert route == "OFFER"
    # Harus merekomendasikan printer multifungsi seperti Epson L3210 atau Canon G3020
    assert "Epson EcoTank L3210" in reply or "Canon PIXMA G3020" in reply
    assert "Scan, Copy" in reply
    assert "Printernya" not in reply or "katalog" in reply

def test_printer_murah_tugas_sekolah(catalog):
    s = new_state()
    s, reply, route = step(s, "Ada printer murah buat anak sekolah?", catalog)
    assert route == "OFFER"
    # Canon TS207 adalah printer paling murah (Rp699.000)
    assert "Canon PIXMA TS207" in reply
    assert "Rp699.000" in reply

def test_spesifikasi_printer_epson_l3210(catalog):
    s = new_state()
    s, reply, route = step(s, "Berapa harga dan fitur Epson EcoTank L3210?", catalog)
    assert route == "PRODUCT_Q"
    assert "Rp2.299.000" in reply
    assert "Epson EcoTank L3210" in reply

def test_komparasi_dua_printer(catalog):
    s = new_state()
    s, reply, route = step(s, "Bedanya Canon PIXMA G3020 dan Brother DCP-T520W apa?", catalog)
    assert route == "COMPARE"
    assert "Harga" in reply
    assert "Fungsi" in reply
    assert "Kecepatan" in reply
    assert "Konektivitas" in reply
    assert "Rp2.599.000" in reply
    assert "Rp2.999.000" in reply

def test_laptop_paling_murah(catalog):
    s = new_state()
    s, reply, route = step(s, "Laptop paling murah ada apa?", catalog)
    assert route == "OFFER"
    # Acer Aspire Lite 14 paling terjangkau (Rp5.199.000)
    assert "Acer Aspire Lite 14" in reply
    assert "Rp5.199.000" in reply

def test_laptop_gaming_high_end(catalog):
    s = new_state()
    s, reply, route = step(s, "Cari laptop gaming spek paling tinggi", catalog)
    assert route == "OFFER"
    # Harus menyodorkan seri gaming spek tertinggi (Lenovo Legion Pro 5 16)
    assert "Lenovo Legion Pro 5 16" in reply
    assert "RTX 4070" in reply

def test_desktop_administrasi_mini(catalog):
    s = new_state()
    s, reply, route = step(s, "Butuh PC desktop untuk kasir dan administrasi", catalog)
    assert route == "OFFER"
    assert "Lenovo IdeaCentre Mini 01" in reply or "ASUS ExpertCenter D500 Tower" in reply

def test_dasar_pemilihan_berbasis_spesifikasi(catalog):
    s = new_state()
    s, reply, route = step(s, "Cari laptop buat insinyur teknik", catalog)
    assert route == "OFFER"
    # Memverifikasi bahwa tidak ada teks artifisial 'katalog menyebut cocok untuk'
    assert "katalog menyebut cocok untuk" not in reply.lower()
    # Menjelaskan rekomendasi berdasarkan prosesor/GPU/RAM
    assert "Dasar pemilihan" in reply
    assert "GPU" in reply or "prosesor" in reply.lower()

def test_summary_tanpa_penggunaan_yang_disarankan(catalog):
    s = new_state()
    s, reply, route = step(s, "Detail spesifikasi Lenovo Legion Pro 5 16", catalog)
    assert route == "PRODUCT_Q"
    assert "Prosesor: Intel Core i7-14650HX" in reply
    assert "RAM: 32 GB DDR5" in reply
    assert "GPU: NVIDIA GeForce RTX 4070 8 GB" in reply
    # Tidak ada baris artifisial 'Penggunaan yang disarankan:'
    assert "Penggunaan yang disarankan" not in reply

def test_spread_tanpa_katalog_usage(catalog):
    s = new_state()
    s, reply, route = step(s, "Ada laptop apa aja?", catalog)
    assert route == "SPREAD"
    assert "Katalog:" not in reply
    assert "termurah" in reply
    assert "tertinggi" in reply

