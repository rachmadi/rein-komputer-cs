# -*- coding: utf-8 -*-
"""
Uji Percakapan Multi-Giliran Berbasis Rubrik Customer Care Bobby Computer
Rubrik Evaluasi (5 Poin):
1. Menjawab apa yang ditanyakan (relevan & natural).
2. Bertanya saat kebutuhan belum ada (kategori-saja tidak langsung menyodorkan daftar produk).
3. Tidak mengulang daftar produk secara kaku (anti-parrot pada giliran lanjutan).
4. Tidak ada kode internal (P03, P05, P15, dsb.) di seluruh teks jawaban pelanggan.
5. Tidak ada tanda ✅ salah (centang hanya jika ada syarat diperiksa dan semuanya terpenuhi).
"""
import re
import pytest
from services.chat_service import process_chat_message, reset_chat_session
from services.agentic_tool_engine import run_agentic_tool, format_conversational_frame
from core.catalog import Catalog


def verify_rubric_invariants(reply: str):
    """Verifikasi invarian universal untuk seluruh respons percakapan Customer Care."""
    # 4. Tidak ada kode internal (P03, P05, M01, G02, dsb.)
    internal_codes = re.findall(r"\b(?:P\d{2}|M\d{2}|G0[1-4])\b", reply)
    assert not internal_codes, f"Ditemukan kode internal dalam jawaban pelanggan: {internal_codes} | Reply: {reply}"

    # Spesifikasi tidak boleh mengandung string literal 'None'
    assert "None" not in reply, f"Ditemukan string literal 'None' dalam spesifikasi: {reply}"

    # Larangan nama kolom teknis di teks pelanggan
    raw_columns = ["ram_gb", "vram_gb", "cpu_tier", "storage_ssd_gb", "gpu_dedicated"]
    for col in raw_columns:
        assert col not in reply.lower(), f"Ditemukan nama kolom teknis '{col}' dalam jawaban pelanggan:\n{reply}"

    # Larangan klaim tanpa dasar
    assert "bergaransi resmi" not in reply.lower(), "Klaim tanpa dasar 'bergaransi resmi' dilarang"
    assert "siap pakai" not in reply.lower(), "Klaim tanpa dasar 'siap pakai' dilarang"

    # Larangan duplikasi kalimat berurutan
    lines = [l.strip() for l in reply.split("\n") if l.strip()]
    for i in range(len(lines) - 1):
        assert lines[i] != lines[i + 1], f"Ditemukan duplikasi baris berurutan: '{lines[i]}'"



def test_rubric_percakapan_1_sapaan():
    """
    Percakapan 1: 'halo'
    Rubrik:
    - Menjawab sapaan dengan ramah
    - Bertanya apa yang sedang dicari
    - Tidak menyodorkan daftar produk
    - Tidak ada tanda ✅
    - Tidak ada kode internal
    """
    sid = "rubric_test_sapaan"
    reset_chat_session(sid)
    res = process_chat_message(sid, "halo")

    reply = res["reply"]
    verify_rubric_invariants(reply)

    assert res["route"] == "GREETING"
    assert len(res.get("products", [])) == 0, "Sapaan tidak boleh menampilkan produk"
    assert "✅" not in reply, "Sapaan tidak boleh memuat tanda centang ✅"
    # Menjawab sapaan dan ramah
    assert any(k in reply.lower() for k in ["halo", "selamat datang", "bobby computer"])
    assert any(k in reply.lower() for k in ["laptop", "pc", "desktop", "bantu", "cari"])


def test_rubric_percakapan_2_kategori_saja():
    """
    Percakapan 2: 'laptop'
    Rubrik:
    - Bertanya saat kebutuhan belum ada: menanyakan peruntukan dan anggaran
    - TIDAK menyodorkan daftar produk
    - TIDAK ada tanda ✅
    - Tidak ada kode internal
    """
    sid = "rubric_test_kategori_saja"
    reset_chat_session(sid)
    res = process_chat_message(sid, "laptop")

    reply = res["reply"]
    verify_rubric_invariants(reply)

    assert res["route"] == "CLARIFY_CATEGORY"
    assert len(res.get("products", [])) == 0, "Kategori-saja DILARANG menampilkan daftar produk"
    assert "✅" not in reply, "Kategori-saja DILARANG menampilkan tanda ✅"
    # Bertanya kebutuhan & budget
    low = reply.lower()
    assert any(k in low for k in ["kebutuhan", "aktivitas", "digunakan", "kerja", "kuliah"])
    assert any(k in low for k in ["anggaran", "budget", "biaya"])


def test_rubric_percakapan_3_multiturn_lengkap():
    """
    Percakapan 3 (Multi-turn dari tangkapan layar):
    Turn 1: 'laptop buat edit video 4k' -> Legion Pro 5 ✅, yang lain dilarang ✅
    Turn 2: 'cuma itu?' -> Penjelasan kontekstual dari state, tawarkan pelonggaran spek/budget, no repeat list
    Turn 3: 'Dari mana kamu tahu kebutuhanku?' -> Jawab jujur belum tahu kebutuhan + tanya ramah
    """
    sid = "rubric_test_multiturn_flow"
    reset_chat_session(sid)
    from services.catalog_service import reload_catalog
    reload_catalog()

    # === TURN 1: Kebutuhan Jelas 'laptop buat edit video 4k' ===
    t1 = process_chat_message(sid, "laptop buat edit video 4k")
    rep1 = t1["reply"]
    verify_rubric_invariants(rep1)

    assert t1["route"] == "FAST_AGENTIC"
    assert len(t1.get("products", [])) > 0, "Harus menyajikan rekomendasi produk"
    assert "✅" in rep1, "Produk yang lolos wajib diberi tanda ✅"
    # Hanya Legion Pro 5 yang ✅
    kodes_1 = [p["kode"] for p in t1["products"]]
    assert "KB-L10" in kodes_1, "Legion Pro 5 (KB-L10) harus menjadi rekomendasi"
    # TUF (KB-L09), Vivobook (KB-L07), Nitro (KB-L06) dilarang ✅
    for blocked_name in ["TUF", "Vivobook", "Nitro", "Aspire"]:
        if blocked_name in rep1:
            segment_before = rep1.split(blocked_name)[0].split("\n")[-1]
            assert "✅" not in segment_before, f"{blocked_name} dilarang berlabel ✅"

    # Pembingkaian ramah (1-2 kalimat pembuka & penutup)
    assert any(k in rep1.lower() for k in ["rekomendasi", "pilihan", "kebutuhan", "cocok"])
    assert any(k in rep1.lower() for k in ["garansi resmi", "siap pakai", "tanyakan", "opsi", "detail"])

    # === TURN 2: Lanjutan 'cuma itu?' ===
    t2 = process_chat_message(sid, "cuma itu?")
    rep2 = t2["reply"]
    verify_rubric_invariants(rep2)

    assert t2["route"] == "FOLLOWUP_OPTIONS"
    # Anti-parrot: Tidak mengulang menyodorkan daftar produk yang sama
    assert len(t2.get("products", [])) == 0, "Turn 'cuma itu?' tidak boleh mengulang daftar produk"
    assert "✅" not in rep2, "Turn 'cuma itu?' tidak boleh memuat tanda ✅"
    # Menjawab dari state sebelumnya (1 model memenuhi seluruh kriteria keras)
    low2 = rep2.lower()
    assert any(k in low2 for k in ["1 model", "1 pilihan", "katalog kami baru ada 1", "memenuhi seluruh spesifikasi"])
    assert any(k in low2 for k in ["alternatif", "ram 16 gb", "terjangkau", "kartu grafis", "anggaran"])

    # === TURN 3: Meta 'Dari mana kamu tahu kebutuhanku?' ===
    t3 = process_chat_message(sid, "Dari mana kamu tahu kebutuhanku?")
    rep3 = t3["reply"]
    verify_rubric_invariants(rep3)

    assert t3["route"] == "META_CLARIFY"
    assert len(t3.get("products", [])) == 0, "Meta query dilarang menyodorkan produk"
    assert "✅" not in rep3, "Meta query dilarang memuat tanda ✅"
    # Jawab jujur belum tahu kebutuhan + tanya ramah
    low3 = rep3.lower()
    assert any(k in low3 for k in ["belum mengetahui", "belum tahu", "rekomendasi umum"])
    assert any(k in low3 for k in ["ceritakan", "aktivitas", "digunakan", "budget", "anggaran"])


def test_rubric_conversational_framing_latency():
    """
    Uji pembingkaian percakapan kode menyusun fakta, templat vs LLM, dan latensi terukur.
    """
    cat = Catalog.from_synthetic_v1_2()
    # Panggil FAST_AGENTIC dengan templat
    res_tpl = run_agentic_tool(
        user_text="laptop buat edit video 4k",
        history=[],
        catalog=cat,
        use_llm_framing=False
    )
    verify_rubric_invariants(res_tpl["reply"])
    metrics_tpl = res_tpl.get("metrics", {})
    frame_meta_tpl = metrics_tpl.get("frame", {})
    assert "frame_latency" in frame_meta_tpl
    assert frame_meta_tpl["frame_mode"] == "template"
    # Latensi templat harus sangat cepat (< 50 ms)
    assert frame_meta_tpl["frame_latency"] < 0.05, f"Templat terlalu lambat: {frame_meta_tpl['frame_latency']}s"
    # Ada pembuka dan penutup
    lines = [line.strip() for line in res_tpl["reply"].split("\n") if line.strip()]
    assert len(lines) >= 3, "Harus memuat pembuka, isi fakta produk, dan penutup"


def test_rubric_percakapan_4_telegram_persona_dan_kritik_spek():
    """
    Percakapan 4 (Kasus nyata Telegram tg_1095607605):
    Turn 1: 'Halo' -> GREETING, ramah, no products, no checkmark.
    Turn 2: 'Laptop' -> CLARIFY_CATEGORY, tanya kebutuhan & budget, no products, no checkmark.
    Turn 3: 'Buat mama sih' -> CLARIFY_CATEGORY (persona mama), tanya aktivitas mama & budget, no products, no checkmark.
    Turn 4: 'Gak kegedean tuh speknya?' -> META_CLARIFY, empati kritik spek kebesaran, minta maaf & klarifikasi aktivitas mama, no products, no checkmark.
    Turn 5: 'Loh...kok ditawarin yang lain? Aku tadi tanya apa gak kegedean spek yang sebelumnya?' -> META_CLARIFY, empati klarifikasi pertanyaan, no products, no checkmark.
    Turn 6: 'Kebutuhannya aja kamu belum tau' -> META_CLARIFY, jujur mengakui belum tahu kebutuhan & tanya ramah, no products, no checkmark.
    """
    sid = "rubric_test_tg_persona_critique"
    reset_chat_session(sid)

    # Turn 1: 'Halo'
    t1 = process_chat_message(sid, "Halo")
    verify_rubric_invariants(t1["reply"])
    assert t1["route"] == "GREETING"
    assert len(t1.get("products", [])) == 0
    assert "✅" not in t1["reply"]

    # Turn 2: 'Laptop'
    t2 = process_chat_message(sid, "Laptop")
    verify_rubric_invariants(t2["reply"])
    assert t2["route"] == "CLARIFY_CATEGORY"
    assert len(t2.get("products", [])) == 0
    assert "✅" not in t2["reply"]

    # Turn 3: 'Buat mama sih'
    t3 = process_chat_message(sid, "Buat mama sih")
    verify_rubric_invariants(t3["reply"])
    assert t3["route"] == "CLARIFY_CATEGORY"
    assert len(t3.get("products", [])) == 0
    assert "✅" not in t3["reply"]
    assert "mama" in t3["reply"].lower()

    # Turn 4: 'Gak kegedean tuh speknya?'
    t4 = process_chat_message(sid, "Gak kegedean tuh speknya?")
    verify_rubric_invariants(t4["reply"])
    assert t4["route"] == "META_CLARIFY"
    assert len(t4.get("products", [])) == 0
    assert "✅" not in t4["reply"]
    assert any(k in t4["reply"].lower() for k in ["terlalu tinggi", "berlebih", "mohon maaf", "mama"])

    # Turn 5: 'Loh...kok ditawarin yang lain? Aku tadi tanya apa gak kegedean spek yang sebelumnya?'
    t5 = process_chat_message(sid, "Loh...kok ditawarin yang lain? Aku tadi tanya apa gak kegedean spek yang sebelumnya?")
    verify_rubric_invariants(t5["reply"])
    assert t5["route"] == "META_CLARIFY"
    assert len(t5.get("products", [])) == 0
    assert "✅" not in t5["reply"]

    # Turn 6: 'Kebutuhannya aja kamu belum tau'
    t6 = process_chat_message(sid, "Kebutuhannya aja kamu belum tau")
    verify_rubric_invariants(t6["reply"])
    assert t6["route"] == "META_CLARIFY"
    assert len(t6.get("products", [])) == 0
    assert "✅" not in t6["reply"]
    assert any(k in t6["reply"].lower() for k in ["belum tahu", "belum mengetahui", "rekomendasi"])


def test_rubric_isolasi_sesi_antar_chat_id():
    """
    Uji Isolasi Sesi: Dua sesi (chat_id berbeda) TIDAK berbagi state.
    - Sesi A: 'laptop buat edit video 4k' -> Menghasilkan rekomendasi produk A (Legion Pro 5)
    - Sesi B: 'cuma itu?' -> Harus menjawab bahwa belum ada rekomendasi yang ditampilkan dan bertanya kebutuhan, tanpa menyebut produk A.
    """
    sid_a = "session_iso_user_A"
    sid_b = "session_iso_user_B"
    reset_chat_session(sid_a)
    reset_chat_session(sid_b)

    # Sesi A meminta laptop edit video 4k
    res_a = process_chat_message(sid_a, "laptop buat edit video 4k")
    verify_rubric_invariants(res_a["reply"])
    assert len(res_a.get("products", [])) > 0
    assert any("Legion" in p.get("nama", "") for p in res_a["products"])

    # Sesi B (pengguna berbeda) langsung bertanya lanjutan 'cuma itu?'
    res_b = process_chat_message(sid_b, "cuma itu?")
    verify_rubric_invariants(res_b["reply"])
    reply_b = res_b["reply"]

    # Sesi B dilarang menyebut produk dari Sesi A
    assert "legion" not in reply_b.lower()
    assert "lenovo" not in reply_b.lower()
    assert len(res_b.get("products", [])) == 0

    # Sesi B harus menjelaskan belum ada rekomendasi dan bertanya kebutuhan
    assert any(k in reply_b.lower() for k in ["belum ada rekomendasi", "belum ada yang kami tampilkan", "belum ada"])
    assert any(k in reply_b.lower() for k in ["kebutuhan", "dicari", "anggaran", "budget"])


def test_rubric_baterai_awet_tanpa_centang_dan_jujur():
    """
    Kebutuhan 'laptop baterai awet':
    - Jangan beri ✅ 'memenuhi seluruh syarat'
    - Jawab jujur bahwa data baterai tidak ada di katalog
    - Arahkan ke laptop tipis tanpa GPU dedicated (profil P01/P16 dengan filter GPU integrated)
    - Tanya budget
    - Tampilkan hasil tanpa klaim syarat penuh
    """
    sid = "rubric_baterai_awet"
    reset_chat_session(sid)
    res = process_chat_message(sid, "laptop baterai awet")
    reply = res["reply"]
    verify_rubric_invariants(reply)

    # Dilarang ada tanda ✅
    assert "✅" not in reply, f"Baterai awet dilarang memiliki tanda ✅:\n{reply}"
    # Dilarang klaim memenuhi seluruh syarat
    assert "memenuhi seluruh syarat" not in reply.lower()

    # Jawab jujur bahwa data baterai tidak ada di katalog
    assert any(k in reply.lower() for k in ["tidak tercantum", "tidak ada", "daya tahan baterai"]), \
        f"Jawaban harus jujur mengenai ketiadaan data baterai:\n{reply}"

    # Arahkan ke laptop tipis tanpa GPU dedicated (integrated GPU)
    prods = res.get("products", [])
    assert len(prods) > 0, "Harus menyajikan opsi laptop tipis hemat daya"
    from core.catalog import Catalog
    cat = Catalog.from_dummy()
    for p in prods:
        cat_p = cat.by_code.get(p["kode"])
        if cat_p:
            assert cat_p.get("gpu_dedicated") == 0, f"Laptop dengan GPU dedicated dilarang muncul untuk baterai awet: {p['kode']}"

    # Profil aktif harus P01 (atau P16), bukan G03
    assert res.get("active_profile_id") in ("P01", "P16")

    # Tanya budget
    assert any(k in reply.lower() for k in ["budget", "anggaran", "biaya"])


def test_rubric_parsing_spesifikasi_generik():
    """
    Uji parsing spesifikasi generik:
    - RAM 32GB (ada di katalog: KB-L10)
    - RAM 16GB (ada di katalog: >= 16GB)
    - RAM 64GB (tidak ada di katalog: 0 produk)
    - SSD 1TB (ada di katalog: KB-L07, KB-L09, KB-L10)
    - Budget di bawah 10 juta (ada di katalog: <= 10.000.000)
    """
    # 1. RAM 32GB
    res_r32 = process_chat_message("test_gen_r32", "laptop RAM 32GB")
    verify_rubric_invariants(res_r32["reply"])
    kodes_r32 = [p["kode"] for p in res_r32.get("products", [])]
    assert "KB-L10" in kodes_r32, "Legion Pro 5 (RAM 32GB) harus ditemukan"

    # 2. RAM 16GB
    res_r16 = process_chat_message("test_gen_r16", "laptop RAM 16GB")
    verify_rubric_invariants(res_r16["reply"])
    assert len(res_r16.get("products", [])) > 0, "Laptop RAM 16GB harus ditemukan"

    # 3. RAM 64GB (melebihi katalog)
    res_r64 = process_chat_message("test_gen_r64", "laptop RAM 64GB")
    verify_rubric_invariants(res_r64["reply"])
    assert len(res_r64.get("products", [])) == 0, "Laptop RAM 64GB tidak ada di katalog"
    assert "tidak tersedia" in res_r64["reply"].lower()

    # 4. SSD 1TB
    res_ssd = process_chat_message("test_gen_ssd", "laptop SSD 1TB")
    verify_rubric_invariants(res_ssd["reply"])
    kodes_ssd = [p["kode"] for p in res_ssd.get("products", [])]
    assert any(k in kodes_ssd for k in ["KB-L07", "KB-L09", "KB-L10"]), "Laptop SSD 1TB harus ditemukan"

    # 5. Budget di bawah 10 juta
    res_b10 = process_chat_message("test_gen_b10", "laptop di bawah 10 juta")
    verify_rubric_invariants(res_b10["reply"])
    for p in res_b10.get("products", []):
        assert p["harga_idr"] <= 10000000, f"Harga {p['harga_idr']} harus <= 10.000.000"


def test_rubric_alasan_gagal_natural_tanpa_nama_kolom():
    """
    Uji penjelasan kegagalan syarat mutlak memakai bahasa natural,
    tanpa nama kolom mentah (ram_gb, vram_gb), dan tanpa duplikasi kalimat header.
    """
    sid = "rubric_fail_natural"
    reset_chat_session(sid)
    # Turn 1: video 4k
    process_chat_message(sid, "laptop buat edit video 4k")
    # Turn 2: yang ASUS aja (ASUS TUF gagal RAM 32GB, Vivobook gagal RAM 32GB + VRAM 8GB)
    res2 = process_chat_message(sid, "yang ASUS aja")
    reply2 = res2["reply"]
    verify_rubric_invariants(reply2)

    # Larangan nama kolom
    for col in ["ram_gb", "vram_gb", "storage_ssd_gb", "cpu_tier"]:
        assert col not in reply2.lower(), f"Kolom teknis '{col}' dilarang muncul di reply:\n{reply2}"

    # Harus memuat format natural
    assert any(k in reply2.lower() for k in ["ram 16 gb", "butuh 32 gb", "vram"]), \
        f"Penjelasan kegagalan harus natural:\n{reply2}"

    occurrences = len(re.findall(r"kandidat terdekat", reply2, re.IGNORECASE))
    assert occurrences <= 1, f"Kalimat 'kandidat terdekat' tidak boleh duplikat (muncul {occurrences}x):\n{reply2}"


def test_rubric_niat_merek_dan_stok():
    """
    Instruksi 8: Pertanyaan merek/stok ('jual laptop acer?', 'ada Asus?', 'punya laptop dell?').
    - Jawab ya/tidak sesuai katalog.
    - Tampilkan produk merek itu, tanpa mengabaikan merek.
    - Tanpa klaim syarat/✅ yang tidak relevan.
    - Produk kosong jika merek tidak tersedia di katalog.
    """
    # 1. 'jual laptop acer?' -> Tersedia di katalog
    res_acer = process_chat_message("test_brand_acer", "jual laptop acer?")
    reply_acer = res_acer["reply"]
    verify_rubric_invariants(reply_acer)
    assert res_acer["route"] == "BRAND_STOCK"
    assert "✅" not in reply_acer, "Pertanyaan merek tanpa syarat tidak boleh diberi centang"
    assert "ya" in reply_acer.lower() and "acer" in reply_acer.lower()
    prods_acer = res_acer.get("products", [])
    assert len(prods_acer) > 0, "Harus menampilkan laptop Acer"
    for p in prods_acer:
        assert "acer" in p["brand"].lower() or "acer" in p["nama"].lower(), f"Produk harus Acer, bukan {p['nama']}"

    # 2. 'ada Asus?' -> Tersedia di katalog
    res_asus = process_chat_message("test_brand_asus", "ada Asus?")
    reply_asus = res_asus["reply"]
    verify_rubric_invariants(reply_asus)
    assert res_asus["route"] == "BRAND_STOCK"
    assert "✅" not in reply_asus
    assert "ya" in reply_asus.lower() and "asus" in reply_asus.lower()
    prods_asus = res_asus.get("products", [])
    assert len(prods_asus) > 0, "Harus menampilkan produk ASUS"
    for p in prods_asus:
        assert "asus" in p["brand"].lower() or "asus" in p["nama"].lower(), f"Produk harus ASUS, bukan {p['nama']}"

    # 3. 'punya laptop dell?' -> Tidak tersedia di katalog
    res_dell = process_chat_message("test_brand_dell", "punya laptop dell?")
    reply_dell = res_dell["reply"]
    verify_rubric_invariants(reply_dell)
    assert res_dell["route"] == "BRAND_STOCK_UNAVAILABLE"
    assert len(res_dell.get("products", [])) == 0, "Dell tidak ada di katalog, produk harus kosong"
    assert any(k in reply_dell.lower() for k in ["belum menyediakan", "belum menjual", "mohon maaf"])
    assert any(k in reply_dell.lower() for k in ["lenovo", "asus", "hp", "acer"])


def test_rubric_rujukan_state_pada_kritik_dan_pertanyaan_balik():
    """
    Instruksi 11: Simpan di state apa yang sudah ditampilkan ke pelanggan dan kebutuhan yang diketahui.
    Jawaban untuk kritik atau pertanyaan balik harus merujuk ke state itu, bukan memicu pencarian baru.
    """
    sid = "test_rubric_state_ref"
    reset_chat_session(sid)

    # Turn 1: Kebutuhan spesifik video 4k
    res1 = process_chat_message(sid, "laptop buat edit video 4k")
    verify_rubric_invariants(res1["reply"])
    assert len(res1.get("products", [])) > 0
    p_offered = res1["products"][0]["nama"]

    # Turn 2: Kritik spesifikasi berlebih ("apa gak kegedean tuh speknya?")
    res2 = process_chat_message(sid, "apa gak kegedean tuh speknya?")
    reply2 = res2["reply"]
    verify_rubric_invariants(reply2)
    assert res2["route"] == "META_CLARIFY"
    # Tidak memicu pencarian baru
    assert len(res2.get("products", [])) == 0, "Kritik tidak boleh memicu daftar produk baru"
    # Merujuk ke produk sebelumnya dari state
    assert p_offered in reply2 or "rekomendasi" in reply2.lower()

    # Turn 3: Pertanyaan meta asal rekomendasi ("Dari mana kamu tahu kebutuhanku?")
    res3 = process_chat_message(sid, "Dari mana kamu tahu kebutuhanku?")
    reply3 = res3["reply"]
    verify_rubric_invariants(reply3)
    assert res3["route"] == "META_CLARIFY"
    assert len(res3.get("products", [])) == 0, "Pertanyaan meta tidak boleh memicu daftar produk baru"
    assert any(k in reply3.lower() for k in ["kebutuhan", "catatan", "rekomendasi"])





