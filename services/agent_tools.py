# -*- coding: utf-8 -*-
"""
Agent Tools Module untuk ReIn Komputer Customer Care.
Menyediakan 4 alat modular yang dipanggil langsung oleh LLM:
1. cari_produk: pencarian katalog berbasis kata kunci fleksibel, kategori, merek, dan budget.
2. detail_produk: lembar spesifikasi lengkap dan raw_data untuk satu atau beberapa produk.
3. pengetahuan_kebutuhan: panduan kebutuhan dan spesifikasi minimum/rekomendasi dari KB.
4. info_toko: kebijakan toko, paket penjualan, dan informasi umum dari KB.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from core.db import get_catalog_inventory
from services.catalog_search import clean_specs
from services.action_engine import build_lembar_spesifikasi
from services.catalog_service import get_active_catalog

logger = logging.getLogger("agent_tools")


def _format_rupiah(angka: int | float | None) -> str:
    if angka is None or angka == 0:
        return "Rp0"
    return f"Rp{int(angka):,}".replace(",", ".")


def _format_ringkas(p: dict) -> dict[str, Any]:
    """Format ringkas produk untuk keluaran alat cari_produk."""
    p_price = p.get("harga") or p.get("harga_idr") or 0
    return {
        "kode": p.get("kode"),
        "nama": p.get("nama"),
        "kategori": p.get("kategori"),
        "merek": p.get("brand") or p.get("merek"),
        "harga": _format_rupiah(p_price),
        "harga_idr": int(p_price),
        "spek_ringkas": clean_specs(p),
        "usage_text": p.get("usage_text", "")
    }


def _search_kb_markdown(query: str) -> list[dict[str, Any]]:
    """Pencarian fallback langsung pada berkas markdown panduan_kebutuhan_v2.md."""
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

    sections = content.split("\n## ")
    q_tokens = [w for w in re.findall(r"\w+", query.lower()) if len(w) >= 2]
    matched = []

    for sec in sections:
        if not sec.strip() or not sec.startswith("P"):
            continue
        sec_low = sec.lower()
        score = 0
        for tok in q_tokens:
            if tok in sec_low:
                score += 1
        if score > 0:
            lines = sec.strip().split("\n")
            header = lines[0]
            pid_m = re.match(r"^(P\d{2})", header)
            pid = pid_m.group(1) if pid_m else header[:3]
            body_text = "\n".join(lines[1:15])
            matched.append((score, {
                "profil_id": pid,
                "judul": header,
                "panduan_spek": body_text[:600]
            }))

    matched.sort(key=lambda x: -x[0])
    return [item for _, item in matched[:2]]


def _get_kb_policy_insight(topik: str) -> str:
    """Mengambil kutipan ringkas kebijakan/panduan umum toko dari KB."""
    topik_low = str(topik or "").lower()
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    kb_path = os.path.join(base_dir, "data", "knowledge", "panduan_kebutuhan_v2.md")
    if not os.path.exists(kb_path):
        return ""

    try:
        with open(kb_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return ""

    sections = content.split("\n## ")
    for sec in sections:
        sec_clean = sec.strip()
        if not sec_clean:
            continue
        sec_header = sec_clean.split("\n")[0].lower()
        if any(k in topik_low for k in ["desktop", "monitor", "paket"]) and "m01" in sec_header:
            return sec_clean[:500]
        elif any(k in topik_low for k in ["printer", "cetak", "struk"]) and "m02" in sec_header:
            return sec_clean[:500]
        elif any(k in topik_low for k in ["cpu", "prosesor"]) and "g01" in sec_header:
            return sec_clean[:500]
        elif any(k in topik_low for k in ["gpu", "vga", "grafis"]) and "g02" in sec_header:
            return sec_clean[:500]
        elif any(k in topik_low for k in ["ram", "storage", "ssd"]) and "g03" in sec_header:
            return sec_clean[:500]

    return ""


# =============================================================================
# 1. CARI PRODUK
# =============================================================================

def cari_produk(
    kata_kunci: str | None = None,
    kategori: str | None = None,
    merek: str | None = None,
    budget_max: int | float | None = None,
    budget_min: int | float | None = None,
    catalog=None
) -> dict[str, Any]:
    """
    Mencari produk di katalog toko ReIn Komputer:
    - kata_kunci dicari longgar (per kata, case-insensitive) di nama, kategori, merek, raw_data, usage_text.
    - budget_max adalah filter keras. Jika tidak ada yang masuk budget, sertakan harga termurah.
    - Kembalikan ringkas: kode, nama, kategori, harga, spek ringkas, usage_text. Maks 5 produk.
    - Kategori & merek diambil dinamis dari get_catalog_inventory() tanpa enum hardcode.
    """
    cat_inst = catalog or get_active_catalog()
    all_products = list(cat_inst.by_code.values())

    inv = get_catalog_inventory()
    valid_cats = {c.lower() for c in inv.get("kategori", [])}

    # Normalisasi filter kategori
    pool = list(all_products)
    if kategori:
        k_str = str(kategori).strip().lower()
        cat_synonyms = {
            "pc": "desktop", "komputer": "desktop", "all-in-one": "desktop", "aio": "desktop",
            "notebook": "laptop", "laptop": "laptop",
            "printer": "printer", "print": "printer", "cetak": "printer",
            "monitor": "monitor", "layar": "monitor"
        }
        target_cat = cat_synonyms.get(k_str, k_str)
        if target_cat in valid_cats:
            pool = [p for p in pool if str(p.get("kategori", "")).lower() == target_cat]
        else:
            pool = [p for p in pool if target_cat in str(p.get("kategori", "")).lower()]

    # Filter merek
    if merek:
        m_str = str(merek).strip().lower()
        pool = [
            p for p in pool
            if m_str in str(p.get("brand", "")).lower() or m_str in str(p.get("nama", "")).lower()
        ]

    # Filter budget_min
    if budget_min is not None and float(budget_min) > 0:
        pool = [p for p in pool if (p.get("harga") or p.get("harga_idr") or 0) >= float(budget_min)]

    # Pencarian longgar kata_kunci
    if kata_kunci and str(kata_kunci).strip():
        kw_clean = str(kata_kunci).strip().lower()
        tokens = [w for w in re.findall(r"\w+", kw_clean) if len(w) >= 2]

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
            if kw_clean in name_text:
                score += 60
            if kw_clean in raw_text:
                score += 45
            if kw_clean in usage_text:
                score += 35

            for tok in tokens:
                if tok in name_text:
                    score += 20
                    if re.search(rf"\b{re.escape(tok)}\b", name_text):
                        score += 10
                if tok in brand_text:
                    score += 15
                if tok in cat_text:
                    score += 10
                if tok in raw_text:
                    score += 15
                if tok in usage_text:
                    score += 10
                if tok in tags_text:
                    score += 10
                if tok in specs_text:
                    score += 8

            if score > 0:
                scored_pool.append((score, p))

        scored_pool.sort(key=lambda item: (-item[0], item[1].get("harga") or item[1].get("harga_idr") or 0))
        pool = [item[1] for item in scored_pool]
    else:
        # Urutkan harga termurah jika tanpa kata kunci
        pool.sort(key=lambda p: (p.get("harga") or p.get("harga_idr") or 0))

    # Filter keras budget_max
    if budget_max is not None and float(budget_max) > 0:
        b_max = float(budget_max)
        under_budget = [p for p in pool if (p.get("harga") or p.get("harga_idr") or 0) <= b_max]
        if under_budget:
            return {
                "status": "sukses",
                "total_ditemukan": len(under_budget),
                "produk": [_format_ringkas(p) for p in under_budget[:5]]
            }
        else:
            # Tidak ada produk yang masuk budget: cari produk termurah dari kandidat yang cocok atau katalog
            cheapest_source = pool if pool else all_products
            cheapest_sorted = sorted(cheapest_source, key=lambda p: (p.get("harga") or p.get("harga_idr") or float("inf")))
            cheapest_p = cheapest_sorted[0] if cheapest_sorted else None
            p_termurah_info = [_format_ringkas(cheapest_p)] if cheapest_p else []
            msg = (
                f"Tidak ada produk yang memenuhi kriteria di bawah budget {_format_rupiah(b_max)}. "
                f"Produk termurah yang tersedia adalah {cheapest_p.get('nama') if cheapest_p else '-'} "
                f"dengan harga {_format_rupiah(cheapest_p.get('harga') or cheapest_p.get('harga_idr')) if cheapest_p else '-' }."
            )
            return {
                "status": "melebihi_budget",
                "pesan": msg,
                "produk_termurah": p_termurah_info,
                "produk": []
            }

    return {
        "status": "sukses",
        "total_ditemukan": len(pool),
        "produk": [_format_ringkas(p) for p in pool[:5]]
    }


# =============================================================================
# 2. DETAIL PRODUK
# =============================================================================

def detail_produk(kode_atau_nama: str | list[str], catalog=None) -> dict[str, Any]:
    """
    Mengambil lembar spesifikasi lengkap dan raw_data untuk satu atau beberapa produk.
    Bisa menerima kode (KB-xxx) atau nama produk (bisa dipisahkan koma atau dalam bentuk list).
    """
    cat_inst = catalog or get_active_catalog()
    all_products = list(cat_inst.by_code.values())

    queries = []
    if isinstance(kode_atau_nama, list):
        queries = [str(x).strip() for x in kode_atau_nama if str(x).strip()]
    elif isinstance(kode_atau_nama, str):
        queries = [x.strip() for x in kode_atau_nama.split(",") if x.strip()]

    matched_results = []
    found_codes = set()

    for q in queries:
        q_upper = q.upper()
        # 1. Cek kode langsung
        if q_upper in cat_inst.by_code:
            p = cat_inst.by_code[q_upper]
            if p["kode"] not in found_codes:
                found_codes.add(p["kode"])
                matched_results.append(p)
            continue

        # 2. Cek nama persis atau substring
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
        return {
            "status": "tidak_ditemukan",
            "pesan": f"Produk '{kode_atau_nama}' tidak ditemukan di katalog.",
            "detail": []
        }

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
        output_details.append({
            "kode": p.get("kode"),
            "nama": p.get("nama"),
            "lembar_spesifikasi": lembar,
            "raw_data": raw_dict
        })

    return {
        "status": "sukses",
        "total": len(output_details),
        "detail": output_details
    }


# =============================================================================
# 3. PENGETAHUAN KEBUTUHAN
# =============================================================================

def pengetahuan_kebutuhan(kebutuhan: str) -> dict[str, Any]:
    """
    Panduan spesifikasi minimum dan rekomendasi dari basis pengetahuan (panduan_kebutuhan_v2.md)
    lewat knowledge_service / RAG Qdrant, dengan fallback langsung ke pembacaan berkas KB.
    """
    if not kebutuhan or not str(kebutuhan).strip():
        return {
            "status": "tidak_ada_input",
            "pesan": "Kebutuhan belum disebutkan."
        }

    k_query = str(kebutuhan).strip()
    profiles_data = []

    # Coba via Qdrant knowledge_service
    try:
        from services.knowledge_service import get_usage_requirements, get_profile_by_id
        reqs = get_usage_requirements(k_query, limit=2)
        pls = reqs.get("profil", [])
        for pl in pls:
            pid = pl.get("profil_id")
            full_p = get_profile_by_id(pid) or {}
            profiles_data.append({
                "profil_id": pid,
                "judul": pl.get("nama") or full_p.get("judul"),
                "panduan_spek": full_p.get("text") or pl.get("ringkasan"),
                "minimum_spek": full_p.get("minimum_spek"),
                "rekomendasi_spek": full_p.get("rekomendasi_spek")
            })
    except Exception as e:
        logger.warning(f"Qdrant lookup skipped / error: {e}")

    # Fallback ke pencarian teks pada panduan_kebutuhan_v2.md
    if not profiles_data:
        profiles_data = _search_kb_markdown(k_query)

    if profiles_data:
        return {
            "status": "sukses",
            "kebutuhan_ditanyakan": k_query,
            "profil_rekomendasi": profiles_data
        }

    return {
        "status": "belum_teridentifikasi",
        "pesan": f"Panduan spesifik untuk '{k_query}' belum teridentifikasi di basis pengetahuan. Tanyakan detail software atau perangkat yang diinginkan."
    }


# =============================================================================
# 4. INFO TOKO
# =============================================================================

def info_toko(topik: str | None = None) -> dict[str, Any]:
    """
    Mengambil kebijakan dan info resmi toko ReIn Komputer dari basis pengetahuan.
    Termasuk kebijakan paket desktop tidak termasuk monitor, kategori/merek resmi, kontak staf.
    """
    topik_low = str(topik or "").lower().strip()
    inv = get_catalog_inventory()
    kontak = os.getenv("KONTAK_STAF", "@cs_reinkomputer")

    info: dict[str, Any] = {
        "nama_toko": "ReIn Komputer",
        "kontak_staf": kontak,
        "kategori_produk": inv.get("kategori", ["desktop", "laptop", "monitor", "printer"]),
        "merek_resmi": inv.get("merek", []),
        "kebijakan_desktop": "Paket desktop tidak termasuk monitor, kecuali disebutkan di nama atau spesifikasi produk.",
    }

    kb_insight = _get_kb_policy_insight(topik_low)
    if kb_insight:
        info["panduan_kb_terkait"] = kb_insight

    return {
        "status": "sukses",
        "topik_ditanya": topik or "umum",
        "info": info
    }


# =============================================================================
# SCHEMAS & EXECUTOR
# =============================================================================

AGENT_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "cari_produk",
            "description": "Mencari produk di katalog toko ReIn Komputer berdasarkan kata kunci tipe/model/kegunaan, kategori, merek, dan batasan budget.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kata_kunci": {
                        "type": "string",
                        "description": "Kata kunci pencarian, nama seri, model, atau karakteristik (misal: 'ecotank', 'printer struk', 'tangki tinta', 'rtx 4050', 'oled', 'gaming')"
                    },
                    "kategori": {
                        "type": "string",
                        "description": "Kategori produk: laptop, desktop, printer, atau monitor"
                    },
                    "merek": {
                        "type": "string",
                        "description": "Merek produk (misal: Asus, Acer, Lenovo, HP, MSI, Epson, Canon, Brother)"
                    },
                    "budget_max": {
                        "type": "integer",
                        "description": "Batas anggaran maksimal dalam angka rupiah (misal: 10000000 untuk 10 juta)"
                    },
                    "budget_min": {
                        "type": "integer",
                        "description": "Batas anggaran minimal dalam angka rupiah"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "detail_produk",
            "description": "Melihat lembar spesifikasi lengkap dan data teknis mendalam dari satu atau beberapa produk berdasarkan kode produk (misal 'KB-L01') atau nama produk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kode_atau_nama": {
                        "type": "string",
                        "description": "Kode produk (misal 'KB-L14', 'KB-P06') atau nama produk (bisa beberapa produk dipisahkan koma)"
                    }
                },
                "required": ["kode_atau_nama"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pengetahuan_kebutuhan",
            "description": "Mencari panduan spesifikasi dan kriteria minimum/rekomendasi komputer berdasarkan kebutuhan atau aktivitas pengguna dari basis pengetahuan toko.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kebutuhan": {
                        "type": "string",
                        "description": "Aktivitas atau kebutuhan penggunaan (misal: 'desain grafis 2d', 'kuliah informatika', 'kasir toko', 'render 3d', 'ai lokal', 'editing video 4k')"
                    }
                },
                "required": ["kebutuhan"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "info_toko",
            "description": "Mencari informasi kebijakan toko, paket penjualan (seperti apakah desktop termasuk monitor), panduan komponen umum (CPU/GPU/RAM), merek/kategori yang tersedia, atau kontak staf.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topik": {
                        "type": "string",
                        "description": "Topik kebijakan atau info toko yang ditanyakan (misal: 'paket desktop', 'monitor desktop', 'kebijakan', 'kontak staf', 'kategori tersedia')"
                    }
                },
                "required": ["topik"]
            }
        }
    }
]


def execute_agent_tool(tool_name: str, tool_args: dict[str, Any], catalog=None) -> dict[str, Any]:
    """Menjalankan alat agent berdasarkan nama dan argumen."""
    t_name = str(tool_name or "").strip()
    args = dict(tool_args or {})

    if t_name == "cari_produk":
        return cari_produk(
            kata_kunci=args.get("kata_kunci"),
            kategori=args.get("kategori"),
            merek=args.get("merek"),
            budget_max=args.get("budget_max"),
            budget_min=args.get("budget_min"),
            catalog=catalog
        )
    elif t_name == "detail_produk":
        return detail_produk(
            kode_atau_nama=args.get("kode_atau_nama") or args.get("kode") or args.get("nama") or "",
            catalog=catalog
        )
    elif t_name == "pengetahuan_kebutuhan":
        return pengetahuan_kebutuhan(
            kebutuhan=args.get("kebutuhan") or args.get("query") or ""
        )
    elif t_name == "info_toko":
        return info_toko(
            topik=args.get("topik") or args.get("query")
        )
    else:
        return {
            "status": "error",
            "pesan": f"Alat '{t_name}' tidak dikenal."
        }
