# -*- coding: utf-8 -*-
"""
Uji Respons atas Pertanyaan Bot untuk Tiap pending_question:
- aktivitas
- budget
- kategori
- merek
- kebutuhan
"""
import pytest
from services.slot_nlu_service import extract_slots_deterministic, understand_message_with_llm
from services.chat_service import process_chat_message, reset_chat_session


def test_pending_question_aktivitas():
    current_slots = {"kategori": "laptop", "merek": "asus"}
    intent, slots = extract_slots_deterministic("Nonton youtube dan browsing santai", "aktivitas", current_slots)
    assert intent == "kebutuhan"
    assert "nonton" in slots["aktivitas"].lower() or "browsing" in slots["aktivitas"].lower()


def test_pending_question_budget():
    current_slots = {"kategori": "laptop", "aktivitas": "kuliah"}
    intent, slots = extract_slots_deterministic("Maksimal 8 juta", "budget", current_slots)
    assert intent == "kebutuhan"
    assert slots.get("budget") == 8000000


def test_pending_question_kategori():
    current_slots = {"aktivitas": "kerja kantor"}
    intent, slots = extract_slots_deterministic("Mau cari laptop", "kategori", current_slots)
    assert intent == "kebutuhan"
    assert slots.get("kategori") == "laptop"


def test_pending_question_merek():
    current_slots = {"kategori": "laptop", "aktivitas": "desain"}
    intent, slots = extract_slots_deterministic("Lebih prefer Lenovo", "merek", current_slots)
    assert slots.get("merek") == "lenovo"


def test_pending_question_kebutuhan():
    current_slots = {"kategori": "laptop"}
    intent, slots = extract_slots_deterministic("Buat kasir toko retail", "kebutuhan", current_slots)
    assert intent == "kebutuhan"
    assert "kasir" in slots.get("aktivitas", "").lower()
