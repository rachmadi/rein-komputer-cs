# -*- coding: utf-8 -*-
"""
Agent Tools Module untuk ReIn Komputer Customer Care.
Dua alat modular sesuai Putaran 18b:
1. katalog: pencarian produk (kata_kunci, kategori, merek, budget) atau lembar spesifikasi lengkap (kode_atau_nama).
2. pengetahuan: panduan kebutuhan pengguna, penjelasan teknis, panduan kategori, dan kebijakan toko dari RAG Qdrant.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from pathlib import Path
from typing import Any
import requests

from core.db import get_catalog_inventory
from services.catalog_search import clean_specs
from services.action_engine import build_lembar_spesifikasi
from services.catalog_service import get_active_catalog

logger = logging.getLogger("agent_tools")

KATALOG_SQL: bool = True
KIRIM_FOTO_OLEH_LLM: bool = True
PRODUK_TERDEKAT: bool = False


def _get_catalog_db_path() -> str:
    path = os.getenv("DB_PATH", "data/catalog.db")
    if not os.path.isabs(path):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidate = os.path.join(base_dir, path)
        if os.path.exists(candidate):
            return candidate
    return path


def _parse_numeric(val: Any) -> float | None:
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    m = re.search(r"[-+]?\d*\.?\d+", str(val))
    if m:
        try:
            return float(m.group(0))
        except ValueError:
            return None
    return None


def _parse_bool(val: Any) -> bool | None:
    if val is None or val == "":
        return None
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ("true", "1", "yes", "ya"):
        return True
    if s in ("false", "0", "no", "tidak"):
        return False
    return None


def _extract_spec_value(p: dict, spec_key: str) -> float:
    """Mengekstrak nilai numerik atau biner dari produk berdasarkan kunci filter spek (Putaran 29 Butir 4)."""
    if spec_key == "ram_min_gb":
        val = p.get("ram_gb")
        if val is not None:
            parsed = _parse_numeric(val)
            if parsed is not None:
                return float(parsed)
        ram_s = str(p.get("ram", ""))
        m = re.search(r"(\d+)\s*gb", ram_s, re.IGNORECASE)
        if m:
            return float(m.group(1))
        return 0.0

    elif spec_key == "ssd_min_gb":
        val = p.get("storage_ssd_gb")
        if val is not None:
            parsed = _parse_numeric(val)
            if parsed is not None:
                return float(parsed)
        st_s = str(p.get("storage", ""))
        m = re.search(r"(\d+)\s*(?:gb|tb)\s*(?:nvme\s*)?ssd", st_s, re.IGNORECASE)
        if m:
            n = float(m.group(1))
            if "tb" in st_s.lower():
                n *= 1024
            return n
        return 0.0

    elif spec_key == "vram_min_gb":
        val = p.get("vram_gb")
        if val is not None:
            parsed = _parse_numeric(val)
            if parsed is not None:
                return float(parsed)
        return 0.0

    elif spec_key == "gpu_dedicated":
        val = p.get("gpu_dedicated")
        if val is not None:
            return 1.0 if _parse_bool(val) else 0.0
        return 0.0

    elif spec_key in ("layar_min_inci", "layar_maks_inci"):
        val = p.get("screen_inch")
        if val is not None:
            parsed = _parse_numeric(val)
            if parsed is not None:
                return float(parsed)
        disp_s = str(p.get("display", ""))
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:\"|inch|inci)", disp_s, re.IGNORECASE)
        if m:
            return float(m.group(1))
        return 0.0

    elif spec_key == "refresh_min_hz":
        val = p.get("refresh_hz")
        if val is not None:
            parsed = _parse_numeric(val)
            if parsed is not None:
                return float(parsed)
        disp_s = str(p.get("display", ""))
        m = re.search(r"(\d+)\s*hz", disp_s, re.IGNORECASE)
        if m:
            return float(m.group(1))
        return 0.0

    return 0.0


def _sort_produk_terdekat(products: list[dict], first_spec_key: str) -> list[dict]:
    """Mengurutkan produk menurut atribut filter spek pertama (terbaik ke terburuk), lalu harga naik (Putaran 29 Butir 4b)."""
    def sort_key(p: dict):
        val = _extract_spec_value(p, first_spec_key)
        price = _parse_numeric(p.get("harga") or p.get("harga_idr")) or 0.0
        if first_spec_key == "layar_maks_inci":
            # Untuk batas layar maksimal, semakin kecil semakin mendekati batas
            return (val if val > 0 else 999.0, price)
        else:
            # Nilai terbesar/tertinggi lebih baik
            return (-val, price)

    return sorted(products, key=sort_key)



def _format_rupiah(angka: int | float | None) -> str:
    if angka is None or angka == 0:
        return "Rp0"
    return f"Rp{int(angka):,}".replace(",", ".")


def _format_ringkas(p: dict) -> dict[str, Any]:
    """Format ringkas produk untuk keluaran alat katalog."""
    p_price = p.get("harga") or p.get("harga_idr") or 0
    img_f = (p.get("image_file") or "").strip()
    has_photo = bool(img_f and Path(img_f).is_file())
    return {
        "kode": p.get("kode"),
        "nama": p.get("nama"),
        "kategori": p.get("kategori"),
        "merek": p.get("brand") or p.get("merek"),
        "harga": _format_rupiah(p_price),
        "harga_idr": int(p_price),
        "spek_ringkas": clean_specs(p),
        "usage_text": p.get("usage_text", ""),
        "ada_foto": has_photo
    }


def _search_kb_markdown_all(query: str) -> list[dict[str, Any]]:
    """Pencarian fallback langsung pada berkas markdown panduan_kebutuhan_v2.md di semua tipe chunk."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    kb_path = os.path.join(base_dir, "data", "knowledge", "panduan_kebutuhan_v2.md")
    if not os.path.exists(kb_path):
        return []

    try:
        with open(kb_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        logger.warning(f"Gagal membaca KB file: {e}")
        return []

    # Buang blok komentar HTML dan lewati bagian sebelum ## pertama
    content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
    sections = content.split("\n## ")
    q_tokens = [w for w in re.findall(r"\w+", query.lower()) if len(w) >= 2]
    matched = []

    for i, sec in enumerate(sections):
        if not sec.strip() or (i == 0 and not sec.startswith("## ")):
            continue
        sec_clean = sec.strip()
        sec_clean = "## " + sec_clean if not sec_clean.startswith("## ") else sec_clean
        sec_low = sec_clean.lower()
        score = 0
        for tok in q_tokens:
            if tok in sec_low:
                score += 1
        if score > 0:
            lines = sec_clean.split("\n")
            header = lines[0].replace("## ", "").strip()
            # Tentukan ID dan tipe
            cid = ""
            m_id = re.search(r"-\s*\*\*ID:\*\*\s*([A-Za-z0-9_-]+)", sec_clean)
            if m_id:
                cid = m_id.group(1).strip()
            elif "kebijakan" in header.lower():
                cid = "K01"
            else:
                cid = f"CH_{i}"

            tipe = "panduan"
            if cid.startswith("P"):
                tipe = "profil"
            elif cid.startswith("G"):
                tipe = "panduan_umum"
            elif cid.startswith("M"):
                tipe = "panduan_kategori"
            elif cid.startswith("K") or "kebijakan" in header.lower():
                tipe = "kebijakan_toko"

            clean_title = re.sub(r"^[PGMK]\d+\s*[-—]\s*", "", header).strip()
            body_text = "\n".join(lines[1:])
            trimmed = body_text.strip()
            if len(trimmed) > 800:
                trimmed = trimmed[:800] + "..."

            matched.append((score, {
                "id": cid,
                "judul": clean_title,
                "tipe": tipe,
                "teks": trimmed
            }))

    matched.sort(key=lambda x: -x[0])
    return [item for _, item in matched[:3]]


# =============================================================================
# 1. ALAT KATALOG (Pencarian & Lembar Spesifikasi)
# =============================================================================

def katalog(
    kata_kunci: str | None = None,
    kategori: str | None = None,
    merek: str | None = None,
    budget_min: int | float | None = None,
    budget_max: int | float | None = None,
    kode_atau_nama: str | list[str] | None = None,
    kirim_foto: bool | None = None,
    urutan: str | None = None,
    ram_min_gb: int | float | None = None,
    ssd_min_gb: int | float | None = None,
    gpu_dedicated: bool | None = None,
    vram_min_gb: int | float | None = None,
    layar_min_inci: int | float | None = None,
    layar_maks_inci: int | float | None = None,
    refresh_min_hz: int | float | None = None,
    catalog=None,
    katalog_sql: bool | None = None,
    kirim_foto_oleh_llm: bool | None = None,
    produk_terdekat: bool | None = None
) -> dict[str, Any]:
    """
    Alat katalog toko ReIn Komputer:
    a. Jika kode_atau_nama diisi:
       Kembalikan lembar spesifikasi lengkap (build_lembar_spesifikasi + raw_data).
       Boleh satu atau beberapa produk (dipisahkan koma atau list).
    b. Selain itu: pencarian katalog.
       - Bila KATALOG_SQL aktif: jalankan query SQL berparameter ke tabel products.
       - Kata dalam kata_kunci yang sama dengan nilai filter kategori/merek (termasuk sinonimnya)
         tidak ikut dinilai.
       - Jika tidak ada kata tersisa, kembalikan semua produk yang lolos filter, urut harga.
       - budget_max tetap filter keras (jika kosong, sertakan harga termurah yang ada).
       - Selalu kembalikan total_cocok (jumlah SEMUA produk yang cocok) dan maksimal 10 produk ringkas:
         kode, nama, kategori, harga, spek ringkas, usage_text.
       - Bila urutan diisi ("termurah"|"termahal"): produk diurutkan harga naik/turun sebelum dipotong 10.
    """
    cat_inst = catalog or get_active_catalog()
    all_products = list(cat_inst.by_code.values())
    active_foto_flag = (
        kirim_foto_oleh_llm if kirim_foto_oleh_llm is not None
        else KIRIM_FOTO_OLEH_LLM
    )
    is_kirim_foto = bool(active_foto_flag) and (
        (kirim_foto is True) or (isinstance(kirim_foto, str) and str(kirim_foto).lower() == "true")
    )

    # -------------------------------------------------------------------------
    # Cabang A: Lembar Spesifikasi Lengkap jika kode_atau_nama diisi
    # -------------------------------------------------------------------------
    if kode_atau_nama:
        queries = []
        if isinstance(kode_atau_nama, list):
            queries = [str(x).strip() for x in kode_atau_nama if str(x).strip()]
        elif isinstance(kode_atau_nama, str):
            queries = [x.strip() for x in kode_atau_nama.split(",") if x.strip()]

        matched_results = []
        found_codes = set()
        for q in queries:
            q_upper = q.upper()
            if q_upper in cat_inst.by_code:
                p = cat_inst.by_code[q_upper]
                if p["kode"] not in found_codes:
                    found_codes.add(p["kode"])
                    matched_results.append(p)
                continue

            q_low = q.lower()
            matched = False
            for p in all_products:
                if p["kode"].upper() == q_upper or q_low == str(p.get("nama", "")).lower():
                    if p["kode"] not in found_codes:
                        found_codes.add(p["kode"])
                        matched_results.append(p)
                    matched = True
                    break
            if not matched:
                for p in all_products:
                    if q_low in str(p.get("nama", "")).lower():
                        if p["kode"] not in found_codes:
                            found_codes.add(p["kode"])
                            matched_results.append(p)
                        matched = True
                        break

        if not matched_results:
            res_dict = {
                "status": "tidak_ditemukan",
                "pesan": f"Produk '{kode_atau_nama}' tidak ditemukan di katalog.",
                "total_cocok": 0,
                "detail": []
            }
            if is_kirim_foto:
                res_dict["foto_tersedia"] = []
                res_dict["foto_tidak_tersedia"] = []
            return res_dict

        output_details = []
        for p in matched_results:
            lembar = build_lembar_spesifikasi(p)
            raw_dict = {}
            raw_val = p.get("raw_data")
            if isinstance(raw_val, dict):
                raw_dict = raw_val
            elif isinstance(raw_val, str) and raw_val.strip():
                try:
                    raw_dict = json.loads(raw_val)
                except Exception:
                    raw_dict = {}
            img_f = (p.get("image_file") or "").strip()
            has_photo = bool(img_f and Path(img_f).is_file())
            output_details.append({
                "kode": p.get("kode"),
                "nama": p.get("nama"),
                "harga": _format_rupiah(p.get("harga") or p.get("harga_idr")),
                "lembar_spesifikasi": lembar,
                "raw_data": raw_dict,
                "usage_text": p.get("usage_text", ""),
                "ada_foto": has_photo
            })

        res_dict = {
            "status": "sukses",
            "total_cocok": len(output_details),
            "detail": output_details
        }
        if is_kirim_foto:
            akan_kirim = []
            tidak_ada = []
            for p in matched_results:
                c = p.get("kode")
                if not c:
                    continue
                img_f = (p.get("image_file") or "").strip()
                has_photo = bool(img_f and Path(img_f).is_file())
                if has_photo:
                    akan_kirim.append(c)
                else:
                    tidak_ada.append(c)
            res_dict["foto_tersedia"] = akan_kirim
            res_dict["foto_tidak_tersedia"] = tidak_ada
        return res_dict

    # -------------------------------------------------------------------------
    # Cabang B: Pencarian Katalog
    # -------------------------------------------------------------------------
    inv = get_catalog_inventory()
    valid_cats = {c.lower() for c in inv.get("kategori", [])}
    valid_brands = {b.lower() for b in inv.get("merek", [])}

    cat_synonyms_map = {
        "pc": "desktop", "komputer": "desktop", "all-in-one": "desktop", "aio": "desktop", "desktop": "desktop",
        "notebook": "laptop", "laptop": "laptop",
        "printer": "printer", "print": "printer", "cetak": "printer",
        "monitor": "monitor", "layar": "monitor"
    }

    target_cat = None
    if kategori:
        k_str = str(kategori).strip().lower()
        target_cat = cat_synonyms_map.get(k_str, k_str)

    target_merek = None
    if merek:
        target_merek = str(merek).strip().lower()

    kw_raw = str(kata_kunci).strip().lower() if kata_kunci else ""
    tokens = [w for w in re.findall(r"\w+", kw_raw) if len(w) >= 2]

    # Ekstraksi otomatis filter kategori jika belum diisi eksplisit
    if not target_cat:
        for tok in tokens:
            if tok in cat_synonyms_map:
                target_cat = cat_synonyms_map[tok]
                break

    # Ekstraksi otomatis filter merek jika belum diisi eksplisit
    if not target_merek:
        for tok in tokens:
            if tok in valid_brands:
                target_merek = tok
                break

    # Himpunan kata filter kategori dan merek yang TIDAK ikut dinilai
    filter_words_to_exclude = set()
    if target_cat:
        for syn, main_cat in cat_synonyms_map.items():
            if main_cat == target_cat:
                filter_words_to_exclude.add(syn)
    if target_merek:
        filter_words_to_exclude.update([w for w in re.findall(r"\w+", target_merek) if len(w) >= 2])

    urutan_norm: str | None = None
    if urutan:
        u_clean = str(urutan).strip().lower()
        if u_clean in ("termurah", "murah", "paling murah", "paling_murah"):
            urutan_norm = "termurah"
        elif u_clean in ("termahal", "mahal", "paling mahal", "paling_mahal"):
            urutan_norm = "termahal"

    b_min = _parse_numeric(budget_min)
    b_max = _parse_numeric(budget_max)
    r_min = _parse_numeric(ram_min_gb)
    s_min = _parse_numeric(ssd_min_gb)
    g_ded = _parse_bool(gpu_dedicated)
    v_min = _parse_numeric(vram_min_gb)
    l_min = _parse_numeric(layar_min_inci)
    l_max = _parse_numeric(layar_maks_inci)
    ref_min = _parse_numeric(refresh_min_hz)

    active_produk_terdekat = (
        produk_terdekat if produk_terdekat is not None
        else PRODUK_TERDEKAT
    )
    active_spec_keys = []
    if r_min is not None and r_min > 0:
        active_spec_keys.append("ram_min_gb")
    if s_min is not None and s_min > 0:
        active_spec_keys.append("ssd_min_gb")
    if v_min is not None and v_min > 0:
        active_spec_keys.append("vram_min_gb")
    if g_ded is not None:
        active_spec_keys.append("gpu_dedicated")
    if l_min is not None and l_min > 0:
        active_spec_keys.append("layar_min_inci")
    if l_max is not None and l_max > 0:
        active_spec_keys.append("layar_maks_inci")
    if ref_min is not None and ref_min > 0:
        active_spec_keys.append("refresh_min_hz")

    use_sql = KATALOG_SQL if katalog_sql is None else bool(katalog_sql)

    if use_sql:
        db_path = _get_catalog_db_path()
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        where_base: list[str] = []
        params_base: list[Any] = []

        if target_cat:
            if target_cat in valid_cats:
                where_base.append("LOWER(kategori) = ?")
                params_base.append(target_cat)
            else:
                where_base.append("LOWER(kategori) LIKE ?")
                params_base.append(f"%{target_cat}%")

        if target_merek:
            where_base.append("(LOWER(brand) LIKE ? OR LOWER(nama) LIKE ?)")
            params_base.append(f"%{target_merek}%")
            params_base.append(f"%{target_merek}%")

        if b_min is not None and b_min > 0:
            where_base.append("CAST(harga_idr AS INTEGER) >= ?")
            params_base.append(int(b_min))

        where_specs: list[str] = []
        params_specs: list[Any] = []

        if r_min is not None and r_min > 0:
            where_specs.append("CAST(ram_gb AS INTEGER) >= ?")
            params_specs.append(int(r_min))

        if s_min is not None and s_min > 0:
            where_specs.append("storage_ssd_gb >= ?")
            params_specs.append(int(s_min))

        if g_ded is not None:
            if g_ded:
                where_specs.append("CAST(gpu_dedicated AS INTEGER) = 1")
            else:
                where_specs.append("(gpu_dedicated = 0 OR gpu_dedicated IS NULL)")

        if v_min is not None and v_min > 0:
            where_specs.append("CAST(vram_gb AS INTEGER) >= ?")
            params_specs.append(int(v_min))

        if l_min is not None and l_min > 0:
            where_specs.append("CAST(screen_inch AS REAL) >= ?")
            params_specs.append(float(l_min))

        if l_max is not None and l_max > 0:
            where_specs.append("CAST(screen_inch AS REAL) <= ?")
            params_specs.append(float(l_max))

        if ref_min is not None and ref_min > 0:
            where_specs.append("CAST(refresh_hz AS INTEGER) >= ?")
            params_specs.append(int(ref_min))

        where_clauses = list(where_base) + where_specs
        params = list(params_base) + params_specs

        if b_max is not None and b_max > 0:
            where_with_bmax = list(where_clauses) + ["CAST(harga_idr AS INTEGER) <= ?"]
            params_with_bmax = list(params) + [int(b_max)]
            sql_check = "SELECT kode FROM products"
            if where_with_bmax:
                sql_check += " WHERE " + " AND ".join(where_with_bmax)
            cur.execute(sql_check, params_with_bmax)
            rows_check = cur.fetchall()
            if not rows_check:
                # Cek dulu apakah 0 hasil disebabkan oleh filter spek (Putaran 29 Butir 4)
                if active_produk_terdekat and where_specs:
                    where_base_with_bmax = list(where_base) + ["CAST(harga_idr AS INTEGER) <= ?"]
                    params_base_with_bmax = list(params_base) + [int(b_max)]
                    sql_check_base = "SELECT kode FROM products"
                    if where_base_with_bmax:
                        sql_check_base += " WHERE " + " AND ".join(where_base_with_bmax)
                    cur.execute(sql_check_base, params_base_with_bmax)
                    rows_base = cur.fetchall()
                    if rows_base:
                        pool_fb = [cat_inst.by_code.get(r[0]) or cat_inst.by_code.get(r[0].upper()) for r in rows_base]
                        pool_fb = [p for p in pool_fb if p]
                        conn.close()
                        first_spec_key = active_spec_keys[0] if active_spec_keys else "ram_min_gb"
                        sorted_terdekat = _sort_produk_terdekat(pool_fb, first_spec_key)
                        prods_terdekat = sorted_terdekat[:3]
                        res_dict = {
                            "status": "sukses",
                            "total_cocok": 0,
                            "catatan": (
                                "Tidak ada produk yang memenuhi filter ini. Sampaikan apa adanya; "
                                "bila relevan, tawarkan produk_terdekat dan sebut perbedaannya. "
                                "Jangan menyarankan menaikkan budget bila pelanggan tidak menyebut budget."
                            ),
                            "produk": [],
                            "produk_terdekat": [_format_ringkas(p) for p in prods_terdekat],
                            "urutan": urutan_norm or "termurah"
                        }
                        if is_kirim_foto:
                            akan_kirim = []
                            tidak_ada = []
                            for p in prods_terdekat:
                                c = p.get("kode")
                                if not c:
                                    continue
                                img_f = (p.get("image_file") or "").strip()
                                if bool(img_f and Path(img_f).is_file()):
                                    akan_kirim.append(c)
                                else:
                                    tidak_ada.append(c)
                            res_dict["foto_tersedia"] = akan_kirim
                            res_dict["foto_tidak_tersedia"] = tidak_ada
                        return res_dict

                # melebihi_budget standar bila bukan karena filter spek
                cheapest_sql = "SELECT kode FROM products"
                cheapest_params = list(params)
                if where_clauses:
                    cheapest_sql += " WHERE " + " AND ".join(where_clauses)
                cheapest_sql += " ORDER BY CAST(harga_idr AS INTEGER) ASC LIMIT 1"
                cur.execute(cheapest_sql, cheapest_params)
                ch_row = cur.fetchone()
                if not ch_row:
                    if target_cat:
                        cur.execute("SELECT kode FROM products WHERE LOWER(kategori) = ? ORDER BY CAST(harga_idr AS INTEGER) ASC LIMIT 1", [target_cat])
                        ch_row = cur.fetchone()
                    if not ch_row:
                        cur.execute("SELECT kode FROM products ORDER BY CAST(harga_idr AS INTEGER) ASC LIMIT 1")
                        ch_row = cur.fetchone()
                conn.close()

                cheapest_p = None
                if ch_row:
                    c_code = ch_row[0]
                    cheapest_p = cat_inst.by_code.get(c_code) or cat_inst.by_code.get(c_code.upper())
                p_termurah_info = [_format_ringkas(cheapest_p)] if cheapest_p else []
                msg = (
                    f"Tidak ada produk yang memenuhi kriteria di bawah budget {_format_rupiah(b_max)}. "
                    f"Produk termurah yang tersedia adalah {cheapest_p.get('nama') if cheapest_p else '-'} "
                    f"dengan harga {_format_rupiah(cheapest_p.get('harga') or cheapest_p.get('harga_idr')) if cheapest_p else '-' }."
                )
                res_dict = {
                    "status": "melebihi_budget",
                    "total_cocok": 0,
                    "pesan": msg,
                    "produk_termurah": p_termurah_info,
                    "produk": [],
                    "urutan": urutan_norm
                }
                if is_kirim_foto:
                    res_dict["foto_tersedia"] = []
                    res_dict["foto_tidak_tersedia"] = []
                return res_dict

            where_clauses = where_with_bmax
            params = params_with_bmax

        where_base_exec = list(where_base)
        params_base_exec = list(params_base)
        if b_max is not None and b_max > 0:
            where_base_exec.append("CAST(harga_idr AS INTEGER) <= ?")
            params_base_exec.append(int(b_max))

        order_sql = "ORDER BY CAST(harga_idr AS INTEGER) DESC" if urutan_norm == "termahal" else "ORDER BY CAST(harga_idr AS INTEGER) ASC"
        query_sql = "SELECT kode FROM products"
        if where_clauses:
            query_sql += " WHERE " + " AND ".join(where_clauses)
        query_sql += " " + order_sql

        cur.execute(query_sql, params)
        rows = cur.fetchall()

        # Bila rows kosong dan filter spek diisi (Putaran 29 Butir 4):
        if not rows and active_produk_terdekat and where_specs:
            query_fb_sql = "SELECT kode FROM products"
            if where_base_exec:
                query_fb_sql += " WHERE " + " AND ".join(where_base_exec)
            cur.execute(query_fb_sql, params_base_exec)
            rows_fb = cur.fetchall()
            if rows_fb:
                conn.close()
                pool_fb = [cat_inst.by_code.get(r[0]) or cat_inst.by_code.get(r[0].upper()) for r in rows_fb]
                pool_fb = [p for p in pool_fb if p]
                first_spec_key = active_spec_keys[0] if active_spec_keys else "ram_min_gb"
                sorted_terdekat = _sort_produk_terdekat(pool_fb, first_spec_key)
                prods_terdekat = sorted_terdekat[:3]
                res_dict = {
                    "status": "sukses",
                    "total_cocok": 0,
                    "catatan": (
                        "Tidak ada produk yang memenuhi filter ini. Sampaikan apa adanya; "
                        "bila relevan, tawarkan produk_terdekat dan sebut perbedaannya. "
                        "Jangan menyarankan menaikkan budget bila pelanggan tidak menyebut budget."
                    ),
                    "produk": [],
                    "produk_terdekat": [_format_ringkas(p) for p in prods_terdekat],
                    "urutan": urutan_norm or "termurah"
                }
                if is_kirim_foto:
                    akan_kirim = []
                    tidak_ada = []
                    for p in prods_terdekat:
                        c = p.get("kode")
                        if not c:
                            continue
                        img_f = (p.get("image_file") or "").strip()
                        if bool(img_f and Path(img_f).is_file()):
                            akan_kirim.append(c)
                        else:
                            tidak_ada.append(c)
                    res_dict["foto_tersedia"] = akan_kirim
                    res_dict["foto_tidak_tersedia"] = tidak_ada
                return res_dict

        conn.close()

        pool = []
        for r in rows:
            c_code = r[0]
            p_obj = cat_inst.by_code.get(c_code) or cat_inst.by_code.get(c_code.upper())
            if p_obj:
                pool.append(p_obj)
    else:
        # Jalur legacy Python filtering
        pool = list(all_products)

        # Filter Kategori
        if target_cat:
            if target_cat in valid_cats:
                pool = [p for p in pool if str(p.get("kategori", "")).lower() == target_cat]
            else:
                pool = [p for p in pool if target_cat in str(p.get("kategori", "")).lower()]

        # Filter Merek
        if target_merek:
            pool = [
                p for p in pool
                if target_merek in str(p.get("brand", "")).lower() or target_merek in str(p.get("nama", "")).lower()
            ]

        # Filter Budget Min
        if b_min is not None and b_min > 0:
            pool = [p for p in pool if (p.get("harga") or p.get("harga_idr") or 0) >= b_min]

        # Filter Budget Max
        if b_max is not None and b_max > 0:
            under_budget = [p for p in pool if (p.get("harga") or p.get("harga_idr") or 0) <= b_max]
            if not under_budget:
                cheapest_source = pool if pool else (all_products if not target_cat else [p for p in all_products if p.get('kategori') == target_cat])
                cheapest_sorted = sorted(cheapest_source, key=lambda p: (p.get("harga") or p.get("harga_idr") or float("inf")))
                cheapest_p = cheapest_sorted[0] if cheapest_sorted else None
                p_termurah_info = [_format_ringkas(cheapest_p)] if cheapest_p else []
                msg = (
                    f"Tidak ada produk yang memenuhi kriteria di bawah budget {_format_rupiah(b_max)}. "
                    f"Produk termurah yang tersedia adalah {cheapest_p.get('nama') if cheapest_p else '-'} "
                    f"dengan harga {_format_rupiah(cheapest_p.get('harga') or cheapest_p.get('harga_idr')) if cheapest_p else '-' }."
                )
                res_dict = {
                    "status": "melebihi_budget",
                    "total_cocok": 0,
                    "pesan": msg,
                    "produk_termurah": p_termurah_info,
                    "produk": [],
                    "urutan": urutan_norm
                }
                if is_kirim_foto:
                    res_dict["foto_tersedia"] = []
                    res_dict["foto_tidak_tersedia"] = []
                return res_dict
            pool = under_budget

    # Kata yang tersisa untuk dinilai
    scoring_tokens = [w for w in tokens if w not in filter_words_to_exclude]

    if scoring_tokens:
        scored_pool = []
        for p in pool:
            name_text = str(p.get("nama", "")).lower()
            cat_text = str(p.get("kategori", "")).lower()
            brand_text = str(p.get("brand", "")).lower()
            usage_text = str(p.get("usage_text", "")).lower()
            tags = p.get("tags") or []
            tags_text = " ".join(str(t).lower() for t in tags) if isinstance(tags, list) else str(tags).lower()

            raw_dict = {}
            raw_val = p.get("raw_data")
            if isinstance(raw_val, dict):
                raw_dict = raw_val
            elif isinstance(raw_val, str) and raw_val.strip():
                try:
                    raw_dict = json.loads(raw_val)
                except Exception:
                    raw_dict = {}
            raw_text = " ".join(f"{k} {v}" for k, v in raw_dict.items()).lower()
            specs_text = f"{p.get('cpu', '')} {p.get('gpu', '')} {p.get('ram', '')} {p.get('storage', '')} {p.get('display', '')}".lower()

            score = 0
            # Cek kecocokan frasa gabungan sisa
            scoring_phrase = " ".join(scoring_tokens)
            if len(scoring_tokens) > 1 and scoring_phrase in name_text:
                score += 50

            for tok in scoring_tokens:
                tok_score = 0
                if tok in name_text:
                    tok_score = max(tok_score, 25)
                    if re.search(rf"\b{re.escape(tok)}\b", name_text):
                        tok_score = max(tok_score, 35)
                if tok in brand_text:
                    tok_score = max(tok_score, 15)
                if tok in raw_text:
                    tok_score = max(tok_score, 20)
                if tok in usage_text:
                    tok_score = max(tok_score, 15)
                if tok in tags_text:
                    tok_score = max(tok_score, 15)
                if tok in specs_text:
                    tok_score = max(tok_score, 10)
                score += tok_score

            if score > 0:
                scored_pool.append((score, p))

        # Putaran 28 Butir 4b: jika hasil tetap 0 karena kata kunci, sertakan produk_di_kategori dan catatan
        if pool and not scored_pool:
            kw_str = kata_kunci if kata_kunci is not None else " ".join(scoring_tokens)
            k_name = target_cat or (target_merek if target_merek else "kategori ini")

            if urutan_norm == "termahal":
                cat_products = sorted(pool, key=lambda p: -(p.get("harga") or p.get("harga_idr") or 0))
            else:
                cat_products = sorted(pool, key=lambda p: (p.get("harga") or p.get("harga_idr") or 0))

            p_kategori_info = [_format_ringkas(p) for p in cat_products[:10]]

            res_dict = {
                "status": "sukses",
                "total_cocok": 0,
                "catatan": (
                    f"Kata kunci '{kw_str}' tidak cocok dengan produk mana pun; "
                    f"berikut produk yang ada di kategori {k_name}. "
                    "Jangan sebut produk atau harga di luar daftar ini."
                ),
                "produk": [],
                "produk_di_kategori": p_kategori_info,
                "urutan": urutan_norm or "termurah"
            }
            if is_kirim_foto:
                akan_kirim = []
                tidak_ada = []
                for p in cat_products[:10]:
                    c = p.get("kode")
                    if not c:
                        continue
                    img_f = (p.get("image_file") or "").strip()
                    has_photo = bool(img_f and Path(img_f).is_file())
                    if has_photo:
                        akan_kirim.append(c)
                    else:
                        tidak_ada.append(c)
                res_dict["foto_tersedia"] = akan_kirim
                res_dict["foto_tidak_tersedia"] = tidak_ada
            return res_dict

        if urutan_norm == "termurah":
            scored_pool.sort(key=lambda item: (item[1].get("harga") or item[1].get("harga_idr") or 0))
        elif urutan_norm == "termahal":
            scored_pool.sort(key=lambda item: -(item[1].get("harga") or item[1].get("harga_idr") or 0))
        else:
            scored_pool.sort(key=lambda item: (-item[0], item[1].get("harga") or item[1].get("harga_idr") or 0))
        pool = [item[1] for item in scored_pool]
    else:
        # Jika tidak ada kata tersisa, urutkan berdasarkan harga
        if urutan_norm == "termurah":
            pool.sort(key=lambda p: (p.get("harga") or p.get("harga_idr") or 0))
        elif urutan_norm == "termahal":
            pool.sort(key=lambda p: -(p.get("harga") or p.get("harga_idr") or 0))
        else:
            pool.sort(key=lambda p: (p.get("harga") or p.get("harga_idr") or 0))

    res_dict = {
        "status": "sukses",
        "total_cocok": len(pool),
        "produk": [_format_ringkas(p) for p in pool[:10]],
        "urutan": urutan_norm
    }
    if is_kirim_foto:
        akan_kirim = []
        tidak_ada = []
        for p in pool[:10]:
            c = p.get("kode")
            if not c:
                continue
            img_f = (p.get("image_file") or "").strip()
            has_photo = bool(img_f and Path(img_f).is_file())
            if has_photo:
                akan_kirim.append(c)
            else:
                tidak_ada.append(c)
        res_dict["foto_tersedia"] = akan_kirim
        res_dict["foto_tidak_tersedia"] = tidak_ada
    return res_dict


# =============================================================================
# 2. ALAT PENGETAHUAN (RAG Qdrant untuk Semua Tipe Chunk)
# =============================================================================

PENGETAHUAN_GABUNGAN: bool = False
PENGETAHUAN_TOPK: int = int(os.getenv("PENGETAHUAN_TOPK", "3"))
CATATAN_PENGETAHUAN_KATALOG: bool = False


def _combine_qdrant_and_keyword(qdrant_items: list[dict], kw_items: list[dict], limit: int = 3) -> list[dict]:
    """Menggabungkan hasil Qdrant dan pencarian kata kunci sesuai urutan Putaran 20 Butir 3b."""
    q_dict = {it["id"]: it for it in qdrant_items if it.get("id")}
    kw_dict = {it["id"]: it for it in kw_items if it.get("id")}

    q_ids = [it["id"] for it in qdrant_items if it.get("id")]
    kw_ids = [it["id"] for it in kw_items if it.get("id")]

    both_ids = [qid for qid in q_ids if qid in kw_dict]
    rest_q_ids = [qid for qid in q_ids if qid not in both_ids]
    rest_kw_ids = [kid for kid in kw_ids if kid not in both_ids and kid not in rest_q_ids]

    ordered_ids = both_ids + rest_q_ids + rest_kw_ids

    final_items = []
    seen = set()
    for cid in ordered_ids:
        if cid not in seen:
            seen.add(cid)
            it = q_dict.get(cid) or kw_dict.get(cid)
            if it:
                final_items.append(it)
    return final_items[:limit]


def pengetahuan(
    pertanyaan: str,
    top_k: Optional[int] = None,
    catatan_pengetahuan_katalog: Optional[bool] = None
) -> dict[str, Any]:
    """
    Mencari panduan kebutuhan pengguna, penjelasan dan pertimbangan teknis komponen,
    panduan memilih kategori, atau kebijakan resmi toko ReIn Komputer.
    Cari ke SEMUA tipe chunk (G, P, M, kebijakan toko) di Qdrant.
    Kembalikan PENGETAHUAN_TOPK chunk teratas beserta ID dan judul bersih.
    """
    active_catatan = (
        CATATAN_PENGETAHUAN_KATALOG if catatan_pengetahuan_katalog is None
        else bool(catatan_pengetahuan_katalog)
    )
    q_str = str(pertanyaan or "").strip()
    if not q_str:
        res_empty = {
            "status": "tidak_ada_input",
            "pesan": "Pertanyaan belum diisi.",
            "total_cocok": 0,
            "pengetahuan": []
        }
        if active_catatan:
            res_empty["catatan"] = "Ini panduan, bukan daftar produk. Bila pelanggan bertanya apakah toko menjual sesuatu atau meminta rekomendasi, panggil katalog juga sebelum menjawab."
        return res_empty

    limit_k = top_k if top_k is not None else PENGETAHUAN_TOPK
    hasil_chunks = []
    sumber = "qdrant"
    alasan_cadangan = None
    qdrant_exception = None

    # 1. Cari via Qdrant (semua tipe chunk)
    try:
        from services.catalog_service import QDRANT_URL, get_embedding
        vec = get_embedding(q_str.lower())
        if not vec:
            qdrant_exception = "embedding_gagal"
        else:
            col_name = os.getenv("QDRANT_KNOWLEDGE_COLLECTION", "computer_knowledge")
            url = f"{QDRANT_URL}/collections/{col_name}/points/search"
            payload = {
                "vector": vec,
                "limit": limit_k,
                "with_payload": True
            }
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                pts = resp.json().get("result", [])
                for pt in pts:
                    pld = pt.get("payload", {})
                    cid = pld.get("id") or ""
                    raw_title = pld.get("judul") or ""
                    clean_title = re.sub(r"^[PGMK]\d+\s*[-—]\s*", "", raw_title).strip()
                    raw_text = pld.get("text") or ""
                    trimmed_text = raw_text.replace("## ", "").strip()
                    if len(trimmed_text) > 800:
                        trimmed_text = trimmed_text[:800] + "..."
                    hasil_chunks.append({
                        "id": cid,
                        "judul": clean_title,
                        "tipe": pld.get("tipe"),
                        "teks": trimmed_text
                    })
            else:
                qdrant_exception = f"http_{resp.status_code}"
    except Exception as e:
        logger.warning(f"Qdrant lookup failed in pengetahuan: {e}")
        qdrant_exception = str(e)

    # 2. Penggabungan atau fallback
    if PENGETAHUAN_GABUNGAN:
        kw_items = _search_kb_markdown_all(q_str)
        hasil_chunks = _combine_qdrant_and_keyword(hasil_chunks, kw_items, limit=limit_k)
        sumber = "gabungan"
    elif not hasil_chunks:
        # Fallback jika Qdrant gagal atau tidak menemukan hasil
        sumber = "kata_kunci"
        alasan_cadangan = qdrant_exception if qdrant_exception else "qdrant_kosong"
        hasil_chunks = _search_kb_markdown_all(q_str)

    res = {
        "status": "sukses",
        "pertanyaan": q_str,
        "total_cocok": len(hasil_chunks),
        "pengetahuan": hasil_chunks[:limit_k],
        "sumber": sumber
    }
    if sumber == "kata_kunci":
        res["alasan_cadangan"] = alasan_cadangan or "qdrant_kosong"
    if active_catatan:
        res["catatan"] = "Ini panduan, bukan daftar produk. Bila pelanggan bertanya apakah toko menjual sesuatu atau meminta rekomendasi, panggil katalog juga sebelum menjawab."
    return res


# =============================================================================
# KOMPATIBILITAS MUNDUR UNTUK ALAT LAMA
# =============================================================================

def cari_produk(
    kata_kunci: str | None = None,
    kategori: str | None = None,
    merek: str | None = None,
    budget_max: int | float | None = None,
    budget_min: int | float | None = None,
    urutan: str | None = None,
    ram_min_gb: int | float | None = None,
    ssd_min_gb: int | float | None = None,
    gpu_dedicated: bool | None = None,
    vram_min_gb: int | float | None = None,
    layar_min_inci: int | float | None = None,
    layar_maks_inci: int | float | None = None,
    refresh_min_hz: int | float | None = None,
    kirim_foto: bool | None = None,
    catalog=None,
    katalog_sql: bool | None = None,
    kirim_foto_oleh_llm: bool | None = None
) -> dict[str, Any]:
    """Kompatibilitas mundur: memetakan ke fungsi katalog."""
    return katalog(
        kata_kunci=kata_kunci,
        kategori=kategori,
        merek=merek,
        budget_min=budget_min,
        budget_max=budget_max,
        urutan=urutan,
        ram_min_gb=ram_min_gb,
        ssd_min_gb=ssd_min_gb,
        gpu_dedicated=gpu_dedicated,
        vram_min_gb=vram_min_gb,
        layar_min_inci=layar_min_inci,
        layar_maks_inci=layar_maks_inci,
        refresh_min_hz=refresh_min_hz,
        kirim_foto=kirim_foto,
        catalog=catalog,
        katalog_sql=katalog_sql,
        kirim_foto_oleh_llm=kirim_foto_oleh_llm
    )


def detail_produk(kode_atau_nama: str | list[str], catalog=None) -> dict[str, Any]:
    """Kompatibilitas mundur: memetakan ke fungsi katalog dengan kode_atau_nama."""
    return katalog(kode_atau_nama=kode_atau_nama, catalog=catalog)


def pengetahuan_kebutuhan(kebutuhan: str) -> dict[str, Any]:
    """Kompatibilitas mundur: memetakan ke fungsi pengetahuan."""
    res = pengetahuan(pertanyaan=kebutuhan)
    return {
        "status": res.get("status", "sukses"),
        "kebutuhan_ditanyakan": kebutuhan,
        "profil_rekomendasi": [
            {
                "profil_id": p.get("id"),
                "judul": p.get("judul"),
                "panduan_spek": p.get("teks")
            }
            for p in res.get("pengetahuan", [])
        ]
    }


def info_toko(topik: str | None = None) -> dict[str, Any]:
    """Kompatibilitas mundur: memetakan ke fungsi pengetahuan dan info toko."""
    inv = get_catalog_inventory()
    kontak = os.getenv("KONTAK_STAF", "@cs_reinkomputer")
    res = pengetahuan(pertanyaan=topik or "kebijakan toko")
    return {
        "status": "sukses",
        "topik_ditanya": topik or "umum",
        "info": {
            "nama_toko": "ReIn Komputer",
            "kontak_staf": kontak,
            "kategori_produk": inv.get("kategori", ["desktop", "laptop", "monitor", "printer"]),
            "merek_resmi": inv.get("merek", []),
            "kebijakan_desktop": "Paket desktop tidak termasuk monitor, kecuali disebutkan di nama atau spesifikasi produk.",
            "pengetahuan_terkait": res.get("pengetahuan", [])
        }
    }


# =============================================================================
# SCHEMAS & EXECUTOR
# =============================================================================

AGENT_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "katalog",
            "description": "Mencari produk, harga, ketersediaan, jumlah produk, atau melihat lembar spesifikasi lengkap di toko ReIn Komputer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kata_kunci": {
                        "type": "string",
                        "description": "Kata kunci pencarian spesifik, model, prosesor, GPU, atau fitur (misal: 'oled', 'ecotank', 'rtx 4060', 'mini', 'struk', 'intel nuc')"
                    },
                    "kategori": {
                        "type": "string",
                        "description": "Kategori produk: laptop, desktop, monitor, atau printer"
                    },
                    "merek": {
                        "type": "string",
                        "description": "Merek produk (misal: Asus, Acer, Lenovo, HP, Apple, MSI, Epson, Canon, Brother)"
                    },
                    "budget_min": {
                        "type": "integer",
                        "description": "Batas anggaran minimal dalam angka rupiah"
                    },
                    "budget_max": {
                        "type": "integer",
                        "description": "Batas anggaran maksimal dalam angka rupiah (misal: 10000000 untuk 10 juta)"
                    },
                    "urutan": {
                        "type": "string",
                        "enum": ["termurah", "termahal"],
                        "description": "Isi termurah/termahal bila pelanggan minta yang paling murah/mahal; produk pertama di hasil adalah jawabannya."
                    },
                    "ram_min_gb": {
                        "type": "integer",
                        "description": "Kapasitas RAM minimal dalam GB (misal: 8, 16, 32)"
                    },
                    "ssd_min_gb": {
                        "type": "integer",
                        "description": "Kapasitas SSD minimal dalam GB (misal: 256, 512, 1000)"
                    },
                    "gpu_dedicated": {
                        "type": "boolean",
                        "description": "Isi true bila butuh GPU diskrit/dedicated (misal gaming/render), false untuk grafis terintegrasi"
                    },
                    "vram_min_gb": {
                        "type": "integer",
                        "description": "Kapasitas VRAM grafis minimal dalam GB (misal: 4, 6, 8)"
                    },
                    "layar_min_inci": {
                        "type": "number",
                        "description": "Ukuran layar minimal dalam inci (misal: 14.0, 15.6, 24.0)"
                    },
                    "layar_maks_inci": {
                        "type": "number",
                        "description": "Ukuran layar maksimal dalam inci (misal: 14.0, 15.6, 27.0)"
                    },
                    "refresh_min_hz": {
                        "type": "integer",
                        "description": "Refresh rate layar minimal dalam Hz (misal: 100, 144, 165)"
                    },
                    "kode_atau_nama": {
                        "type": "string",
                        "description": "Kode produk (misal 'KB-L14', 'KB-D11') atau nama produk spesifik untuk melihat lembar spesifikasi lengkap dan raw_data"
                    },
                    "kirim_foto": {
                        "type": "boolean",
                        "description": "Isi true bila pelanggan ingin melihat foto produk yang dicari, atau bila menurutmu foto membantu pelanggan; foto hanya terkirim untuk produk yang ada_foto-nya true."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pengetahuan",
            "description": "Mencari panduan kebutuhan pengguna, penjelasan dan pertimbangan teknis komponen, panduan memilih kategori, atau kebijakan resmi toko ReIn Komputer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pertanyaan": {
                        "type": "string",
                        "description": "Pertanyaan atau kebutuhan yang ingin dicari panduan/kebijakannya (misal: 'apakah paket desktop dapat monitor', 'panduan memilih prosesor', 'kebutuhan render 3d', 'printer kantor volume tinggi')"
                    }
                },
                "required": ["pertanyaan"]
            }
        }
    }
]


def get_agent_tools_schema(kirim_foto_oleh_llm: bool = False) -> list[dict[str, Any]]:
    """Mengembalikan skema alat agen; bila kirim_foto_oleh_llm False, parameter kirim_foto dihilangkan."""
    import copy
    tools = copy.deepcopy(AGENT_TOOLS_SCHEMA)
    if not kirim_foto_oleh_llm:
        for t in tools:
            if t.get("function", {}).get("name") == "katalog":
                props = t.get("function", {}).get("parameters", {}).get("properties", {})
                props.pop("kirim_foto", None)
    return tools


def execute_agent_tool(
    tool_name: str,
    tool_args: dict[str, Any],
    catalog=None,
    kirim_foto_oleh_llm: bool | None = None,
    catatan_pengetahuan_katalog: bool | None = None,
    produk_terdekat: bool | None = None
) -> dict[str, Any]:
    """Menjalankan alat agent berdasarkan nama dan argumen."""
    t_name = str(tool_name or "").strip()
    args = dict(tool_args or {})
    active_foto_flag = kirim_foto_oleh_llm if kirim_foto_oleh_llm is not None else args.get("kirim_foto_oleh_llm")
    active_catatan = catatan_pengetahuan_katalog if catatan_pengetahuan_katalog is not None else args.get("catatan_pengetahuan_katalog")
    active_terdekat = produk_terdekat if produk_terdekat is not None else args.get("produk_terdekat")

    if t_name == "katalog":
        return katalog(
            kata_kunci=args.get("kata_kunci"),
            kategori=args.get("kategori"),
            merek=args.get("merek"),
            budget_min=args.get("budget_min"),
            budget_max=args.get("budget_max"),
            kode_atau_nama=args.get("kode_atau_nama") or args.get("kode") or args.get("nama"),
            kirim_foto=args.get("kirim_foto"),
            urutan=args.get("urutan"),
            ram_min_gb=args.get("ram_min_gb"),
            ssd_min_gb=args.get("ssd_min_gb"),
            gpu_dedicated=args.get("gpu_dedicated"),
            vram_min_gb=args.get("vram_min_gb"),
            layar_min_inci=args.get("layar_min_inci"),
            layar_maks_inci=args.get("layar_maks_inci"),
            refresh_min_hz=args.get("refresh_min_hz"),
            catalog=catalog,
            katalog_sql=args.get("katalog_sql"),
            kirim_foto_oleh_llm=active_foto_flag,
            produk_terdekat=active_terdekat
        )
    elif t_name == "pengetahuan":
        return pengetahuan(
            pertanyaan=args.get("pertanyaan") or args.get("query") or args.get("kebutuhan") or args.get("topik") or "",
            top_k=args.get("top_k"),
            catatan_pengetahuan_katalog=active_catatan
        )
    elif t_name == "cari_produk":
        return katalog(
            kata_kunci=args.get("kata_kunci"),
            kategori=args.get("kategori"),
            merek=args.get("merek"),
            budget_min=args.get("budget_min"),
            budget_max=args.get("budget_max"),
            urutan=args.get("urutan"),
            ram_min_gb=args.get("ram_min_gb"),
            ssd_min_gb=args.get("ssd_min_gb"),
            gpu_dedicated=args.get("gpu_dedicated"),
            vram_min_gb=args.get("vram_min_gb"),
            layar_min_inci=args.get("layar_min_inci"),
            layar_maks_inci=args.get("layar_maks_inci"),
            refresh_min_hz=args.get("refresh_min_hz"),
            kirim_foto=args.get("kirim_foto"),
            catalog=catalog,
            katalog_sql=args.get("katalog_sql"),
            kirim_foto_oleh_llm=args.get("kirim_foto_oleh_llm")
        )
    elif t_name == "detail_produk":
        return katalog(
            kode_atau_nama=args.get("kode_atau_nama") or args.get("kode") or args.get("nama") or "",
            kirim_foto=args.get("kirim_foto"),
            catalog=catalog,
            katalog_sql=args.get("katalog_sql"),
            kirim_foto_oleh_llm=args.get("kirim_foto_oleh_llm")
        )
    elif t_name == "pengetahuan_kebutuhan":
        return pengetahuan(
            pertanyaan=args.get("kebutuhan") or args.get("query") or "",
            catatan_pengetahuan_katalog=active_catatan
        )
    elif t_name == "info_toko":
        return pengetahuan(
            pertanyaan=args.get("topik") or args.get("query") or "kebijakan toko",
            catatan_pengetahuan_katalog=active_catatan
        )
    else:
        return {
            "status": "error",
            "pesan": f"Alat '{t_name}' tidak dikenal."
        }
