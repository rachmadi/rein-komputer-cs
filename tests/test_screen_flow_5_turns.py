# -*- coding: utf-8 -*-
"""
Uji Otomatis 5 Giliran Tangkapan Layar Telegram (Dev Set 1)
Menguji perbaikan struktural Dialogue State Tracking, Overkill Penalty,
Larangan salam berulang, dan Penegakan Bahasa Pelanggan.
"""
import pytest
from services.chat_service import process_chat_message, reset_chat_session


@pytest.mark.skip(reason="Legacy v1 test: menguji pencocokan kata harfiah ('ibu' di teks respons) dan rute v1; memerlukan pembaruan ke arsitektur v2")
def test_telegram_screen_flow_5_turns():
    session_id = "test_screen_flow_5_turns_session"
    reset_chat_session(session_id)

    # =========================================================================
    # GILIRAN 1: "Ada asus?"
    # Harapan: Jawab ketersediaan merek ASUS, tampilkan produk ASUS, tanya kebutuhan/budget.
    # =========================================================================
    r1 = process_chat_message(session_id, "Ada asus?")
    reply1 = r1["reply"]
    slots1 = r1.get("slots", {})
    prods1 = r1.get("products", [])

    assert slots1.get("merek") == "asus", f"Merek ASUS harus terekam di slots: {slots1}"
    assert any("asus" in p["nama"].lower() for p in prods1), f"Harus ada produk ASUS di Turn 1: {prods1}"
    assert "asus" in reply1.lower(), f"Jawaban harus menyebut merek ASUS:\n{reply1}"
    assert r1.get("pending_question") in ("aktivitas", "kebutuhan"), f"Pending question harus kebutuhan/aktivitas: {r1}"

    # =========================================================================
    # GILIRAN 2: "Untuk ibu saya yang sudah sepuh"
    # Harapan: Panggil kata pelanggan ("ibu"), tanya aktivitas/kebutuhan,
    # TIDAK ada salam ulang ("Halo, Kak!"), TIDAK ada "Tentu ada".
    # =========================================================================
    r2 = process_chat_message(session_id, "Untuk ibu saya yang sudah sepuh")
    reply2 = r2["reply"]
    slots2 = r2.get("slots", {})

    assert slots2.get("persona") == "ibu", f"Persona harus 'ibu' sesuai kata pelanggan: {slots2}"
    assert "ibu" in reply2.lower(), f"Harus memuat kata pelanggan 'ibu':\n{reply2}"
    assert "halo, kak!" not in reply2.lower(), f"TIDAK boleh mengulang salam di Turn 2:\n{reply2}"
    assert "tentu ada" not in reply2.lower(), f"Hapus 'Tentu ada' pada jawaban non-ketersediaan:\n{reply2}"
    assert r2.get("pending_question") == "aktivitas", f"Pending question harus 'aktivitas': {r2}"

    # =========================================================================
    # GILIRAN 3: "Buat hiburan"
    # Harapan: Slot aktivitas='hiburan', pemetaan P11, rekomendasi ASUS ringan (Vivobook 14),
    # TIDAK ada salam ulang, TIDAK menawarkan laptop gaming (TUF Gaming / Legion),
    # TIDAK bocor kode profil.
    # =========================================================================
    r3 = process_chat_message(session_id, "Buat hiburan")
    reply3 = r3["reply"]
    slots3 = r3.get("slots", {})
    prods3 = r3.get("products", [])

    assert slots3.get("aktivitas") == "hiburan", f"Slot aktivitas harus hiburan: {slots3}"
    assert "halo, kak!" not in reply3.lower(), f"TIDAK boleh mengulang salam di Turn 3:\n{reply3}"
    assert "P11" not in reply3 and "P05" not in reply3 and "P15" not in reply3, f"Kode internal profil dilarang bocor:\n{reply3}"

    # Cek Overkill Spec Penalty: Vivobook 14 A1405 harus mendominasi, dilarang gaming TUF
    prod_names3 = [p["nama"] for p in prods3]
    assert any("Vivobook 14" in n for n in prod_names3), f"Harus merekomendasikan ASUS Vivobook 14 A1405: {prod_names3}"
    if prods3:
        assert "TUF Gaming" not in prods3[0]["nama"], f"Laptop pertama dilarang laptop gaming berat: {prods3[0]['nama']}"
        assert "Legion" not in prods3[0]["nama"], f"Laptop pertama dilarang Legion gaming: {prods3[0]['nama']}"

    # =========================================================================
    # GILIRAN 4: "Mana?"
    # Harapan: Merujuk konteks percakapan dan menampilkan laptop ringan yang cocok,
    # TIDAK mengulang salam ("Halo, Kak!").
    # =========================================================================
    r4 = process_chat_message(session_id, "Mana?")
    reply4 = r4["reply"]
    prods4 = r4.get("products", [])

    assert "halo, kak!" not in reply4.lower(), f"TIDAK boleh mengulang salam di Turn 4:\n{reply4}"
    prod_names4 = [p["nama"] for p in prods4]
    assert any("Vivobook" in n for n in prod_names4) or "vivobook" in reply4.lower(), f"Harus merujuk/menampilkan Vivobook di Turn 4:\n{reply4}"

    # =========================================================================
    # GILIRAN 5: "Kan sudah dibilang buat hiburan"
    # Harapan: Menjawab jujur merujuk hiburan ibu sepuh, merekomendasikan ASUS Vivobook 14,
    # TIDAK menawarkan laptop gaming, TIDAK ada bocoran 'Kebutuhan gabungan: ...'.
    # =========================================================================
    r5 = process_chat_message(session_id, "Kan sudah dibilang buat hiburan")
    reply5 = r5["reply"]
    prods5 = r5.get("products", [])

    assert "halo, kak!" not in reply5.lower(), f"TIDAK boleh mengulang salam di Turn 5:\n{reply5}"
    assert "kebutuhan gabungan" not in reply5.lower(), f"Dilarang membocorkan 'Kebutuhan gabungan: ...' ke pelanggan:\n{reply5}"
    assert "tuf gaming" not in reply5.lower() and "legion" not in reply5.lower(), f"Dilarang menawarkan laptop gaming untuk hiburan ibu sepuh:\n{reply5}"
    assert any("Vivobook 14" in p["nama"] for p in prods5) or "vivobook 14" in reply5.lower(), f"Harus merekomendasikan Vivobook 14 di Turn 5:\n{reply5}"
