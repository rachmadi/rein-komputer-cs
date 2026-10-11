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
from typing import Any
import requests

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
    """Format ringkas produk untuk keluaran alat katalog."""
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

    sections = content.split("\n## ")
    q_tokens = [w for w in re.findall(r"\w+", query.lower()) if len(w) >= 2]
    matched = []

    for i, sec in enumerate(sections):
        sec_clean = sec.strip()
        if not sec_clean:
            continue
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
    catalog=None
) -> dict[str, Any]:
    """
    Alat katalog toko ReIn Komputer:
    a. Jika kode_atau_nama diisi:
       Kembalikan lembar spesifikasi lengkap (build_lembar_spesifikasi + raw_data).
       Boleh satu atau beberapa produk (dipisahkan koma atau list).
    b. Selain itu: pencarian katalog.
       - Kata dalam kata_kunci yang sama dengan nilai filter kategori/merek (termasuk sinonimnya)
         tidak ikut dinilai.
       - Jika tidak ada kata tersisa, kembalikan semua produk yang lolos filter, urut harga.
       - budget_max tetap filter keras (jika kosong, sertakan harga termurah yang ada).
       - Selalu kembalikan total_cocok (jumlah SEMUA produk yang cocok) dan maksimal 10 produk ringkas:
         kode, nama, kategori, harga, spek ringkas, usage_text.
    """
    cat_inst = catalog or get_active_catalog()
    all_products = list(cat_inst.by_code.values())

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
            return {
                "status": "tidak_ditemukan",
                "pesan": f"Produk '{kode_atau_nama}' tidak ditemukan di katalog.",
                "total_cocok": 0,
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
                "harga": _format_rupiah(p.get("harga") or p.get("harga_idr")),
                "lembar_spesifikasi": lembar,
                "raw_data": raw_dict
            })

        return {
            "status": "sukses",
            "total_cocok": len(output_details),
            "detail": output_details
        }

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
    if budget_min is not None and float(budget_min) > 0:
        pool = [p for p in pool if (p.get("harga") or p.get("harga_idr") or 0) >= float(budget_min)]

    # Kata yang tersisa untuk dinilai
    scoring_tokens = [w for w in tokens if w not in filter_words_to_exclude]

    # Sinonim dan varian bentuk khusus (misal: mini <-> nuc, aio <-> all-in-one)
    alias_map = {
        "mini": ["mini", "nuc"],
        "nuc": ["nuc", "mini"],
        "aio": ["aio", "all-in-one"],
        "all-in-one": ["aio", "all-in-one"]
    }

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
                search_variants = alias_map.get(tok, [tok])
                tok_score = 0
                for v in search_variants:
                    if v in name_text:
                        tok_score = max(tok_score, 25)
                        if re.search(rf"\b{re.escape(v)}\b", name_text):
                            tok_score = max(tok_score, 35)
                    if v in brand_text:
                        tok_score = max(tok_score, 15)
                    if v in raw_text:
                        tok_score = max(tok_score, 20)
                    if v in usage_text:
                        tok_score = max(tok_score, 15)
                    if v in tags_text:
                        tok_score = max(tok_score, 15)
                    if v in specs_text:
                        tok_score = max(tok_score, 10)
                score += tok_score

            if score > 0:
                scored_pool.append((score, p))

        scored_pool.sort(key=lambda item: (-item[0], item[1].get("harga") or item[1].get("harga_idr") or 0))
        pool = [item[1] for item in scored_pool]
    else:
        # Jika tidak ada kata tersisa, urutkan berdasarkan harga
        pool.sort(key=lambda p: (p.get("harga") or p.get("harga_idr") or 0))

    # Filter Keras budget_max
    if budget_max is not None and float(budget_max) > 0:
        b_max = float(budget_max)
        under_budget = [p for p in pool if (p.get("harga") or p.get("harga_idr") or 0) <= b_max]
        if under_budget:
            return {
                "status": "sukses",
                "total_cocok": len(under_budget),
                "produk": [_format_ringkas(p) for p in under_budget[:10]]
            }
        else:
            cheapest_source = pool if pool else (all_products if not target_cat else [p for p in all_products if p.get('kategori') == target_cat])
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
                "total_cocok": 0,
                "pesan": msg,
                "produk_termurah": p_termurah_info,
                "produk": []
            }

    return {
        "status": "sukses",
        "total_cocok": len(pool),
        "produk": [_format_ringkas(p) for p in pool[:10]]
    }


# =============================================================================
# 2. ALAT PENGETAHUAN (RAG Qdrant untuk Semua Tipe Chunk)
# =============================================================================

def pengetahuan(pertanyaan: str) -> dict[str, Any]:
    """
    Mencari panduan kebutuhan pengguna, penjelasan dan pertimbangan teknis komponen,
    panduan memilih kategori, atau kebijakan resmi toko ReIn Komputer.
    Cari ke SEMUA tipe chunk (G, P, M, kebijakan toko) di Qdrant.
    Kembalikan 3 chunk teratas beserta ID dan judul bersih (tanpa kode internal P01/G01 di judul).
    """
    q_str = str(pertanyaan or "").strip()
    if not q_str:
        return {
            "status": "tidak_ada_input",
            "pesan": "Pertanyaan belum diisi.",
            "total_cocok": 0,
            "pengetahuan": []
        }

    hasil_chunks = []

    # 1. Cari via Qdrant (semua tipe chunk)
    try:
        from services.catalog_service import QDRANT_URL, get_embedding
        vec = get_embedding(q_str.lower())
        if vec:
            col_name = os.getenv("QDRANT_KNOWLEDGE_COLLECTION", "computer_knowledge")
            url = f"{QDRANT_URL}/collections/{col_name}/points/search"
            payload = {
                "vector": vec,
                "limit": 3,
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
    except Exception as e:
        logger.warning(f"Qdrant lookup failed in pengetahuan: {e}")

    # 2. Fallback jika Qdrant gagal atau tidak menemukan hasil
    if not hasil_chunks:
        hasil_chunks = _search_kb_markdown_all(q_str)

    return {
        "status": "sukses",
        "pertanyaan": q_str,
        "total_cocok": len(hasil_chunks),
        "pengetahuan": hasil_chunks[:3]
    }


# =============================================================================
# KOMPATIBILITAS MUNDUR UNTUK ALAT LAMA
# =============================================================================

def cari_produk(
    kata_kunci: str | None = None,
    kategori: str | None = None,
    merek: str | None = None,
    budget_max: int | float | None = None,
    budget_min: int | float | None = None,
    catalog=None
) -> dict[str, Any]:
    """Kompatibilitas mundur: memetakan ke fungsi katalog."""
    return katalog(
        kata_kunci=kata_kunci,
        kategori=kategori,
        merek=merek,
        budget_min=budget_min,
        budget_max=budget_max,
        catalog=catalog
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
                    "kode_atau_nama": {
                        "type": "string",
                        "description": "Kode produk (misal 'KB-L14', 'KB-D11') atau nama produk spesifik untuk melihat lembar spesifikasi lengkap dan raw_data"
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


def execute_agent_tool(tool_name: str, tool_args: dict[str, Any], catalog=None) -> dict[str, Any]:
    """Menjalankan alat agent berdasarkan nama dan argumen."""
    t_name = str(tool_name or "").strip()
    args = dict(tool_args or {})

    if t_name == "katalog":
        return katalog(
            kata_kunci=args.get("kata_kunci"),
            kategori=args.get("kategori"),
            merek=args.get("merek"),
            budget_min=args.get("budget_min"),
            budget_max=args.get("budget_max"),
            kode_atau_nama=args.get("kode_atau_nama") or args.get("kode") or args.get("nama"),
            catalog=catalog
        )
    elif t_name == "pengetahuan":
        return pengetahuan(
            pertanyaan=args.get("pertanyaan") or args.get("query") or args.get("kebutuhan") or args.get("topik") or ""
        )
    elif t_name == "cari_produk":
        return katalog(
            kata_kunci=args.get("kata_kunci"),
            kategori=args.get("kategori"),
            merek=args.get("merek"),
            budget_min=args.get("budget_min"),
            budget_max=args.get("budget_max"),
            catalog=catalog
        )
    elif t_name == "detail_produk":
        return katalog(
            kode_atau_nama=args.get("kode_atau_nama") or args.get("kode") or args.get("nama") or "",
            catalog=catalog
        )
    elif t_name == "pengetahuan_kebutuhan":
        return pengetahuan(
            pertanyaan=args.get("kebutuhan") or args.get("query") or ""
        )
    elif t_name == "info_toko":
        return pengetahuan(
            pertanyaan=args.get("topik") or args.get("query") or "kebijakan toko"
        )
    else:
        return {
            "status": "error",
            "pesan": f"Alat '{t_name}' tidak dikenal."
        }
