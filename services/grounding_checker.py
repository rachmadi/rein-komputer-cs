# -*- coding: utf-8 -*-
"""
services/grounding_checker.py
Pemeriksa Grounding dan Keselamatan Fakta untuk ReIn Komputer (Antigravity v2).

Aturan Pemeriksaan:
1. Nominal harga ("Rp ...") yang disebut dalam teks harus ada di FAKTA atau produk_tampil.
2. Dilarang menyebut kode internal katalog (KB-L01, KB-D01, P01, dll).
3. Dilarang menyebut kata teknis/database (None, nan, null, schema, db_path).
4. Dilarang membuat klaim garansi pasti jika fakta toko data_tersedia = False.
5. Panjang teks tidak boleh melebihi batas wajar (maksimal 420 karakter).
"""
from __future__ import annotations

import os
import re
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

from core.config import KONTAK_STAF
EMERGENCY_FALLBACK_TEXT = (
    f"Maaf Kak, saya belum bisa menjawab ini dengan tepat. "
    f"Boleh dicoba sekali lagi, atau Kakak bisa menghubungi {KONTAK_STAF}."
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
        """Ekstrak semua nominal harga yang sah dari fakta, state, dan produk_tampil."""
        valid_prices = set()

        def recurse_extract(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in (
                        "harga", "harga_idr", "budget", "min_harga", "max_harga",
                        "harga_termurah_kategori", "harga_termurah_saat_ini",
                        "harga_termahal_kategori", "harga_termahal_saat_ini",
                        "budget_pelanggan", "batas_dipakai", "price", "harga_num"
                    ):
                        if isinstance(v, (int, float)):
                            valid_prices.add(int(v))
                        elif isinstance(v, str):
                            digits = re.sub(r"[^\d]", "", v)
                            if digits and len(digits) >= 5:
                                try:
                                    valid_prices.add(int(digits))
                                except ValueError:
                                    pass
                    elif isinstance(v, str) and ("rp" in v.lower() or "juta" in v.lower() or "jt" in v.lower()):
                        digits = re.sub(r"[^\d]", "", v)
                        if digits and len(digits) >= 5:
                            try:
                                valid_prices.add(int(digits))
                            except ValueError:
                                pass
                    elif isinstance(v, (dict, list)):
                        recurse_extract(v)
            elif isinstance(obj, list):
                for item in obj:
                    recurse_extract(item)

        recurse_extract(fakta)
        if state:
            recurse_extract(state.get("produk_tampil", []))
            recurse_extract(state.get("history_produk_tampil", []))
            b_val = state.get("budget")
            if b_val:
                if isinstance(b_val, (int, float)):
                    valid_prices.add(int(b_val))
                elif isinstance(b_val, str):
                    try:
                        valid_prices.add(int(b_val.strip()))
                    except ValueError:
                        from services.catalog_search import parse_budget_from_text
                        parsed_b = parse_budget_from_text(b_val)
                        if parsed_b:
                            valid_prices.add(parsed_b)

        return valid_prices

    @staticmethod
    def extract_spec_numbers_from_facts(fakta: dict, state: dict | None = None) -> set[int]:
        """Ekstrak angka spesifikasi (RAM GB, SSD GB, tier, dll) dari fakta evaluasi dan produk_tampil."""
        nums = set()
        eval_prods = fakta.get("evaluasi_produk", [])
        for ep in eval_prods:
            angka = ep.get("angka_aktual", {})
            for v in angka.values():
                if isinstance(v, (int, float)) and v > 0:
                    nums.add(int(v))
                    if v >= 512:
                        nums.add(1)
            standar = ep.get("standar_profil", {})
            for sub in ("minimum", "rekomendasi"):
                for v in standar.get(sub, {}).values():
                    if isinstance(v, (int, float)) and v > 0:
                        nums.add(int(v))
                        if v >= 512:
                            nums.add(1)
            for selisih in ("selisih_terhadap_minimum", "selisih_terhadap_rekomendasi"):
                for v in ep.get(selisih, {}).values():
                    if isinstance(v, (int, float)) and v > 0:
                        nums.add(int(v))

        raw_prods = list(fakta.get("produk_list", []) or fakta.get("produk", []) or [])
        if fakta.get("alternatif_cocok"):
            raw_prods.extend(fakta.get("alternatif_cocok", []))
        if state and state.get("produk_tampil"):
            raw_prods.extend(state.get("produk_tampil", []))
        if fakta.get("produk_tampil"):
            raw_prods.extend(fakta.get("produk_tampil", []))

        for p in raw_prods:
            if isinstance(p, dict):
                specs = p.get("spesifikasi", {}) if isinstance(p.get("spesifikasi"), dict) else {}
                ls = p.get("lembar_spesifikasi", {}) if isinstance(p.get("lembar_spesifikasi"), dict) else {}
                for k in ("ram_gb", "storage_ssd_gb", "vram_gb", "ram", "ssd", "vram"):
                    v = specs.get(k) or p.get(k)
                    if isinstance(v, (int, float)) and v > 0:
                        nums.add(int(v))
                        if v >= 512:
                            nums.add(1)
                    elif isinstance(v, str):
                        m_dig = re.findall(r"\b(\d+)\s*(?:gb|tb)\b", v.lower())
                        for md in m_dig:
                            nums.add(int(md))
                for lk, lv in ls.items():
                    if isinstance(lv, (int, float)) and lv > 0:
                        nums.add(int(lv))
                        if lv >= 512:
                            nums.add(1)
                    elif isinstance(lv, str):
                        for dig in re.findall(r"\b(\d+)\b", lv):
                            try:
                                n_val = int(dig)
                                if n_val > 0:
                                    nums.add(n_val)
                                    if n_val >= 512:
                                        nums.add(1)
                            except ValueError:
                                pass
        return nums

    @staticmethod
    def extract_fact_schema_keys(obj) -> set[str]:
        """Ekstrak secara dinamis semua nama key field dari skema fakta."""
        keys = set()
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(k, str):
                    keys.add(k)
                keys.update(GroundingChecker.extract_fact_schema_keys(v))
        elif isinstance(obj, list):
            for item in obj:
                keys.update(GroundingChecker.extract_fact_schema_keys(item))
        return keys

    def check(self, teks: str, fakta: dict, state: dict | None = None, penilaian: dict | None = None) -> Tuple[bool, List[str]]:
        """
        Memeriksa apakah teks jawaban LLM mematuhi grounding dan keselamatan fakta.
        Mengembalikan (is_valid, list_pelanggaran).
        """
        violations = []
        if not teks or not teks.strip():
            return False, ["Teks jawaban kosong."]

        # 1. Periksa batas panjang karakter (maksimal 600 karakter)
        if len(teks) > 600:
            violations.append(f"Teks terlalu panjang ({len(teks)} karakter, maksimal 600 karakter).")

        # 2. Periksa kebocoran kode internal (KB-L01, KB-D01, KB-P01, P01, P11, dll)
        leak_m = re.findall(r"\b(?:KB-[A-Z]\d+|P\d{2})\b", teks, re.IGNORECASE)
        if leak_m:
            violations.append(f"Menyebut kode internal terlarang: {', '.join(leak_m)}.")

        # 3. Periksa istilah skema fakta internal dinamis dan istilah teknis sistem
        system_leak_terms = [
            "tier", "cpu_tier", "selisih", "fakta", "score", "profil_id",
            "ram_gb", "storage_ssd_gb", "gpu_vram_gb", "vram_gb", "gpu_dedicated", "fakta_eksekusi",
            "filter"
        ]
        for term in system_leak_terms:
            if re.search(rf"\b{re.escape(term)}\b", teks, re.IGNORECASE):
                violations.append(f"Menyebut istilah skema/sistem internal '{term}'.")

        leak_syntax = ["(got ", ">=", "<="]
        for ls in leak_syntax:
            if ls in teks.lower():
                violations.append(f"Menyebut sintaks kriteria teknis internal '{ls}'.")

        # Tolak "kendala teknis" kecuali pada sistem_error
        if fakta.get("status") != "sistem_error" and "kendala teknis" in teks.lower():
            violations.append("Menyebut 'kendala teknis' di luar status sistem_error.")

        schema_keys = self.extract_fact_schema_keys(fakta)
        forbidden_schema_terms = set()
        for sk in schema_keys:
            if "_" in sk:
                forbidden_schema_terms.add(sk)

        for term in forbidden_schema_terms:
            if re.search(rf"\b{re.escape(term)}\b", teks, re.IGNORECASE):
                violations.append(f"Menyebut nama field skema fakta internal '{term}'.")

        technical_words = ["none", "nan", "null", "db_path", "pydantic", "schema_valid", "session_state"]
        for tw in technical_words:
            if re.search(rf"\b{tw}\b", teks, re.IGNORECASE):
                violations.append(f"Menyebut istilah teknis internal '{tw}'.")

        # C-Spek: Larang frasa 'sistem mendeteksi' / 'sistem kami mendeteksi'
        if re.search(r"\b(?:sistem(?: kami)? mendeteksi|kami mendeteksi|sistem kami melihat|sistem mencatat)\b", teks, re.IGNORECASE):
            violations.append("Menyebut frasa terlarang 'sistem mendeteksi' / 'sistem kami mendeteksi'.")

        # C-Grounding: Melarang generator menyebut produk memenuhi=False sebagai 'cocok'/'sangat membantu'/'memadai'
        all_eval_prods = list(fakta.get("produk", []) or []) + list(fakta.get("evaluasi_produk", []) or [])
        for p in all_eval_prods:
            if not isinstance(p, dict):
                continue
            cat_min = p.get("catatan_minimum") or {}
            is_unmet = (cat_min.get("memenuhi") is False) or (p.get("status_kecocokan") == "di_bawah_minimum")
            if is_unmet:
                pola_puji = r"\b(?:cocok|sangat\s+cocok|sangat\s+membantu|memadai|cukup\s+memadai)\b"
                if re.search(pola_puji, teks, re.IGNORECASE):
                    pola_negasi = r"\b(?:kurang|tidak|belum|bukan)\s+(?:cocok|memadai|sangat\s+cocok|sangat\s+membantu)\b"
                    puji_matches = list(re.finditer(pola_puji, teks, re.IGNORECASE))
                    for pm in puji_matches:
                        start_pos = max(0, pm.start() - 25)
                        snippet = teks[start_pos:pm.end()].lower()
                        if not re.search(pola_negasi, snippet):
                            p_name = p.get("nama") or "tersebut"
                            violations.append(f"Menyebut produk yang tidak memenuhi spesifikasi ({p_name}) sebagai 'cocok'/'sangat membantu'/'memadai'.")
                            break

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
            valid_nums = self.extract_spec_numbers_from_facts(fakta, state=state)
            spec_matches = re.findall(r"(?:ram|ssd|vram)\s*(?:sebesar\s+)?(\d+)\s*(?:gb|tb)\b", teks.lower())
            for sm in spec_matches:
                val = int(sm)
                if val not in valid_nums:
                    violations.append(f"Menyebutkan angka spesifikasi {val} yang tidak ada di fakta evaluasi produk.")
            gb_matches = re.findall(r"(\d+)\s*gb\b", teks.lower())
            for gm in gb_matches:
                val = int(gm)
                if val not in valid_nums:
                    violations.append(f"Menyebutkan kapasitas memori {val} GB yang tidak ada di fakta.")

        # 7. Konsistensi ketiadaan produk: total_ditemukan = 0 / tidak_ditemukan tidak boleh disertai klaim produk tersedia
        total_ditemukan = fakta.get("total_ditemukan")
        status_fakta = fakta.get("status")
        if (total_ditemukan == 0 or status_fakta in ("tidak_ditemukan", "belum_ada_hasil")):
            klaim_tersedia_patterns = [
                r"(?<!belum\s)(?<!tidak\s)(?<!bukan\s)\b(?:kami ada|kami sediakan|tersedia beberapa|ada beberapa unit|silakan pilih unit|berikut rekomendasi|rekomendasi pilihan)\b",
                r"(?<!belum\s)(?<!tidak\s)\b(?:ada unit|tersedia unit|tersedia opsi|ada pilihan produk|bisa mempertimbangkan pilihan)\b"
            ]
            for pat in klaim_tersedia_patterns:
                if re.search(pat, teks, re.IGNORECASE):
                    violations.append("Mengklaim produk tersedia padahal fakta total_ditemukan = 0 atau status tidak ditemukan.")
                    break

        # D1: Jika belum_dicari == True, generator dilarang menyatakan "ada" atau "tidak ada" tanpa lookup
        if fakta.get("belum_dicari"):
            # Pola dipersempit agar hanya mengenai klaim ketersediaan produk/stok (disertai kata laptop/desktop/printer/komputer/pc/stok/unit/barang)
            klaim_tanpa_lookup = [
                r"\b(?:stok(?:nya)?\s+ada|tersedia\s+stok|stok\s+tersedia)\b",
                r"\b(?:kami\s+(?:punya|ada))\b[^\.\,\;]{0,40}\b(?:stok|unit|barang|produk|laptop|desktop|printer|komputer|pc)\b",
                r"\b(?:tersedia|ready)\s+di\s+toko\b[^\.\,\;]{0,40}\b(?:stok|unit|barang|produk|laptop|desktop|printer|komputer|pc)\b",
                r"\b(?:stok|unit|barang|produk|laptop|desktop|printer|komputer|pc)\b[^\.\,\;]{0,40}\b(?:tersedia|ready)\s+di\s+toko\b",
                r"\b(?:stok(?:nya)?\b[^\.\,\;]*?\b(?:kosong|habis|ada|tersedia))\b",
                r"\b(?:kami\s+tidak\s+(?:jual|sedia))\b[^\.\,\;]{0,40}\b(?:unit|barang|produk|laptop|desktop|printer|komputer|pc)\b",
                r"\b(?:kami\s+tidak\s+(?:ada|punya))\b[^\.\,\;]{0,40}\b(?:stok|unit|barang|produk|laptop|desktop|printer|komputer|pc)\b",
                r"\b(?:tidak\s+ada\s+stok|stok\s+habis|stok\s+kosong)\b",
                r"\b(?:tidak\s+tersedia\s+di\s+toko)\b[^\.\,\;]{0,40}\b(?:stok|unit|barang|produk|laptop|desktop|printer|komputer|pc)\b",
            ]
            for pat in klaim_tanpa_lookup:
                if re.search(pat, teks, re.IGNORECASE):
                    violations.append("Menyatakan produk/stok ada atau tidak ada padahal belum_dicari bernilai True.")
                    break

        # D3: Jangan menyebut "data belum tercatat/belum lengkap" untuk kategori yang ada di katalog
        catalog_cats = ["laptop", "desktop", "printer", "komputer", "pc"]
        cat_present = any(c in teks.lower() for c in catalog_cats) or (state and str(state.get("kategori", "")).lower() in catalog_cats) or (str(fakta.get("kategori", "")).lower() in catalog_cats)
        if cat_present:
            pola_data_belum_ada = [
                r"\b(?:data\s+.*?(?:belum\s+(?:tercatat|lengkap|ada)|tidak\s+lengkap))\b",
                r"\b(?:belum\s+tercatat\s+di\s+(?:sistem|data|katalog))\b",
                r"\b(?:informasi\s+.*?(?:kategori|produk)\s+.*?(?:belum\s+(?:tercatat|lengkap)))\b"
            ]
            for pat in pola_data_belum_ada:
                if re.search(pat, teks, re.IGNORECASE):
                    violations.append("Menyebut 'data belum tercatat/belum lengkap' untuk kategori yang ada di katalog.")
                    break

        # 8. Kartu produk harus cocok dengan produk yang disebut di teks
        produk_list = fakta.get("produk") or fakta.get("perbandingan") or (state.get("produk_tampil") if state else [])
        produk_luar = fakta.get("produk_luar_katalog") or []
        if (produk_list and isinstance(produk_list, list)) or produk_luar:
            known_models = ["vivobook", "ideapad", "aspire", "legion", "tuf", "macbook", "pavilion", "thinkpad", "predator", "yoga", "zenbook", "rog", "loq", "victus", "omen"]
            card_names_str = (" ".join([f"{p.get('nama', '')} {p.get('brand', '')} {p.get('merek', '')}" for p in (produk_list or [])]) + " " + " ".join([str(x) for x in produk_luar])).lower()
            for km in known_models:
                if re.search(rf"\b{km}\b", teks, re.IGNORECASE):
                    if km not in card_names_str:
                        violations.append(f"Teks menyebutkan model '{km}' yang tidak ada pada kartu produk yang ditampilkan.")

        # 9. Pengecualian merek: jika merek_kecuali ada, tidak boleh ada produk merek itu
        merek_kecuali = fakta.get("merek_kecuali") or (state.get("merek_kecuali") if state else None)
        if merek_kecuali:
            mk_clean = str(merek_kecuali).strip().lower()
            # Cek di produk fakta
            for p in (fakta.get("produk") or []):
                p_brand = str(p.get("brand") or p.get("merek") or "").lower()
                p_nama = str(p.get("nama") or "").lower()
                if mk_clean == p_brand or mk_clean in p_brand or mk_clean in p_nama:
                    violations.append(f"Daftar produk memuat merek '{merek_kecuali}' padahal diminta dikecualikan.")
                    break
            # Cek di teks: tidak boleh menawarkan atau merekomendasikan produk merek_kecuali
            if re.search(rf"\b(?:ada|opsi|rekomendasi|pilihan|unit|laptop|desktop)\s+.*?\b{mk_clean}\b", teks, re.IGNORECASE) or re.search(rf"\b{mk_clean}\s+(?:vivobook|zenbook|tuf|rog|aspire|ideapad)\b", teks, re.IGNORECASE):
                violations.append(f"Teks merekomendasikan merek '{merek_kecuali}' yang diminta untuk dikecualikan.")

        # 10. Konsistensi penilaian spesifikasi terhadap tanda selisih (evaluasi_kecocokan)
        if fakta.get("evaluasi_produk"):
            for ep in fakta["evaluasi_produk"]:
                kode = ep.get("kode")
                expected_status = ep.get("status_kecocokan")
                if not expected_status:
                    diff_min = ep.get("selisih_terhadap_minimum", {})
                    diff_rec = ep.get("selisih_terhadap_rekomendasi", {})
                    if any(v < 0 for v in diff_min.values() if isinstance(v, (int, float))):
                        expected_status = "di_bawah_minimum"
                    elif all(v >= 0 for v in diff_rec.values() if isinstance(v, (int, float))):
                        expected_status = "memenuhi_rekomendasi"
                    else:
                        expected_status = "memenuhi_minimum"

                if penilaian and isinstance(penilaian, dict) and kode in penilaian:
                    actual_penilaian = penilaian[kode]
                    if actual_penilaian != expected_status:
                        violations.append(
                            f"Penilaian untuk produk '{kode}' adalah '{actual_penilaian}' bertentangan dengan tanda selisih numerik yang menunjukkan '{expected_status}'."
                        )

        # 11. Larangan halusinasi spesifikasi hardware pada giliran non-produk
        non_product_statuses = (
            "sapaan", "basa_basi", "tidak_jelas",
            "profil_tidak_ditemukan", "profil_tidak_ditemukan_berulang",
            "info_toko", "tanya_kebutuhan"
        )
        status_fakta = fakta.get("status")
        if status_fakta in non_product_statuses:
            if mentioned_prices:
                violations.append(f"Menyebutkan nominal harga pada giliran non-produk ({status_fakta}).")
            if re.search(r"\b\d+\s*(?:gb|tb|ghz|mhz|ram|ssd|vram|core)\b", teks, re.IGNORECASE):
                violations.append(f"Menyebutkan spesifikasi perangkat keras pada giliran non-produk ({status_fakta}).")
            non_prod_models = ["vivobook", "ideapad", "aspire", "legion", "tuf", "macbook", "pavilion", "thinkpad", "predator", "zenbook", "rog", "loq", "victus", "omen"]
            for npm in non_prod_models:
                if re.search(rf"\b{npm}\b", teks, re.IGNORECASE):
                    violations.append(f"Menyebutkan model produk '{npm}' pada giliran non-produk ({status_fakta}).")
                    break

        # 12. Konsistensi kategori di jawaban
        active_prods = fakta.get("produk") or (state.get("produk_tampil") if state else [])
        if active_prods and isinstance(active_prods, list) and len(active_prods) > 0:
            cats = {str(p.get("kategori", "")).lower() for p in active_prods if p.get("kategori")}
            if len(cats) == 1:
                cur_cat = list(cats)[0]
                conflicting = {"laptop", "desktop", "printer", "monitor"} - {cur_cat}
                for c_cat in conflicting:
                    if re.search(rf"\b(?:berikut|ini|rekomendasi|pilihan|unit)\s+(?:adalah\s+)?{c_cat}\b", teks, re.IGNORECASE):
                        violations.append(f"Menyebut kategori '{c_cat}' yang bertentangan dengan kategori produk aktif '{cur_cat}'.")

        # 13. Pemeriksaan konsistensi status tidak_ada_dalam_anggaran (anggaran vs min_cat_price)
        if status_fakta == "tidak_ada_dalam_anggaran":
            min_cat_val = fakta.get("harga_termurah_kategori")
            klaim_ada_anggaran = [
                r"\b(?:tersedia|ada|bisa dapat|dapat)\s+(?:laptop|desktop|unit|produk)?\s*(?:di bawah|dengan harga|seharga)\b"
            ]
            for pat in klaim_ada_anggaran:
                if re.search(pat, teks, re.IGNORECASE) and not re.search(r"\b(?:belum|tidak|bukan)\s+ada\b", teks, re.IGNORECASE):
                    violations.append("Mengklaim produk tersedia dalam anggaran padahal status tidak_ada_dalam_anggaran.")
                    break
            for mp in mentioned_prices:
                if min_cat_val and mp < min_cat_val:
                    violations.append(f"Menyebut nominal harga Rp{mp:,} di bawah harga termurah katalog Rp{min_cat_val:,}.")

        # 14. Pemeriksaan status produk_tidak_di_katalog
        if status_fakta == "produk_tidak_di_katalog":
            klaim_tersedia_katalog = [
                r"\b(?:tersedia di katalog|tersedia di toko kami|kami menjual|stok kami ada)\b"
            ]
            for pat in klaim_tersedia_katalog:
                if re.search(pat, teks, re.IGNORECASE) and not re.search(r"\b(?:tidak|belum)\s+tersedia\b", teks, re.IGNORECASE):
                    violations.append("Mengklaim produk luar katalog tersedia di ReIn Komputer.")
                    break

        # 15. Validasi nilai spesifikasi termuat pada tanya_spesifikasi (F4)
        if status_fakta == "sukses" and (fakta.get("atribut_ditanya") or fakta.get("spesifikasi_produk")):
            specs = fakta.get("spesifikasi_produk") or fakta.get("spesifikasi") or []
            for sp in specs:
                val = sp.get("nilai") or sp.get("nilai_spesifikasi")
                attr = sp.get("atribut")
                if val and attr != "spek_umum":
                    val_str = str(val).lower()
                    val_tokens = [tok for tok in re.split(r"[\s\|\,\;]+", val_str) if len(tok) >= 2 and tok not in ("inci", "fhd", "ips", "ram", "ssd", "ddr4", "ddr5", "tipe")]
                    if val_str not in teks.lower() and not any(tok in teks.lower() for tok in val_tokens):
                        violations.append(f"Teks tanya_spesifikasi tidak memuat nilai spesifikasi yang diminta ({val}).")

        is_valid = len(violations) == 0
        return is_valid, violations
