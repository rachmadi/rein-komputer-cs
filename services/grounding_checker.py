# -*- coding: utf-8 -*-
"""
services/grounding_checker.py
Pemeriksa Grounding dan Keselamatan Fakta untuk Bobby Computer (Antigravity v2).

Aturan Pemeriksaan:
1. Nominal harga ("Rp ...") yang disebut dalam teks harus ada di FAKTA atau produk_tampil.
2. Dilarang menyebut kode internal katalog (KB-L01, KB-D01, P01, dll).
3. Dilarang menyebut kata teknis/database (None, nan, null, schema, db_path).
4. Dilarang membuat klaim garansi pasti jika fakta toko data_tersedia = False.
5. Panjang teks tidak boleh melebihi batas wajar (maksimal 420 karakter).
"""
from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

EMERGENCY_FALLBACK_TEXT = (
    "Maaf Kak, saya kurang menangkap maksudnya. Boleh diulang, atau mau saya hubungkan ke staf?"
)


class GroundingChecker:
    @staticmethod
    def extract_prices_from_text(text: str) -> List[int]:
        """Ekstrak semua nominal harga rupiah dari teks percakapan."""
        prices = []
        # Cari pola Rp 5.000.000 atau Rp5000000 atau 5 juta
        matches_rp = re.findall(r"rp\s*([\d\.,]+)", text.lower())
        for m in matches_rp:
            clean_digits = re.sub(r"[^\d]", "", m)
            if clean_digits and len(clean_digits) >= 5:  # minimal 10 ribu
                try:
                    prices.append(int(clean_digits))
                except ValueError:
                    pass

        # Cari pola 'X juta' atau 'X jt'
        matches_jt = re.findall(r"(\d+(?:[\.,]\d+)?)\s*(?:juta|jt)\b", text.lower())
        for m in matches_jt:
            val_str = m.replace(",", ".")
            try:
                nominal = int(float(val_str) * 1_000_000)
                prices.append(nominal)
            except ValueError:
                pass

        return prices

    @staticmethod
    def extract_prices_from_facts(fakta: dict, state: dict | None = None) -> set[int]:
        """Ekstrak semua nominal harga yang sah dari fakta dan state."""
        valid_prices = set()

        def recurse_extract(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in ("harga", "harga_idr", "budget", "min_harga", "max_harga") and isinstance(v, (int, float)):
                        valid_prices.add(int(v))
                    elif isinstance(v, (dict, list)):
                        recurse_extract(v)
            elif isinstance(obj, list):
                for item in obj:
                    recurse_extract(item)

        recurse_extract(fakta)
        if state:
            recurse_extract(state.get("produk_tampil", []))
            if state.get("budget"):
                valid_prices.add(int(state["budget"]))

        return valid_prices

    @staticmethod
    def extract_spec_numbers_from_facts(fakta: dict) -> set[int]:
        """Ekstrak angka spesifikasi (RAM GB, SSD GB, tier, dll) dari fakta evaluasi."""
        nums = set()
        eval_prods = fakta.get("evaluasi_produk", [])
        for ep in eval_prods:
            angka = ep.get("angka_aktual", {})
            for v in angka.values():
                if isinstance(v, (int, float)) and v > 0:
                    nums.add(int(v))
            standar = ep.get("standar_profil", {})
            for sub in ("minimum", "rekomendasi"):
                for v in standar.get(sub, {}).values():
                    if isinstance(v, (int, float)) and v > 0:
                        nums.add(int(v))
            for selisih in ("selisih_terhadap_minimum", "selisih_terhadap_rekomendasi"):
                for v in ep.get(selisih, {}).values():
                    if isinstance(v, (int, float)) and v > 0:
                        nums.add(int(v))
        return nums

    def check(self, teks: str, fakta: dict, state: dict | None = None) -> Tuple[bool, List[str]]:
        """
        Memeriksa apakah teks jawaban LLM mematuhi grounding dan keselamatan fakta.
        Mengembalikan (is_valid, list_pelanggaran).
        """
        violations = []
        if not teks or not teks.strip():
            return False, ["Teks jawaban kosong."]

        # 1. Periksa batas panjang karakter (maksimal 420 karakter)
        if len(teks) > 420:
            violations.append(f"Teks terlalu panjang ({len(teks)} karakter, maksimal 420 karakter).")

        # 2. Periksa kebocoran kode internal (KB-L01, KB-D01, KB-P01, P01, P11, dll)
        leak_m = re.findall(r"\b(?:KB-[A-Z]\d+|P\d{2})\b", teks, re.IGNORECASE)
        if leak_m:
            violations.append(f"Menyebut kode internal terlarang: {', '.join(leak_m)}.")

        # 3. Periksa kata teknis sistem / Python / DB
        technical_words = ["none", "nan", "null", "db_path", "pydantic", "schema_valid", "session_state"]
        for tw in technical_words:
            if re.search(rf"\b{tw}\b", teks, re.IGNORECASE):
                violations.append(f"Menyebut istilah teknis internal '{tw}'.")

        # 4. Periksa klaim garansi palsu jika data_tersedia == False
        if fakta.get("topik") == "garansi" and fakta.get("data_tersedia") is False:
            if re.search(r"\bgaransi\s*(?:resmi\s*)?(\d+)\s*(?:tahun|bulan)\b", teks.lower()):
                violations.append("Membuat klaim spesifik durasi garansi padahal data toko mengarahkan ke staf.")

        # 5. Periksa kesahihan nominal harga yang disebut
        mentioned_prices = self.extract_prices_from_text(teks)
        if mentioned_prices:
            valid_prices = self.extract_prices_from_facts(fakta, state=state)
            # Izinkan toleransi jika harga ada di valid_prices atau kelipatan juta yang dekat (misal 5 jt untuk 5.199.000)
            for p in mentioned_prices:
                is_grounded = False
                for vp in valid_prices:
                    # Toleransi pembulatan juta (misal Rp5.199.000 disebut 5 juta)
                    if abs(p - vp) <= 500_000 or p == vp:
                        is_grounded = True
                        break
                if not is_grounded:
                    violations.append(f"Menyebutkan nominal harga Rp{p:,} yang tidak tercatat di fakta.")

        # 6. Periksa kesahihan angka spesifikasi pada evaluasi_kecocokan
        if fakta.get("evaluasi_produk"):
            valid_nums = self.extract_spec_numbers_from_facts(fakta)
            spec_matches = re.findall(r"(?:ram|ssd|vram|tier)\s*(\d+)", teks.lower())
            for sm in spec_matches:
                val = int(sm)
                if val not in valid_nums:
                    violations.append(f"Menyebutkan angka spesifikasi {val} yang tidak ada di fakta evaluasi produk.")
            gb_matches = re.findall(r"(\d+)\s*gb\b", teks.lower())
            for gm in gb_matches:
                val = int(gm)
                if val not in valid_nums:
                    violations.append(f"Menyebutkan kapasitas memori {val} GB yang tidak ada di fakta.")

        is_valid = len(violations) == 0
        return is_valid, violations
