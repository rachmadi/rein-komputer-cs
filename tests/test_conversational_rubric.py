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
    internal_codes = re.findall(r"\b[PMG]\d{2}\b", reply)
    assert not internal_codes, f"Ditemukan kode internal dalam jawaban pelanggan: {internal_codes} | Reply: {reply}"

    # Spesifikasi tidak boleh mengandung string literal 'None'
    assert "None" not in reply, f"Ditemukan string literal 'None' dalam spesifikasi: {reply}"


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

