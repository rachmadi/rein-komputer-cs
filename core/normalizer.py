# -*- coding: utf-8 -*-
"""
Normalisasi input teks sesuai Spesifikasi v1.2 §5A
1. Huruf kecil
2. Buang tanda baca (pertahankan titik/koma dalam angka seperti 12.000.000 atau 9,5 juta)
3. Tanda hubung dan underscore menjadi spasi (ram-nya -> ram nya)
4. Gabungkan/tangani sufiks -nya untuk atribut
5. Singkatan umum (jt->juta, gk/gak/ga/nggak->tidak, yg->yang, utk->untuk, dgn->dengan, bgt->banget, dsb.)
6. Spasi berulang diringkas
7. Pencocokan per token atau frasa utuh, tidak per substring.
"""
from __future__ import annotations
import re

ABBREVIATIONS: dict[str, str] = {
    "jt": "juta",
    "yg": "yang",
    "utk": "untuk",
    "dgn": "dengan",
    "bgt": "banget",
    "gk": "tidak",
    "gak": "tidak",
    "ga": "tidak",
    "nggak": "tidak",
    "ngga": "tidak",
    "enggak": "tidak",
    "tdk": "tidak",
    "udah": "sudah",
    "udh": "sudah",
    "aja": "saja",
    "kalo": "kalau",
    "kl": "kalau",
    "tau": "tahu",
    "gatau": "tidak tahu",
    "makasih": "terima kasih",
    "thx": "terima kasih",
    "thanks": "terima kasih",
    "blm": "belum",
    "lu": "kamu",
    "loe": "kamu",
    "lo": "kamu",
    "gue": "saya",
    "gw": "saya",
    "aku": "saya",
    "sy": "saya",
    "bokap": "papa",
    "nyokap": "mama",
    "ortu": "orang tua",
    "adek": "adik",
    "malem": "malam",
    "met": "selamat",
}

# Stem kata penting agar sufiks -nya dapat dinormalisasi dengan benar
ATTR_STEMS = {
    "ram", "prosesor", "processor", "cpu", "gpu", "vga", "harga", "storage", "ssd",
    "layar", "display", "laptop", "desktop", "monitor", "memori", "memory", "spek",
    "spesifikasi", "windows", "produk", "kapasitas", "warna", "stok", "baterai",
    "garansi", "os", "detail", "berat",
}

NEGATIONS = {"tidak", "bukan"}

def normalize(text: str) -> str:
    """
    Normalisasi string sesuai aturan §5A.
    """
    if not text:
        return ""
    
    t = text.lower()
    
    # Ganti dash, underscore, slash, hyphen menjadi spasi
    t = re.sub(r"[-_/\\\u2013\u2014]", " ", t)
    
    # Hapus karakter selain a-z, 0-9, titik, koma, dan spasi
    t = re.sub(r"[^a-z0-9., ]", " ", t)
    
    # Buang titik/koma yang BUKAN diapit digit (misal: "Halo, Kak!" -> koma hilang, tapi "12.000.000" tetap)
    t = re.sub(r"(?<!\d)[.,]|[.,](?!\d)", " ", t)
    
    # Pisahkan angka yang menempel dengan jt/juta (misal: "12jt" -> "12 juta")
    t = re.sub(r"(\d)(jt|juta|jutaan)\b", r"\1 \2", t)
    
    tokens = t.split()
    processed_tokens: list[str] = []
    
    for tok in tokens:
        # Ekspansi singkatan
        expanded = ABBREVIATIONS.get(tok, tok)
        for part in expanded.split():
            # Tangani sufiks -nya
            if part == "nya":
                continue
            if part.endswith("nya") and part[:-3] in ATTR_STEMS:
                part = part[:-3]
            processed_tokens.append(part)
            
    return " ".join(processed_tokens)


def has_token(norm_text: str, token: str) -> bool:
    """Pencocokan token tunggal (bukan substring)."""
    return f" {token} " in f" {norm_text} "


def has_phrase(norm_text: str, phrase: str) -> bool:
    """Pencocokan frasa utuh per token."""
    return f" {phrase} " in f" {norm_text} "


NEGATIONS = {"tidak", "bukan", "jangan", "tanpa", "belum"}
NEG_CONNECTORS = {"perlu", "usah", "butuh", "mau", "ingin", "buat", "untuk"}

def find_phrase(norm_text: str, phrases: list[str] | set[str]) -> str | None:
    """
    Cari frasa pertama yang cocok dalam teks ternormalisasi,
    dengan mengecek apakah frasa tersebut tidak dinegasikan secara langsung.
    """
    padded = f" {norm_text} "
    for ph in phrases:
        pattern = re.escape(f" {ph} ")
        for m in re.finditer(pattern, padded):
            # Cek token sebelum frasa apakah kata negasi ("tidak", "bukan", "tidak perlu", "bukan untuk")
            before_words = padded[:m.start()].split()
            if before_words:
                if before_words[-1] in NEGATIONS:
                    continue
                if len(before_words) >= 2 and before_words[-2] in NEGATIONS and before_words[-1] in NEG_CONNECTORS:
                    continue
            return ph
    return None
