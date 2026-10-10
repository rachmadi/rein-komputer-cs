# -*- coding: utf-8 -*-
"""
services/catalog_search.py
Modul deterministik murni untuk pencarian, filter, operator, penilaian,
match_report, dan patokan harga katalog Bobby Computer.

Sesuai Antigravity v2:
- Logika fakta dan keselamatan dieksekusi secara deterministik (Python murni).
- Menghasilkan data terstruktur (JSON/dict), bukan templat percakapan.
"""
from __future__ import annotations

import os
import json
import re
import logging
from typing import Any
from core.catalog import Catalog
from services.knowledge_service import get_profile_by_id

logger = logging.getLogger(__name__)


def parse_budget_from_text(text: str) -> int | None:
    """Ekstrak nominal budget (contoh: '10 juta', '10jt', '6-7 juta', '7.500.000') ke integer rupiah (Putaran 13 Butir D)."""
    if not text:
        return None
    text_clean = str(text).strip()

    # 1. Rentang harga (misal '6-7 juta', '6–7 jt', '6 s/d 7 juta', '6 sampai 7 juta') -> ambil batas atas yang sah
    m_range = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:-|–|—|s/?d|sampai)\s*(\d+(?:[.,]\d+)?)\s*(?:-?an\s*)?(?:juta|jt)?\b', text_clean, re.IGNORECASE)
    if m_range:
        upper_str = m_range.group(2).replace(',', '.')
        is_jt = bool(re.search(r'(?:juta|jt)\b', text_clean, re.IGNORECASE))
        try:
            num = float(upper_str)
            if is_jt or num <= 100:
                return int(num * 1_000_000)
            return int(num)
        except ValueError:
            pass

    # 2. Desimal juta (misal '7.5 juta', '7,5 jt')
    m_dec = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:-?an\s*)?(?:juta|jt)\b', text_clean, re.IGNORECASE)
    if m_dec:
        dec_str = m_dec.group(1).replace(',', '.')
        try:
            return int(float(dec_str) * 1_000_000)
        except ValueError:
            pass

    # 3. Format rupiah bertitik/lengkap (misal '7.500.000', 'Rp7.500.000')
    m_dot = re.search(r'(?:rp\s*)?(\d{1,3}(?:\.\d{3}){1,3})\b', text_clean, re.IGNORECASE)
    if m_dot:
        clean = m_dot.group(1).replace('.', '')
        try:
            return int(clean)
        except ValueError:
            pass

    # 4. Format juta biasa
    t_no_punct = text_clean.lower().replace('.', '').replace(',', '')
    m_jt = re.search(r'(\d+)\s*(?:-?an\s*)?(?:juta|jt)\b', t_no_punct)
    if m_jt:
        try:
            return int(m_jt.group(1)) * 1_000_000
        except ValueError:
            pass

    # 5. Angka nominal mandiri (misal 5000000 s/d 100000000)
    for token in re.findall(r'\b\d{6,9}\b', t_no_punct):
        try:
            val = int(token)
            if 500_000 <= val <= 100_000_000:
                return val
        except ValueError:
            pass

    return None


def has_tag(product: dict, tag_str: str) -> bool:
    """Cek apakah produk memiliki tag tertentu."""
    tags = product.get("tags") or []
    return any(tag_str.lower() in str(t).lower() for t in tags)


def clean_specs(p_item: dict) -> str:
    """Format ringkas spesifikasi produk untuk pelaporan."""
    parts = []
    if p_item.get("cpu"):
        parts.append(str(p_item["cpu"]))
    if p_item.get("gpu"):
        parts.append(str(p_item["gpu"]))
    r = p_item.get("ram") or (
        f"{p_item.get('ram_gb')} GB" + (f" {p_item.get('ram_type')}" if p_item.get("ram_type") else "")
        if p_item.get("ram_gb") else None
    )
    if r:
        parts.append(f"RAM {r}")
    if p_item.get("storage"):
        parts.append(str(p_item["storage"]))
    return " | ".join(parts) if parts else "Spesifikasi standar"


_clean_specs = clean_specs


def format_natural_unmet_list(unmet_list: list[str]) -> list[str]:
    """Mengubah daftar kegagalan syarat mentah (misal: 'ram_gb >= 16 (got 8)') menjadi kalimat bahasa alami bebas sintaksis teknis."""
    natural_parts = []
    for item in unmet_list:
        if not item:
            continue
        item_str = str(item).strip()

        m_vram = re.search(r"\bvram(?:_gb)?\b\s*(?:>=|==|=)\s*(\d+)(?:\s*\(got\s*(\d+)\))?", item_str, re.IGNORECASE)
        if m_vram:
            req_v = m_vram.group(1)
            got_v = m_vram.group(2)
            if got_v and got_v != "0":
                natural_parts.append(f"VRAM {got_v} GB (butuh {req_v} GB)")
            else:
                natural_parts.append(f"butuh VRAM {req_v} GB")
            continue

        m_ram = re.search(r"\bram(?:_gb)?\b\s*(?:>=|==|=)\s*(\d+)(?:\s*\(got\s*(\d+)\))?", item_str, re.IGNORECASE)
        if m_ram:
            req_v = m_ram.group(1)
            got_v = m_ram.group(2)
            if got_v:
                natural_parts.append(f"RAM {got_v} GB (butuh {req_v} GB)")
            else:
                natural_parts.append(f"butuh RAM {req_v} GB")
            continue

        m_ssd = re.search(r"(?:storage_ssd_gb|ssd_gb|ssd)\s*(?:>=|==|=)\s*(\d+)(?:\s*\(got\s*(\d+)\))?", item_str, re.IGNORECASE)
        if m_ssd:
            req_v = int(m_ssd.group(1))
            got_v = int(m_ssd.group(2)) if m_ssd.group(2) else None
            req_lbl = f"{req_v//1024} TB" if req_v >= 1024 else f"{req_v} GB"
            if got_v is not None:
                got_lbl = f"{got_v//1024} TB" if got_v >= 1024 else f"{got_v} GB"
                natural_parts.append(f"SSD {got_lbl} (butuh {req_lbl})")
            else:
                natural_parts.append(f"butuh SSD {req_lbl}")
            continue

        m_cpu = re.search(r"cpu(?:_tier)?\s*(?:>=|==|=)\s*(\d+)(?:\s*\(got\s*(\d+)\))?", item_str, re.IGNORECASE)
        if m_cpu:
            req_v = m_cpu.group(1)
            got_v = m_cpu.group(2)
            if got_v:
                natural_parts.append(f"prosesor tingkat {got_v} (butuh tingkat {req_v})")
            else:
                natural_parts.append(f"butuh prosesor tingkat {req_v}")
            continue

        if "gpu_dedicated" in item_str:
            natural_parts.append("belum memiliki GPU dedicated")
            continue

        m_na = re.search(r"^([a-z_]+)\s*\(tidak tersedia\)", item_str, re.IGNORECASE)
        if m_na:
            fld = m_na.group(1).replace("_gb", "").replace("_", " ")
            natural_parts.append(f"{fld} tidak tercantum")
            continue

        cleaned = re.sub(r"\(got\s*[^)]*\)", "", item_str)
        cleaned = re.sub(r"\b([a-z_]+)_gb\b", r"\1", cleaned)
        cleaned = cleaned.replace(">=", "minimal").replace("<=", "maksimal").replace("==", "=").replace("_", " ").strip()
        if cleaned:
            natural_parts.append(cleaned)

    return natural_parts


def format_natural_unmet_requirements(unmet_list: list[str]) -> str:
    """Format daftar syarat yang belum terpenuhi menjadi teks alami bahasa Indonesia."""
    natural_parts = format_natural_unmet_list(unmet_list)
    if natural_parts:
        return f"Belum memenuhi: {', '.join(natural_parts)}"
    return ""


def apply_filters(product: dict, filters: list[dict]) -> tuple[bool, str | None, int, dict]:
    """
    Evaluasi filter kecocokan profil terhadap spesifikasi produk secara deterministik.
    Operator yang didukung: >=, <=, ==, =
    Mengembalikan (passed, failure_reason, penalty, report_dict)
    """
    penalty = 0
    failed_reasons = []
    failed_details = []
    unknown_details = []
    report = {"terpenuhi": [], "tidak_terpenuhi": [], "tidak_diketahui": []}

    for f in filters:
        field = f["field"]
        op = f["op"]
        val = f["value"]
        mandatory = (f.get("strength") == "hard" or f.get("mandatory") is True)

        pval = product.get(field)
        if field == "vram_gb":
            if product.get("gpu_dedicated") == 0:
                pval = 0
            elif product.get("gpu_dedicated") == 1 and pval is None:
                report["tidak_diketahui"].append("VRAM_GB")
                unknown_details.append("VRAM_GB (Dedicated)")
                penalty -= 10
                continue

        if pval is None:
            report["tidak_diketahui"].append(field)
            unknown_details.append(field)
            if mandatory:
                failed_reasons.append(field)
                report["tidak_terpenuhi"].append(f"{field} (tidak tersedia)")
                penalty -= 50
            else:
                penalty -= 5
            continue

        passed = False
        if op not in (">=", "<=", "==", "="):
            raise ValueError(f"Unknown operator: {op}")
        try:
            if op == ">=":
                passed = float(pval) >= float(val)
            elif op == "<=":
                passed = float(pval) <= float(val)
            elif op in ("==", "="):
                passed = str(pval).lower() == str(val).lower()
        except Exception:
            passed = False

        if passed:
            report["terpenuhi"].append(field)
        else:
            report["tidak_terpenuhi"].append(f"{field} {op} {val} (got {pval})")
            if mandatory:
                failed_reasons.append(field)
                failed_details.append(f"{field} {op} {val}")
            else:
                penalty -= int(f.get("penalty", 10))

    if failed_reasons:
        return False, f"Belum memenuhi minimum: {', '.join(failed_reasons)}", penalty, report
    return True, None, penalty, report


def merge_filters(f1: list[dict], f2: list[dict]) -> list[dict]:
    """Gabungkan dua daftar filter profil."""
    return (f1 or []) + (f2 or [])


def _match_legacy_query(p: dict, q: str) -> bool:
    """Pencocokan query lama berbasis merek/kata unik nama produk."""
    q = q.lower()
    brands = ["acer", "asus", "lenovo", "hp", "nitro", "vivobook", "tuf", "ideapad", "legion", "macbook", "apple", "rog"]
    matched_brands = [b for b in brands if re.search(r"\b" + b + r"\b", q)]
    if matched_brands:
        return any(b in p["nama"].lower() for b in matched_brands)

    common_words = [
        "laptop", "notebook", "pc", "desktop", "komputer", "printer", "layar", "monitor",
        "ram", "ssd", "gb", "tb", "jt", "juta", "murah", "di", "bawah", "dibawah", "buat", "untuk",
        "ada", "yang", "aja", "saja", "kalo", "kalau", "mau", "cari"
    ]
    tokens = [w for w in re.findall(r"\w+", q) if not w.isdigit()]
    specific_tokens = [w for w in tokens if w not in common_words]
    if not specific_tokens:
        return True
    return any(w in p["nama"].lower() for w in specific_tokens) or q in str(p.get("tags", "")).lower()


def should_skip_rag(text: str, catalog: Catalog) -> bool:
    """Guard heuristik lama untuk menentukan apakah pencarian query murni melewati RAG."""
    t = text.lower()
    non_intents = ["harga", "cicilan", "jam buka", "lokasi", "diskon", "garansi", "cara bayar", "klaim"]
    greetings = ["halo", "hi", "hai", "p", "terima kasih", "makasih", "apa kabar"]
    if any(f" {k} " in f" {t} " for k in non_intents):
        return True
    if any(f" {k} " in f" {t} " for k in greetings):
        return True
    brands = ["acer", "asus", "lenovo", "hp", "nitro", "vivobook", "tuf", "ideapad", "legion", "macbook", "apple", "rog"]
    for p in catalog.products:
        if p["kode"].lower() in t:
            return True
    for b in brands:
        if re.search(r"\b" + b + r"\b", t) and "buat" not in t and "untuk" not in t and "kebutuhan" not in t:
            return True
    return False


def check_fast_path(text: str, catalog: Catalog, previous_lowest_price: int | None = None) -> tuple[bool, str, dict]:
    """Guard fast-path lama untuk sapaan dan pencarian merek sederhana."""
    t = text.lower().strip()
    greetings = ["halo", "hi", "hai", "p", "terima kasih", "makasih", "apa kabar"]
    if any(t == k or t.startswith(k + " ") for k in greetings):
        return True, "Halo Kak! Ada produk yang sedang dicari hari ini?", {}

    brands = ["acer", "asus", "lenovo", "hp", "nitro", "vivobook", "tuf", "ideapad", "legion", "macbook", "apple", "rog"]
    has_brand = any(b in f" {t} " for b in brands)

    narrowing_keywords = ["lebih murah", "yang lain", "yang asus", "yang ssd", "yang ram", "kalo", "kalau", "aja"]
    is_narrowing = any(k in t for k in narrowing_keywords)

    is_pure_query = (has_brand or "laptop" in t or "komputer" in t or "pc" in t or is_narrowing) and "buat" not in t and "untuk" not in t and "kebutuhan" not in t

    if is_pure_query:
        args = {"query": text}
        if "lebih murah" in t or "yang murah" in t:
            args["max_harga"] = (previous_lowest_price - 1) if previous_lowest_price else 10_000_000
        return True, "Berikut hasil pencarian dari katalog kami:", {"name": "search_catalog", "args": args}

    return False, "", {}


def execute_tool(
    name: str,
    args: dict,
    catalog: Catalog,
    session_offered: list[str] = [],
    user_text: str = "",
    active_profile_id: str | None = None,
    active_category: str | None = None
) -> tuple[str, list[dict], str | None, str | None]:
    """
    Eksekusi tool pencarian katalog Bobby Computer.
    Mengembalikan (teks_fakta, daftar_produk, kategori_aktif, profil_id_aktif).
    """
    if name == "search_catalog":
        if not isinstance(args, dict):
            return json.dumps({"status": "error", "message": "Argumen LLM bukan JSON"}), [], None, None
        explicit_cat = args.get("kategori") or active_category
        if explicit_cat == "all":
            explicit_cat = None
        profil_id = str(args.get("profil_id", ""))
        min_harga = args.get("min_harga")
        max_harga = args.get("max_harga")
        query = str(args.get("query", "")).lower()
        kebutuhan = str(args.get("kebutuhan", ""))
        if not max_harga:
            max_harga = parse_budget_from_text(user_text)

        filters_to_apply = []
        info_profil = ""

        if kebutuhan and not should_skip_rag(kebutuhan, catalog):
            from services.knowledge_service import get_usage_requirements
            reqs = get_usage_requirements(kebutuhan)
            pls = reqs.get("profil", [])
            valid_pls = [
                p for p in pls
                if p.get("tipe") == "profil" and str(p.get("profil_id", "")).startswith("P") and not str(p.get("profil_id", "")).startswith(("G", "M"))
            ]
            if valid_pls:
                if len(valid_pls) == 1:
                    profil_id = valid_pls[0]["profil_id"]
                elif len(valid_pls) >= 2:
                    p1 = get_profile_by_id(valid_pls[0]["profil_id"])
                    p2 = get_profile_by_id(valid_pls[1]["profil_id"])
                    if p1 and p2 and p1.get("tipe") == "profil" and p2.get("tipe") == "profil":
                        filters_to_apply = merge_filters(p1.get("filter", []), p2.get("filter", []))
                        n1 = re.sub(r"^[A-Z]\d{2}\s*[—–\-:]\s*", "", p1.get("judul", "")).strip()
                        n2 = re.sub(r"^[A-Z]\d{2}\s*[—–\-:]\s*", "", p2.get("judul", "")).strip()
                        info_profil = f"Kebutuhan gabungan: {n1} & {n2} (memakai syarat terberat)\n"
                        profil_id = f"{valid_pls[0]['profil_id']},{valid_pls[1]['profil_id']}"
                    else:
                        profil_id = valid_pls[0]["profil_id"]
                else:
                    profil_id = active_profile_id
            else:
                profil_id = None

        if not profil_id and not kebutuhan and active_profile_id:
            profil_id = active_profile_id

        if profil_id:
            ids = [x.strip() for x in str(profil_id).split(",") if x.strip()]
            valid_ids = [x for x in ids if x.startswith("P") and not x.startswith(("G", "M"))]
            profil_id = ",".join(valid_ids) if valid_ids else None

        if profil_id and not filters_to_apply:
            ids = [x.strip() for x in profil_id.split(",") if x.strip()]
            if len(ids) == 1:
                prof_data = get_profile_by_id(ids[0])
                if prof_data:
                    filters_to_apply = prof_data.get("filter", [])
            elif len(ids) >= 2:
                p1 = get_profile_by_id(ids[0])
                p2 = get_profile_by_id(ids[1])
                if p1 and p2 and p1.get("tipe") == "profil" and p2.get("tipe") == "profil":
                    filters_to_apply = merge_filters(p1.get("filter", []), p2.get("filter", []))
                    n1 = re.sub(r"^[A-Z]\d{2}\s*[—–\-:]\s*", "", p1.get("judul") or ids[0]).strip()
                    n2 = re.sub(r"^[A-Z]\d{2}\s*[—–\-:]\s*", "", p2.get("judul") or ids[1]).strip()
                    info_profil = f"Kebutuhan gabungan: {n1} & {n2} (memakai syarat terberat)\n"

        check_text = (query + " " + user_text).lower()

        # Deteksi kebutuhan "baterai awet"
        is_baterai_req = any(k in check_text for k in ["baterai awet", "daya tahan baterai", "batre awet", "baterai tahan lama", "batre tahan lama", "baterainya awet"])
        if is_baterai_req:
            explicit_cat = "laptop"
            profil_id = "P01"
            filters_to_apply = [{"field": "gpu_dedicated", "op": "==", "value": 0, "strength": "hard"}]

        # Parsing spesifikasi generik: RAM, SSD, dan Budget
        # 1. RAM generik
        m_ram_req = re.search(r"\bram\s*(\d+)\s*gb\b|\b(\d+)\s*gb\s*ram\b", check_text)
        if m_ram_req:
            req_ram_val = int(m_ram_req.group(1) or m_ram_req.group(2))
            max_cat_ram = max((p.get("ram_gb") or 0) for p in catalog.products)
            if req_ram_val > max_cat_ram:
                return "Produk tidak tersedia.", [], explicit_cat, None
            filters_to_apply.append({"field": "ram_gb", "op": ">=", "value": req_ram_val, "strength": "hard"})

        # 2. SSD generik (GB / TB)
        m_ssd_req = re.search(r"\bssd\s*(\d+)\s*(tb|gb)\b|\b(\d+)\s*(tb|gb)\s*ssd\b", check_text)
        if m_ssd_req:
            val_num = int(m_ssd_req.group(1) or m_ssd_req.group(3))
            unit = (m_ssd_req.group(2) or m_ssd_req.group(4)).lower()
            req_ssd_val = val_num * 1000 if unit == "tb" else val_num
            max_cat_ssd = max((p.get("storage_ssd_gb") or 0) for p in catalog.products)
            if req_ssd_val > max_cat_ssd:
                return "Produk tidak tersedia.", [], explicit_cat, None
            filters_to_apply.append({"field": "storage_ssd_gb", "op": ">=", "value": req_ssd_val, "strength": "hard"})

        # 3. Budget generik
        if not max_harga:
            max_harga = parse_budget_from_text(check_text)

        if not explicit_cat:
            cat_keywords = {
                "laptop": ("laptop", "notebook"),
                "desktop": ("desktop", "pc meja", "komputer meja", "tower", "all-in-one", "aio", "pc", "komputer"),
                "printer": ("printer", "cetak", "print", "tinta", "ink tank"),
                "monitor": ("monitor", "layar", "display")
            }
            earliest_idx = 9999
            for cname, kwords in cat_keywords.items():
                for kw in kwords:
                    idx = check_text.find(kw)
                    if idx != -1 and idx < earliest_idx:
                        earliest_idx = idx
                        explicit_cat = cname

        brand_filter = args.get("brand")
        if not brand_filter and query:
            try:
                from services.intent_router import detect_brand
                brand_filter = detect_brand(query)
            except ImportError:
                pass

        check_profile_str = str(profil_id or "").upper()
        is_light_profile_id = any(pid in check_profile_str for pid in ["P11", "P01", "P14"])
        check_text = (query + " " + user_text).lower()
        heavy_kw = ["game", "gaming", "gamer", "render", "3d", "blender", "4k", "arsitek", "autocad", "rtx", "gtx"]
        is_heavy = any(k in check_text for k in heavy_kw)
        light_kw = ["hiburan", "nonton", "video", "youtube", "film", "streaming", "browsing", "santai", "sepuh", "tua", "ibu", "ayah", "kakek", "nenek", "belajar", "harian", "anak sekolah", "office", "administrasi"]
        is_light_text = any(k in check_text for k in light_kw)
        is_light_usage = (is_light_profile_id or is_light_text) and not is_heavy

        scored_products = []
        relaxed_products = []
        for p in catalog.products:
            if explicit_cat and p["kategori"] != explicit_cat:
                continue
            if brand_filter:
                p_brand = (p.get("brand") or "").lower()
                p_name = (p.get("nama") or "").lower()
                b_target = "apple" if brand_filter.lower() == "macbook" else brand_filter.lower()
                if b_target not in p_brand and b_target not in p_name:
                    continue
            p_price = p.get("harga_idr") or 0
            if max_harga and p_price > max_harga:
                continue
            if min_harga and p_price < min_harga:
                continue

            passed, reason, penalty, report = apply_filters(p, filters_to_apply)

            if query:
                if not _match_legacy_query(p, query):
                    if "gaming" in query and not has_tag(p, "gaming"):
                        continue
                    if "desain" in query and not has_tag(p, "desain"):
                        continue
                    if "murah" in query and p_price > 10_000_000:
                        continue
                    if "144hz" in query and p.get("refresh_hz", 60) < 144:
                        continue
                    continue

            score = 50 + penalty
            if p["kode"] not in session_offered:
                score += 15

            if is_light_usage:
                # Overkill Spec Penalty untuk profil/kebutuhan santai/ringan & persona sepuh
                if p.get("gpu_dedicated") == 1:
                    score -= 80  # Penalti berat GPU dedicated (panas, bising, boros daya)
                else:
                    score += 20  # Bonus grafis terintegrasi (senyap, hemat daya)

                if (p.get("ram_gb") or 0) > 16:
                    score -= 40  # Penalti RAM jauh di atas rekomendasi

                if (p.get("harga_idr") or 0) > 15_000_000:
                    score -= 50  # Penalti harga jauh di atas kebutuhan

                if p.get("screen_inch") in (14.0, 15.6):
                    score += 15  # Layar nyaman
                if any(k in check_text for k in ["sepuh", "tua", "kakek", "nenek", "ibu", "ayah"]) and p.get("screen_inch") == 15.6:
                    score += 10  # Preferensi layar lebih lega untuk orang tua
            else:
                score += (p.get("cpu_tier") or 0) * 2
                if p.get("gpu_dedicated") == 1:
                    score += 5

            p_output = {
                "kode": p["kode"],
                "nama": p["nama"],
                "harga_idr": p.get("harga_idr"),
                "cpu": p.get("cpu"),
                "gpu": p.get("gpu"),
                "vram_gb": p.get("vram_gb"),
                "ram": p.get("ram"),
                "ram_gb": p.get("ram_gb"),
                "ram_type": p.get("ram_type"),
                "storage": p.get("storage"),
                "screen_inch": p.get("screen_inch"),
                "match_report": report
            }
            if passed:
                scored_products.append((score, p_output))
            else:
                p_output["alasan_gagal"] = reason
                relaxed_products.append((score, p_output))

        if not scored_products and not relaxed_products:
            if "lebih murah" in user_text.lower() or "yang murah" in user_text.lower():
                return "Tidak ada yang lebih murah yang memenuhi kebutuhan ini.", [], explicit_cat, profil_id
            return "Produk tidak tersedia.", [], explicit_cat, profil_id

        # Urutkan menurut kecocokan dengan kebutuhan (skor tertinggi) lalu harga (termurah)
        scored_products.sort(key=lambda x: (x[0], -(x[1].get('harga_idr') or 0)), reverse=True)
        # Urut kandidat relaksasi: sedikit kegagalan dulu (naik), skor tiebreaker (turun)
        relaxed_products.sort(
            key=lambda x: (len(x[1].get("match_report", {}).get("tidak_terpenuhi", [])), -x[0])
        )
        top_prods = [p for s, p in scored_products[:3]]

        has_filter_checked = bool(filters_to_apply)

        if not top_prods:
            top_relaxed = [p for s, p in relaxed_products[:2]]
            if "lebih murah" in user_text.lower() or "yang murah" in user_text.lower():
                res_str = f"{info_profil}Tidak ada yang lebih murah yang memenuhi kebutuhan ini. Kandidat terdekat:\n"
            else:
                res_str = f"{info_profil}Kandidat terdekat:\n"
            for p in top_relaxed:
                mr = p.get("match_report", {})
                unmet = mr.get("tidak_terpenuhi", [])
                fail_lbl = format_natural_unmet_requirements(unmet) or p.get("alasan_gagal", "")
                res_str += f"- {p['nama']} | Rp{p.get('harga_idr',0):,} | {clean_specs(p)}\n  {fail_lbl}\n"
            return res_str, top_relaxed, explicit_cat, profil_id

        if is_baterai_req:
            res_str = "Beberapa pilihan laptop tipis dengan grafis terintegrasi (lebih hemat daya):\n\n"
            for idx, p in enumerate(top_prods):
                res_str += f"{idx+1}. **{p['nama']}** | Rp{p.get('harga_idr',0):,}\n  Spesifikasi: {clean_specs(p)}\n\n"
            return res_str, top_prods, explicit_cat, profil_id

        if not has_filter_checked:
            res_str = "Beberapa pilihan produk kami:\n\n"
        else:
            res_str = f"{info_profil}\n"

        for idx, p in enumerate(top_prods):
            mr = p.get("match_report", {})
            fails = mr.get("tidak_terpenuhi", [])
            unk = mr.get('tidak_diketahui', [])

            if not has_filter_checked:
                icon_prefix = f"{idx+1}."
            else:
                icon = "✅" if not fails else "⚠️"
                if len(fails) >= 2 or ("alasan_gagal" in p and "Belum memenuhi minimum" in str(p.get("alasan_gagal", ""))):
                    icon = "❌"
                if p.get("alasan_gagal") == "VRAM belum tercantum, mohon konfirmasi ke staf":
                    icon = "⚠️"
                icon_prefix = f"{icon} {idx+1}."

            unk_str = f"\n  (Tidak Diketahui: {', '.join(unk)})" if unk else ""
            res_str += f"{icon_prefix} **{p['nama']}** | Rp{p.get('harga_idr',0):,}\n  Spesifikasi: {clean_specs(p)}{unk_str}\n\n"
        return res_str, top_prods, explicit_cat, profil_id

    return json.dumps({"status": "error", "message": f"Tool '{name}' tidak dikenal."}), [], None, None
