# -*- coding: utf-8 -*-
"""
services/action_engine.py
Mesin Deterministik Per Aksi untuk ReIn Komputer (Antigravity v2).

Prinsip:
- Fungsi murni deterministik, tidak menghasilkan kalimat percakapan bebas.
- Menghasilkan fakta terstruktur (JSON/dict) untuk dikonsumsi Generator LLM.
- Menegakkan seluruh aturan Tabel Perilaku ReIn Komputer (A1-A12 & B1-B13).
"""
from __future__ import annotations

import os
import re
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.schema_actions import (
    ParserOutput, ActionEnum, ActionArguments, AtributSpesifikasiEnum,
    SlotEnum, AlasanTidakJelasEnum
)
from services.catalog_search import apply_filters, clean_specs, format_natural_unmet_requirements, parse_budget_from_text
from services.knowledge_service import get_usage_requirements, get_profile_by_id
from core.catalog import Catalog
from core.config import KONTAK_STAF

logger = logging.getLogger(__name__)


def parse_int_safe(val: Any) -> Optional[int]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    val_str = str(val).strip().lower()
    if not val_str:
        return None
    b = parse_budget_from_text(val_str)
    if b is not None:
        return b
    digits = re.sub(r"[^\d]", "", val_str)
    if digits:
        try:
            return int(digits)
        except ValueError:
            pass
    return None


def parse_float_safe(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    m = re.search(r"(\d+(?:[.,]\d+)?)", str(val))
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            pass
    return None


def format_rupiah(nominal: int | float | None) -> str:
    if nominal is None:
        return "Rp0"
    return f"Rp{int(nominal):,}".replace(",", ".")


@dataclass
class ActionResult:
    aksi: ActionEnum
    fakta: Dict[str, Any]
    produk_list: List[Dict[str, Any]] = field(default_factory=list)
    profil_id: Optional[str] = None


def get_product_price(p: dict) -> int:
    return int(p.get("harga") or p.get("harga_idr") or 0)


def get_product_brand(p: dict) -> str:
    return str(p.get("brand") or p.get("merek") or "").strip().lower()


def get_product_screen_inch(p: dict) -> float | None:
    val = p.get("screen_inch") or p.get("ukuran_layar")
    if val is not None:
        try:
            return float(val)
        except (ValueError, TypeError):
            pass
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:inci|inch|\"|'|s\b)", str(p.get("display") or "") + " " + str(p.get("nama") or ""))
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def cpu_tier_to_description(tier: int) -> str:
    mapping = {
        1: "Intel Core i3 / Ryzen 3 / seri N (komputasi harian dasar)",
        2: "Intel Core i5 / Ryzen 5 / Core Ultra 5 (multitasking standar & kerja aktif)",
        3: "Intel Core i7 / Ryzen 7 / Core Ultra 7 (performa tinggi & beban grafis)",
        4: "Intel Core i9 / Ryzen 9 / Core Ultra 9 (komputasi profesional sangat berat)"
    }
    return mapping.get(tier, f"Kelas prosesor tingkat {tier}")


class ActionEngine:
    def __init__(self, catalog: Catalog | None = None, db_path: str | None = None):
        if catalog:
            self.catalog = catalog
        else:
            try:
                self.catalog = Catalog.from_db(db_path=db_path)
            except Exception as e:
                logger.warning(f"Fallback to Catalog.from_dummy: {e}")
                self.catalog = Catalog.from_dummy()

    def get_product_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        c_clean = str(code).strip().upper()
        for p in self.catalog.products:
            if p.get("kode", "").upper() == c_clean:
                return p
        return None

    def execute(self, parsed: ParserOutput, session_state: dict | None = None) -> ActionResult:
        state = session_state if session_state is not None else {}
        if parsed.pembaruan_state:
            for k, v in parsed.pembaruan_state.model_dump(exclude_unset=True).items():
                if v is not None:
                    state[k] = v

        aksi = parsed.aksi
        args = parsed.argumen

        if aksi == ActionEnum.MINTA_REKOMENDASI:
            return self._handle_minta_rekomendasi(args, state)
        elif aksi == ActionEnum.CARI_PRODUK:
            return self._handle_cari_produk(args, state)
        elif aksi == ActionEnum.EVALUASI_KECOCOKAN:
            return self._handle_evaluasi_kecocokan(args, state)
        elif aksi == ActionEnum.TANYA_SPESIFIKASI:
            return self._handle_tanya_spesifikasi(args, state)
        elif aksi == ActionEnum.BANDINGKAN:
            return self._handle_bandingkan(args, state)
        elif aksi == ActionEnum.LANJUTAN_HASIL:
            return self._handle_lanjutan_hasil(args, state)
        elif aksi == ActionEnum.TANYA_INFO_TOKO:
            return self._handle_tanya_info_toko(args, state)
        elif aksi == ActionEnum.JAWAB_PERTANYAAN_BOT:
            return self._handle_jawab_pertanyaan_bot(args, state)
        elif aksi == ActionEnum.PERBAIKI_PERCAKAPAN:
            return self._handle_perbaiki_percakapan(args, state)
        elif aksi == ActionEnum.SAPA:
            return self._handle_sapa(args, state)
        elif aksi == ActionEnum.BASA_BASI:
            return self._handle_basa_basi(args, state)
        else:  # TIDAK_JELAS
            return self._handle_tidak_jelas(args, state)

    # -------------------------------------------------------------------------
    # 1. minta_rekomendasi (B1, B3, B4, B5, B6, B7)
    # -------------------------------------------------------------------------
    def _handle_minta_rekomendasi(self, args: ActionArguments, state: dict) -> ActionResult:
        kebutuhan_teks = args.kebutuhan_teks or state.get("kebutuhan_teks") or ""
        persona = args.persona or state.get("persona")
        budget_max = parse_int_safe(args.budget_max or state.get("budget"))

        # B1: Pelanggan menyebut PERSONA SAJA tanpa aktivitas konkret
        if persona and (not kebutuhan_teks or kebutuhan_teks.strip().lower() == persona.strip().lower()):
            fakta = {
                "status": "tanya_kebutuhan",
                "persona": persona,
                "slot_diisi": "persona",
                "pesan": f"Persona '{persona}' telah dicatat. Tanyakan aktivitas atau kebutuhan spesifik yang akan dijalankan."
            }
            return ActionResult(aksi=ActionEnum.MINTA_REKOMENDASI, fakta=fakta, produk_list=[])

        # B3: Hapus default kategori 'laptop'. Simpulkan dari kebutuhan jika jelas, jika tidak biarkan None
        kategori = args.kategori or state.get("kategori")
        if not kategori and kebutuhan_teks:
            k_low = kebutuhan_teks.lower()
            if any(w in k_low for w in ["bawa-bawa", "mobile", "kuliah", "sekolah", "kampus", "kafe", "mobilitas", "baterai"]):
                kategori = "laptop"
            elif any(w in k_low for w in ["kasir", "pos", "toko kelontong", "pc tetap", "desktop"]):
                kategori = "desktop"
            elif "printer" in k_low or "cetak" in k_low:
                kategori = "printer"
            elif "monitor" in k_low or "layar tambahan" in k_low:
                kategori = "monitor"

        # B7: Anggaran di bawah harga terendah katalog
        if budget_max:
            cat_candidates = [p for p in self.catalog.products if not kategori or p.get("kategori", "").lower() == str(kategori).lower()]
            if cat_candidates:
                min_cat_price = min(get_product_price(p) for p in cat_candidates)
                if budget_max < min_cat_price:
                    fakta = {
                        "status": "tidak_ada_dalam_anggaran",
                        "budget_pelanggan": budget_max,
                        "budget_pelanggan_formatted": format_rupiah(budget_max),
                        "harga_termurah_kategori": min_cat_price,
                        "harga_termurah_kategori_formatted": format_rupiah(min_cat_price),
                        "kategori": kategori or "katalog",
                        "pesan": f"Belum ada produk dalam rentang anggaran {format_rupiah(budget_max)}. Opsi termurah yang tersedia adalah {format_rupiah(min_cat_price)}."
                    }
                    return ActionResult(aksi=ActionEnum.MINTA_REKOMENDASI, fakta=fakta, produk_list=[])

        # B4 & B5: Penelusuran profil kebutuhan via RAG
        profil_id = None
        prof_data = None
        if kebutuhan_teks:
            try:
                reqs = get_usage_requirements(kebutuhan_teks)
                pls = reqs.get("profil", [])
                valid_pls = [p for p in pls if str(p.get("profil_id", "")).startswith("P")]
                if valid_pls:
                    profil_id = valid_pls[0]["profil_id"]
                    prof_data = get_profile_by_id(profil_id)
            except Exception as exc:
                logger.error(f"Kegagalan Qdrant/embedding saat mengambil profil: {exc}")
                fakta = {
                    "status": "sistem_error",
                    "kontak_staf": KONTAK_STAF,
                    "pesan": "Sistem basis data pengetahuan sedang mengalami gangguan sementara."
                }
                return ActionResult(aksi=ActionEnum.MINTA_REKOMENDASI, fakta=fakta, produk_list=[])

        if not profil_id and state.get("profil_aktif"):
            profil_id = state.get("profil_aktif")
            prof_data = get_profile_by_id(profil_id)

        # B4: Profil tidak ditemukan di RAG
        if not profil_id or not prof_data:
            miss_count = state.get("consecutive_profile_misses", 0) + 1
            state["consecutive_profile_misses"] = miss_count
            if miss_count >= 2:
                fakta = {
                    "status": "profil_tidak_ditemukan_berulang",
                    "kebutuhan_teks": kebutuhan_teks,
                    "kontak_staf": KONTAK_STAF,
                    "pesan": "Kebutuhan belum terpetakan setelah 2 kali penelusuran. Tawarkan pencarian berbasis kategori/budget atau hubungi staf."
                }
            else:
                fakta = {
                    "status": "profil_tidak_ditemukan",
                    "kebutuhan_teks": kebutuhan_teks,
                    "pesan": "Kebutuhan belum dapat dipetakan secara spesifik ke profil katalog."
                }
            return ActionResult(aksi=ActionEnum.MINTA_REKOMENDASI, fakta=fakta, produk_list=[])
        else:
            state["consecutive_profile_misses"] = 0

        filters = prof_data.get("filter", [])
        candidates = []
        for p in self.catalog.products:
            if kategori and p.get("kategori", "").lower() != kategori.lower():
                continue
            if budget_max and get_product_price(p) > budget_max:
                continue
            passed, failure_reason, penalty, report = apply_filters(p, filters)
            candidates.append({
                "product": p,
                "passed": passed,
                "penalty": penalty,
                "failure_reason": failure_reason,
                "report": report
            })

        # B6: Tidak ada produk yang memenuhi spesifikasi minimum
        if candidates and all(not c["passed"] for c in candidates):
            candidates.sort(key=lambda x: (-x["penalty"], get_product_price(x["product"])))
            closest = candidates[0]
            closest_prod = closest["product"]
            rep = closest["report"]
            unmet = rep.get("tidak_terpenuhi", []) or [f"{r} tidak terpenuhi" for r in rep.get("tidak_diketahui", [])] or [str(closest.get("failure_reason") or "spesifikasi belum memenuhi")]
            fakta = {
                "status": "belum_ada_yang_memenuhi",
                "profil": {
                    "id": profil_id,
                    "judul": prof_data.get("judul"),
                    "minimum_spek": prof_data.get("minimum_spek")
                },
                "produk_terdekat": {
                    "kode": closest_prod.get("kode"),
                    "nama": closest_prod.get("nama"),
                    "harga": get_product_price(closest_prod),
                    "harga_formatted": format_rupiah(get_product_price(closest_prod)),
                    "spesifikasi": clean_specs(closest_prod),
                    "kekurangan": unmet
                },
                "kontak_staf": KONTAK_STAF,
                "pesan": "Saat ini belum ada stok produk yang memenuhi syarat minimum kebutuhan tersebut."
            }
            return ActionResult(aksi=ActionEnum.MINTA_REKOMENDASI, fakta=fakta, produk_list=[])

        # Urutkan: lolos semua dulu, penalty tertinggi (paling sedikit penalti), harga termurah
        candidates.sort(key=lambda x: (not x["passed"], -x["penalty"], get_product_price(x["product"])))
        top_matches = candidates[:3]

        formatted_prods = []
        for item in top_matches:
            p = item["product"]
            rep = item["report"]
            p_price = get_product_price(p)
            formatted_prods.append({
                "kode": p.get("kode"),
                "nama": p.get("nama"),
                "kategori": p.get("kategori"),
                "harga": p_price,
                "harga_formatted": format_rupiah(p_price),
                "spesifikasi": clean_specs(p),
                "image_url": p.get("image_url"),
                "match_report": {
                    "lolos_semua": item["passed"],
                    "terpenuhi": rep.get("terpenuhi", []),
                    "tidak_terpenuhi": rep.get("tidak_terpenuhi", []),
                    "tidak_diketahui": rep.get("tidak_diketahui", [])
                }
            })

        fakta = {
            "status": "sukses",
            "profil": {
                "id": profil_id,
                "judul": prof_data.get("judul"),
                "minimum_spek": prof_data.get("minimum_spek"),
                "rekomendasi_spek": prof_data.get("rekomendasi_spek")
            },
            "kebutuhan_teks": kebutuhan_teks,
            "total_ditemukan": len(formatted_prods),
            "produk": formatted_prods
        }
        return ActionResult(
            aksi=ActionEnum.MINTA_REKOMENDASI,
            fakta=fakta,
            produk_list=formatted_prods,
            profil_id=profil_id
        )

    # -------------------------------------------------------------------------
    # 2. cari_produk (B2, B7)
    # -------------------------------------------------------------------------
    def _handle_cari_produk(self, args: ActionArguments, state: dict) -> ActionResult:
        kategori = args.kategori or state.get("kategori")
        merek = args.merek
        merek_kecuali = args.merek_kecuali
        nama_model = args.nama_model
        gpu = args.gpu
        min_harga = parse_int_safe(args.min_harga)
        max_harga = parse_int_safe(args.max_harga or state.get("budget"))
        ram_gb_min = parse_int_safe(args.ram_gb_min)
        storage_gb_min = parse_int_safe(args.storage_gb_min)
        ukuran_layar = parse_float_safe(args.ukuran_layar)

        # B7: Anggaran di bawah harga terendah kategori
        if max_harga:
            cat_candidates = [p for p in self.catalog.products if not kategori or p.get("kategori", "").lower() == str(kategori).lower()]
            if cat_candidates:
                min_cat_price = min(get_product_price(p) for p in cat_candidates)
                if max_harga < min_cat_price:
                    fakta = {
                        "status": "tidak_ada_dalam_anggaran",
                        "budget_pelanggan": max_harga,
                        "budget_pelanggan_formatted": format_rupiah(max_harga),
                        "harga_termurah_kategori": min_cat_price,
                        "harga_termurah_kategori_formatted": format_rupiah(min_cat_price),
                        "kategori": kategori or "katalog",
                        "pesan": f"Belum ada produk dalam rentang anggaran {format_rupiah(max_harga)}. Opsi termurah adalah {format_rupiah(min_cat_price)}."
                    }
                    return ActionResult(aksi=ActionEnum.CARI_PRODUK, fakta=fakta, produk_list=[])

        matches = []
        for p in self.catalog.products:
            p_cat = str(p.get("kategori", "")).strip().lower()
            p_nama = str(p.get("nama", "")).strip().lower()
            p_brand = get_product_brand(p)

            if kategori and p_cat != kategori.strip().lower():
                continue
            if merek:
                m_clean = str(merek).strip().lower()
                if m_clean != p_brand and m_clean not in p_brand and m_clean not in p_nama:
                    continue
            if merek_kecuali:
                mk_clean = str(merek_kecuali).strip().lower()
                if mk_clean == p_brand or mk_clean in p_brand or mk_clean in p_nama:
                    continue
            if nama_model and nama_model.strip().lower() not in p_nama:
                continue
            if gpu and gpu.strip().lower() not in str(p.get("gpu", "")).strip().lower():
                continue
            if min_harga and get_product_price(p) < min_harga:
                continue
            if max_harga and get_product_price(p) > max_harga:
                continue
            if ram_gb_min and (p.get("ram_gb") or 0) < ram_gb_min:
                continue
            if storage_gb_min and (p.get("storage_ssd_gb") or 0) < storage_gb_min:
                continue
            if ukuran_layar is not None:
                p_inch = get_product_screen_inch(p)
                if p_inch is not None and abs(p_inch - ukuran_layar) > 0.6:
                    continue

            matches.append(p)

        matches.sort(key=lambda x: get_product_price(x))
        top_matches = matches[:3]

        formatted_prods = []
        for p in top_matches:
            p_price = get_product_price(p)
            formatted_prods.append({
                "kode": p.get("kode"),
                "nama": p.get("nama"),
                "kategori": p.get("kategori"),
                "harga": p_price,
                "harga_formatted": format_rupiah(p_price),
                "spesifikasi": clean_specs(p),
                "image_url": p.get("image_url")
            })

        if not formatted_prods:
            fakta = {
                "status": "tidak_ditemukan",
                "kriteria": {
                    "kategori": kategori, "merek": merek, "merek_kecuali": merek_kecuali,
                    "gpu": gpu, "max_harga": max_harga, "ram_gb_min": ram_gb_min
                },
                "kategori_tersedia": sorted(list(set(str(p.get("kategori")).lower() for p in self.catalog.products if p.get("kategori")))),
                "merek_tersedia": sorted(list(set(get_product_brand(p) for p in self.catalog.products if get_product_brand(p))))
            }
        else:
            # B2: Kategori saja atau merek saja -> tandai butuh dipersempit
            is_broad = bool((merek or kategori) and not (nama_model or gpu or ram_gb_min or max_harga))
            fakta = {
                "status": "sukses",
                "merek_kecuali": merek_kecuali,
                "total_cocok": len(matches),
                "total_ditemukan": len(formatted_prods),
                "produk": formatted_prods,
                "butuh_persempit": is_broad
            }

        return ActionResult(
            aksi=ActionEnum.CARI_PRODUK,
            fakta=fakta,
            produk_list=formatted_prods
        )

    # -------------------------------------------------------------------------
    # 3. evaluasi_kecocokan
    # -------------------------------------------------------------------------
    def _handle_evaluasi_kecocokan(self, args: ActionArguments, state: dict) -> ActionResult:
        target_codes = args.produk or [p.get("kode") for p in state.get("produk_tampil", []) if p.get("kode")]
        kebutuhan_teks = args.kebutuhan_teks or state.get("kebutuhan_teks") or ""

        # B14: Jika tidak ada produk yang dievaluasi
        if not target_codes:
            fakta = {
                "status": "belum_ada_produk",
                "pesan": "Belum ada produk yang dipilih atau ditampilkan untuk dievaluasi."
            }
            return ActionResult(aksi=ActionEnum.EVALUASI_KECOCOKAN, fakta=fakta)

        profil_id = state.get("profil_aktif")
        prof_data = None
        if not profil_id and kebutuhan_teks:
            try:
                reqs = get_usage_requirements(kebutuhan_teks)
                pls = reqs.get("profil", [])
                valid_pls = [p for p in pls if str(p.get("profil_id", "")).startswith("P")]
                if valid_pls:
                    profil_id = valid_pls[0]["profil_id"]
            except Exception as e:
                logger.warning(f"Error evaluasi profiling: {e}")

        if profil_id:
            prof_data = get_profile_by_id(profil_id)

        # B14: Tanpa profil kebutuhan yang valid
        if not profil_id or not prof_data:
            fakta = {
                "status": "profil_tidak_ditemukan",
                "pesan": "Kebutuhan penggunaan belum ditentukan atau profil tidak ditemukan untuk evaluasi kelayakan."
            }
            return ActionResult(aksi=ActionEnum.EVALUASI_KECOCOKAN, fakta=fakta)

        # Cek ketersediaan produk di katalog (B16)
        catalog_products = []
        for code in target_codes:
            p = None
            for pt in state.get("produk_tampil", []):
                if str(pt.get("kode", "")).upper() == str(code).strip().upper():
                    p = pt
                    break
            if not p:
                p = self.get_product_by_code(code)
            if p:
                catalog_products.append(p)

        if not catalog_products:
            # B16: Produk di luar katalog -> cari padanan terdekat deterministik
            closest = None
            for p in self.catalog.products:
                if str(p.get("kategori", "")).lower() == "laptop":
                    closest = p
                    break
            if not closest and self.catalog.products:
                closest = self.catalog.products[0]
            padanan = {
                "kode": closest.get("kode"),
                "nama": closest.get("nama"),
                "kategori": closest.get("kategori"),
                "harga": get_product_price(closest),
                "harga_formatted": format_rupiah(get_product_price(closest)),
                "spesifikasi": clean_specs(closest)
            } if closest else {}
            fakta = {
                "status": "produk_tidak_di_katalog",
                "produk_diminta": target_codes,
                "padanan_terdekat": padanan,
                "pesan": f"Produk {', '.join([str(c) for c in target_codes])} tidak tersedia di katalog ReIn Komputer. Pilihan padanan terdekat yang tersedia adalah {padanan.get('nama', '')}."
            }
            return ActionResult(aksi=ActionEnum.EVALUASI_KECOCOKAN, fakta=fakta)

        filters = prof_data.get("filter", []) if prof_data else []

        eval_results = []
        for p in catalog_products:
            p_price = get_product_price(p)
            p_cpu_tier = p.get("cpu_tier") or 1
            p_ram = p.get("ram_gb") or 8
            p_ssd = p.get("storage_ssd_gb") or 256
            p_vram = p.get("vram_gb") or p.get("gpu_vram_gb") or 0

            min_cpu = 1
            min_ram = 8
            min_ssd = 256
            min_vram = 0

            for f in filters:
                f_field = f.get("field")
                f_val = f.get("value")
                if f_field == "cpu_tier" and isinstance(f_val, (int, float)):
                    min_cpu = int(f_val)
                elif f_field == "ram_gb" and isinstance(f_val, (int, float)):
                    min_ram = int(f_val)
                elif f_field == "storage_ssd_gb" and isinstance(f_val, (int, float)):
                    min_ssd = int(f_val)
                elif f_field == "vram_gb" and isinstance(f_val, (int, float)):
                    min_vram = int(f_val)

            rec_cpu = min(4, min_cpu + 1)
            rec_ram = max(16, min_ram * 2) if min_ram < 16 else min_ram
            rec_ssd = max(512, min_ssd * 2) if min_ssd < 512 else min_ssd
            rec_vram = max(min_vram, 4 if min_vram > 0 else 0)

            diff_min = [p_cpu_tier - min_cpu, p_ram - min_ram, p_ssd - min_ssd, p_vram - min_vram]
            diff_rec = [p_cpu_tier - rec_cpu, p_ram - rec_ram, p_ssd - rec_ssd, p_vram - rec_vram]
            if any(d < 0 for d in diff_min):
                status_kecocokan = "di_bawah_minimum"
            elif all(d >= 0 for d in diff_rec):
                status_kecocokan = "memenuhi_rekomendasi"
            else:
                status_kecocokan = "memenuhi_minimum"

            eval_results.append({
                "kode": p.get("kode"),
                "nama": p.get("nama"),
                "harga": p_price,
                "harga_formatted": format_rupiah(p_price),
                "spesifikasi_aktual": clean_specs(p),
                "status_kecocokan": status_kecocokan,
                "deskripsi_cpu": {
                    "aktual": p.get("cpu") or f"Tingkat prosesor {p_cpu_tier}",
                    "minimum": cpu_tier_to_description(min_cpu),
                    "rekomendasi": cpu_tier_to_description(rec_cpu)
                },
                "angka_aktual": {
                    "cpu_tier": p_cpu_tier,
                    "ram_gb": p_ram,
                    "ssd_gb": p_ssd,
                    "gpu_vram_gb": p_vram
                },
                "standar_profil": {
                    "minimum": {
                        "cpu_tier": min_cpu,
                        "ram_gb": min_ram,
                        "ssd_gb": min_ssd,
                        "gpu_vram_gb": min_vram
                    },
                    "rekomendasi": {
                        "cpu_tier": rec_cpu,
                        "ram_gb": rec_ram,
                        "ssd_gb": rec_ssd,
                        "gpu_vram_gb": rec_vram
                    }
                },
                "selisih_terhadap_minimum": {
                    "cpu_tier": p_cpu_tier - min_cpu,
                    "ram_gb": p_ram - min_ram,
                    "ssd_gb": p_ssd - min_ssd,
                    "gpu_vram_gb": p_vram - min_vram
                },
                "selisih_terhadap_rekomendasi": {
                    "cpu_tier": p_cpu_tier - rec_cpu,
                    "ram_gb": p_ram - rec_ram,
                    "ssd_gb": p_ssd - rec_ssd,
                    "gpu_vram_gb": p_vram - rec_vram
                }
            })

        fakta = {
            "status": "sukses",
            "kebutuhan_teks": kebutuhan_teks,
            "profil_id": profil_id,
            "profil_judul": prof_data.get("judul") if prof_data else None,
            "evaluasi_produk": eval_results
        }
        return ActionResult(aksi=ActionEnum.EVALUASI_KECOCOKAN, fakta=fakta)

    # -------------------------------------------------------------------------
    # 4. tanya_spesifikasi (A5)
    # -------------------------------------------------------------------------
    def _handle_tanya_spesifikasi(self, args: ActionArguments, state: dict) -> ActionResult:
        target_codes = args.produk or [p.get("kode") for p in state.get("produk_tampil", []) if p.get("kode")]
        attr = args.atribut or AtributSpesifikasiEnum.LAINNYA

        if not target_codes:
            fakta = {
                "status": "belum_ada_produk",
                "pesan": "Belum ada produk yang dipilih untuk ditanyakan spesifikasinya."
            }
            return ActionResult(aksi=ActionEnum.TANYA_SPESIFIKASI, fakta=fakta)

        # Cek produk di katalog
        catalog_products = []
        for code in target_codes:
            p = None
            for pt in state.get("produk_tampil", []):
                if str(pt.get("kode", "")).upper() == str(code).strip().upper():
                    p = pt
                    break
            if not p:
                p = self.get_product_by_code(code)
            if p:
                catalog_products.append(p)

        if not catalog_products:
            # B16: Produk di luar katalog
            closest = None
            for p in self.catalog.products:
                if str(p.get("kategori", "")).lower() == "laptop":
                    closest = p
                    break
            if not closest and self.catalog.products:
                closest = self.catalog.products[0]
            padanan = {
                "kode": closest.get("kode"),
                "nama": closest.get("nama"),
                "kategori": closest.get("kategori"),
                "harga": get_product_price(closest),
                "harga_formatted": format_rupiah(get_product_price(closest)),
                "spesifikasi": clean_specs(closest)
            } if closest else {}
            fakta = {
                "status": "produk_tidak_di_katalog",
                "produk_diminta": target_codes,
                "padanan_terdekat": padanan,
                "pesan": f"Produk {', '.join([str(c) for c in target_codes])} tidak tersedia di katalog ReIn Komputer. Pilihan padanan terdekat yang tersedia adalah {padanan.get('nama', '')}."
            }
            return ActionResult(aksi=ActionEnum.TANYA_SPESIFIKASI, fakta=fakta)

        # B15: Mapping spesifikasi per kategori
        fakta_items = []
        ada_tidak_tersedia = False

        for p in catalog_products:
            kategori = str(p.get("kategori", "")).lower()
            val = None

            if attr == AtributSpesifikasiEnum.HARGA:
                p_price = get_product_price(p)
                val = format_rupiah(p_price)
            elif attr == AtributSpesifikasiEnum.RAM:
                if kategori in ("laptop", "desktop", "all-in-one"):
                    val = p.get("ram") or (f"{p.get('ram_gb')} GB" if p.get("ram_gb") else None)
            elif attr == AtributSpesifikasiEnum.STORAGE:
                if kategori in ("laptop", "desktop", "all-in-one"):
                    val = p.get("storage") or (f"{p.get('storage_ssd_gb')} GB" if p.get("storage_ssd_gb") else None)
            elif attr == AtributSpesifikasiEnum.CPU:
                if kategori in ("laptop", "desktop", "all-in-one"):
                    val = p.get("cpu")
            elif attr == AtributSpesifikasiEnum.GPU:
                if kategori in ("laptop", "desktop", "all-in-one"):
                    val = p.get("gpu")
            elif attr == AtributSpesifikasiEnum.LAYAR:
                if kategori in ("laptop", "monitor"):
                    val = p.get("display") or (f"{p.get('screen_inch')} inci" if p.get("screen_inch") else None)
            elif attr == AtributSpesifikasiEnum.BATERAI:
                if kategori == "laptop":
                    val = p.get("baterai")
            elif attr == AtributSpesifikasiEnum.PORT:
                val = p.get("ports") or p.get("port")
            elif attr == AtributSpesifikasiEnum.BOBOT:
                val = p.get("bobot")
            elif attr == AtributSpesifikasiEnum.KEYBOARD:
                val = p.get("keyboard")
            elif attr == AtributSpesifikasiEnum.KAMERA:
                if kategori == "laptop":
                    val = p.get("webcam") or p.get("kamera")
            else:
                val = p.get(attr.value if hasattr(attr, "value") else str(attr))

            if not val:
                ada_tidak_tersedia = True
            else:
                fakta_items.append({
                    "kode": p.get("kode"),
                    "nama": p.get("nama"),
                    "atribut": attr.value if hasattr(attr, "value") else str(attr),
                    "nilai_spesifikasi": str(val)
                })

        if ada_tidak_tersedia and not fakta_items:
            fakta = {
                "status": "atribut_tidak_tersedia",
                "atribut_ditanya": attr.value if hasattr(attr, "value") else str(attr),
                "pesan": f"Informasi spesifikasi '{attr.value if hasattr(attr, 'value') else str(attr)}' tidak tersedia untuk produk tersebut."
            }
        else:
            fakta = {
                "status": "sukses",
                "atribut_ditanya": attr.value if hasattr(attr, "value") else str(attr),
                "spesifikasi": fakta_items
            }

        return ActionResult(aksi=ActionEnum.TANYA_SPESIFIKASI, fakta=fakta)

    # -------------------------------------------------------------------------
    # 5. bandingkan (A6)
    # -------------------------------------------------------------------------
    def _handle_bandingkan(self, args: ActionArguments, state: dict) -> ActionResult:
        target_codes = args.produk or [p.get("kode") for p in state.get("produk_tampil", []) if p.get("kode")]
        items = []
        for code in target_codes:
            p = self.get_product_by_code(code)
            if not p:
                continue
            p_price = get_product_price(p)
            items.append({
                "kode": p.get("kode"),
                "nama": p.get("nama"),
                "harga": p_price,
                "harga_formatted": format_rupiah(p_price),
                "cpu": p.get("cpu"),
                "gpu": p.get("gpu"),
                "ram": p.get("ram") or f"{p.get('ram_gb', '')} GB",
                "storage": p.get("storage") or f"{p.get('storage_ssd_gb', '')} GB",
                "display": p.get("display") or f"{p.get('ukuran_layar', '')} inci"
            })

        produk_luar = args.produk_luar_katalog or []
        status = "sukses"
        catatan = None
        if produk_luar:
            nama_luar_str = ", ".join(produk_luar)
            if items:
                status = "sebagian_tidak_di_katalog"
                catatan = f"Produk '{nama_luar_str}' tidak tersedia di katalog ReIn Komputer. Berikut spesifikasi produk di katalog kami untuk perbandingan."
            else:
                status = "tidak_di_katalog"
                catatan = f"Produk '{nama_luar_str}' tidak tersedia di katalog ReIn Komputer."

        fakta = {
            "status": status,
            "total_dibandingkan": len(items),
            "perbandingan": items,
            "produk_luar_katalog": produk_luar,
            "catatan": catatan
        }
        return ActionResult(aksi=ActionEnum.BANDINGKAN, fakta=fakta)

    # -------------------------------------------------------------------------
    # 6. lanjutan_hasil (B3, B8, B9)
    # -------------------------------------------------------------------------
    def _handle_lanjutan_hasil(self, args: ActionArguments, state: dict) -> ActionResult:
        tampil = state.get("produk_tampil", [])

        # B9: Jika belum ada produk tampil
        if not tampil:
            fakta = {
                "status": "belum_ada_hasil",
                "alasan": "rujukan_tidak_ada",
                "pesan": "Belum ada produk yang ditampilkan sebelumnya untuk disesuaikan.",
                "total_ditemukan": 0,
                "produk": []
            }
            return ActionResult(aksi=ActionEnum.LANJUTAN_HASIL, fakta=fakta, produk_list=[])

        jenis = args.jenis.value if hasattr(args.jenis, "value") else str(args.jenis)

        # B3: Kategori aktif diambil dari produk_tampil di sesi
        kategori = tampil[0].get("kategori") or state.get("kategori") or "laptop"

        candidates = [p for p in self.catalog.products if p.get("kategori", "").lower() == str(kategori).lower()]

        batas_dipakai = None
        if jenis == "lebih_murah":
            lowest_p = min((get_product_price(p) for p in tampil), default=10_000_000)
            matches = [p for p in candidates if get_product_price(p) < lowest_p]
            matches.sort(key=lambda x: -get_product_price(x))

            # B8: Tidak ada opsi lebih murah
            if not matches:
                min_cat_price = min((get_product_price(p) for p in candidates), default=lowest_p)
                fakta = {
                    "status": "tidak_ada_lebih_murah",
                    "harga_termurah_saat_ini": lowest_p,
                    "harga_termurah_saat_ini_formatted": format_rupiah(lowest_p),
                    "harga_termurah_kategori": min_cat_price,
                    "harga_termurah_kategori_formatted": format_rupiah(min_cat_price),
                    "kategori": kategori,
                    "kategori_dipakai": kategori,
                    "pesan": f"Produk yang ditampilkan sebelumnya sudah merupakan opsi paling terjangkau di katalog kami ({format_rupiah(lowest_p)})."
                }
                return ActionResult(aksi=ActionEnum.LANJUTAN_HASIL, fakta=fakta, produk_list=[])
            batas_dipakai = lowest_p
            state["budget"] = get_product_price(matches[0])

        elif jenis == "lebih_mahal":
            highest_p = max((get_product_price(p) for p in tampil), default=5_000_000)
            matches = [p for p in candidates if get_product_price(p) > highest_p]
            matches.sort(key=lambda x: get_product_price(x))

            # B8: Tidak ada opsi lebih mahal
            if not matches:
                max_cat_price = max((get_product_price(p) for p in candidates), default=highest_p)
                fakta = {
                    "status": "tidak_ada_lebih_mahal",
                    "harga_termahal_saat_ini": highest_p,
                    "harga_termahal_saat_ini_formatted": format_rupiah(highest_p),
                    "harga_termahal_kategori": max_cat_price,
                    "harga_termahal_kategori_formatted": format_rupiah(max_cat_price),
                    "kategori": kategori,
                    "kategori_dipakai": kategori,
                    "pesan": f"Produk yang ditampilkan sebelumnya sudah merupakan opsi tertinggi di katalog kami ({format_rupiah(highest_p)})."
                }
                return ActionResult(aksi=ActionEnum.LANJUTAN_HASIL, fakta=fakta, produk_list=[])
            batas_dipakai = highest_p
            state["budget"] = get_product_price(matches[-1]) if matches else highest_p

        elif jenis == "yang_lain" or jenis == "filter_tambahan" or args.merek_kecuali or args.filter:
            seen_kodes = {p.get("kode") for p in tampil}
            matches = [p for p in candidates if p.get("kode") not in seen_kodes]
            if not matches:
                matches = list(candidates)
            matches.sort(key=lambda x: get_product_price(x))
        else:
            matches = []

        if args.merek_kecuali:
            mk_clean = str(args.merek_kecuali).strip().lower()
            matches = [
                p for p in matches
                if mk_clean != get_product_brand(p)
                and mk_clean not in get_product_brand(p)
                and mk_clean not in str(p.get("nama", "")).lower()
            ]

        top = matches[:3]
        formatted = []
        for p in top:
            p_price = get_product_price(p)
            formatted.append({
                "kode": p.get("kode"),
                "nama": p.get("nama"),
                "kategori": p.get("kategori"),
                "harga": p_price,
                "harga_formatted": format_rupiah(p_price),
                "spesifikasi": clean_specs(p),
                "image_url": p.get("image_url")
            })

        fakta = {
            "status": "sukses",
            "jenis": jenis,
            "kategori": kategori,
            "kategori_dipakai": kategori,
            "batas_harga": batas_dipakai,
            "merek_kecuali": args.merek_kecuali,
            "total_ditemukan": len(formatted),
            "produk": formatted
        }
        return ActionResult(aksi=ActionEnum.LANJUTAN_HASIL, fakta=fakta, produk_list=formatted)

    # -------------------------------------------------------------------------
    # 7. tanya_info_toko (A9)
    # -------------------------------------------------------------------------
    def _handle_tanya_info_toko(self, args: ActionArguments, state: dict) -> ActionResult:
        topik = args.topik.value if hasattr(args.topik, "value") else str(args.topik)
        kontak_staf = KONTAK_STAF
        fakta = {
            "status": "info_toko",
            "topik": topik,
            "data_tersedia": False,
            "kontak_staf": kontak_staf,
            "arahan": f"Berikan kontak staf toko di {kontak_staf} secara sopan tanpa menyebut estimasi durasi respons atau janji spesifik."
        }
        return ActionResult(aksi=ActionEnum.TANYA_INFO_TOKO, fakta=fakta, produk_list=[])

    # -------------------------------------------------------------------------
    # 8. jawab_pertanyaan_bot (A7)
    # -------------------------------------------------------------------------
    def _handle_jawab_pertanyaan_bot(self, args: ActionArguments, state: dict) -> ActionResult:
        slot = args.slot.value if hasattr(args.slot, "value") else str(args.slot)
        slot_val = args.nilai

        # Perbarui slot state yang relevan
        if slot in ("kategori", "category"):
            state["kategori"] = str(slot_val).strip().lower()
        elif slot in ("budget", "anggaran"):
            state["budget"] = parse_int_safe(slot_val)
        elif slot in ("persona",):
            state["persona"] = str(slot_val).strip().lower()
        elif slot in ("kebutuhan", "aktivitas"):
            state["kebutuhan_teks"] = str(slot_val).strip()
        elif slot in ("merek", "brand"):
            state["merek"] = str(slot_val).strip().lower()

        state["pending_question"] = None

        # Jalankan ulang aksi dengan slot yang baru
        if state.get("kebutuhan_teks"):
            return self._handle_minta_rekomendasi(args, state)
        else:
            return self._handle_cari_produk(args, state)

    # -------------------------------------------------------------------------
    # 9. perbaiki_percakapan
    # -------------------------------------------------------------------------
    def _handle_perbaiki_percakapan(self, args: ActionArguments, state: dict) -> ActionResult:
        jenis = args.jenis.value if hasattr(args.jenis, "value") else str(args.jenis)
        fakta = {
            "status": "sukses",
            "jenis": jenis,
            "rujukan": args.rujukan,
            "kebutuhan_terekam": state.get("kebutuhan_teks"),
            "pertanyaan_terakhir_bot": state.get("pending_question")
        }
        return ActionResult(aksi=ActionEnum.PERBAIKI_PERCAKAPAN, fakta=fakta, produk_list=[])

    # -------------------------------------------------------------------------
    # 10. sapa, basa_basi, tidak_jelas (B12)
    # -------------------------------------------------------------------------
    def _handle_sapa(self, args: ActionArguments, state: dict) -> ActionResult:
        fakta = {
            "status": "sapaan",
            "sebutan": state.get("sebutan")
        }
        return ActionResult(aksi=ActionEnum.SAPA, fakta=fakta, produk_list=[])

    def _handle_basa_basi(self, args: ActionArguments, state: dict) -> ActionResult:
        jenis = args.jenis.value if hasattr(args.jenis, "value") else str(args.jenis)
        fakta = {
            "status": "basa_basi",
            "jenis": jenis
        }
        return ActionResult(aksi=ActionEnum.BASA_BASI, fakta=fakta, produk_list=[])

    def _handle_tidak_jelas(self, args: ActionArguments, state: dict) -> ActionResult:
        alasan = args.alasan.value if hasattr(args.alasan, "value") else str(args.alasan or "tidak_dipahami")
        if alasan not in ("tidak_dipahami", "rujukan_tidak_ada", "bertentangan", "sistem_error"):
            alasan = "tidak_dipahami"

        pesan_map = {
            "tidak_dipahami": "Maksud pesan belum dapat dipastikan secara spesifik. Silakan jelaskan kebutuhan perangkat yang dicari.",
            "rujukan_tidak_ada": "Produk yang dirujuk tidak ditemukan di daftar yang sedang tampil.",
            "bertentangan": "Informasi yang diberikan tidak konsisten atau bernilai kosong.",
            "sistem_error": "Terjadi kendala teknis pada sistem pemrosesan pesan."
        }
        fakta = {
            "status": "tidak_jelas",
            "alasan": alasan,
            "pesan": pesan_map[alasan]
        }
        return ActionResult(aksi=ActionEnum.TIDAK_JELAS, fakta=fakta, produk_list=[])
