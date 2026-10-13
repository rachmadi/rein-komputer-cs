# -*- coding: utf-8 -*-
"""
Intent Router untuk Asisten Penjualan Bobby Computer
Mengklasifikasikan niat pengguna ke dalam 7 kelas sebelum pencarian:
1. sapaan
2. kategori-saja
3. kebutuhan-jelas
4. produk-spesifik
5. lanjutan
6. meta
7. di-luar-topik
"""
from __future__ import annotations

import re
from typing import Literal

IntentClass = Literal[
    "sapaan",
    "kategori-saja",
    "kebutuhan-jelas",
    "produk-spesifik",
    "lanjutan",
    "meta",
    "di-luar-topik",
    "merek-stok"
]

# Daftar pola dan kata kunci
GREETINGS_PATTERN = r"^(halo|hai|hi|hey|hello|selamat\s+(pagi|siang|sore|malam)|assalamu[']?alaikum|p|permisi|bot)\b"

META_PATTERNS = [
    r"dari\s+mana\s+kamu\s+tahu",
    r"kok\s+(kamu\s+)?(bisa\s+)?tahu",
    r"kenapa\s+(kamu\s+)?(nawarin|rekomendasiin|pilih)\s+(ini|yang\s+ini)",
    r"kamu\s+(ini\s+)?(ai|bot|robot|manusia)",
    r"siapa\s+kamu",
    r"apakah\s+kamu\s+(ai|bot|robot)",
    r"kebutuhan(nya)?\s+(aja\s+)?(kamu\s+)?belum\s+(tahu|tau)",
    r"belum\s+(tahu|tau)\s+kebutuhan",
    r"(gak|tidak|kurang)\s+(kegedean|kebesaran|kemahalan|ketinggian|keberatan|overkill)",
    r"terlalu\s+(besar|tinggi|berat|mahal|spek|berlebih)",
    r"spek(nya)?\s+(gak\s+)?kegedean",
    r"kok\s+(malah\s+)?(ditawarin|nawarin)",
    r"aku\s+(kan\s+|tadi\s+)?(tanya|nanya)",
    r"kurang\s+nangkap",
    r"bukan\s+itu\s+maksud(ku|nya)?",
    r"maksudku\s+bukan",
]

PERSONA_PATTERNS = [
    r"\b(buat|untuk)?\s*(mama|ibu|bunda|mamaku|ibuku|papa|ayah|bapak|papaku|ayahku|bapakku|anak|anakku|adik|adikku|kakak|istri|suami|kakek|nenek|orang\s*tua)\b"
]

OUT_OF_DOMAIN_PATTERNS = [
    r"jam\s+buka",
    r"tutup\s+jam",
    r"buka\s+jam",
    r"alamat(\s+toko)?",
    r"lokasi(\s+toko)?",
    r"cabang",
    r"cicil(an)?",
    r"kredit",
    r"paylater",
    r"ongk(os)?\s*kirim",
    r"ongkir",
    r"garansi(\s+berapa\s+lama|\s+resmi)?",
    r"servis",
    r"service\s*center",
    r"cara\s+bayar",
    r"resep",
]

FOLLOW_UP_PATTERNS = [
    r"cuma\s+itu(\s*(\?|aja))?",
    r"hanya\s+itu",
    r"ada\s+yang\s+lain",
    r"yang\s+lain(\s+ada|\s*(\?|aja))?",
    r"ada\s+lagi",
    r"pilihan\s+lain",
    r"opsi\s+lain",
    r"rekomendasi\s+lain",
    r"ada\s+yang\s+lebih\s+murah",
    r"lebih\s+murah(\s*(\?|ada))?",
    r"yang\s+lebih\s+murah",
    r"yang\s+lebih\s+mahal",
    r"yang\s+[a-z0-9\-]+\s+aja",  # misal "yang ASUS aja", "yang 16GB aja"
    r"kalau\s+[a-z0-9\-]+(\s+gimana|\s*(\?))?",
    r"kalo\s+[a-z0-9\-]+(\s+gimana|\s*(\?))?",
]

CATEGORIES = ["laptop", "notebook", "desktop", "komputer", "pc", "printer", "monitor"]

PRODUCT_CODES = [r"\bkb-[ldmp]\d{2}\b"]
PRODUCT_MODELS = [
    "legion", "loq", "ideapad", "thinkpad",
    "vivobook", "zenbook", "tuf", "rog strix", "expertcenter",
    "nitro", "aspire", "predator", "swift",
    "pavilion", "omen", "victus", "prodesk",
    "pixma", "ecotank", "laserjet", "smart tank"
]

NEED_INDICATORS = [
    "kebutuhan", "dipakai", "dipake", "kerja", "kantor", "kuliah", "sekolah", "mahasiswa", "pelajar",
    "gaming", "game", "render", "rendering", "editing", "edit", "desain", "foto", "video",
    "blender", "photoshop", "autocad", "sketchup", "revit", "coding", "ngoding", "program",
    "data science", "machine learning", "ai", "kasir", "toko", "admin", "streaming", "obs",
    "musik", "fl studio", "trading", "saham", "crypto", "baterai awet", "ringan", "tipis",
    "ngetik", "browsing", "office", "excel", "word", "belajar", "santai", "nonton", "youtube"
]

SPEC_INDICATORS = [
    r"\bram\s*\d+\s*(gb)?\b",
    r"\d+\s*gb\s*ram\b",
    r"\bvram\s*\d+\s*(gb)?\b",
    r"\brtx\s*\d+\b",
    r"\bgtx\s*\d+\b",
    r"\bcore\s*i[3579]\b",
    r"\bryzen\s*[3579]\b",
    r"\b\d+\s*(tb|gb)\s*ssd\b",
    r"\bssd\s*\d+\s*(tb|gb)\b",
    r"\b(budget|anggaran|harga|dana|di\s*bawah|dibawah|maksimal|maks|kurang\s*dari|under)\s*(\d+)?\s*(juta|jt)\b",
    r"\b\d+\s*(juta|jt)\b",
]

from core.db import get_catalog_inventory

CATALOG_BRANDS = get_catalog_inventory()["merek"]
OTHER_BRANDS = [
    "dell", "apple", "macbook", "msi", "samsung", "toshiba", "axioo", "zyrex",
    "huawei", "xiaomi", "redmibook", "advan", "infinix", "avita", "sony", "vaio", "razer", "alienware", "fujitsu"
]
ALL_KNOWN_BRANDS = CATALOG_BRANDS + OTHER_BRANDS

BRAND_STOCK_PATTERNS = [
    r"\b(ada|jual|punya|ready|stok|stock|sedia|menyediakan)\b",
    r"\b(apakah\s+(ada|jual|punya|menyediakan))\b",
]

def detect_brand(text: str) -> str | None:
    low = text.lower()
    for b in ALL_KNOWN_BRANDS:
        if re.search(r"\b" + re.escape(b) + r"\b", low):
            return b
    return None

def classify_intent(text: str, has_prior_context: bool = False) -> IntentClass:
    """
    Mengklasifikasikan niat pengguna ke dalam 8 kelas:
    sapaan, kategori-saja, kebutuhan-jelas, produk-spesifik, lanjutan, meta, di-luar-topik, merek-stok.
    """
    raw = text.strip()
    low = raw.lower()

    # 1. META: Pertanyaan tentang asisten, asal rekomendasi, atau kritik alur/spek
    for pat in META_PATTERNS:
        if re.search(pat, low):
            return "meta"

    # 2. DI-LUAR-TOPIK: Operasional toko, garansi, kredit, atau topik di luar IT
    for pat in OUT_OF_DOMAIN_PATTERNS:
        if re.search(pat, low):
            # Kecuali jika jelas menanyakan spesifikasi produk
            if not any(ni in low for ni in ["laptop", "komputer", "pc", "desktop"]):
                return "di-luar-topik"
            elif any(pat_ood in low for pat_ood in ["jam buka", "alamat", "cicil", "lokasi"]):
                return "di-luar-topik"

    # 3. LANJUTAN: Pertanyaan kelanjutan dari konteks sebelumnya ("cuma itu?", "ada yang lain?", "yang ASUS aja")
    for pat in FOLLOW_UP_PATTERNS:
        if re.search(pat, low):
            return "lanjutan"

    # 4. MEREK-STOK: Pertanyaan stok atau penjualan merek ("jual laptop acer?", "ada Asus?", "punya Dell?")
    matched_brand = detect_brand(low)
    has_specific_product = any(re.search(pat, low) for pat in PRODUCT_CODES) or any(re.search(r"\b" + re.escape(model) + r"\b", low) for model in PRODUCT_MODELS)
    if matched_brand and not has_specific_product:
        has_need = any(re.search(r"\b" + nd + r"\b", low) for nd in NEED_INDICATORS)
        has_spec = any(re.search(pat, low) for pat in SPEC_INDICATORS)
        if not has_need and not has_spec:
            has_stock_query = any(re.search(pat, low) for pat in BRAND_STOCK_PATTERNS) or any(k in low for k in ["jual", "ready", "stok", "ada", "punya", "sedia"])
            if has_stock_query or len(low.split()) <= 3:
                return "merek-stok"

    # 4. SAPAAN: Pesan hanya berupa sapaan/salam murni
    if re.search(GREETINGS_PATTERN, low):
        # Periksa apakah ada sebutan kategori atau kebutuhan
        has_cat = any(re.search(r"\b" + cat + r"\b", low) for cat in CATEGORIES)
        has_need = any(re.search(r"\b" + nd + r"\b", low) for nd in NEED_INDICATORS)
        if not has_cat and not has_need:
            return "sapaan"

    # 5. PRODUK-SPESIFIK: Menyebut kode produk atau model seri spesifik
    for pat in PRODUCT_CODES:
        if re.search(pat, low):
            return "produk-spesifik"
    for model in PRODUCT_MODELS:
        if re.search(r"\b" + re.escape(model) + r"\b", low):
            # Jika user bilang "laptop buat game" bukan produk-spesifik
            return "produk-spesifik"

    # 6. KEBUTUHAN-JELAS vs KATEGORI-SAJA (termasuk persona tanpa aktivitas konkret)
    has_cat = any(re.search(r"\b" + cat + r"\b", low) for cat in CATEGORIES)
    has_need = any(re.search(r"\b" + nd + r"\b", low) for nd in NEED_INDICATORS)
    has_spec = any(re.search(pat, low) for pat in SPEC_INDICATORS)
    has_persona = any(re.search(pat, low) for pat in PERSONA_PATTERNS)

    # Persona tanpa kebutuhan/spesifikasi jelas ("buat mama sih", "untuk papa", "buat anak")
    if has_persona and not has_need and not has_spec:
        return "kategori-saja"

    if has_need or has_spec:
        return "kebutuhan-jelas"

    if has_cat:
        # User hanya menyebut kategori ("laptop", "ada laptop?", "desktop", "printer")
        # tanpa ada kebutuhan atau spesifikasi jelas
        return "kategori-saja"

    # Jika ada sapaan dengan kata lain tapi tanpa kategori/kebutuhan
    if re.search(GREETINGS_PATTERN, low):
        return "sapaan"

    # Default fallback: jika sangat pendek dan tidak spesifik
    if len(low.split()) <= 2 and not has_need:
        return "sapaan"

    return "kebutuhan-jelas"
