# -*- coding: utf-8 -*-
"""
Deteksi Dialogue Acts, Entitas, dan Penanda Percakapan (§5A, §5B, §8, §11, §14, §18)
"""
from __future__ import annotations

import re
from core.normalizer import has_phrase, find_phrase, has_token
from core.taxonomy import (
    NEED_LEXICON, NEED_TAGS, PERSONA_LEXICON, IDENTITY_TYPE, IDENTITY_STUDENT,
    CATEGORY_WORDS, ATTR_LEXICON, HARDWARE_LEXICON, UNAVAILABLE, COMPARE_WORDS, COMPARE_PHRASES,
    UNCERTAIN_PHRASES, META_CRITIQUE_PHRASES, SERVICE_REQUEST_PHRASES, PURCHASE_TOKENS, CANCEL_SET, CLOSING_SET,
    NONPRODUCT_WORDS, AVAIL_VERBS, AVAIL_SKIP, META_NARRATIVE_WORDS, INSULT_WORDS,
    CATALOG_DOUBT_PHRASES, META_EXPLANATION_PHRASES, CAPABILITY_PHRASES, BANTER_PHRASES,
    GRAMMAR_WORDS, MISMATCH_PHRASES, BRAND_LEXICON, SPEC_OBJECTION_PHRASES
)

BUDGET_MARKERS = [
    ("tidak lebih dari", "max", False), ("kurang dari", "max", True),
    ("di bawah", "max", True), ("dibawah", "max", True), ("ke bawah", "max", False),
    ("maksimal", "max", False), ("maksimum", "max", False), ("maks", "max", False),
    ("max", "max", False), ("paling tinggi", "max", False), ("paling banyak", "max", False),
    ("sampai", "max", False),
    ("di atas", "min", True), ("diatas", "min", True), ("lebih dari", "min", True),
    ("ke atas", "min", False), ("minimal", "min", False), ("min", "min", False),
    ("sekitar", "target", False), ("kisaran", "target", False), ("kira kira", "target", False),
    ("budget", "max", False), ("dana", "max", False), ("uang", "max", False),
]

PREF_PHRASES = {
    "cheapest": ["paling murah", "termurah", "yang murah", "murah saja", "asal murah",
                 "yang penting murah", "ada yang murah"],
    "most_expensive": ["paling mahal", "termahal", "yang mahal", "mahal saja",
                       "spek paling tinggi", "spesifikasi paling tinggi", "spek tertinggi", "spesifikasi tertinggi"],
    "large_ram": ["ram gede", "ram besar", "memori gede", "memori besar", "ram terbesar",
                  "ram paling besar"],
    "large_processor": ["prosesor gede", "prosesor besar", "cpu gede", "cpu besar",
                        "prosesor paling besar"],
    "discrete_gpu": [
        "vga dedicated", "gpu dedicated", "pakai vga", "pake vga", "ada vga",
        "ada vga-nya", "ada gpu", "vga diskrit", "kartu grafis dedicated",
        "gpu diskrit", "vga terpisah", "pakai rtx", "pake rtx", "ada rtx",
        "vga nvidia", "gpu nvidia", "geforce", "rtx", "gtx"
    ],
    "large_vram": [
        "vram gede", "vram besar", "vga gede", "vga besar", "gpu gede", "gpu besar",
        "vram 8gb", "vram 8 gb", "vram 6gb", "vram 6 gb", "vram paling besar", "vga paling besar"
    ],
}

REL_PHRASES = {
    "cheaper": ["lebih murah", "murah dikit", "murahan dikit"],
    "pricier": [
        "lebih mahal", "bagusan", "lebih bagus", "bagusan dikit", "bagus dikit",
        "lebih kencang", "lebih kuat", "kurang kuat", "tidak kuat", "gak kuat",
        "kurang kencang", "kurang sanggup", "tidak sanggup", "gak sanggup",
        "ada yang lebih bagus", "ada yang lebih tinggi", "lebih bagus lagi",
        "yang lebih bagus", "yang lebih tinggi", "yang lebih kencang",
        "penyimpanan gede", "penyimpanan besar", "storage gede", "storage besar",
        "storage lebih besar", "penyimpanan lebih besar", "ssd gede", "ssd besar",
        "harddisk gede", "harddisk besar", "butuh penyimpanan", "butuh storage",
        "vga lebih bagus", "gpu lebih tinggi", "vga lebih kuat", "vga lebih kencang",
        "gpu lebih bagus", "vga lebih tinggi", "gpu lebih kencang"
    ]
}

GPU_EXPLANATION_PHRASES = [
    "pertimbangan penggunaan", "jadi pertimbangan", "fungsi gpu", "pengaruh gpu",
    "penggunaan gpu", "peran gpu", "kenapa butuh gpu", "kenapa harus gpu",
    "beda gpu", "beda vga", "gpu buat apa", "vga buat apa", "pentingnya gpu"
]

def parse_number_amount(num: str, unit: str | None) -> int | None:
    try:
        if unit:
            return int(round(float(num.replace(",", ".")) * 1_000_000))
        digits = re.sub(r"[.,]", "", num)
        v = int(digits)
        return v if v >= 100_000 else None
    except ValueError:
        return None

def extract_budget(norm_text: str) -> dict | None:
    unit = None
    m = re.search(r"\b(?:rp ?)?(\d+(?:[.,]\d+)?) (juta|jutaan)\b", norm_text)
    if m:
        unit = m.group(2)
        amount = parse_number_amount(m.group(1), "juta")
    else:
        m = re.search(r"\brp ?(\d[\d.,]*)", norm_text)
        if m:
            amount = parse_number_amount(m.group(1), None)
        else:
            m = re.search(r"\b(\d{6,9})\b", norm_text)
            amount = parse_number_amount(m.group(1), None) if m else None
            
    if not m or not amount:
        return None
        
    before = norm_text[max(0, m.start() - 30):m.start()]
    after = norm_text[m.end():m.end() + 15]
    for phrase, kind, strict in BUDGET_MARKERS:
        if has_phrase(before, phrase) or has_phrase(before.strip(), phrase) \
                or has_phrase(after, phrase) or before.rstrip().endswith(phrase):
            return {"kind": kind, "amount": amount, "strict": strict}
    if unit == "jutaan":
        return {"kind": "target", "amount": amount, "strict": False}
    return {"kind": "target", "amount": amount, "strict": False}

PRICE_CONFIRM_PHRASES = [
    "lebih mahal ya", "lebih mahal kan", "lebih mahal kah", "kok lebih mahal", "kenapa lebih mahal", "apakah lebih mahal",
    "lebih murah ya", "lebih murah kan", "lebih murah kah", "kok lebih murah", "kenapa lebih murah", "apakah lebih murah",
    "mahalan mana", "murahan mana", "mahalan yang mana", "murahan yang mana",
    "agak mahal ya", "agak lebih mahal ya", "mahal juga ya", "murah juga ya",
    "lebih mahal ya kak", "lebih murah ya kak", "lebih mahal ya min", "lebih murah ya min",
    "lebih mahal dong", "lebih murah dong", "mahalan ini ya", "murahan ini ya",
    "mahalan itu ya", "murahan itu ya"
]

def is_price_confirm_or_inquiry(norm_text: str) -> bool:
    if any(has_phrase(norm_text, p) for p in PRICE_CONFIRM_PHRASES):
        return True
    toks = norm_text.split()
    if any(w in toks for w in ("mahal", "murah", "mahalan", "murahan")):
        if any(w in toks for w in ("lebih", "agak", "kok", "kenapa", "apakah")):
            if any(w in toks for w in ("ya", "kan", "kah", "kok", "kenapa", "apakah", "mana", "dong")):
                return True
    return False

def extract_preferences(norm_text: str) -> dict:
    prefs = []
    for key, phrases in PREF_PHRASES.items():
        if find_phrase(norm_text, phrases):
            prefs.append(key)
    rel = None
    if not is_price_confirm_or_inquiry(norm_text):
        for key, phrases in REL_PHRASES.items():
            if find_phrase(norm_text, phrases):
                rel = key
    if rel:
        prefs = [p for p in prefs if p not in ("cheapest", "most_expensive")]
    return {"prefs": prefs, "rel": rel}

def extract_needs(norm_text: str) -> list[str]:
    found = []
    for tag, phrases in NEED_LEXICON.items():
        if find_phrase(norm_text, phrases):
            found.append(tag)
    if not found and find_phrase(norm_text, IDENTITY_STUDENT):
        found = ["student"]
    return found

def extract_persona(norm_text: str) -> str | None:
    for persona, phrases in PERSONA_LEXICON.items():
        if find_phrase(norm_text, phrases):
            return persona
    return None

def extract_persona_name(norm_text: str) -> str | None:
    for p in ("om aku", "omku", "om", "pamanku", "paman", "papaku", "papa", "ayahku", "ayah",
              "bapakku", "bapak", "mamaku", "mama", "ibuku", "ibu", "tanteku", "tante",
              "bibiku", "bibi", "kakek", "nenek", "anakku", "anak", "adikku", "adik"):
        if has_phrase(norm_text, p):
            if p in ("om aku", "omku", "om", "pamanku", "paman"):
                return "Om"
            if p in ("papaku", "papa", "ayahku", "ayah", "bapakku", "bapak"):
                return "Papa"
            if p in ("mamaku", "mama", "ibuku", "ibu"):
                return "Mama"
            if p in ("tanteku", "tante", "bibiku", "bibi"):
                return "Tante"
            return p.capitalize()
    return None

def extract_user_type(norm_text: str) -> str | None:
    for word, typ in IDENTITY_TYPE.items():
        if find_phrase(norm_text, [word]):
            return typ
    return None

def extract_category(norm_text: str) -> str | None:
    toks = norm_text.split()
    cats = []
    for t in toks:
        clean_t = re.sub(r"(?:lah|kah|pun|nya)$", "", t)
        c = CATEGORY_WORDS.get(t) or CATEGORY_WORDS.get(clean_t)
        if c and c not in cats:
            cats.append(c)
    if not cats:
        return None
    if len(cats) > 1 and "monitor" in cats:
        cats.remove("monitor")
    if "computer" in cats and len(cats) > 1:
        specific = [c for c in cats if c != "computer"]
        if len(specific) == 1:
            return specific[0]
    if len(cats) > 1:
        return "computer"
    return cats[0]

def extract_vendor_negation(norm_text: str) -> dict | None:
    """
    Mendeteksi penolakan/negasi vendor CPU oleh pelanggan.
    Contoh: 'beliau gak mau kalo ryzen', 'jangan amd', 'selain ryzen', 'papa gak suka ryzen'
    """
    text = f" {norm_text.lower()} "
    # Pola 1: negasi sebelum kata vendor
    p1 = re.search(
        r"\b(?:gak|nggak|tidak|jangan|bukan|ogah|anti|hindari|kurang\s+suka|alergi|menolak|selain|kecuali)\s+"
        r"(?:mau\s+)?(?:kalo\s+|kalau\s+)?(?:pake\s+|pakai\s+)?(?:yang\s+)?(?:prosesor\s+|proc\s+|cpu\s+)?"
        r"(ryzen|amd|intel)\b",
        text
    )
    if p1:
        raw_word = p1.group(1)
        return {
            "negated": True,
            "excluded": "amd" if raw_word in ("ryzen", "amd") else "intel",
            "target": "intel" if raw_word in ("ryzen", "amd") else "amd",
            "raw_word": raw_word
        }

    # Pola 2: vendor sebelum negasi
    p2 = re.search(
        r"\b(ryzen|amd|intel)\b.*?\b(?:gak\s+mau|nggak\s+mau|tidak\s+mau|jangan|dihindari|kurang\s+suka)\b",
        text
    )
    if p2:
        raw_word = p2.group(1)
        return {
            "negated": True,
            "excluded": "amd" if raw_word in ("ryzen", "amd") else "intel",
            "target": "intel" if raw_word in ("ryzen", "amd") else "amd",
            "raw_word": raw_word
        }

    # Pola 3: "kalau bisa jangan ryzen"
    p3 = re.search(
        r"\b(?:kalo|kalau)\s+bisa\s+(?:jangan|selain|hindari)\s+(?:pake\s+|pakai\s+)?(ryzen|amd|intel)\b",
        text
    )
    if p3:
        raw_word = p3.group(1)
        return {
            "negated": True,
            "excluded": "amd" if raw_word in ("ryzen", "amd") else "intel",
            "target": "intel" if raw_word in ("ryzen", "amd") else "amd",
            "raw_word": raw_word
        }

    return None

def extract_brand_negation(norm_text: str) -> dict | None:
    """
    Mendeteksi penolakan/negasi merek laptop oleh pelanggan.
    Contoh: 'gak mau acer', 'jangan asus', 'selain lenovo'
    """
    text = f" {norm_text.lower()} "
    for brand, aliases in BRAND_LEXICON.items():
        for alias in aliases:
            p1 = re.search(
                rf"\b(?:gak|nggak|tidak|jangan|bukan|ogah|anti|hindari|kurang\s+suka|alergi|menolak|selain|kecuali)\s+"
                rf"(?:mau\s+)?(?:kalo\s+|kalau\s+)?(?:pake\s+|pakai\s+)?(?:merk\s+|brand\s+)?{re.escape(alias)}\b",
                text
            )
            if p1:
                return {"negated": True, "excluded_brand": brand, "alias": alias}
            p2 = re.search(
                rf"\b{re.escape(alias)}\b.*?\b(?:gak\s+mau|nggak\s+mau|tidak\s+mau|jangan|dihindari)\b",
                text
            )
            if p2:
                return {"negated": True, "excluded_brand": brand, "alias": alias}
    return None

def extract_vendor_os(norm_text: str) -> tuple[str | None, str | None]:
    neg = extract_vendor_negation(norm_text)
    if neg:
        vendor = neg["target"]
    else:
        toks = set(norm_text.split())
        vendor = None
        if "intel" in toks and not toks & {"amd", "ryzen"}:
            vendor = "intel"
        elif toks & {"amd", "ryzen"} and "intel" not in toks:
            vendor = "amd"

    toks = set(norm_text.split())
    os_ = None
    for w in ("windows", "linux", "macos"):
        if w in toks:
            os_ = w
    return vendor, os_

def extract_brand(norm_text: str) -> str | None:
    # Jangan deteksi brand jika sedang dinegasikan ("gak mau acer")
    if extract_brand_negation(norm_text):
        return None
    toks = set(norm_text.split())
    for brand, aliases in BRAND_LEXICON.items():
        for alias in aliases:
            if alias in toks or has_phrase(norm_text, alias):
                return brand
    return None

def detect_attrs(norm_text: str) -> list[str]:
    return [a for a, phrases in ATTR_LEXICON.items() if find_phrase(norm_text, phrases)]

def detect_unavailable(norm_text: str) -> list[str]:
    res = []
    for label, phrases in UNAVAILABLE.items():
        if label == "berat":
            # Cegah salah deteksi jika kata 'berat' digunakan untuk konteks intensitas komputasi/grafis
            if re.search(
                r"\b(?:grafis|gaming|game|render|rendering|kerja|pekerjaan|tugas|aplikasi|software|program|beban|komputasi|multitasking)\s+berat\b|"
                r"\bberat\s+(?:di|untuk|buat)\s+(?:grafis|gaming|game|render|rendering|kerja|komputasi|tugas)\b",
                norm_text
            ):
                continue
        if find_phrase(norm_text, phrases):
            res.append(label)
    return res

def is_meta_critique(norm_text: str) -> bool:
    """Deteksi keluhan pelanggan atas alur CS (misal: 'kurang nangkap kok nawarin', 'ditanya jual apa malah disuruh cerita')."""
    if any(has_phrase(norm_text, p) for p in META_CRITIQUE_PHRASES):
        return True
    if re.search(r"\b(?:belum|kurang|tidak|gak)\b.*\b(?:nangkap|nangkep|paham|ngerti|tahu|tau|bilang|ngomong)\b.*\b(?:nawarin|nawarkan|tawarkan|rekomendasi)\b", norm_text):
        return True
    if re.search(r"\b(?:kok|tapi)\b.*\b(?:nawarin|nawarkan)\b", norm_text):
        return True
    if re.search(r"\b(?:emang|memang)\b.*\b(?:tahu|tau)\b.*\b(?:butuh|mau|gimana)\b", norm_text):
        return True
    if re.search(r"\b(?:tahu|tau) dari mana\b", norm_text):
        return True
    if re.search(r"\b(?:ditanya|tanya)\b.*\bmalah\b", norm_text):
        return True
    if re.search(r"\b(?:malah)\b.*\b(?:nanya|tanya|suruh|cerita|yang lain)\b", norm_text):
        return True
    return False

def is_spec_objection(norm_text: str) -> bool:
    """Deteksi keluhan/keberatan pelanggan atas spesifikasi produk (misal: 'tanggung banget', 'speknya nanggung')."""
    return any(has_phrase(norm_text, p) for p in SPEC_OBJECTION_PHRASES) or bool(re.search(r"\b(?:tanggung|nanggung)\b", norm_text))

def is_uncertain(norm_text: str) -> bool:
    # Pertanyaan daftar produk atau inventaris ("ada apa saja", "jual apa saja") BUKAN ketidakpastian
    if any(has_phrase(norm_text, p) for p in ("ada apa", "jual apa", "punya apa", "produk apa", "tersedia apa")):
        return False
    if not any(has_phrase(norm_text, p) for p in UNCERTAIN_PHRASES):
        return False
    if extract_budget(norm_text) or detect_attrs(norm_text):
        return False
    return True

def is_correction(norm_text: str) -> bool:
    if any(has_phrase(norm_text, p) for p in ("bukan harga", "bukan daftar harga")):
        return True
    return bool(re.search(r"\b(?:tanya|nanya)\b.*\b(?:laptop|produk|desktop|monitor|spek|"
                          r"spesifikasi)\b.*\bbukan\b", norm_text))

def is_hardware_spec_query(norm_text: str) -> bool:
    toks = set(norm_text.split())
    for category_list in HARDWARE_LEXICON.values():
        for phrase in category_list:
            if phrase in toks or has_phrase(norm_text, phrase):
                return True
    return False

def detect_category_guard(norm_text: str) -> str | None:
    """Deteksi pertanyaan ketersediaan kategori produk atau layanan di luar katalog (§19)."""
    toks = norm_text.split()
    if not toks:
        return None
    if any(t in META_NARRATIVE_WORDS for t in toks):
        return None
    # Jika input menyatakan persona penerima, kebutuhan, kategori, budget, brand toko, atau spesifikasi perangkat
    if (
        extract_persona(norm_text)
        or extract_needs(norm_text)
        or extract_category(norm_text)
        or extract_budget(norm_text)
        or extract_brand(norm_text)
        or detect_attrs(norm_text)
        or is_hardware_spec_query(norm_text)
    ):
        return None
    if is_uncertain(norm_text):
        return None
    if any(has_phrase(norm_text, p) for p in (
        "tidak punya info", "gak punya info", "belum punya info", "tanpa info", "gak ada info",
        "kurang info", "mana bisa", "mana mungkin", "masa sih", "kok bisa", "gimana bisa",
        "gak kuat", "tidak kuat", "kurang kuat", "ya gak kuat", "ya tidak kuat",
        "bisa untuk", "bisa buat", "bisa dipake", "bisa dipakai", "bisa pake", "bisa pakai",
        "emang bisa", "emangnya bisa", "bisa gak", "bisa tidak",
        "kuat buat", "kuat untuk", "sanggup buat", "sanggup untuk"
    )):
        return None
    if not any(t in AVAIL_VERBS for t in toks):
        return None
    for t in toks:
        if t in CATEGORY_WORDS:
            return None
    candidates = []
    for t in toks:
        if t in AVAIL_VERBS or t in AVAIL_SKIP or t in NONPRODUCT_WORDS or t in GRAMMAR_WORDS or t.isdigit():
            continue
        for brand_key, brand_aliases in BRAND_LEXICON.items():
            if t == brand_key or t in brand_aliases:
                return None
        for category_list in HARDWARE_LEXICON.values():
            if t in category_list:
                return None
        is_need = False
        for phrases in NEED_LEXICON.values():
            if t in phrases:
                is_need = True
                break
        if is_need:
            return None
        is_persona = False
        for phrases in PERSONA_LEXICON.values():
            if t in phrases:
                is_persona = True
                break
        if is_persona:
            return None
        is_attr = False
        for phrases in ATTR_LEXICON.values():
            if t in phrases:
                is_attr = True
                break
        if is_attr:
            return None
        for phrases in UNAVAILABLE.values():
            if t in phrases:
                is_attr = True
                break
        if is_attr:
            return None
        is_pref = False
        for phrases in REL_PHRASES.values():
            if t in phrases:
                is_pref = True
                break
        if is_pref:
            return None
        for phrases in PREF_PHRASES.values():
            if t in phrases:
                is_pref = True
                break
        if is_pref:
            return None
        candidates.append(t)
    if candidates:
        return candidates[0]
    return None

def is_mismatch(norm_text: str) -> bool:
    return any(has_phrase(norm_text, p) for p in MISMATCH_PHRASES)

def is_insult(norm_text: str) -> bool:
    toks = set(norm_text.split())
    return bool(toks & INSULT_WORDS)

def is_catalog_doubt(norm_text: str) -> bool:
    return any(has_phrase(norm_text, p) for p in CATALOG_DOUBT_PHRASES)

def is_meta_explanation(norm_text: str) -> bool:
    return any(has_phrase(norm_text, p) for p in META_EXPLANATION_PHRASES)

def is_capability_inquiry(norm_text: str) -> bool:
    return any(has_phrase(norm_text, p) for p in CAPABILITY_PHRASES)

def is_banter(norm_text: str) -> bool:
    return any(has_phrase(norm_text, p) for p in BANTER_PHRASES)

CHOICE_OR_REC_PHRASES = [
    "mana yang bagus", "yang bagus mana", "yang bagus apa", "mana yang cocok",
    "yang cocok mana", "yang cocok apa", "mana yang oke", "yang oke apa",
    "yang mana yang bagus", "mana yang lebih bagus", "yang paling bagus", "mana yang rekomen",
    "rekomendasi", "rekomendasikan", "rekomendasi laptop", "rekomendasi pc",
    "rekomendasi desktop", "pilihan apa", "pilihan apa saja", "pilihan apa aja",
    "ada pilihan apa", "kasih pilihan", "tunjukin pilihan", "lihat pilihan",
    "ada rekomendasi", "kasih rekomendasi", "saran apa", "saran kamu apa", "saran kamu yang mana",
    "pilihin", "cariin", "laptop apa", "pc apa", "komputer apa",
    "pilihan laptop", "pilihan komputer", "bagus mana", "cocok mana", "mending mana",
    "pilihan terbaik", "laptop terbaik", "komputer terbaik", "yang mana", "pilihan yang mana",
    "mana", "mana?", "mana produknya", "mana barangnya", "mana pilihannya", "mana opsinya",
    "mana rekomendasinya", "mana laptopnya", "mana pc nya", "mana komputernya",
    "tunjukin", "tunjukkan", "tunjukin dong", "tunjukkan dong", "lihat dong", "liat dong",
    "kasih lihat", "kasih liat", "spill", "spill dong"
]

def is_choice_or_recommendation_query(norm_text: str) -> bool:
    if any(has_phrase(norm_text, p) for p in ("di mana", "dimana", "ke mana", "kemana")):
        return False
    return any(has_phrase(norm_text, p) for p in CHOICE_OR_REC_PHRASES)

def is_persona_insist(norm_text: str) -> bool:
    """Deteksi penegasan bahwa perangkat ditujukan untuk persona keluarga (misal: 'kan mama yang butuh', 'kan buat mama')."""
    daily_tools = {"gemini", "chatgpt", "canva", "zoom", "browsing", "sosmed", "youtube", "office", "word", "excel"}
    if any(t in norm_text.split() for t in daily_tools):
        return False
    if any(has_phrase(norm_text, p) for p in (
        "kan mama yang butuh", "kan papa yang butuh", "kan mama yang pake", "kan papa yang pake",
        "kan buat mama", "kan buat papa", "kan mama", "kan papa", "mama yang butuh", "papa yang butuh",
        "kan tadi buat mama", "kan tadi buat papa"
    )):
        return True
    return bool(re.search(r"\b(?:kan|lah)\b.*\b(?:mama|mamaku|papa|papaku|ortu|ibu|ayah)\b.*\b(?:yang\s+)?(?:butuh|pake|pakai|cari)\b", norm_text))

def is_need_negation(norm_text: str) -> tuple[str, str] | None:
    """Deteksi pernyataan negasi atas aktivitas/kebutuhan (misal: 'mamaku gak kerja', 'mamaku bukan anak sekolah', 'gak main game')."""
    if any(has_phrase(norm_text, p) for p in (
        "gak kerja", "tidak kerja", "bukan buat kerja", "bukan kerja", "mama gak kerja", "mamaku gak kerja",
        "papa gak kerja", "papaku gak kerja", "gak buat kerja", "tidak buat kerja"
    )) or bool(re.search(r"\b(?:bukan|tidak|gak|nggak)\b.*\b(?:buat\s+)?(?:kerja|kantor|bekerja)\b", norm_text)):
        return ("not_work", "kerja")

    if any(has_phrase(norm_text, p) for p in (
        "bukan anak sekolah", "bukan anak sekolahan", "bukan buat sekolah", "bukan buat belajar",
        "bukan buat kuliah", "gak sekolah", "tidak sekolah", "bukan sekolah", "bukan belajar"
    )) or bool(re.search(r"\b(?:bukan|tidak|gak|nggak)\b.*\b(?:anak\s+)?(?:sekolah|belajar|kuliah|mahasiswa)\b", norm_text)):
        return ("not_school", "sekolah")

    if any(has_phrase(norm_text, p) for p in (
        "bukan buat game", "bukan buat ngegame", "bukan buat main game", "gak buat game", "gak buat main game",
        "tidak buat game", "tidak buat main game", "tidak main game", "gak main game", "nggak main game",
        "bukan game", "bukan gamer", "gak main", "tidak main"
    )) or bool(re.search(r"\b(?:bukan|tidak|gak|nggak|ngga)\b.*\b(?:buat\s+)?(?:main\s+)?(?:game|gaming|ngegame)\b", norm_text)):
        return ("not_game", "gaming")

    return None

def is_size_or_weight_objection(norm_text: str) -> tuple[str, str] | None:
    """Deteksi keluhan/keberatan atas dimensi atau bobot fisik perangkat (misal: 'nitro kegedean', 'terlalu berat')."""
    # Deteksi keberatan ukuran / dimensi
    if any(has_phrase(norm_text, p) for p in (
        "kegedean", "kebesaran", "terlalu gede", "terlalu besar", "kegedean sih", "terlalu lebar",
        "lebar banget", "gede banget", "besar banget"
    )) or bool(re.search(r"\b(?:kegedean|kebesaran)\b", norm_text)):
        return ("size", "kegedean")

    # Deteksi keberatan bobot (pastikan bukan 'beban/grafis berat')
    if not re.search(
        r"\b(?:grafis|gaming|game|render|rendering|kerja|pekerjaan|tugas|aplikasi|software|program|beban|komputasi|multitasking)\s+berat\b|"
        r"\bberat\s+(?:di|untuk|buat)\s+(?:grafis|gaming|game|render|rendering|kerja|komputasi|tugas)\b",
        norm_text
    ):
        if any(has_phrase(norm_text, p) for p in (
            "terlalu berat", "berat banget", "berat ya", "keberatan", "keberatan bawa", "bobotnya berat"
        )) or bool(re.search(r"\b(?:terlalu|agak|sangat)\s+berat\b", norm_text)):
            return ("weight", "berat")

    return None

def is_recommendation_request(norm_text: str) -> bool:
    """Deteksi permintaan rekomendasi langsung yang definitif (misal: 'apa rekomendasimu', 'saran kamu apa')."""
    if any(has_phrase(norm_text, p) for p in (
        "apa rekomendasimu", "apa rekomendasi kamu", "rekomendasimu apa", "rekomendasi kamu apa",
        "rekomendasinya apa", "apa rekomendasinya", "rekomendasi terbaik apa",
        "apa saranmu", "apa saran kamu", "saran kamu apa", "saranmu apa", "sarannya apa", "apa sarannya",
        "menurut kamu yang mana", "menurutmu yang mana", "gimana menurutmu", "gimana menurut kamu",
        "enaknya ambil yang mana", "enaknya yang mana", "pilihkan yang mana", "pilihin yang mana",
        "bagusnya ambil yang mana", "bagusnya yang mana", "kamu saranin apa", "kamu rekomendasikan apa",
        "rekomendasi mana", "saran mana"
    )):
        return True
    return bool(re.search(r"\b(?:apa\s+)?(?:rekomendasi|saran)(?:mu| kamu|nya)?\s*(?:apa|mana)?\b", norm_text)) and any(w in norm_text for w in ("rekomendasi", "saran"))

def is_need_insist(norm_text: str) -> str | None:
    """Deteksi penegasan bahwa perangkat hanya untuk kebutuhan tertentu (misal: 'kan buat nonton', 'kan cuma buat nonton')."""
    if any(has_phrase(norm_text, p) for p in (
        "kan buat nonton", "kan untuk nonton", "kan cuma buat nonton", "kan cuma nonton",
        "kan tadi buat nonton", "kan buat nonton doang", "kan cuma buat nonton aja", "cuma buat nonton"
    )):
        return "nonton"
    m = re.search(r"\b(?:kan|lah)\s+(?:cuma\s+|hanya\s+)?(?:buat|untuk|tadi\s+buat|tadi\s+untuk)\s+(nonton|streaming|browsing|youtube|hiburan|santai)\b", norm_text)
    if m:
        return m.group(1)
    return None

TYPE_INVENTORY_PHRASES = [
    "tipe apa", "seri apa", "model apa", "varian apa",
    "ada tipe apa", "ada seri apa", "ada model apa", "ada varian apa",
    "tipe apa aja", "tipe apa saja", "seri apa aja", "seri apa saja",
    "model apa aja", "model apa saja", "varian apa aja", "varian apa saja",
    "tipenya apa", "serinya apa", "modelnya apa", "variannya apa",
    "tipenya apa aja", "tipenya apa saja", "serinya apa aja", "serinya apa saja",
    "modelnya apa aja", "modelnya apa saja",
    "apa saja tipenya", "apa aja tipenya", "apa saja serinya", "apa aja serinya",
    "apa saja modelnya", "apa aja modelnya",
    "ada apa aja", "ada apa saja", "punya apa aja", "punya apa saja",
    "pilihan tipenya", "pilihan tipe", "daftar tipe", "daftar model", "daftar seri",
    "ada tipe", "ada model", "ada seri"
]

ALTERNATIVE_REQUEST_PHRASES = [
    "pilihan lain", "opsi lain", "tipe lain", "model lain", "seri lain", "varian lain",
    "merek lain", "brand lain", "selain ini", "selain itu", "selain tipe ini",
    "selain model ini", "selain produk ini", "selain yang ini", "yang lain", "ada yang lain",
    "ada lagi", "alternatif lain", "rekomendasi lain", "pilihan lainnya", "opsi lainnya",
    "tipe lainnya", "selain dia", "selain seri ini", "produk lain", "laptop tipe lain",
    "desktop tipe lain", "printer tipe lain", "selain laptop ini", "selain printer ini"
]

def is_alternative_request(norm_text: str) -> bool:
    """Deteksi permintaan opsi/tipe/produk alternatif atau lain."""
    if any(has_phrase(norm_text, p) for p in ALTERNATIVE_REQUEST_PHRASES):
        return True
    toks = norm_text.split()
    if "lain" in toks or "lainnya" in toks or "selain" in toks:
        if any(w in toks for w in ("ada", "pilihan", "opsi", "tipe", "seri", "model", "varian", "merek", "brand", "rekomendasi", "alternatif", "apa", "punya", "bisa", "mau")):
            return True
        if "selain" in toks:
            return True
    return False

def is_type_or_inventory_query(norm_text: str) -> bool:
    if any(has_phrase(norm_text, p) for p in TYPE_INVENTORY_PHRASES):
        return True
    return bool(re.search(r"\b(?:ada|tanya|nanya)\b.*\b(?:tipe|seri|model|varian)\s+apa\b", norm_text))

def is_spec_or_rag_query(norm_text: str, state: dict | None = None) -> bool:
    """
    Menentukan apakah pesan pelanggan sudah masuk tahap spesifikasi teknis / rekomendasi produk / query katalog (RAG).
    Jika True -> jalankan RAG (Qdrant & engine deterministik).
    Jika False -> serahkan pada model kecil untuk obrolan awal/chit-chat ramah.
    """
    toks = set(norm_text.split())
    # 0. Permintaan pilihan komputer / rekomendasi katalog / inventaris tipe ("mana yang bagus", "ada tipe apa")
    if is_choice_or_recommendation_query(norm_text) or is_type_or_inventory_query(norm_text) or is_recommendation_request(norm_text) or is_alternative_request(norm_text):
        return True
    # 0A. Keberatan ukuran/bobot atau penegasan kebutuhan
    if is_size_or_weight_objection(norm_text) or is_need_insist(norm_text) or is_need_negation(norm_text):
        return True
    # 0AA. Merek / Brand disebutkan (acer, asus, lenovo, hp, canon, epson, dsb.)
    if extract_brand(norm_text):
        return True
    # 0B. Kategori perangkat disebutkan (laptop, desktop, monitor, komputer)
    if extract_category(norm_text):
        return True
    # 0C. Persona penerima disebutkan (Papa, Mama, Om, dsb.)
    if extract_persona(norm_text):
        return True
    # 0D. Niat beli / transaksi
    if find_phrase(norm_text, PURCHASE_TOKENS):
        return True
    # 0E. Ketidakpastian (terserah, belum tahu, bebas)
    if is_uncertain(norm_text):
        return True
    # 1. Kebutuhan workload (misal: "bikin gambar", "developer", "kuliah", "office", "gaming")
    if extract_needs(norm_text):
        return True
    # 2. Atribut spesifikasi teknis / harga (misal: "spek", "ram", "cpu", "gpu", "storage", "harga", "layar")
    if detect_attrs(norm_text):
        return True
    # 3. Angka / batas budget (misal: "budget 10 juta", "di bawah 8 jt")
    if extract_budget(norm_text):
        return True
    # 4. Atribut yang tidak tersedia di katalog (stok, baterai, garansi, dsb.)
    if detect_unavailable(norm_text):
        return True
    # 5. Vendor CPU / OS / Hardware Spec (intel, amd, ryzen, nvidia, rtx, i7, ram, dsb.)
    if is_hardware_spec_query(norm_text) or extract_vendor_os(norm_text)[0] or extract_vendor_os(norm_text)[1]:
        return True
    # 6. Preferensi ranking / spesifikasi relatif ("paling murah", "ram gede", "lebih kencang", "tidak kuat")
    pref_res = extract_preferences(norm_text)
    if pref_res["prefs"] or pref_res["rel"]:
        return True
    # 7. Kata pengembangan yang ambigu (development, developer, dev)
    if toks & {"development", "developer", "dev"}:
        return True
    # 8. Kata kecocokan beban kerja ("cocok buat...", "bisa buat...")
    if any(has_phrase(norm_text, p) for p in ("cocok untuk", "cocok buat", "emang cocok", "apakah cocok", "bisa buat", "bisa untuk")):
        return True
    # 9. Koreksi spesifikasi ("bukan harga", "tanya spek")
    if is_correction(norm_text):
        return True
    # 10. Jika state sudah menawarkan produk dan pelanggan memilih atau keberatan atas spesifikasi
    if state and state.get("offered_products"):
        if toks & {"pertama", "kedua", "ketiga"} or re.search(r"\b(?:nomor|nomer|no|opsi|pilihan) ?\d\b", norm_text):
            return True
        if any(has_phrase(norm_text, p) for p in ("yang itu", "yang tadi", "produk itu", "barang itu", "opsi lain", "pilihan lain")):
            return True
        if is_mismatch(norm_text) or any(has_phrase(norm_text, p) for p in ("mana bisa", "gak kuat", "tidak kuat", "kurang kuat", "kuatlah")):
            return True
    return False
