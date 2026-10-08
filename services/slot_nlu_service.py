# -*- coding: utf-8 -*-
"""
Slot-based NLU & Dialogue State Tracking Service
Bobby Computer Customer Care

Mengintegrasikan pemahaman LLM singkat (JSON output, num_predict <= 80)
dengan Dialogue State Tracker (DST) dan aturan penentu langkah (Dialogue Policy).
"""
from __future__ import annotations

import os
import re
import json
import time
import sqlite3
import urllib.request
import logging

from core.acts import extract_persona_name

logger = logging.getLogger("slot_nlu")

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_NLU_MODEL = "gemma4:e4b"
DB_PATH = os.getenv("DB_PATH", "data/catalog.db")

# Daftar merek dinamis dari database katalog Bobby Computer
def get_catalog_brands() -> list[str]:
    try:
        db_file = os.getenv("DB_PATH", "data/catalog.db")
        if os.path.exists(db_file):
            conn = sqlite3.connect(db_file)
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT brand FROM products WHERE brand IS NOT NULL AND brand != ''")
            brands = [r[0].lower() for r in cur.fetchall()]
            conn.close()
            if brands:
                return brands
    except Exception as e:
        logger.warning(f"Gagal memuat merek dinamis dari DB: {e}")
    return ["lenovo", "asus", "hp", "acer", "canon", "epson", "brother"]

# Pemetaan Aktivitas ke Profil (LLM + Knowledge Base)
def map_activity_to_profile(aktivitas: str | None, persona: str | None = None) -> str | None:
    """
    Memetakan aktivitas ke profil katalog KB:
    - Game HANYA jika pelanggan menyebut game!
    - Aktivitas nonton, browsing, hiburan ringan, ibu sepuh -> P11 (atau P01).
    - Bila ragu, kembalikan None agar asisten bertanya.
    """
    if not aktivitas:
        # Jika persona orang tua tanpa aktivitas spesifik
        if persona and persona.lower() in ("ibu", "mama", "bapak", "ayah", "kakek", "nenek"):
            return "P11"
        return None

    low = aktivitas.lower().strip()

    # 1. Game HANYA jika menyebut game secara eksplisit
    is_game = any(k in low for k in ["game", "gaming", "gamer", "valorant", "gta", "genshin", "dota", "steam"])
    if is_game:
        if any(k in low for k in ["berat", "aaa", "hardcore", "rtx", "maksimal", "kompetitif"]):
            return "P05"
        elif any(k in low for k in ["santai", "kuliah", "sesekali", "kerja"]):
            return "P16"
        else:
            return "P04"

    # 2. Hiburan ringan, nonton, santai, browsing, orang tua / sepuh -> P11 atau P01
    is_light_entertainment = any(k in low for k in [
        "hiburan", "nonton", "video", "youtube", "film", "streaming",
        "browsing", "santai", "harian", "sepuh", "tua", "belajar", "ngetik", "word"
    ])
    if is_light_entertainment:
        return "P11"

    # 3. Kebutuhan profesional / teknis spesifik
    if any(k in low for k in ["edit video 4k", "editing 4k", "render 3d", "blender", "animasi"]):
        return "P03"
    if any(k in low for k in ["desain", "foto", "photoshop", "illustrator", "corel", "gambar"]):
        return "P02"
    if any(k in low for k in ["koding", "ngoding", "program", "python", "docker", "developer"]):
        return "P06"
    if any(k in low for k in ["arsitek", "autocad", "sketchup", "revit"]):
        return "P07"
    if any(k in low for k in ["kasir", "toko", "pos", "barcode"]):
        return "P15"
    if any(k in low for k in ["akuntan", "excel", "formula", "keuangan"]):
        return "P14"
    if any(k in low for k in ["kantor", "administrasi", "kerja"]):
        return "P01"

    return None

def parse_budget_amount(text: str) -> int | None:
    """Mengekstrak nilai rupiah dari teks budget."""
    low = text.lower()
    # Format: "10 juta", "10jt", "10.000.000"
    m_jt = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:juta|jt)", low)
    if m_jt:
        val_str = m_jt.group(1).replace(",", ".")
        try:
            return int(float(val_str) * 1_000_000)
        except Exception:
            pass
    m_num = re.search(r"\b(\d{1,2})[.,](\d{3})[.,](\d{3})\b", low)
    if m_num:
        try:
            return int(m_num.group(0).replace(".", "").replace(",", ""))
        except Exception:
            pass
    return None

def extract_slots_deterministic(
    user_text: str,
    pending_question: str | None,
    current_slots: dict
) -> tuple[str, dict]:
    """
    Fallback NLU deterministik yang sangat akurat untuk menangani Pending Question dan Slot.
    """
    low = user_text.lower().strip()
    slots = dict(current_slots or {})
    catalog_brands = get_catalog_brands()

    # 1. Deteksi persona dengan kata asli pelanggan
    p_name = extract_persona_name(user_text)
    if p_name:
        # Gunakan kata pelanggan (misal: "ibu", "bapak", "anak")
        slots["persona"] = p_name.lower()

    # 2. Deteksi merek
    for b in catalog_brands + ["dell", "apple", "macbook", "msi"]:
        if re.search(r"\b" + re.escape(b) + r"\b", low):
            slots["merek"] = b
            break

    # 3. Deteksi kategori
    if any(k in low for k in ["laptop", "notebook"]):
        slots["kategori"] = "laptop"
    elif any(k in low for k in ["desktop", "komputer", "pc", "aio"]):
        slots["kategori"] = "desktop"
    elif any(k in low for k in ["printer", "cetak"]):
        slots["kategori"] = "printer"
    elif any(k in low for k in ["monitor", "layar"]):
        slots["kategori"] = "monitor"

    # 4. Deteksi budget
    bg = parse_budget_amount(user_text)
    if bg:
        slots["budget"] = bg

    from services.intent_router import classify_intent
    c_intent = classify_intent(user_text, bool(pending_question or current_slots))

    # 5. Intent khusus: Meta & Lanjutan (prioritas utama sebelum pending question)
    if c_intent in ("meta", "meta_protes") or any(k in low for k in ["kegedean", "kebesaran", "kemahalan", "dari mana kamu", "kok ditawarin"]):
        return "meta", slots

    if low in ("mana?", "mana", "mana produknya?", "mana laptopnya?"):
        return "lanjutan", slots

    if any(k in low for k in ["kan sudah dibilang", "kan buat hiburan", "kan tadi kubilang", "kan sudah kubilang"]):
        if any(k in low for k in ["hiburan", "nonton"]):
            slots["aktivitas"] = "hiburan"
        return "meta_protes", slots

    # 6. Ekstraksi berbasis PENDING QUESTION
    if pending_question == "aktivitas":
        act_keywords = [
            "hiburan", "nonton", "video", "youtube", "film", "streaming", "browsing",
            "santai", "game", "gaming", "kuliah", "kerja", "kantor", "koding", "ngoding",
            "program", "desain", "foto", "render", "3d", "arsitek", "autocad", "kasir",
            "akuntan", "excel", "ngetik", "word", "belajar", "sekolah"
        ]
        has_act_kw = any(k in low for k in act_keywords)
        if has_act_kw:
            clean_act = re.sub(r"^(buat|untuk|hanya\s+buat|cuma\s+buat|kan\s+sudah\s+dibilang\s+buat)\s+", "", low).strip()
            slots["aktivitas"] = clean_act
            return "kebutuhan", slots
        elif p_name:
            # Pelanggan menyebut persona/penerima di pesan ini (bukan aktivitas), sehingga slot aktivitas tetap kosong
            slots["aktivitas"] = None
            return "kategori-saja", slots
        else:
            clean_act = re.sub(r"^(buat|untuk|hanya\s+buat|cuma\s+buat|kan\s+sudah\s+dibilang\s+buat)\s+", "", low).strip()
            slots["aktivitas"] = clean_act or "hiburan"
            return "kebutuhan", slots

    elif pending_question == "budget" and bg:
        slots["budget"] = bg
        return "kebutuhan", slots

    elif pending_question == "kategori" and slots.get("kategori"):
        return "kebutuhan", slots

    if c_intent in ("meta", "kategori-saja", "lanjutan", "di-luar-topik", "sapaan", "merek-stok"):
        return c_intent, slots

    if any(k in low for k in ["hiburan", "game", "gaming", "kuliah", "kerja", "render", "koding", "kasir"]):
        clean_act = re.sub(r"^(buat|untuk)\s+", "", low).strip()
        slots["aktivitas"] = clean_act
        return "kebutuhan", slots

    if slots.get("persona") and not slots.get("aktivitas"):
        return "kategori-saja", slots

    return "kebutuhan", slots


def understand_message_with_llm(
    user_text: str,
    pending_question: str | None = None,
    current_slots: dict | None = None,
    model: str = DEFAULT_NLU_MODEL
) -> dict:
    """
    Satu panggilan LLM singkat (format JSON, num_predict <= 80)
    untuk mengekstrak intent dan slots.
    Jika LLM lambat/gagal, otomatis memakai fallback deterministik yang kokoh.
    """
    t0 = time.perf_counter()
    current_slots = current_slots or {}
    catalog_brands = get_catalog_brands()

    sys_prompt = (
        "Kamu asisten NLU ekstraksi slot untuk toko komputer Bobby Computer.\n"
        "Ekstrak intent dan slots dari pesan pelanggan ke format JSON ringkas.\n"
        "Daftar Intent: sapaan, tanya_merek_stok, kebutuhan, produk_spesifik, lanjutan, meta_protes, di_luar_topik.\n"
        f"Merek tersedia: {', '.join(catalog_brands)}.\n"
        "PENTING:\n"
        "1. Jika ada Pending Question, perlakukan pesan pelanggan sebagai jawaban untuk slot itu!\n"
        "   Contoh: pending 'aktivitas' + pesan 'Buat hiburan' -> intent 'kebutuhan', slot aktivitas='hiburan'.\n"
        "   Contoh: pending 'kebutuhan' + pesan 'Untuk ibu saya yang sudah sepuh' -> slot persona='ibu'.\n"
        "2. Ekstrak kata persona sesuai kata asli pelanggan (misal: 'ibu', 'bapak', 'mama').\n"
        "Format JSON:\n"
        "{\"intent\": \"...\", \"slots\": {\"persona\": null, \"aktivitas\": null, \"budget\": null, \"kategori\": null, \"merek\": null}}"
    )
    user_prompt = f"Pending Question: {pending_question}\nSlots Saat Ini: {json.dumps(current_slots)}\nPesan Pelanggan: \"{user_text}\""

    req_data = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False,
        "format": "json",
        "options": {
            "num_predict": 80,
            "temperature": 0.0
        },
        "keep_alive": "60m"
    }

    try:
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat",
            data=json.dumps(req_data).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            raw_res = json.loads(resp.read().decode("utf-8"))
        latency = time.perf_counter() - t0
        content = raw_res.get("message", {}).get("content", "")
        parsed = json.loads(content)

        extracted_intent = parsed.get("intent", "kebutuhan")
        extracted_slots = parsed.get("slots", {}) or {}

        # Merge slots dengan slot saat ini
        merged_slots = dict(current_slots)
        for k, v in extracted_slots.items():
            if v is not None:
                merged_slots[k] = v

        # Safeguard: Persona kata asli pelanggan & pembersihan slot aktivitas jika baru menyebut persona
        p_real = extract_persona_name(user_text)
        act_keywords = [
            "hiburan", "nonton", "video", "youtube", "film", "streaming", "browsing",
            "santai", "game", "gaming", "kuliah", "kerja", "kantor", "koding", "ngoding",
            "program", "desain", "foto", "render", "3d", "arsitek", "autocad", "kasir",
            "akuntan", "excel", "ngetik", "word", "belajar", "sekolah"
        ]
        has_act_kw = any(k in user_text.lower() for k in act_keywords)
        if p_real:
            merged_slots["persona"] = p_real.lower()
            if not has_act_kw:
                merged_slots["aktivitas"] = None

        # Safeguard: Jika ada kata hiburan atau nonton
        if has_act_kw and ("hiburan" in user_text.lower() or "nonton" in user_text.lower()):
            merged_slots["aktivitas"] = "hiburan"
            extracted_intent = "kebutuhan"

        # Safeguard: "Mana?" tidak boleh menjadi sapaan
        if user_text.strip().lower() in ("mana?", "mana", "mana produknya?"):
            extracted_intent = "lanjutan"

        # Safeguard dengan classify_intent untuk meta, kategori-saja, lanjutan, di-luar-topik, sapaan, merek-stok
        from services.intent_router import classify_intent
        c_intent = classify_intent(user_text, bool(pending_question or current_slots))
        if c_intent in ("meta", "meta_protes"):
            extracted_intent = "meta"
        elif c_intent in ("kategori-saja", "lanjutan", "di-luar-topik", "sapaan", "merek-stok"):
            if not (pending_question == "aktivitas" and has_act_kw):
                extracted_intent = c_intent

        return {
            "intent": extracted_intent,
            "slots": merged_slots,
            "latency_ms": round(latency * 1000, 2),
            "source": "llm"
        }

    except Exception as e:
        latency = time.perf_counter() - t0
        logger.info(f"Slot NLU fallback ke deterministik ({e}) dalam {latency:.3f}s")
        intent_det, slots_det = extract_slots_deterministic(user_text, pending_question, current_slots)
        return {
            "intent": intent_det,
            "slots": slots_det,
            "latency_ms": round(latency * 1000, 2),
            "source": "deterministic_fallback"
        }
