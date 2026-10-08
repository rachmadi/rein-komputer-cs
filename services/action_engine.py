# -*- coding: utf-8 -*-
"""
services/action_engine.py
Mesin Deterministik Per Aksi untuk Bobby Computer (Antigravity v2).

Prinsip:
- Fungsi murni deterministik, tidak menghasilkan kalimat percakapan.
- Menghasilkan fakta terstruktur (JSON/dict) untuk dikonsumsi Generator LLM.
- Menjalankan aksi:
  1. minta_rekomendasi (RAG profil -> filter katalog -> ranking & match report)
  2. cari_produk (filter katalog SQL/memory berparameter)
  3. evaluasi_kecocokan (alat evaluasi spek vs syarat profil)
  4. tanya_spesifikasi (fakta atribut produk katalog)
  5. bandingkan (komparasi berdampingan produk)
  6. lanjutan_hasil (lebih murah/mahal, yang lain, filter tambahan)
  7. tanya_info_toko (info toko ke staf)
  8. jawab_pertanyaan_bot, perbaiki_percakapan, sapa, basa_basi, tidak_jelas
"""
from __future__ import annotations

import os
import re
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.schema_actions import ParserOutput, ActionEnum, ActionArguments, AtributSpesifikasiEnum
from services.catalog_search import apply_filters, clean_specs, format_natural_unmet_requirements
from services.knowledge_service import get_usage_requirements, get_profile_by_id
from core.catalog import Catalog

logger = logging.getLogger(__name__)


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
        state = session_state or {}
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
    # 1. minta_rekomendasi
    # -------------------------------------------------------------------------
    def _handle_minta_rekomendasi(self, args: ActionArguments, state: dict) -> ActionResult:
        kebutuhan_teks = args.kebutuhan_teks or state.get("kebutuhan_teks") or ""
        budget_max = args.budget_max or state.get("budget")
        kategori = args.kategori or state.get("kategori") or "laptop"

        profil_id = None
        prof_data = None
        if kebutuhan_teks:
            reqs = get_usage_requirements(kebutuhan_teks)
            pls = reqs.get("profil", [])
            valid_pls = [p for p in pls if str(p.get("profil_id", "")).startswith("P")]
            if valid_pls:
                profil_id = valid_pls[0]["profil_id"]
                prof_data = get_profile_by_id(profil_id)

        if not profil_id and state.get("profil_aktif"):
            profil_id = state.get("profil_aktif")
            prof_data = get_profile_by_id(profil_id)

        if not profil_id or not prof_data:
            fakta = {
                "status": "profil_tidak_ditemukan",
                "kebutuhan_teks": kebutuhan_teks,
                "pesan": "Kebutuhan belum terdaftar dalam basis pengetahuan profil toko."
            }
            return ActionResult(aksi=ActionEnum.MINTA_REKOMENDASI, fakta=fakta)

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
    # 2. cari_produk
    # -------------------------------------------------------------------------
    def _handle_cari_produk(self, args: ActionArguments, state: dict) -> ActionResult:
        kategori = args.kategori or state.get("kategori")
        merek = args.merek
        merek_kecuali = args.merek_kecuali
        nama_model = args.nama_model
        gpu = args.gpu
        min_harga = args.min_harga
        max_harga = args.max_harga or state.get("budget")
        ram_gb_min = args.ram_gb_min
        storage_gb_min = args.storage_gb_min
        ukuran_layar = args.ukuran_layar

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
            if ukuran_layar:
                p_inch = get_product_screen_inch(p)
                if p_inch is not None and abs(p_inch - float(ukuran_layar)) > 0.6:
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
            fakta = {
                "status": "sukses",
                "merek_kecuali": merek_kecuali,
                "total_cocok": len(matches),
                "total_ditemukan": len(formatted_prods),
                "produk": formatted_prods
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

        profil_id = state.get("profil_aktif")
        prof_data = None
        if not profil_id and kebutuhan_teks:
            reqs = get_usage_requirements(kebutuhan_teks)
            pls = reqs.get("profil", [])
            valid_pls = [p for p in pls if str(p.get("profil_id", "")).startswith("P")]
            if valid_pls:
                profil_id = valid_pls[0]["profil_id"]

        if profil_id:
            prof_data = get_profile_by_id(profil_id)

        filters = prof_data.get("filter", []) if prof_data else []

        eval_results = []
        for code in target_codes:
            p = self.get_product_by_code(code)
            if not p:
                continue

            p_price = get_product_price(p)
            p_cpu_tier = p.get("cpu_tier") or 1
            p_ram = p.get("ram_gb") or 8
            p_ssd = p.get("storage_ssd_gb") or 256
            p_vram = p.get("vram_gb") or p.get("gpu_vram_gb") or 0

            # Target minimum dan rekomendasi dari profil
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
    # 4. tanya_spesifikasi
    # -------------------------------------------------------------------------
    def _handle_tanya_spesifikasi(self, args: ActionArguments, state: dict) -> ActionResult:
        target_codes = args.produk or [p.get("kode") for p in state.get("produk_tampil", []) if p.get("kode")]
        attr = args.atribut or AtributSpesifikasiEnum.LAINNYA

        attr_key_map = {
            AtributSpesifikasiEnum.RAM: "ram",
            AtributSpesifikasiEnum.STORAGE: "storage",
            AtributSpesifikasiEnum.CPU: "cpu",
            AtributSpesifikasiEnum.GPU: "gpu",
            AtributSpesifikasiEnum.LAYAR: "display",
            AtributSpesifikasiEnum.BATERAI: "baterai",
            AtributSpesifikasiEnum.PORT: "ports",
            AtributSpesifikasiEnum.BOBOT: "bobot",
            AtributSpesifikasiEnum.KEYBOARD: "keyboard",
            AtributSpesifikasiEnum.KAMERA: "webcam"
        }
        col = attr_key_map.get(attr)

        fakta_items = []
        for code in target_codes:
            p = self.get_product_by_code(code)
            if not p:
                continue
            val = p.get(col) if col else None
            if not val:
                val = clean_specs(p)

            fakta_items.append({
                "kode": p.get("kode"),
                "nama": p.get("nama"),
                "atribut": attr.value,
                "nilai_spesifikasi": str(val)
            })

        fakta = {
            "status": "sukses",
            "atribut_ditanya": attr.value,
            "spesifikasi": fakta_items
        }
        return ActionResult(aksi=ActionEnum.TANYA_SPESIFIKASI, fakta=fakta)

    # -------------------------------------------------------------------------
    # 5. bandingkan
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
                catatan = f"Produk '{nama_luar_str}' tidak tersedia di katalog Bobby Computer (toko kami berfokus pada laptop dan PC Windows resmi). Berikut spesifikasi produk di katalog kami untuk perbandingan."
            else:
                status = "tidak_di_katalog"
                catatan = f"Produk '{nama_luar_str}' tidak tersedia di katalog Bobby Computer."

        fakta = {
            "status": status,
            "total_dibandingkan": len(items),
            "perbandingan": items,
            "produk_luar_katalog": produk_luar,
            "catatan": catatan
        }
        return ActionResult(aksi=ActionEnum.BANDINGKAN, fakta=fakta)

    # -------------------------------------------------------------------------
    # 6. lanjutan_hasil
    # -------------------------------------------------------------------------
    def _handle_lanjutan_hasil(self, args: ActionArguments, state: dict) -> ActionResult:
        tampil = state.get("produk_tampil", [])
        if not tampil:
            fakta = {
                "status": "belum_ada_hasil",
                "pesan": "Belum ada produk yang ditampilkan sebelumnya untuk disesuaikan.",
                "total_ditemukan": 0,
                "produk": []
            }
            return ActionResult(aksi=ActionEnum.LANJUTAN_HASIL, fakta=fakta, produk_list=[])

        jenis = args.jenis.value if hasattr(args.jenis, "value") else str(args.jenis)
        kategori = state.get("kategori") or "laptop"

        candidates = [p for p in self.catalog.products if p.get("kategori", "").lower() == kategori.lower()]

        if jenis == "lebih_murah":
            lowest_p = min((get_product_price(p) for p in tampil), default=10_000_000)
            matches = [p for p in candidates if get_product_price(p) < lowest_p]
            matches.sort(key=lambda x: -get_product_price(x))  # harga tertinggi di bawah patokan
        elif jenis == "lebih_mahal":
            highest_p = max((get_product_price(p) for p in tampil), default=5_000_000)
            matches = [p for p in candidates if get_product_price(p) > highest_p]
            matches.sort(key=lambda x: get_product_price(x))
        elif jenis == "yang_lain":
            seen_kodes = {p.get("kode") for p in tampil}
            matches = [p for p in candidates if p.get("kode") not in seen_kodes]
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
            "merek_kecuali": args.merek_kecuali,
            "total_ditemukan": len(formatted),
            "produk": formatted
        }
        return ActionResult(aksi=ActionEnum.LANJUTAN_HASIL, fakta=fakta, produk_list=formatted)

    # -------------------------------------------------------------------------
    # 7. tanya_info_toko
    # -------------------------------------------------------------------------
    def _handle_tanya_info_toko(self, args: ActionArguments, state: dict) -> ActionResult:
        topik = args.topik.value if hasattr(args.topik, "value") else str(args.topik)
        fakta = {
            "topik": topik,
            "data_tersedia": False,
            "kontak_staf": os.getenv("KONTAK_STAF", "@cs_bobbycomputer"),
            "arahan": "Arahkan pelanggan menghubungi staf toko di @cs_bobbycomputer untuk informasi toko resmi."
        }
        return ActionResult(aksi=ActionEnum.TANYA_INFO_TOKO, fakta=fakta)

    # -------------------------------------------------------------------------
    # 8. jawab_pertanyaan_bot
    # -------------------------------------------------------------------------
    def _handle_jawab_pertanyaan_bot(self, args: ActionArguments, state: dict) -> ActionResult:
        slot = args.slot.value if hasattr(args.slot, "value") else str(args.slot)
        fakta = {
            "slot_dijawab": slot,
            "nilai": args.nilai,
            "kebutuhan_teks": state.get("kebutuhan_teks"),
            "persona": state.get("persona"),
            "budget": state.get("budget"),
            "kategori": state.get("kategori")
        }
        return ActionResult(aksi=ActionEnum.JAWAB_PERTANYAAN_BOT, fakta=fakta)

    # -------------------------------------------------------------------------
    # 9. perbaiki_percakapan
    # -------------------------------------------------------------------------
    def _handle_perbaiki_percakapan(self, args: ActionArguments, state: dict) -> ActionResult:
        jenis = args.jenis.value if hasattr(args.jenis, "value") else str(args.jenis)
        fakta = {
            "jenis": jenis,
            "rujukan": args.rujukan,
            "kebutuhan_terekam": state.get("kebutuhan_teks"),
            "pertanyaan_terakhir_bot": state.get("pending_question")
        }
        return ActionResult(aksi=ActionEnum.PERBAIKI_PERCAKAPAN, fakta=fakta)

    # -------------------------------------------------------------------------
    # 10. sapa, basa_basi, tidak_jelas
    # -------------------------------------------------------------------------
    def _handle_sapa(self, args: ActionArguments, state: dict) -> ActionResult:
        fakta = {
            "status": "sapaan",
            "sebutan": state.get("sebutan")
        }
        return ActionResult(aksi=ActionEnum.SAPA, fakta=fakta)

    def _handle_basa_basi(self, args: ActionArguments, state: dict) -> ActionResult:
        jenis = args.jenis.value if hasattr(args.jenis, "value") else str(args.jenis)
        fakta = {
            "jenis": jenis
        }
        return ActionResult(aksi=ActionEnum.BASA_BASI, fakta=fakta)

    def _handle_tidak_jelas(self, args: ActionArguments, state: dict) -> ActionResult:
        fakta = {
            "alasan": args.alasan or "Maksud pesan belum dapat dipastikan secara spesifik"
        }
        return ActionResult(aksi=ActionEnum.TIDAK_JELAS, fakta=fakta)
