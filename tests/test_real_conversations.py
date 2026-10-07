# -*- coding: utf-8 -*-
"""
Automated Test Suite: Kasus-Kasus Percakapan Nyata dari Terminal
Memastikan tidak ada lagi regresi atas kasus:
1. Buat Papa (Persona Recognition, bukan blind spread)
2. Kurang nangkap kok nawarin? (Meta-critique handling, bukan gaslighting 'biar gak bingung')
3. Bingung aku (Anti-parrot looping pada gaming/offer)
4. Nanya resep, fesbukan, ChatGPT (Daily activity, bukan out_of_domain toko masak)
5. Ada yang bagusan dikit? (Pricier relative preference, bukan category guard)
6. Buka gak malem ini? (Informasi operasional toko)
"""
import pytest
from core.catalog import Catalog
from core.state import new_state
from core.engine import step

@pytest.fixture
def catalog():
    return Catalog.from_synthetic_v1_2()

def test_kasus_papa_guided_clarification(catalog):
    """
    Skenario: 'Buat Papa' tidak boleh langsung mengeksekusi sebaran buta (blind spread)
    menawarkan laptop gaming 16 juta, melainkan harus mengklarifikasi aktivitas Papa.
    """
    s = new_state()
    s, r1, route1 = step(s, "Jual laptop?", catalog)
    assert route1 == "ASK"
    
    s, r2, route2 = step(s, "Buat Papa", catalog)
    assert route2 == "ASK"
    # Memastikan tidak langsung menyodorkan Garuda Gaming G15 16 juta
    assert "Garuda Gaming G15" not in r2
    assert "Papa" in r2
    assert "ngetik" in r2 or "santai" in r2 or "kantor" in r2
    
    # Pengguna menjawab aktivitas
    s, r3, route3 = step(s, "Buat kerja ngetik sama browsing aja sih", catalog)
    assert route3 == "OFFER"
    assert "NusaTech Student 14" in r3

def test_kasus_meta_critique(catalog):
    """
    Skenario: Pengguna memprotes alur CS ('Kurang nangkap kok nawarin?').
    Bot tidak boleh meng-gaslight dengan 'Biar gak makin bingung...',
    melainkan harus meminta maaf atas ketergesa-gesaannya dan kembali meminta klarifikasi.
    """
    s = new_state()
    s, _, _ = step(s, "Jual laptop?", catalog)
    s, _, _ = step(s, "Buat Papa", catalog)
    s, r3, route3 = step(s, "Kurang nangkap kok nawarin?", catalog)
    assert route3 == "META_ALIGN"
    assert "maaf" in r3.lower()
    assert "biar nggak makin bingung" not in r3.lower()
    assert "biar gak makin bingung" not in r3.lower()

def test_kasus_anti_parrot_gaming(catalog):
    """
    Skenario: Pengguna menyatakan 'Waduh... bingung aku' setelah penawaran 3 laptop gaming.
    Bot DILARANG mengulang teks penawaran 3 laptop yang sama (parrot loop),
    melainkan harus mengontraskan opsi paling hemat vs opsi performa tertinggi.
    """
    s = new_state()
    s, _, _ = step(s, "Butuh laptop", catalog)
    s, r1, route1 = step(s, "Abang sih hobinya main game", catalog)
    assert route1 == "OFFER"
    assert "Garuda Gaming G15" in r1
    
    # Pengguna bingung
    s, r2, route2 = step(s, "Waduh... bingung aku", catalog)
    assert route2 == "UNCERTAIN_HELP"
    # Respons harus berupa panduan komparasi kontras
    assert "paling hemat" in r2 or "AstraBook 15 Pro" in r2
    assert "tertinggi" in r2 or "Garuda Gaming G15" in r2
    # TIDAK BOLEH mengulang template offer 'Nah, khusus buat gaming, aku punya beberapa pilihan mantap'
    assert "Nah, khusus buat gaming" not in r2

def test_kasus_resep_fesbuk_chatgpt(catalog):
    """
    Skenario: 'Mama sih paling juga buat nanya resep sama Chatgpt sama fesbukan'.
    Aktivitas web kasual ini HARUS dipetakan ke daily workload / laptop hemat,
    DILARANG keras menjawab 'Bobby Computer belum buka layanannya'.
    """
    s = new_state()
    s, _, _ = step(s, "Jual laptop?", catalog)
    s, r, route = step(s, "Mama sih paling juga buat nanya resep sama Chatgpt sama fesbukan", catalog)
    assert route == "OFFER"
    assert "NusaTech Student 14" in r
    assert "belum buka layanannya" not in r.lower()

def test_kasus_bagusan_dikit(catalog):
    """
    Skenario: 'Ada yang bagusan dikit?' setelah penawaran.
    HARUS diperlakukan sebagai preferensi relatif 'pricier',
    DILARANG keras dituduh 'katalog kami cuma ada laptop, desktop, dan monitor'.
    """
    s = new_state()
    s, _, _ = step(s, "Laptop untuk kerja", catalog)
    s, r, route = step(s, "Ada yang bagusan dikit?", catalog)
    assert route in ("REFINE", "OFFER", "MORE")
    assert "katalog kami saat ini hanya ada laptop" not in r

def test_kasus_operasional_toko(catalog):
    """
    Skenario: 'Boby buka gak malem ini?'
    Dijawab jujur bahwa informasi jam operasional toko belum tersedia di katalog.
    """
    s = new_state()
    s, r, route = step(s, "Boby buka gak malem ini?", catalog)
    assert route == "UNAVAILABLE"
    assert "jam operasional" in r.lower() or "buka" in r.lower() or "toko" in r.lower()

def test_kasus_bikin_pr_dan_belajar_nangkap(catalog):
    """
    Skenario nyata dari pengujian pengguna:
    1. 'Bantuin bikin PR bisa?' -> CATEGORY_GUARD toko komputer (§19)
    2. 'Kok gak bisa?' -> META_ALIGN klarifikasi peran asisten toko Bobby Computer
    3. 'Belajar nangkap dong kak' -> META_ALIGN minta maaf, TIDAK menawarkan laptop kuliah!
    4. 'Belajar nangkap gak perlu kuliah, kak' -> META_ALIGN, negasi 'tidak perlu kuliah' tidak memicu student need!
    """
    s = new_state()
    s, r1, route1 = step(s, "Bantuin bikin PR bisa?", catalog)
    assert route1 == "CATEGORY_GUARD"
    assert "laptop, desktop, dan monitor" in r1.lower()
    assert "perkuliahan" not in r1.lower()

    s, r2, route2 = step(s, "Kok gak bisa?", catalog)
    assert route2 == "META_ALIGN"
    assert "laptop, desktop, atau monitor" in r2.lower()
    assert "perkuliahan" not in r2.lower()

    s, r3, route3 = step(s, "Belajar nangkap dong kak", catalog)
    assert route3 == "META_ALIGN"
    # DILARANG keras menyodorkan laptop kuliah (NusaTech Student 14) hanya karena kata 'belajar'
    assert "kuliah" not in r3.lower()
    assert "nusatech student" not in r3.lower()

    s, r4, route4 = step(s, "Belajar nangkap gak perlu kuliah, kak", catalog)
    assert route4 == "META_ALIGN"
    # DILARANG keras menyodorkan laptop kuliah
    assert "kuliah/perkuliahan" not in r4.lower()
    assert "nusatech student" not in r4.lower()

def test_kasus_malem_dan_nawarkan_apa(catalog):
    """
    Skenario pengujian terbaru pengguna:
    1. 'Malem' -> Salam malam (DIRECT), bukan 'belum menangkap maksudnya'
    2. 'Gitu aja gak nangkap' -> META_ALIGN (minta maaf atas ketidaktanggapan, TIDAK minta maaf 'terburu-buru menawarkan' karena belum pernah offer!)
    3. 'Nawarkan apa? Jasa pijat?' -> CATEGORY_GUARD (hanya ada laptop, desktop, monitor; TIDAK membawa-bawa 'PR' atau 'tugas')
    4. 'Yang minta kerjain PR siapa?' -> META_ALIGN (minta maaf atas salah paham, arahkan ke laptop/desktop/monitor)
    """
    s = new_state()
    s, r1, route1 = step(s, "Malem", catalog)
    assert route1 == "DIRECT"
    assert "halo" in r1.lower() or "selamat" in r1.lower()
    assert "belum menangkap" not in r1.lower()

    s, r2, route2 = step(s, "Gitu aja gak nangkap", catalog)
    assert route2 == "META_ALIGN"
    assert "menawarkan" not in r2.lower()  # DILARANG minta maaf 'terburu-buru menawarkan' karena memang belum offer

    s, r3, route3 = step(s, "Nawarkan apa? Jasa pijat?", catalog)
    assert route3 == "CATEGORY_GUARD"
    assert "laptop, desktop, dan monitor" in r3.lower()
    assert "pr" not in r3.lower()  # DILARANG menyebut PR

    s, r4, route4 = step(s, "Yang minta kerjain PR siapa?", catalog)
    assert route4 == "META_ALIGN"
    assert "laptop, desktop, atau monitor" in r4.lower()

def test_kasus_konsultan_it_dan_critique(catalog):
    """
    Skenario:
    1. 'Kata Papa, buat kerja' -> Menawarkan laptop kerja/office
    2. 'Papaku konsultan IT' -> Mengenali konsultan IT / programming, bukan 'belum menangkap maksudnya'
    3. 'Gitu aja gak nangkap' -> Menangani keluhan secara santun, tidak berulang unknown
    """
    s = new_state()
    s, _, _ = step(s, "Kata Papa, buat kerja", catalog)
    s, r2, route2 = step(s, "Papaku konsultan IT", catalog)
    assert route2 in ("OFFER", "ASK")
    assert "belum menangkap maksudnya" not in r2.lower()

    s, r3, route3 = step(s, "Gitu aja gak nangkap", catalog)
    assert route3 == "META_ALIGN"
    assert "maaf" in r3.lower()

def test_kasus_ada_dan_cs_bego(catalog):
    """
    Skenario nyata dari screenshot pengguna (media_1791176771564.png):
    1. 'hai' -> CS: 'Halo, Kak! Ada yang bisa saya bantu?' (DIRECT)
    2. 'ada' -> Afirmasi salam ('Boleh, Kak! Sedang mencari laptop, desktop, atau monitor...') (ASK), BUKAN 'belum menangkap maksudnya'!
    3. 'Lah..tadi kan nanya, ada yang bisa saya bantu. Aku jawab ada' -> Penjelasan meta percakapan, BUKAN category guard!
    4. 'Ah...kamu pasti gak liat katalog.' -> Pembelaan katalog secara sopan, BUKAN loop 'belum menangkap maksudnya'!
    5. 'CS bego' -> De-eskalasi makian dengan minta maaf dan menawarkan bantuan secara santun, BUKAN loop 'belum menangkap maksudnya'!
    """
    s = new_state()
    s, r1, route1 = step(s, "hai", catalog)
    assert route1 == "DIRECT"
    assert "ada yang bisa saya bantu" in r1.lower()

    s, r2, route2 = step(s, "ada", catalog)
    assert route2 == "ASK"
    assert "belum menangkap maksudnya" not in r2.lower()
    assert "boleh" in r2.lower() or "laptop" in r2.lower()

    s, r3, route3 = step(s, "Lah..tadi kan nanya, ada yang bisa saya bantu. Aku jawab ada", catalog)
    assert route3 == "META_ALIGN"
    # DILARANG memicu category guard 'hanya ada laptop, desktop, dan monitor'
    assert "hanya ada laptop, desktop, dan monitor" not in r3.lower()

    s, r4, route4 = step(s, "Ah...kamu pasti gak liat katalog.", catalog)
    assert route4 == "META_ALIGN"
    assert "belum menangkap maksudnya" not in r4.lower()
    assert "katalog" in r4.lower()

    s, r5, route5 = step(s, "CS bego", catalog)
    assert route5 == "META_ALIGN"
    assert "belum menangkap maksudnya" not in r5.lower()
    assert "maaf" in r5.lower()

def test_kasus_sore_dan_bisa_bantu_apa(catalog):
    """
    Skenario nyata dari screenshot terbaru pengguna (media_1791177214821.png):
    1. 'Sore' -> DIRECT (Halo Kak! Ada yang bisa saya bantu?)
    2. 'Emang bisa bantu apa?' -> DIRECT (Di Bobby Computer, saya siap membantu memberikan rekomendasi laptop, desktop, dan monitor...)
    3. 'Gak perlu ditangkap' -> META_ALIGN (Hehe iya Kak... bercanda ya...)
    4. 'Cari kamu' -> DIRECT (Hehe kalau saya selalu siap melayani di sini Kak... Tapi saya asisten virtual khusus laptop...)
    """
    s = new_state()
    s, r1, route1 = step(s, "Sore", catalog)
    assert route1 == "DIRECT"
    assert "halo" in r1.lower() or "bisa saya bantu" in r1.lower()

    s, r2, route2 = step(s, "Emang bisa bantu apa?", catalog)
    assert route2 == "DIRECT"
    assert "laptop, desktop, dan monitor" in r2.lower()
    assert "belum menangkap maksudnya" not in r2.lower()

    s, r3, route3 = step(s, "Gak perlu ditangkap", catalog)
    assert route3 == "META_ALIGN"
    assert "belum menangkap maksudnya" not in r3.lower()

    s, r4, route4 = step(s, "Cari kamu", catalog)
    assert route4 == "DIRECT"
    assert "laptop" in r4.lower() or "asisten" in r4.lower()
    assert "belum menangkap maksudnya" not in r4.lower()

def test_kasus_bantu_beliin_dan_critique(catalog):
    """
    Skenario dialog nyata 10:
    1. 'Sore' -> DIRECT
    2. 'Bantu apa?' -> DIRECT
    3. 'Bantu beliin bisa?' -> PURCHASE (§18 penjelasan transaksi dan penawaran bantuan perangkat)
    4. 'Beliin gak ada?' -> PURCHASE
    5. 'Notebook gak ada?' -> ASK ('Ada, Kak! Laptopnya mau dipakai untuk apa, Kak?')
    6. 'Untuk apa ya?' -> SPREAD ('Supaya ada gambaran, ini pilihan dari yang termurah sampai tertinggi...')
    7. 'Belum nangkap tapi nawarin' -> META_ALIGN (Minta maaf terburu-buru, jelaskan opsi sebagai referensi)
    8. 'Emang kamu tau aku butuh yang gimana?' -> META_ALIGN (Jawab jujur belum tahu persis, tanyakan kebutuhan secara natural)
    """
    s = new_state()
    s, r1, route1 = step(s, "Sore", catalog)
    assert route1 == "DIRECT"

    s, r2, route2 = step(s, "Bantu apa?", catalog)
    assert route2 == "DIRECT"

    s, r3, route3 = step(s, "Bantu beliin bisa?", catalog)
    assert route3 == "PURCHASE"
    assert "transaksi dan pemesanan" in r3.lower()

    s, r4, route4 = step(s, "Beliin gak ada?", catalog)
    assert route4 == "PURCHASE"

    s, r5, route5 = step(s, "Notebook gak ada?", catalog)
    assert route5 == "ASK"
    assert "ada, kak" in r5.lower()

    s, r6, route6 = step(s, "Untuk apa ya?", catalog)
    assert route6 == "SPREAD"
    assert "supaya ada gambaran" in r6.lower()

    s, r7, route7 = step(s, "Belum nangkap tapi nawarin", catalog)
    assert route7 == "META_ALIGN"
    assert "terburu-buru" in r7.lower()

    s, r8, route8 = step(s, "Emang kamu tau aku butuh yang gimana?", catalog)
    assert route8 == "META_ALIGN"
    assert "belum tahu persis" in r8.lower()

def test_kasus_desain_dan_perbandingan_dua_produk(catalog):
    """
    Skenario dialog nyata 1 (Desain & Komparasi 2 Produk Ditawarkan):
    1. 'halo' -> DIRECT
    2. 'ada laptop?' -> ASK ('Ada, Kak!')
    3. 'desain' -> OFFER (AstraBook 15 Pro + NusaTech Creator 15)
    4. 'Ada yang bagusan dikit?' -> REFINE
    5. 'Gak ada yang lain?' -> MORE
    6. 'Opsi 1 itu ram berapa?' -> PRODUCT_Q
    7. 'Pake gpu?' -> PRODUCT_Q
    8. 'Bagus mana?' -> COMPARE (Membandingkan AstraBook 15 Pro vs NusaTech Creator 15)
    9. 'Itu kan ada 2. Bagus mana?' -> COMPARE
    """
    s = new_state()
    s, _, _ = step(s, "halo", catalog)
    s, r2, route2 = step(s, "ada laptop?", catalog)
    assert route2 == "ASK"
    assert "ada, kak" in r2.lower()

    s, r3, route3 = step(s, "desain", catalog)
    assert route3 == "OFFER"
    assert "AstraBook 15 Pro" in r3
    assert "NusaTech Creator 15" in r3

    s, r4, route4 = step(s, "Ada yang bagusan dikit?", catalog)
    assert route4 == "REFINE"

    s, r5, route5 = step(s, "Gak ada yang lain?", catalog)
    assert route5 == "MORE"

    s, r6, route6 = step(s, "Opsi 1 itu ram berapa?", catalog)
    assert route6 == "PRODUCT_Q"
    assert "16 GB" in r6

    s, r7, route7 = step(s, "Pake gpu?", catalog)
    assert route7 == "PRODUCT_Q"
    assert "RTX 2050" in r7

    s, r8, route8 = step(s, "Bagus mana?", catalog)
    assert route8 == "COMPARE"
    assert "AstraBook 15 Pro" in r8
    assert "NusaTech Creator 15" in r8
    assert "perbandingan" in r8.lower()

    s, r9, route9 = step(s, "Itu kan ada 2. Bagus mana?", catalog)
    assert route9 == "COMPARE"
    assert "AstraBook 15 Pro" in r9
    assert "NusaTech Creator 15" in r9

def test_kasus_berapaan_dan_gak_tahu_harga(catalog):
    """
    Skenario dialog nyata dari screenshot terbaru pengguna (media_1791181052475.png):
    1. 'Ada laptop' -> ASK ('Ada, Kak! Laptopnya mau dipakai untuk apa, Kak?')
    2. 'Berapaan, kak?' -> PRODUCT_Q (Menyebutkan rentang harga laptop di katalog dan contoh model, BUKAN 'belum ada produk yang dibahas'!)
    3. 'Kalo gak tahu harga ya gak beli' -> PRODUCT_Q (Mengafirmasi pentingnya tahu harga dan memberi kisaran laptop, BUKAN niat beli transaksi katalog!)
    4. 'Yang beli siapa?' -> META_ALIGN (Menjelaskan secara santun bahwa tidak harus beli sekarang, BUKAN loop niat beli!)
    """
    s = new_state()
    s, r1, route1 = step(s, "Ada laptop", catalog)
    assert route1 == "ASK"
    assert "ada, kak" in r1.lower()

    s, r2, route2 = step(s, "Berapaan, kak?", catalog)
    assert route2 == "PRODUCT_Q"
    assert "belum ada produk yang sedang kita bahas" not in r2.lower()
    assert "7.999.000" in r2
    assert "15.999.000" in r2

    s, r3, route3 = step(s, "Kalo gak tahu harga ya gak beli", catalog)
    assert route3 == "PRODUCT_Q"
    assert "transaksi dan pemesanan" not in r3.lower()
    assert "7.999.000" in r3

    s, r4, route4 = step(s, "Yang beli siapa?", catalog)
    assert route4 == "META_ALIGN"
    assert "transaksi dan pemesanan langsung" not in r4.lower()
    assert "tidak harus beli sekarang" in r4.lower() or "salah tangkap" in r4.lower()

def test_kasus_kata_papa_yang_bisa_gambar(catalog):
    """
    Skenario pengujian terbaru pengguna:
    1. 'Ada apa aja?' -> DIRECT (katalog listing kategori)
    2. 'laptop deh' -> ASK (tanya kebutuhan laptop)
    3. 'Kata papa, yang bisa gambar' -> OFFER (AstraBook 15 Pro untuk desain, BUKAN Category Guard!)
    4. 'Kata papa yang bisa bikin gambar' -> OFFER (AstraBook 15 Pro, BUKAN Category Guard!)
    """
    s = new_state()
    s, r1, route1 = step(s, "Ada apa aja?", catalog)
    assert route1 == "DIRECT"
    assert "laptop" in r1.lower()
    assert "desktop" in r1.lower()

    s, r2, route2 = step(s, "laptop deh", catalog)
    assert s["category"] == "laptop"

    s, r3, route3 = step(s, "Kata papa, yang bisa gambar", catalog)
    assert route3 == "OFFER"
    assert "AstraBook 15 Pro" in r3
    assert "desain" in r3.lower()
    assert "hanya ada laptop, desktop" not in r3.lower()

    s, r4, route4 = step(s, "Kata papa yang bisa bikin gambar", catalog)
    assert route4 == "OFFER"
    assert "AstraBook 15 Pro" in r4
    assert "hanya ada laptop, desktop" not in r4.lower()

def test_kasus_developer_dan_cocok_dan_refine(catalog):
    """
    Skenario pengujian developer dan keberatan performa:
    1. 'Mmm...papa sih kerja' -> OFFER (office)
    2. 'Papaku developer' -> OFFER (programming, BUKAN mengulang office!)
    3. 'Emang cocok buat developer?' -> SUITABILITY (menjelaskan kecocokan)
    4. 'Mana bisa' -> REFINE (menawarkan opsi lebih kuat, BUKAN Category Guard!)
    5. 'Ya gak kuatlah' -> REFINE (menawarkan opsi tertinggi)
    """
    s = new_state()
    s, r0, _ = step(s, "laptop", catalog)
    s, r1, route1 = step(s, "Mmm...papa sih kerja", catalog)
    assert route1 == "OFFER"
    assert "office" in r1.lower()

    s, r2, route2 = step(s, "Papaku developer", catalog)
    assert "programming" in r2.lower()
    assert "hanya ada laptop, desktop" not in r2.lower()

    s, r3, route3 = step(s, "Emang cocok buat developer?", catalog)
    assert route3 in ("SUITABILITY", "OFFER")
    assert "programming" in r3.lower() or "developer" in r3.lower()

    s, r4, route4 = step(s, "Mana bisa", catalog)
    assert route4 == "REFINE"
    assert "hanya ada laptop, desktop" not in r4.lower()

def test_kasus_beda_laptop_desktop_dan_info(catalog):
    """
    Skenario pengujian perbandingan kategori dan ketidaktahuan teknis:
    1. 'Apa bedanya laptop sama desktop?' -> COMPARE_CATEGORY
    2. 'Kl gak punya info gimana?' -> Bukan Category Guard
    """
    s = new_state()
    s, r1, route1 = step(s, "Apa bedanya laptop sama desktop?", catalog)
    assert route1 == "COMPARE_CATEGORY"
    assert "portabel" in r1.lower()
    assert "desktop" in r1.lower()
    assert "kencana office mini" not in r1.lower()

    s, r2, route2 = step(s, "Kl gak punya info gimana?", catalog)
    assert "hanya ada laptop, desktop, dan monitor" not in r2.lower()

def test_kasus_arsitek_dan_gemini_full_dialog(catalog):
    """
    Skenario pengujian lengkap dari percakapan pengguna (Arsitek -> Bandingkan -> Spek -> Refine -> Decision -> Gemini):
    1. 'Mamaku arsitek' -> Rekomendasi desain & rendering (AstraBook 15 Pro & Garuda Gaming G15)
    2. 'Yang cocok buat arsitek yang mana?' -> SUITABILITY menjelaskan kecocokan
    3. 'Mana yang bagus dari 2 itu?' -> COMPARE perbandingan kedua laptop
    4. 'Speknya gimana itu, Mbak?' -> PRODUCT_Q rincian spek
    5. 'Ada yang lebih bagus gak?' -> REFINE menyatakan Garuda Gaming G15 sudah tertinggi
    6. 'Cocok yang mana nih, Mbak? Ntar aku diomelin mama kalo salah pilih' -> DECISION_HELP panduan use-case
    7. 'Garansi berapa lama tuh?' -> UNAVAILABLE
    8. 'Tapi, mama sering pake gemini juga' -> PRODUCT_TOOL_SUPPORT konfirmasi lancar untuk Gemini
    """
    s = new_state()
    s["category"] = "laptop"
    s["persona"] = "family_elder"

    s, r1, route1 = step(s, "Mamaku arsitek", catalog)
    assert route1 == "OFFER"
    assert "AstraBook 15 Pro" in r1
    assert "Garuda Gaming G15" in r1

    s, r2, route2 = step(s, "Yang cocok buat arsitek yang mana?", catalog)
    assert route2 == "SUITABILITY"
    assert "AstraBook 15 Pro" in r2
    assert "Garuda Gaming G15" in r2

    s, r3, route3 = step(s, "Mana yang bagus dari 2 itu?", catalog)
    assert route3 == "COMPARE"
    assert "11.999.000" in r3
    assert "15.999.000" in r3

    s, r4, route4 = step(s, "Speknya gimana itu, Mbak?", catalog)
    assert route4 == "PRODUCT_Q"
    assert "KB-L02" in r4 or "AstraBook 15 Pro" in r4
    assert "KB-L05" in r4 or "Garuda Gaming G15" in r4

    s, r5, route5 = step(s, "Ada yang lebih bagus gak?", catalog)
    assert route5 == "REFINE"
    assert "paling tinggi" in r5.lower() or "garuda" in r5.lower()

    s, r6, route6 = step(s, "Cocok yang mana nih, Mbak? Ntar aku diomelin mama kalo salah pilih", catalog)
    assert route6 == "DECISION_HELP"
    assert "Mama" in r6
    assert "AstraBook 15 Pro" in r6
    assert "Garuda Gaming G15" in r6

    s, r7, route7 = step(s, "Garansi berapa lama tuh?", catalog)
    assert route7 == "UNAVAILABLE"
    assert "garansi" in r7.lower()

    s, r8, route8 = step(s, "Tapi, mama sering pake gemini juga", catalog)
    assert route8 == "PRODUCT_TOOL_SUPPORT"
    assert "Gemini" in r8
    assert "AstraBook 15 Pro" in r8 or "Garuda Gaming G15" in r8

def test_kasus_insinyur_dan_max_spec_clarify(catalog):
    """
    Skenario pengujian insinyur & keraguan spesifikasi tertinggi:
    1. 'Om ku orang kantoran' -> OFFER office (NusaTech Student 14 & AstraBook 14 Core)
    2. 'Keknya gak cocok deh. Om aku insinyur' -> OFFER teknik/desain/render (AstraBook 15 Pro & Garuda Gaming G15)
    3. 'Paling tinggi??' -> MAX_SPEC_CLARIFY mengklarifikasi Garuda Gaming G15 dan menawarkan opsi desktop Rajawali Creator
    4. 'Paing tingginya cuma segitu?' -> MAX_SPEC_CLARIFY
    5. 'Boleh juga tuh desktopnya' -> OFFER desktop (Rajawali Creator 18.999.000)
    """
    s = new_state()
    s["category"] = "laptop"

    s, r1, route1 = step(s, "Om ku orang kantoran", catalog)
    assert route1 == "OFFER"
    assert "NusaTech Student 14" in r1 or "AstraBook 14 Core" in r1

    s, r2, route2 = step(s, "Keknya gak cocok deh. Om aku insinyur", catalog)
    assert route2 == "OFFER"
    assert "AstraBook 15 Pro" in r2 or "Garuda Gaming G15" in r2
    assert "paling tinggi spesifikasinya di katalog laptop kami" not in r2.lower()

    s, r3, route3 = step(s, "Paling tinggi??", catalog)
    assert route3 == "MAX_SPEC_CLARIFY"
    assert "Garuda Gaming G15" in r3
    assert "Rajawali Creator" in r3

    s, r4, route4 = step(s, "Paing tingginya cuma segitu?", catalog)
    assert route4 == "MAX_SPEC_CLARIFY"
    assert "Garuda Gaming G15" in r4
    assert "Rajawali Creator" in r4

    s, r5, route5 = step(s, "Boleh juga tuh desktopnya", catalog)
    assert route5 == "OFFER"
    assert "Rajawali Creator" in r5
    assert "monitor tidak termasuk" in r5.lower()

def test_kasus_gpu_pertimbangan_dan_grafis_berat(catalog):
    """
    Skenario pengujian pertimbangan GPU dan beban grafis berat:
    1. 'Penggunaan gpu juga jadi pertimbangan penggunaan' -> GPU_GUIDANCE
    2. 'Grafis berat' -> OFFER (menyarankan laptop dengan dedicated GPU, BUKAN salah mengira berat fisik!)
    3. 'Kalau yang cuma buat ngetik ada?' -> OFFER (laptop hemat daya / iGPU)
    """
    s = new_state()
    s["category"] = "laptop"

    s, r1, route1 = step(s, "Penggunaan gpu juga jadi pertimbangan penggunaan", catalog)
    assert route1 == "GPU_GUIDANCE"
    assert "GPU Dedicated" in r1 or "dedicated" in r1.lower()
    assert "GPU Integrated" in r1 or "integrated" in r1.lower()

    s, r2, route2 = step(s, "Grafis berat", catalog)
    assert route2 == "OFFER"
    # Tidak boleh ada salah deteksi atribut fisik berat (UNAVAILABLE)
    assert "informasi berat belum tersedia" not in r2.lower()
    assert "hanya ada laptop, desktop" not in r2.lower()
    # Harus merekomendasikan produk dengan kartu grafis bertenaga
    assert any(code in s["offered_products"] for code in ["KB-L05", "KB-L02", "KB-L06", "KB-L07", "KB-L09"])

def test_kasus_acer_ngegame_dan_anti_ribet():
    """
    Skenario pengujian pertanyaan merek, 'ngegame', dan permintaan produk langsung (anti-ribet):
    1. 'Ada laptop acer gak?' -> ASK (langsung konfirmasi brand Acer dan tanya kebutuhan)
    2. 'Buat ngegame' -> OFFER (langsung tawarkan Acer Nitro V 15 tanpa tanya ulang!)
    3. 'mana?' -> OFFER (tetap tampilkan/pertahankan produk, tidak bertanya lagi)
    4. 'macem2' -> OFFER (memahami fleksibilitas game, tidak terjebak tanya ulang)
    """
    real_cat = Catalog.from_dummy()
    s = new_state()

    s, r1, route1 = step(s, "Ada laptop acer gak?", real_cat)
    assert route1 == "ASK"
    assert "Acer" in r1
    assert "Laptop Acer mau dipakai untuk apa" in r1 or "kebutuhan apa" in r1.lower()

    s, r2, route2 = step(s, "Buat ngegame", real_cat)
    assert route2 == "OFFER"
    assert "Acer Nitro V 15" in r2
    assert "RTX 2050" in r2 or "gaming" in r2.lower()
    # Tidak boleh ada perulangan pertanyaan "rencananya untuk kebutuhan apa"
    assert "rencananya untuk kebutuhan apa" not in r2.lower()

    s, r3, route3 = step(s, "mana?", real_cat)
    assert route3 == "OFFER"
    assert "Acer Nitro V 15" in r3

    s, r4, route4 = step(s, "macem2", real_cat)
    assert route4 == "OFFER"
    assert "Acer Nitro V 15" in r4

def test_kasus_ada_tipe_apa_asus():
    """
    Skenario pengujian pertanyaan tipe inventaris ('Ada tipe apa?'):
    1. 'Ada laptop asus gak?' -> ASK (konfirmasi brand Asus dan tanya kebutuhan)
    2. 'Ada tipe apa?' -> INVENTORY_LIST (langsung tampilkan seluruh tipe Asus tanpa tanya balik!)
    3. 'Aku tanya...ada tipe apa?' -> INVENTORY_LIST (tidak terjebak parroting / looping)
    4. 'Yang paling murah' -> OFFER (langsung filter Asus Vivobook 14)
    """
    real_cat = Catalog.from_dummy()
    s = new_state()

    s, r1, route1 = step(s, "Ada laptop asus gak?", real_cat)
    assert route1 == "ASK"
    assert "Asus" in r1

    s, r2, route2 = step(s, "Ada tipe apa?", real_cat)
    assert route2 == "INVENTORY_LIST"
    assert "ASUS Vivobook 14" in r2
    assert "ASUS TUF Gaming A15" in r2
    assert "pilihan tipe" in r2.lower()

    s, r3, route3 = step(s, "Aku tanya...ada tipe apa?", real_cat)
    assert route3 == "INVENTORY_LIST"
    assert "ASUS Vivobook 14" in r3

    s, r4, route4 = step(s, "Yang paling murah", real_cat)
    assert route4 == "OFFER"
    assert "ASUS Vivobook 14" in r4

def test_kasus_dek_jual_apa_dan_disuruh_cerita():
    """
    Skenario:
    1. 'Dek' -> Sekadar salam (DIRECT)
    2. 'Jual apa?' -> Menampilkan kategori toko langsung (DIRECT)
    3. 'Ditanya jual apa malah disuruh cerita' -> Permintaan maaf & daftar kategori (META_ALIGN)
    """
    real_cat = Catalog.from_dummy()
    s = new_state()

    s, r1, route1 = step(s, "Dek", real_cat)
    assert route1 == "DIRECT"
    assert "Halo, Kak" in r1

    s, r2, route2 = step(s, "Jual apa?", real_cat)
    assert route2 == "DIRECT"
    assert "laptop" in r2.lower()
    assert "desktop" in r2.lower()
    assert "printer" in r2.lower()

    s, r3, route3 = step(s, "Ditanya jual apa malah disuruh cerita", real_cat)
    assert route3 == "META_ALIGN"
    assert "maaf" in r3.lower()
    assert "laptop" in r3.lower()

def test_kasus_obrolan_awal_dengan_llm():
    """
    Skenario pengujian obrolan awal menggunakan LLM lokal:
    1. 'Tanya dong' -> LLM_OPENING (bukan pertanyaan kaku)
    2. 'Papa suruh cari laptop' -> LLM_OPENING
    """
    real_cat = Catalog.from_dummy()
    s = new_state()

    s, r1, route1 = step(s, "Tanya dong", real_cat, llm_model="gemma3:1b")
    assert route1 in ("AGENTIC", "FAST_AGENTIC", "ASK")
    assert len(r1) > 5

    s, r2, route2 = step(s, "Papa suruh cari laptop", real_cat, llm_model="gemma3:1b")
    assert route2 in ("AGENTIC", "FAST_AGENTIC", "ASK")
    assert len(r2) > 5
    assert s.get("category") == "laptop"
    assert s.get("persona_name") == "Papa"

def test_kasus_jual_acer_dan_cuma_1_itu():
    """
    Skenario pengujian pertanyaan merek Acer dan keraguan jumlah produk:
    1. 'Mbak' -> DIRECT (salam)
    2. 'Jual acer gak?' -> INVENTORY_LIST (tampilkan 2 tipe Acer, bukan kategori out-of-catalog guard)
    3. 'Cuma 1 itu/' -> ALTERNATIVE_SUGGEST (tidak terjebak parrot loop, tawarkan alternatif)
    """
    real_cat = Catalog.from_dummy()
    s = new_state()

    s, r1, route1 = step(s, "Mbak", real_cat)
    assert route1 == "DIRECT"

    s, r2, route2 = step(s, "Jual acer gak?", real_cat)
    assert route2 == "INVENTORY_LIST"
    assert "Acer Aspire Lite 14" in r2
    assert "Acer Nitro V 15" in r2

    s, r3, route3 = step(s, "Cuma 1 itu/", real_cat)
    assert route3 == "ALTERNATIVE_SUGGEST"
    assert "Acer Aspire Lite 14" in r3
    assert "Acer Nitro V 15" in r3

def test_kasus_intel_nvidia_dan_core_i7():
    """
    Skenario pengujian pertanyaan spesifikasi hardware (Intel + Nvidia, Core i7) & retensi konteks:
    1. 'ada asus?' -> 'laptop' -> INVENTORY_LIST (ASUS)
    2. 'Gak ada intel yang pake nvidia?' -> PRODUCT_Q (bukan CATEGORY_GUARD!)
    3. 'Ya laptoplah maksudnya' -> INVENTORY_LIST (ASUS, suffix -lah diparsing)
    4. 'Kan bahas asus' -> INVENTORY_LIST (ASUS)
    5. 'Kalo acer ada?' -> INVENTORY_LIST (Acer)
    6. 'Gak ada yang core i7?' -> PRODUCT_Q (bukan CATEGORY_GUARD, jelaskan Acer Core i5 & rekomendasikan Legion Core i7)
    """
    real_cat = Catalog.from_dummy()
    s = new_state()

    s, _, _ = step(s, "ada asus?", real_cat)
    s, r2, route2 = step(s, "laptop", real_cat)
    assert route2 == "INVENTORY_LIST"
    assert "ASUS Vivobook" in r2

    # Query kombinasi hardware Intel + Nvidia pada konteks ASUS
    s, r3, route3 = step(s, "Gak ada intel yang pake nvidia?", real_cat)
    assert route3 == "PRODUCT_Q"
    assert "CATEGORY_GUARD" not in route3
    assert "Acer Nitro V 15" in r3
    assert "Lenovo LOQ 15" in r3

    # Penegasan kategori dengan akhiran -lah
    s, r4, route4 = step(s, "Ya laptoplah maksudnya", real_cat)
    assert route4 == "INVENTORY_LIST"
    assert "ASUS" in r4

    # Penegasan merek 'Kan bahas asus'
    s, r5, route5 = step(s, "Kan bahas asus", real_cat)
    assert route5 == "INVENTORY_LIST"
    assert "ASUS Vivobook" in r5

    # Pindah merek ke Acer
    s, r6, route6 = step(s, "Kalo acer ada?", real_cat)
    assert route6 == "INVENTORY_LIST"
    assert "Acer Nitro V 15" in r6

    # Pertanyaan spesifikasi prosesor Core i7 pada konteks Acer
    s, r7, route7 = step(s, "Gak ada yang core i7?", real_cat)
    assert route7 == "PRODUCT_Q"
    assert "CATEGORY_GUARD" not in route7
    assert "Core i7" in r7 or "core i7" in r7
    assert "Lenovo Legion Pro 5 16" in r7


def test_kasus_desktop_monitor_termasuk(catalog):
    """
    Skenario: Setelah melihat daftar desktop Lenovo, pelanggan bertanya
    'Termasuk monitor gak?' — harus dijawab dengan info bundling, bukan CATEGORY_GUARD.
    """
    s = new_state()
    s, _, _ = step(s, "Ada lenovo?", catalog)
    s, _, _ = step(s, "Kalo desktop", catalog)
    
    # Pertanyaan bundling — tidak boleh jadi CATEGORY_GUARD
    s, r, route = step(s, "Termasuk monitor gak?", catalog)
    assert route == "BUNDLE_Q", f"Seharusnya BUNDLE_Q, dapat: {route}"
    assert "monitor tidak termasuk" in r.lower() or "monitor" in r.lower()
    # Kategori tidak boleh berubah ke "monitor"
    assert s.get("category") != "monitor"


def test_kasus_desktop_monitor_termasuk_variant(catalog):
    """
    Skenario: Variasi pertanyaan 'Monitornya termasuk gak?' — tetap harus BUNDLE_Q.
    """
    s = new_state()
    s["category"] = "desktop"
    s, _, _ = step(s, "Ada desktop apa aja?", catalog)
    
    s, r, route = step(s, "Monitornya termasuk gak?", catalog)
    assert route == "BUNDLE_Q", f"Seharusnya BUNDLE_Q, dapat: {route}"
    assert "monitor" in r.lower()


def test_bundle_question_laptop_context(catalog):
    """
    Skenario: 'Termasuk monitor gak?' dalam konteks laptop — jawab bahwa layar sudah built-in.
    """
    s = new_state()
    s, _, _ = step(s, "Ada laptop acer?", catalog)
    
    s, r, route = step(s, "Termasuk monitor gak?", catalog)
    assert route == "BUNDLE_Q", f"Seharusnya BUNDLE_Q, dapat: {route}"
    assert "laptop" in r.lower() or "layar" in r.lower() or "terintegrasi" in r.lower() or "monitor" in r.lower()


def test_kasus_lenovo_desktop_monitor_full_dialogue():
    """
    Skenario: Dialog lengkap persis seperti keluhan pengguna di terminal:
    Anda: Ada lenovo?
    CS: Ada, Kak! Untuk merek Lenovo kami menyediakan perangkat desktop dan laptop...
    Anda: Kalo desktop
    CS: Untuk desktop Lenovo, di katalog Bobby Computer ada 2 pilihan tipe: ...
    Anda: Termasuk monitor gak?
    CS: (Harus menjelaskan monitor tidak termasuk, BUKAN category guard!)
    Anda: Maksudnya desktop termasuk monitor gak?
    CS: (Harus menjawab soal monitor, BUKAN mengulang daftar inventaris!)
    """
    real_cat = Catalog.from_dummy()
    s = new_state()
    s, r1, route1 = step(s, "Ada lenovo?", real_cat)
    assert route1 == "ASK"
    assert "Lenovo" in r1 or "lenovo" in r1.lower()

    s, r2, route2 = step(s, "Kalo desktop", real_cat)
    assert route2 == "INVENTORY_LIST"
    assert "Lenovo IdeaCentre" in r2 or "Lenovo LOQ Tower" in r2

    # Turn 3: Termasuk monitor gak?
    s, r3, route3 = step(s, "Termasuk monitor gak?", real_cat)
    assert route3 == "BUNDLE_Q", f"Turn 3 route seharusnya BUNDLE_Q, dapat: {route3}"
    assert "CATEGORY_GUARD" not in route3
    assert "monitor" in r3.lower()
    assert "tidak termasuk" in r3.lower() or "belum termasuk" in r3.lower()

    # Turn 4: Maksudnya desktop termasuk monitor gak?
    s, r4, route4 = step(s, "Maksudnya desktop termasuk monitor gak?", real_cat)
    assert route4 == "BUNDLE_Q", f"Turn 4 route seharusnya BUNDLE_Q, dapat: {route4}"
    assert route4 != "INVENTORY_LIST", "Turn 4 tidak boleh mengulang daftar tipe desktop!"
    assert "CATEGORY_GUARD" not in route4
    assert "monitor" in r4.lower()


def test_kasus_itu_desktop_dan_loq_itu_desktop():
    """
    Skenario verifikasi kegagalan pengguna terbaru:
    Anda: halo
    Anda: ada lenovo
    Anda: desktop aja deh
    CS: (menampilkan Lenovo IdeaCentre Mini 01 & Lenovo LOQ Tower 17)
    Anda: Itu desktop?
    CS: (Harus konfirmasi bahwa kedua pilihan adalah desktop, BUKAN mengulang daftar inventaris!)
    Anda: Loq itu desktop?
    CS: (Harus menjelaskan LOQ Tower 17 adalah desktop, ada juga varian laptop LOQ 15, BUKAN mengulang daftar!)
    """
    real_cat = Catalog.from_dummy()
    s = new_state()
    s, _, _ = step(s, "halo", real_cat)
    s, _, _ = step(s, "ada lenovo", real_cat)
    s, r_list, route_list = step(s, "desktop aja deh", real_cat)
    assert route_list in ("AGENTIC", "FAST_AGENTIC", "INVENTORY_LIST")
    assert "Lenovo LOQ Tower 17" in r_list

    # Turn: Itu desktop?
    s, r_itu, route_itu = step(s, "Itu desktop?", real_cat)
    assert route_itu == "CATEGORY_CONFIRM"
    assert route_itu != "INVENTORY_LIST", "Tidak boleh mengulang INVENTORY_LIST!"
    assert "desktop" in r_itu.lower()

    # Turn: Loq itu desktop?
    s, r_loq, route_loq = step(s, "Loq itu desktop?", real_cat)
    assert route_loq == "CATEGORY_CONFIRM"
    assert route_loq != "INVENTORY_LIST", "Tidak boleh mengulang INVENTORY_LIST!"
    assert "LOQ Tower" in r_loq or "loq tower" in r_loq.lower()
    assert "LOQ 15" in r_loq or "laptop" in r_loq.lower()


def test_kasus_gpu_minimal_6gb_vram():
    """
    Skenario:
    Pelanggan sedang membahas Acer Nitro V 15 (GPU RTX 2050 4 GB).
    Pelanggan mengeluh 'Tanggung banget 4 gb'.
    Pelanggan bertanya 'Yang gpu minimal 6 gb ada apa aja?'.
    Sistem harus menjelaskan bahwa Acer hanya punya 4 GB, dan memberikan rekomendasi laptop merek lain
    dengan GPU minimal 6 GB (ASUS Vivobook Pro 15 RTX 3050 6GB, Lenovo LOQ RTX 4050 6GB, ASUS TUF RTX 4060 8GB).
    Sistem TIDAK BOLEH mengulang daftar Acer Aspire Lite & Nitro V 15!
    """
    real_cat = Catalog.from_dummy()
    s = new_state()
    s, _, _ = step(s, "jual laptop?", real_cat)
    s, r_acer, route_acer = step(s, "Ada acer?", real_cat)
    assert route_acer in ("AGENTIC", "FAST_AGENTIC", "INVENTORY_LIST")
    assert "Acer Nitro V 15" in r_acer

    s, _, _ = step(s, "GPU?", real_cat)
    s, _, _ = step(s, "Spek lengkap deh", real_cat)

    # Turn: Yang gpu minimal 6 gb ada apa aja?
    s, r_vram, route_vram = step(s, "Yang gpu minimal 6 gb ada apa aja?", real_cat)
    assert route_vram == "PRODUCT_Q"
    assert route_vram != "INVENTORY_LIST", "Tidak boleh mengulang INVENTORY_LIST Acer!"
    assert "Acer Nitro V 15" in r_vram or "Acer" in r_vram
    assert "6 GB" in r_vram or "6 gb" in r_vram.lower()
    assert "ASUS Vivobook Pro 15 OLED" in r_vram or "Lenovo LOQ 15" in r_vram

    # Turn: Gpu minimal 6 gb ada apa aja (tanpa 'yang')
    s, r_vram2, route_vram2 = step(s, "Gpu minimal 6 gb ada apa aja", real_cat)
    assert route_vram2 == "PRODUCT_Q"
    assert "ASUS Vivobook Pro 15 OLED" in r_vram2 or "Lenovo LOQ 15" in r_vram2


def test_kasus_pc_mini_dan_nitro_objection():
    """
    Skenario Percakapan Nyata Terminal:
    1. Tanya 'Ada pc mini gak?' -> konfirmasi/penawaran Lenovo IdeaCentre Mini 01.
    2. 'Itu doang?' -> konfirmasi hanya 1 PC mini dan menawarkan opsi desktop tower lain.
    3. 'Lah...itu doang mini pc nya?' -> konsisten menjelaskan varian mini PC cuma 1.
    4. 'Gak pake gpu?' -> menjelaskan GPU terintegrasi (Intel UHD) & menawarkan desktop dengan GPU dedicated.
    5. 'Ada nitro gak?' -> detail Acer Nitro V 15.
    6. 'Tanggung banget' -> empati atas spesifikasi Nitro V 15 (RTX 2050) & merekomendasikan opsi GPU >= 6 GB.
    7. 'Lah..kan lagi bahas si nitro. Malah yang lain' -> CS kembali fokus ke Nitro V 15.
    """
    real_cat = Catalog.from_dummy()
    s = new_state()
    s, r_halo, route_halo = step(s, "Halo", real_cat)
    s, r_jual, route_jual = step(s, "jual apa?", real_cat)
    
    s, r_mini, route_mini = step(s, "Ada pc mini gak?", real_cat)
    assert "IdeaCentre Mini" in r_mini
    assert s.get("selected_product") == "KB-D01"
    assert "KB-D01" in s.get("offered_products", [])
    
    s, r_doang, route_doang = step(s, "Itu doang?", real_cat)
    assert route_doang in ("AGENTIC", "FAST_AGENTIC", "DIRECT")
    assert "1 tipe" in r_doang or "satu" in r_doang.lower()
    assert "IdeaCentre Mini" in r_doang
    assert "ExpertCenter" in r_doang or "LOQ Tower" in r_doang
    
    s, r_doang2, route_doang2 = step(s, "Lah...itu doang mini pc nya?", real_cat)
    assert route_doang2 in ("AGENTIC", "FAST_AGENTIC", "DIRECT")
    assert "IdeaCentre Mini" in r_doang2
    
    s, r_gpu, route_gpu = step(s, "Gak pake gpu?", real_cat)
    assert route_gpu == "PRODUCT_Q"
    assert "terintegrasi" in r_gpu.lower() or "intel uhd" in r_gpu.lower()
    assert "dedicated" in r_gpu.lower() or "terpisah" in r_gpu.lower()
    
    s, r_nitro, route_nitro = step(s, "Ada nitro gak?", real_cat)
    assert route_nitro == "SELECT"
    assert "Acer Nitro V 15" in r_nitro
    assert s.get("selected_product") == "KB-L06"
    assert "KB-L06" in s.get("offered_products", [])
    
    s, r_tanggung, route_tanggung = step(s, "Tanggung banget", real_cat)
    assert route_tanggung == "PRODUCT_Q"
    assert "tanggung" in r_tanggung.lower()
    assert "Vivobook Pro 15" in r_tanggung or "LOQ 15" in r_tanggung or "TUF Gaming" in r_tanggung
    
    s, r_fokus, route_fokus = step(s, "Lah..kan lagi bahas si nitro. Malah yang lain", real_cat)
    assert route_fokus == "PRODUCT_FOCUS"
    assert "Acer Nitro V 15" in r_fokus
    assert "fokus" in r_fokus.lower()

def test_kasus_laptop_mama_dan_negasi_aktivitas():
    """
    Skenario percakapan pengguna dari terminal (Kasus Mama & Negasi Aktivitas):
    1. 'Ada laptop?' -> ASK (Tanya kebutuhan)
    2. 'di mana?' -> UNAVAILABLE (Info operasional toko online, bukan blind spread)
    3. 'Buat Mama sih' -> ASK (Klarifikasi persona Mama)
    4. 'Mamaku gak kerja' -> OFFER (Laptop harian santai: Acer Aspire Lite 14 & Lenovo IdeaPad Slim 3 14)
    5. 'Mamaku bukan anak sekolah' -> PERSONA_ALIGN (Selaras dengan laptop santai untuk orang tua)
    6. 'Kan mama yang butuh?' -> PERSONA_ALIGN (Penegasan persona Mama dengan opsi santai)
    """
    real_cat = Catalog.from_dummy()
    s = new_state()

    s, r1, route1 = step(s, "Ada laptop?", real_cat, llm_model="gemma3:1b")
    assert route1 == "ASK"
    assert "laptop" in r1.lower()

    s, r2, route2 = step(s, "di mana?", real_cat, llm_model="gemma3:1b")
    assert route2 == "UNAVAILABLE"
    assert "toko" in r2.lower() or "online" in r2.lower()

    s, r3, route3 = step(s, "Buat Mama sih", real_cat, llm_model="gemma3:1b")
    assert route3 == "ASK"
    assert "Mama" in r3

    s, r4, route4 = step(s, "Mamaku gak kerja", real_cat, llm_model="gemma3:1b")
    assert route4 == "OFFER"
    assert "Acer Aspire Lite 14" in r4
    assert "Lenovo IdeaPad Slim 3 14" in r4
    assert s.get("persona_name") == "Mama"

    s, r5, route5 = step(s, "Mamaku bukan anak sekolah", real_cat, llm_model="gemma3:1b")
    assert route5 == "PERSONA_ALIGN"
    assert "Acer Aspire Lite 14" in r5
    assert "Lenovo IdeaPad Slim 3 14" in r5

    s, r6, route6 = step(s, "Kan mama yang butuh?", real_cat, llm_model="gemma3:1b")
    assert route6 == "PERSONA_ALIGN"
    assert "Mama" in r6
    assert "Acer Aspire Lite 14" in r6 or "Lenovo" in r6


def test_kasus_acer_mama_nonton_nitro_kegedean():
    """
    Skenario percakapan nyata dari terminal:
    1. 'Jual laptop acer?' -> ASK (tanya kebutuhan)
    2. 'untuk mama sih' -> ASK (klarifikasi persona Mama)
    3. 'Paling untuk nonton' -> OFFER (menawarkan Acer Aspire Lite 14 & Acer Nitro V 15)
    4. 'Nitro kegedean' -> SIZE_OBJECTION (menolak Nitro karena bobot/layar besar, memilih Aspire Lite 14)
    5. 'Apa rekomendasimu?' -> RECOMMENDATION (rekomendasi definitif berbasis use-case Mama/nonton)
    6. 'Kan buat nonton?' -> NEED_INSIST (penegasan kebutuhan nonton santai, tidak tertipu daily tools 'aplikasi tersebut')
    7. 'Nitro kegedean kalo cuma buat nonton' -> SIZE_OBJECTION (konsisten memilih Aspire Lite 14)
    8. 'Mama cuma nonton doang, gak main game' -> NEED_ALIGN (bukan salah paham keraguan jumlah katalog, coret laptop gaming)
    """
    real_cat = Catalog.from_dummy()
    s = new_state()

    s, r1, route1 = step(s, "Jual laptop acer?", real_cat, llm_model="llama3-groq-tool-use:8b")
    assert route1 == "ASK"
    assert "Acer" in r1 or "acer" in r1.lower()

    s, r2, route2 = step(s, "untuk mama sih", real_cat, llm_model="llama3-groq-tool-use:8b")
    assert route2 == "ASK"
    assert "Mama" in r2
    assert s.get("persona_name") == "Mama"

    s, r3, route3 = step(s, "Paling untuk nonton", real_cat, llm_model="llama3-groq-tool-use:8b")
    assert route3 == "OFFER"
    assert "Acer Aspire Lite 14" in r3
    assert "Acer Nitro V 15" in r3
    assert set(s.get("offered_products", [])) == {"KB-L01", "KB-L06"}

    # Turn 4: Nitro kegedean
    s, r4, route4 = step(s, "Nitro kegedean", real_cat, llm_model="llama3-groq-tool-use:8b")
    assert route4 == "SIZE_OBJECTION"
    assert "Acer Aspire Lite 14" in r4
    assert s.get("selected_product") == "KB-L01"
    assert s.get("offered_products") == ["KB-L01"]
    # Tidak boleh menyemburkan ringkasan spek Nitro
    assert "Prosesor: Intel Core i5-13420H" not in r4

    # Turn 5: Apa rekomendasimu?
    s, r5, route5 = step(s, "Apa rekomendasimu?", real_cat, llm_model="llama3-groq-tool-use:8b")
    assert route5 == "RECOMMENDATION"
    assert "Acer Aspire Lite 14" in r5
    assert "rekomendasi" in r5.lower()
    # Tidak boleh amnesia bertanya 'mencari laptop untuk apa'
    assert "mau dipakai untuk apa" not in r5.lower()
    assert "sedang dicari" not in r5.lower()

    # Turn 6: Kan buat nonton?
    s, r6, route6 = step(s, "Kan buat nonton?", real_cat, llm_model="llama3-groq-tool-use:8b")
    assert route6 == "NEED_INSIST"
    assert "Acer Aspire Lite 14" in r6
    # Tidak boleh looping parrot 'aplikasi tersebut'
    assert "aplikasi tersebut" not in r6.lower()

    # Turn 7: Nitro kegedean kalo cuma buat nonton
    s, r7, route7 = step(s, "Nitro kegedean kalo cuma buat nonton", real_cat, llm_model="llama3-groq-tool-use:8b")
    assert route7 == "SIZE_OBJECTION"
    assert "Acer Aspire Lite 14" in r7
    assert s.get("selected_product") == "KB-L01"

    # Turn 8: Mama cuma nonton doang, gak main game
    s, r8, route8 = step(s, "Mama cuma nonton doang, gak main game", real_cat, llm_model="llama3-groq-tool-use:8b")
    assert route8 == "NEED_ALIGN"
    assert "Acer Aspire Lite 14" in r8
    # DILARANG KERAS memicu keraguan jumlah katalog ('Tentu tidak cuma satu Kak')
    assert "tentu tidak cuma satu" not in r8.lower()
    assert "tidak cuma satu" not in r8.lower()


def test_kasus_negasi_ryzen_konstruksi():
    """
    Skenario Nyata Screenshot 4:
    Turn 1: 'Kata papa, yang bisa dipake ngitung konstruksi'
    Turn 2: 'Beliau gak mau kalo Ryzen'
    Verifikasi:
    - CS TIDAK BOLEH merekomendasikan laptop AMD Ryzen!
    - CS harus mengenali persona 'Papa' dari kata 'Beliau'.
    - CS harus mengalihkan rekomendasi ke laptop bertenaga Intel Core yang cocok untuk konstruksi/grafis.
    - Route harus SPEC_NEGATION.
    """
    from services.catalog_service import reload_catalog
    real_cat = reload_catalog()
    s = new_state()

    # Turn 1
    s, r1, route1 = step(s, "Kata papa, yang bisa dipake ngitung konstruksi", real_cat)
    assert route1 == "OFFER"
    assert s.get("persona_name") == "Papa"

    # Turn 2: Negasi vendor Ryzen
    s, r2, route2 = step(s, "Beliau gak mau kalo Ryzen", real_cat)
    assert route2 == "SPEC_NEGATION"
    assert "Papa" in r2
    assert "Intel Core" in r2
    assert "AMD Ryzen" in r2  # Menyebutkan bahwa AMD Ryzen dihindari/dialihkan

    # Verifikasi seluruh produk yang ditawarkan murni Intel Core!
    offered_codes = s.get("offered_products", [])
    assert len(offered_codes) > 0
    for code in offered_codes:
        prod = real_cat.by_code[code]
        assert prod["cpu_vendor"] == "intel", f"Produk {prod['nama']} bukan Intel!"
        assert "ryzen" not in prod["cpu"].lower(), f"Produk {prod['nama']} adalah Ryzen!"


def test_kasus_asus_info_ram_dan_itu_semua_untuk_kantoran():
    """
    Sesi chatlog pengguna Telegram:
    Turn 1: 'Laptop asus ada?' -> ASK
    Turn 2: 'Untuk kerja' -> OFFER (menawarkan ASUS Vivobook 14, Vivobook Pro 15, TUF Gaming A15)
    Turn 3: 'Kok gak ada info ramnya berapa?' -> PRODUCT_Q (fokus jawab spesifikasi RAM tiap produk, bukan re-offer)
    Turn 4: 'Itu semua untuk kantoran?' -> SUITABILITY (klarifikasi peruntukan: kantor murni vs performa grafis/RTX)
    """
    from services.catalog_service import reload_catalog
    real_cat = reload_catalog()
    s = new_state()

    # Turn 1
    s, r1, route1 = step(s, "Laptop asus ada?", real_cat)
    assert route1 == "ASK"
    assert s.get("constraints", {}).get("brand") == "asus"

    # Turn 2
    s, r2, route2 = step(s, "Untuk kerja", real_cat)
    assert route2 == "OFFER"
    assert len(s.get("offered_products", [])) == 3
    assert "KB-L03" in s["offered_products"]
    assert "KB-L07" in s["offered_products"]
    assert "KB-L09" in s["offered_products"]

    # Turn 3: Pertanyaan RAM - harus fokus menjawab spesifikasi RAM tanpa re-offer
    s, r3, route3 = step(s, "Kok gak ada info ramnya berapa?", real_cat)
    assert route3 == "PRODUCT_Q"
    assert "RAM" in r3
    assert "16 GB" in r3
    assert "ASUS Vivobook 14" in r3

    # Turn 4: 'Itu semua untuk kantoran?' - harus mengevaluasi kecocokan 3 laptop yang sedang dibahas
    s, r4, route4 = step(s, "Itu semua untuk kantoran?", real_cat)
    assert route4 == "SUITABILITY"
    assert "ASUS Vivobook 14" in r4
    assert "ASUS TUF Gaming A15" in r4
    assert "kantor" in r4.lower()
    assert "rtx" in r4.lower() or "grafis" in r4.lower()


def test_kasus_telegram_laptop_ke_printer_flow():
    """
    Skenario pengujian alur percakapan Telegram pengguna riil (Turn 44-53):
    1. 'Nitro cocok gak buat desain?' -> SUITABILITY / SELECT (Acer Nitro V 15)
    2. 'Ukuran layar berapa?' -> PRODUCT_Q (15,6 inci FHD 144 Hz)
    3. 'Merek lain yang setara apa?' -> Rekomendasi Lenovo LOQ 15
    4. 'Lebih mahal ya?' -> COMPARE (membandingkan LOQ 15 Rp14,7jt vs Nitro V 15 Rp12,9jt, RTX 4050 vs RTX 2050)
    5. 'Kalo printer?' -> OFFER (Reset vendor intel & brand acer, tampilkan printer tanpa bocor 'intel')
    6. 'Harga di bawah 1 juta, pilihannya apa aja?' -> OFFER (Canon PIXMA TS207 Rp699rb, bukan paradoks EMPTY!)
    7. 'Pilihan lain ada?' -> MORE (Menjelaskan TS207 satu-satunya <1jt, opsi naik budget ke Epson L121 & L3210)
    8. 'Maksudku selain tipe ini' -> MORE (Konsisten upsell printer)
    9. 'Printer tipe lain' -> MORE (Konsisten upsell printer)
    """
    real_cat = Catalog.from_dummy()
    s = new_state()
    s["category"] = "laptop"

    # Turn 1: Nitro cocok gak buat desain?
    s, r1, route1 = step(s, "Nitro cocok gak buat desain?", real_cat)
    assert "Acer Nitro V 15" in r1

    # Turn 2: Ukuran layar berapa?
    s, r2, route2 = step(s, "Ukuran layar berapa?", real_cat)
    assert route2 == "PRODUCT_Q"
    assert "15,6" in r2

    # Turn 3: Set history seolah bot merekomendasikan Lenovo LOQ 15
    s["selected_product"] = "KB-L06"  # Acer Nitro V 15
    s["history"].append(("user", "Merek lain yang setara apa?"))
    s["history"].append((
        "assistant",
        "Untuk kebutuhan desain, dari pilihan di atas yang paling pas adalah **Lenovo LOQ 15** (Harga Rp14.799.000). "
        "Laptop ini ditenagai Intel Core i5-12450HX, RAM 16 GB DDR5, GPU NVIDIA GeForce RTX 4050 6 GB."
    ))

    # Turn 4: Lebih mahal ya? -> Harus COMPARE, bukan REFINE
    s, r4, route4 = step(s, "Lebih mahal ya?", real_cat)
    assert route4 == "COMPARE"
    assert "Lenovo LOQ 15" in r4
    assert "Acer Nitro V 15" in r4
    assert "1.800.000" in r4
    assert "RTX 4050" in r4

    # Turn 5: Kalo printer? -> Harus reset vendor & brand
    s, r5, route5 = step(s, "Kalo printer?", real_cat)
    assert s["category"] == "printer"
    assert s["constraints"]["vendor"] is None
    assert s["constraints"]["brand"] is None
    assert "intel" not in r5.lower()
    assert "Canon PIXMA TS207" in r5

    # Turn 6: Harga di bawah 1 juta, pilihannya apa aja? -> Canon TS207 Rp699rb harus ditemukan!
    s, r6, route6 = step(s, "Harga di bawah 1 juta, pilihannya apa aja?", real_cat)
    assert "Canon PIXMA TS207" in r6
    assert "699.000" in r6
    # Tidak boleh ada paradoks 'belum ada yang di bawah 1 juta' dan tidak boleh sebut 'laptop'
    assert "belum ada yang di bawah" not in r6.lower()
    assert "laptop" not in r6.lower()

    # Turn 7: Pilihan lain ada? -> Upsell ke printer di atas 1 juta
    s, r7, route7 = step(s, "Pilihan lain ada?", real_cat)
    assert route7 == "MORE"
    assert "Canon PIXMA TS207" in r7
    assert "Epson EcoTank L121" in r7 or "Epson EcoTank L3210" in r7

    # Turn 8: Maksudku selain tipe ini -> Konsisten
    s, r8, route8 = step(s, "Maksudku selain tipe ini", real_cat)
    assert route8 == "MORE"
    assert "Epson EcoTank L121" in r8 or "Epson EcoTank L3210" in r8

    # Turn 9: Printer tipe lain -> Konsisten
    s, r9, route9 = step(s, "Printer tipe lain", real_cat)
    assert route9 == "MORE"
    assert "Epson EcoTank L121" in r9 or "Epson EcoTank L3210" in r9
















