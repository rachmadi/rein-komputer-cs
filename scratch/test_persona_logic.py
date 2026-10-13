import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

PERSONA_PATTERNS = [
    r"\b(buat|untuk)?\s*(mama|ibu|bunda|mamaku|ibuku|papa|ayah|bapak|papaku|ayahku|bapakku|anak|anakku|adik|adikku|kakak|istri|suami|kakek|nenek|orang\s*tua)\b"
]

NEED_INDICATORS = [
    "kebutuhan", "dipakai", "dipake", "kerja", "kantor", "kuliah", "sekolah",
    "gaming", "game", "render", "rendering", "editing", "edit", "desain", "foto", "video",
    "blender", "photoshop", "autocad", "sketchup", "revit", "coding", "ngoding", "program",
    "data science", "machine learning", "ai", "kasir", "toko", "admin", "streaming", "obs",
    "musik", "fl studio", "trading", "saham", "crypto", "baterai awet", "ringan", "tipis",
    "ngetik", "browsing", "office", "excel", "word", "belajar", "santai", "nonton", "youtube"
]

def check_intent(text):
    low = text.lower()
    has_need = any(re.search(r"\b" + nd + r"\b", low) for nd in NEED_INDICATORS)
    has_persona = any(re.search(p, low) for p in PERSONA_PATTERNS)
    
    if has_persona and not has_need:
        return "kategori-saja"  # Kebutuhan belum jelas, klarifikasi aktivitas persona
    if has_need:
        return "kebutuhan-jelas"
    return "lainnya"

queries = [
    "Buat mama sih",
    "Buat papa",
    "buat anak sekolah",
    "buat mama nonton youtube dan ngetik",
    "laptop buat edit video 4k",
    "laptop kuliah sehari-hari",
    "komputer buat game berat tapi kasir"
]

for q in queries:
    print(f"'{q}' -> {check_intent(q)}")
