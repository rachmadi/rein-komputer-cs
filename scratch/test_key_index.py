# -*- coding: utf-8 -*-
import sys
import re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.catalog_service import get_active_catalog

cat = get_active_catalog()

def build_product_key_index(catalog):
    # Mapping: product_code -> set of keys
    product_keys = {}
    
    # 1. Koleksi token alfanumerik per produk
    # token_to_codes: token_lower -> set of codes
    token_to_codes = {}
    
    # 2. Koleksi frasa dua kata per produk
    # phrase_to_codes: phrase_lower -> set of codes
    phrase_to_codes = {}
    
    for code, p in catalog.by_code.items():
        product_keys[code] = set()
        
        # Key 1: kode produk
        product_keys[code].add(code)
        
        nama = str(p.get("nama") or "").strip()
        brand = str(p.get("brand") or p.get("merek") or "").strip()
        
        # Key 2: nama lengkap
        if nama:
            product_keys[code].add(nama)
            
        # Key 3: nama tanpa merek di depannya
        nama_no_brand = nama
        if brand and nama.lower().startswith(brand.lower()):
            nama_no_brand = nama[len(brand):].strip().lstrip("-").strip()
            if nama_no_brand and len(nama_no_brand) >= 3 and nama_no_brand.lower() != nama.lower():
                product_keys[code].add(nama_no_brand)
                
        # Untuk token alfanumerik khas:
        # Token nama (termasuk potongan di kiri/kanan tanda hubung) yang panjangnya >=3, berisi huruf dan angka
        raw_tokens = re.split(r"[\s]+", nama)
        sub_tokens = set()
        for rt in raw_tokens:
            cleaned = rt.strip(".,;:()\"'[]{}")
            if cleaned:
                # potong juga di tanda hubung
                parts = cleaned.split("-")
                if len(parts) > 1:
                    for part in parts:
                        p_clean = part.strip(".,;:()\"'[]{}")
                        if p_clean:
                            sub_tokens.add(p_clean)
                sub_tokens.add(cleaned)
                
        for tok in sub_tokens:
            tok_low = tok.lower()
            if len(tok) >= 3 and any(c.isalpha() for c in tok) and any(c.isdigit() for c in tok):
                token_to_codes.setdefault(tok_low, set()).add(code)
                
        # Untuk frasa 2 kata berurutan:
        # nama (tanpa merek, hanya bagian sebelum "+")
        nama_pre_plus = nama.split("+")[0].strip()
        if brand and nama_pre_plus.lower().startswith(brand.lower()):
            nama_pre_plus = nama_pre_plus[len(brand):].strip().lstrip("-").strip()
            
        words = [w.strip(".,;:()\"'[]{}") for w in re.split(r"\s+", nama_pre_plus) if w.strip(".,;:()\"'[]{}")]
        for i in range(len(words) - 1):
            w1 = words[i]
            w2 = words[i+1]
            if len(w1) >= 2 and len(w2) >= 2:
                phrase = f"{w1} {w2}".strip()
                phrase_to_codes.setdefault(phrase.lower(), set()).add(code)
                
    # Tambahkan token alfanumerik yang hanya muncul di satu produk
    for tok_low, codes in token_to_codes.items():
        if len(codes) == 1:
            c = list(codes)[0]
            product_keys[c].add(tok_low)
            
    # Tambahkan frasa dua kata yang hanya muncul di satu produk
    for phr_low, codes in phrase_to_codes.items():
        if len(codes) == 1:
            c = list(codes)[0]
            product_keys[c].add(phr_low)
            
    return product_keys

index = build_product_key_index(cat)
print("Index built for", len(index), "products.")

# Verifikasi tes properti yang diminta:
# 1. "Mac mini M2", "VG27AQ", "T82X", "24MP400", dan "MacBook Pro" cocok ke produk yang benar
test_cases = {
    "Mac mini M2": "KB-D11",
    "VG27AQ": "KB-M05",
    "T82X": "KB-P09",
    "24MP400": "KB-M01",
    "MacBook Pro": "KB-L30"
}

for q, expected_code in test_cases.items():
    found = []
    q_low = q.lower()
    for code, keys in index.items():
        for k in keys:
            pattern = rf"(?<!\w){re.escape(k)}(?!\w)"
            if re.search(pattern, q, re.IGNORECASE):
                found.append((code, k))
                break
    print(f"Query '{q}': expected {expected_code}, found: {found}")
    assert any(c == expected_code for c, _ in found), f"FAILED for {q}"

# 2. Kalimat "cocok untuk gaming, slim, modern, dan layar oled" tidak cocok ke produk mana pun
sentence = "cocok untuk gaming, slim, modern, dan layar oled"
matched_sentence = []
for code, keys in index.items():
    for k in keys:
        pattern = rf"(?<!\w){re.escape(k)}(?!\w)"
        if re.search(pattern, sentence, re.IGNORECASE):
            matched_sentence.append((code, k))
            break
print("Matched for sentence:", matched_sentence)
assert len(matched_sentence) == 0, f"Expected 0 matches for generic sentence, got: {matched_sentence}"

# 3. Setiap kunci hanya cocok ke produknya sendiri
collision_count = 0
for code1, keys1 in index.items():
    for k in keys1:
        pattern = rf"(?<!\w){re.escape(k)}(?!\w)"
        for code2, keys2 in index.items():
            if code1 != code2:
                # Cek apakah kunci k dari code1 cocok ke nama produk code2
                name2 = cat.by_code[code2]["nama"]
                if re.search(pattern, name2, re.IGNORECASE):
                    # print(f"Key '{k}' from {code1} matches name of {code2}: {name2}")
                    collision_count += 1
print("Key cross-matching count across catalog product names:", collision_count)
