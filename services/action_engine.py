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


def build_lembar_spesifikasi(p: dict) -> dict[str, Any]:
    """Merakit lembar spesifikasi lengkap: semua kolom tidak kosong + isi raw_data (Putaran 13 Butir C)."""
    if not isinstance(p, dict):
        return {}
    specs: dict[str, Any] = {}

    field_labels = {
        "nama": "nama",
        "kategori": "kategori",
        "brand": "merek",
        "cpu": "prosesor",
        "ram": "ram",
        "storage": "penyimpanan",
        "gpu": "grafis",
        "display": "layar",
        "os": "sistem_operasi",
    }
    for k, label in field_labels.items():
        v = p.get(k)
        if v not in (None, "", [], {}):
            specs[label] = v

    p_price = p.get("harga") or p.get("harga_idr")
    if p_price:
        specs["harga"] = format_rupiah(int(p_price))

    raw = p.get("raw_data")
    if raw:
        raw_dict = {}
        if isinstance(raw, dict):
            raw_dict = raw
        elif isinstance(raw, str):
            try:
                raw_dict = json.loads(raw)
            except Exception:
                pass
        for rk, rv in raw_dict.items():
            if rv not in (None, "", [], {}):
                lbl = "kecepatan_cetak" if rk == "kecepatan" else rk
                specs[lbl] = rv

    extra_fields = ["fungsi", "teknologi", "kecepatan", "resolusi", "konektivitas", "garansi"]
    for ef in extra_fields:
        v = p.get(ef)
        if v not in (None, "", [], {}) and ef not in specs:
            lbl = "kecepatan_cetak" if ef == "kecepatan" else ef
            specs[lbl] = v

    return specs


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

    def resolve_produk(self, args: ActionArguments, state: dict) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Resolusi produk satu pintu (D1, D2, D3, B14, B15, B16, A5-A7):
        Mengembalikan (daftar produk katalog penuh, daftar kode rujukan).
        Membaca nilai lengkap dari self.catalog.products. state['produk_tampil']
        hanya digunakan untuk rujukan urutan nomor atau pemetaan rujukan.
        """
        raw_codes = args.produk or args.rujukan_produk or []
        tampil = state.get("produk_tampil", [])
        history_tampil = state.get("history_produk_tampil", [])
        fokus = state.get("produk_dibahas", [])
        if isinstance(fokus, str):
            fokus = [fokus]
        prev_stack = state.get("produk_dibahas_sebelumnya", [])

        # Jika args.produk dan args.rujukan_produk kosong, ambil produk default:
        if not raw_codes:
            if fokus:
                raw_codes = [c for c in fokus if c]
            elif prev_stack and isinstance(prev_stack, list) and prev_stack[0].get("kode"):
                raw_codes = [c for c in prev_stack[0].get("kode") if c]
            else:
                ptd = state.get("produk_terakhir_dibahas")
                if ptd:
                    if isinstance(ptd, list):
                        raw_codes = [x.get("kode") if isinstance(x, dict) else str(x) for x in ptd]
                    elif isinstance(ptd, dict):
                        raw_codes = [ptd.get("kode")] if ptd.get("kode") else []
                    else:
                        raw_codes = [str(ptd)]
                elif tampil:
                    raw_codes = [p.get("kode") for p in tampil if p.get("kode")]

        if not raw_codes:
            return [], []

        resolved_products = []
        resolved_codes = []

        for ref in raw_codes:
            ref_str = str(ref).strip()
            ref_clean = ref_str.lower()
            matched_code = None

            # Cek apakah rujukan ditujukan ke riwayat/sebelumnya (F6)
            is_history_ref = bool(re.search(r"\b(sebelumnya|tadi|kemarin|lalu|riwayat|dulu)\b", ref_clean))

            # 0. Rujukan afirmatif pendek / demonstratif ("boleh", "ya", "itu", "tadi", "mau", dll.)
            if re.search(r"^(?:ya|iya|boleh|mau|ok|oke|siap|tampilkan|mau\s+lihat|itu|ini|yang\s+itu|tadi|yang\s+tadi|produk\s+tadi|laptop\s+tadi|printer\s+tadi)$", ref_clean):
                if fokus:
                    matched_code = fokus[0]
                elif prev_stack and isinstance(prev_stack, list) and prev_stack[0].get("kode"):
                    matched_code = prev_stack[0].get("kode")[0]
                elif tampil and tampil[0].get("kode"):
                    matched_code = tampil[0]["kode"]

            # 0b. Rujukan termurah tadi / paling murah tadi
            if not matched_code and ref_clean in ("paling murah", "yang paling murah", "termurah", "yang termurah", "yang paling murah tadi", "termurah tadi"):
                target_src = history_tampil if is_history_ref else tampil
                if not target_src:
                    target_src = tampil or history_tampil
                if target_src:
                    cheap_p = min(target_src, key=lambda x: get_product_price(x))
                    matched_code = cheap_p.get("kode")

            # 1. Cek rujukan kode langsung di katalog (misal 'KB-L01')
            if not matched_code and self.get_product_by_code(ref_str):
                matched_code = ref_str.upper()

            # 2. Cek rujukan numerik (indeks 1-based, misal 1, '1', 'nomor 1', 'opsi 1 sebelumnya')
            if not matched_code:
                m_num = re.search(r"^(?:nomor\s*|unit\s*|opsi\s*|produk\s*|pilihan\s*|ke-?\s*)?\[?(\d+)\]?(?:\s+(?:sebelumnya|tadi|kemarin|lalu|riwayat|dulu))?$", ref_str, re.IGNORECASE)
                if m_num:
                    idx = int(m_num.group(1)) - 1
                    if is_history_ref and history_tampil and 0 <= idx < len(history_tampil):
                        matched_code = history_tampil[idx].get("kode")
                    elif not is_history_ref and 0 <= idx < len(tampil):
                        matched_code = tampil[idx].get("kode")
                    elif history_tampil and 0 <= idx < len(history_tampil):
                        matched_code = history_tampil[idx].get("kode")
                    else:
                        resolved_codes.append(ref_str)
                        continue

            # 2b. Cek rujukan kata ordinal ('pertama', 'kedua', 'ketiga')
            if not matched_code:
                ord_map = {"pertama": 0, "kesatu": 0, "kedua": 1, "ketiga": 2}
                for w_ord, o_idx in ord_map.items():
                    if re.search(rf"\b(opsi|nomor|unit|pilihan|produk)?\s*{w_ord}\b", ref_str, re.IGNORECASE):
                        if is_history_ref and history_tampil and 0 <= o_idx < len(history_tampil):
                            matched_code = history_tampil[o_idx].get("kode")
                            break
                        elif not is_history_ref and 0 <= o_idx < len(tampil):
                            matched_code = tampil[o_idx].get("kode")
                            break
                        elif history_tampil and 0 <= o_idx < len(history_tampil):
                            matched_code = history_tampil[o_idx].get("kode")
                            break

            # 3. Cek rujukan nama sebagian / merek menurut hirarki: fokus -> sebelumnya -> tampil/riwayat -> katalog
            if not matched_code:
                clean_kw = re.sub(r"\b(sebelumnya|tadi|kemarin|lalu|riwayat|dulu|yang|itu)\b", "", ref_clean).strip()

                # 3a. Cek fokus
                if fokus:
                    fokus_matched = []
                    for fc in fokus:
                        p_fc = self.get_product_by_code(fc)
                        if p_fc:
                            if clean_kw in str(p_fc.get("nama", "")).lower() or clean_kw == get_product_brand(p_fc):
                                fokus_matched.append(p_fc)
                    if len(fokus_matched) == 1:
                        matched_code = fokus_matched[0].get("kode")
                    elif len(fokus_matched) > 1:
                        state["_ambigu_info"] = {"ambigu": True, "kandidat": fokus_matched}

                # 3b. Cek tumpukan sebelumnya
                if not matched_code and prev_stack:
                    prev_matched = []
                    for entry in prev_stack:
                        e_codes = entry.get("kode", []) if isinstance(entry, dict) else [entry]
                        e_label = str(entry.get("label_kebutuhan", "")).lower() if isinstance(entry, dict) else ""
                        label_hit = bool(e_label and (clean_kw in e_label or e_label in clean_kw))
                        for ec in e_codes:
                            p_ec = self.get_product_by_code(ec)
                            if p_ec:
                                if label_hit or clean_kw in str(p_ec.get("nama", "")).lower() or clean_kw == get_product_brand(p_ec):
                                    if p_ec not in prev_matched:
                                        prev_matched.append(p_ec)
                        if prev_matched:
                            break
                    if len(prev_matched) == 1:
                        matched_code = prev_matched[0].get("kode")
                    elif len(prev_matched) > 1:
                        state["_ambigu_info"] = {"ambigu": True, "kandidat": prev_matched}

                # 3c. Cek produk_tampil lalu history_tampil
                if not matched_code:
                    search_targets = (history_tampil if is_history_ref else tampil) or []
                    fallback_targets = (tampil if is_history_ref else history_tampil) or []
                    tampil_matched = []
                    for pt in search_targets:
                        pt_nama = str(pt.get("nama", "")).lower()
                        pt_brand = get_product_brand(pt)
                        if (clean_kw and clean_kw in pt_nama) or clean_kw == pt_brand:
                            if pt not in tampil_matched:
                                tampil_matched.append(pt)
                    if not tampil_matched:
                        for pt in fallback_targets:
                            pt_nama = str(pt.get("nama", "")).lower()
                            pt_brand = get_product_brand(pt)
                            if (clean_kw and clean_kw in pt_nama) or clean_kw == pt_brand:
                                if pt not in tampil_matched:
                                    tampil_matched.append(pt)
                    if len(tampil_matched) == 1:
                        matched_code = tampil_matched[0].get("kode")
                    elif len(tampil_matched) > 1:
                        state["_ambigu_info"] = {"ambigu": True, "kandidat": tampil_matched}

                # 3d. Cek katalog luas
                if not matched_code:
                    clean_ref = re.sub(r"\b(desktop|laptop|komputer|pc|unit|seri|tipe|model|printer)\b", "", clean_kw, flags=re.IGNORECASE).strip()
                    tokens = [t for t in re.split(r"\s+", clean_ref) if len(t) >= 2]
                    cat_matched = []
                    for p_cat in self.catalog.products:
                        p_nama = str(p_cat.get("nama", "")).lower()
                        p_brand = get_product_brand(p_cat)
                        if (clean_kw and clean_kw in p_nama) or clean_kw == p_brand or (tokens and all((tok in p_nama or tok in p_brand) for tok in tokens)):
                            if p_cat not in cat_matched:
                                cat_matched.append(p_cat)
                    if len(cat_matched) == 1:
                        matched_code = cat_matched[0].get("kode")
                    elif len(cat_matched) > 1:
                        state["_ambigu_info"] = {"ambigu": True, "kandidat": cat_matched}

            if matched_code:
                full_p = self.get_product_by_code(matched_code)
                if full_p:
                    matched_pt = None
                    all_session_prods = list(tampil) + [p for p in (history_tampil or []) if p not in tampil]
                    for pt in all_session_prods:
                        if str(pt.get("kode", "")).upper() == matched_code.upper():
                            matched_pt = pt
                            break
                    if matched_pt:
                        merged_p = dict(full_p)
                        merged_p.update({k: v for k, v in matched_pt.items() if v is not None})
                    else:
                        merged_p = full_p

                    if merged_p not in resolved_products:
                        resolved_products.append(merged_p)
                        resolved_codes.append(matched_code)
            else:
                resolved_codes.append(ref_str)

        return resolved_products, resolved_codes

    def execute(self, parsed: ParserOutput, session_state: dict | None = None) -> ActionResult:
        state = session_state if session_state is not None else {}
        if parsed.pembaruan_state:
            for k, v in parsed.pembaruan_state.model_dump(exclude_unset=True).items():
                if v is not None:
                    state[k] = v

        aksi = parsed.aksi
        args = parsed.argumen

        # C1: Jika parser mengeluarkan kriteria produk di aksi non-pencarian (tidak_jelas, basa_basi, sapa), jalankan pencarian
        # (Kecuali jika alasan adalah sistem_error)
        is_sys_err = getattr(args, "alasan", None) in (AlasanTidakJelasEnum.SISTEM_ERROR, "sistem_error")
        if aksi in (ActionEnum.TIDAK_JELAS, ActionEnum.BASA_BASI, ActionEnum.SAPA) and not is_sys_err:
            has_crit = bool(
                args.kategori or args.merek or (args.max_harga is not None) or (args.budget_max is not None) or
                args.kebutuhan_teks or (parsed.pembaruan_state and (
                    parsed.pembaruan_state.kategori or parsed.pembaruan_state.merek or
                    parsed.pembaruan_state.kebutuhan_teks or (parsed.pembaruan_state.budget is not None)
                ))
            )
            if has_crit:
                if args.kebutuhan_teks or state.get("kebutuhan_teks"):
                    return self._handle_minta_rekomendasi(args, state)
                else:
                    return self._handle_cari_produk(args, state)

        if aksi == ActionEnum.MINTA_REKOMENDASI:
            res = self._handle_minta_rekomendasi(args, state)
        elif aksi == ActionEnum.CARI_PRODUK:
            res = self._handle_cari_produk(args, state)
        elif aksi == ActionEnum.EVALUASI_KECOCOKAN:
            res = self._handle_evaluasi_kecocokan(args, state)
        elif aksi == ActionEnum.TANYA_SPESIFIKASI:
            res = self._handle_tanya_spesifikasi(args, state)
        elif aksi == ActionEnum.BANDINGKAN:
            res = self._handle_bandingkan(args, state)
        elif aksi == ActionEnum.LANJUTAN_HASIL:
            res = self._handle_lanjutan_hasil(args, state)
        elif aksi == ActionEnum.TANYA_INFO_TOKO:
            res = self._handle_tanya_info_toko(args, state)
        elif aksi == ActionEnum.JAWAB_PERTANYAAN_BOT:
            res = self._handle_jawab_pertanyaan_bot(args, state)
        elif aksi == ActionEnum.PERBAIKI_PERCAKAPAN:
            res = self._handle_perbaiki_percakapan(args, state, parsed=parsed)
        elif aksi == ActionEnum.SAPA:
            res = self._handle_sapa(args, state)
        elif aksi == ActionEnum.BASA_BASI:
            res = self._handle_basa_basi(args, state)
        else:  # TIDAK_JELAS
            res = self._handle_tidak_jelas(args, state)

        if state.get("_ambigu_info", {}).get("ambigu"):
            res.fakta["ambigu"] = True
            cands = state["_ambigu_info"].get("kandidat", [])
            res.fakta["kandidat_ambigu"] = [p.get("nama") for p in cands if isinstance(p, dict)]
            if res.fakta.get("kandidat_ambigu"):
                res.fakta["pesan"] = f"Ada beberapa pilihan yang cocok ({', '.join(res.fakta['kandidat_ambigu'])}). Maksud Kakak yang mana?"

        if "belum_dicari" not in res.fakta:
            res.fakta["belum_dicari"] = False if res.produk_list else True
        return res

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
                "belum_dicari": True,
                "pesan": f"Persona '{persona}' telah dicatat. Tanyakan aktivitas atau kebutuhan spesifik yang akan dijalankan."
            }
            return ActionResult(aksi=ActionEnum.MINTA_REKOMENDASI, fakta=fakta, produk_list=[])

        # B3: Hapus default kategori 'laptop'. Simpulkan dari kebutuhan jika jelas, jika tidak biarkan None
        kategori = args.kategori or state.get("kategori")
        kriteria_pelanggan = state.get("kriteria_pelanggan", {}) or {}
        merek = args.merek or state.get("merek") or kriteria_pelanggan.get("merek")
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
            if merek:
                m_clean = str(merek).strip().lower()
                m_cands = [p for p in cat_candidates if m_clean == get_product_brand(p) or m_clean in str(p.get("nama", "")).lower()]
                if m_cands:
                    cat_candidates = m_cands
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
                        "kategori_tersedia": sorted(list(set(str(p.get("kategori")).lower() for p in self.catalog.products if p.get("kategori")))),
                        "merek_tersedia": sorted(list(set(get_product_brand(p) for p in self.catalog.products if get_product_brand(p) and (not kategori or str(p.get("kategori", "")).lower() == str(kategori).lower())))),
                        "belum_dicari": False,
                        "pesan": f"Belum ada produk dalam rentang anggaran {format_rupiah(budget_max)}. Opsi termurah yang tersedia adalah {format_rupiah(min_cat_price)}."
                    }
                    if merek:
                        fakta["merek"] = merek
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
            p_kat = p.get("kategori", "").lower()
            if kategori and p_kat != kategori.lower():
                continue
            has_pc_req = any(f.get("field") in ("ram_gb", "ram", "cpu_tier", "cpu", "storage_ssd_gb", "gpu", "vram_gb") for f in filters)
            if not kategori and p_kat == "printer" and has_pc_req:
                continue
            if budget_max and get_product_price(p) > budget_max:
                continue
            if merek:
                p_brand = get_product_brand(p)
                p_nama = str(p.get("nama", "")).strip().lower()
                m_clean = str(merek).strip().lower()
                if m_clean != p_brand and m_clean not in p_brand and m_clean not in p_nama:
                    continue
            prod_kat = str(p.get("kategori", "")).lower()
            effective_filters = filters
            if prod_kat == "printer":
                pc_fields = {"ram_gb", "ram", "storage_ssd_gb", "storage", "cpu_tier", "cpu", "vram_gb", "gpu_dedicated", "gpu", "screen_inch"}
                effective_filters = [f for f in filters if f.get("field") not in pc_fields]
            passed, failure_reason, penalty, report = apply_filters(p, effective_filters)
            candidates.append({
                "product": p,
                "passed": passed,
                "penalty": penalty,
                "failure_reason": failure_reason,
                "report": report
            })

        if not candidates:
            all_brands = set(get_product_brand(p) for p in self.catalog.products if get_product_brand(p))
            is_brand_outside = bool(merek and str(merek).strip().lower() not in all_brands)
            if is_brand_outside:
                fakta = {
                    "status": "produk_tidak_di_katalog",
                    "merek": merek,
                    "kontak_staf": KONTAK_STAF,
                    "kategori_tersedia": sorted(list(set(str(p.get("kategori")).lower() for p in self.catalog.products if p.get("kategori")))),
                    "merek_tersedia": sorted(list(set(get_product_brand(p) for p in self.catalog.products if get_product_brand(p) and (not kategori or str(p.get("kategori", "")).lower() == str(kategori).lower())))),
                    "belum_dicari": False,
                    "pesan": f"Produk dengan merek '{merek}' saat ini belum tersedia di katalog ReIn Komputer."
                }
                return ActionResult(aksi=ActionEnum.MINTA_REKOMENDASI, fakta=fakta, produk_list=[])
            else:
                fakta = {
                    "status": "belum_ada_yang_memenuhi",
                    "merek": merek,
                    "kategori": kategori,
                    "kontak_staf": KONTAK_STAF,
                    "kategori_tersedia": sorted(list(set(str(p.get("kategori")).lower() for p in self.catalog.products if p.get("kategori")))),
                    "merek_tersedia": sorted(list(set(get_product_brand(p) for p in self.catalog.products if get_product_brand(p) and (not kategori or str(p.get("kategori", "")).lower() == str(kategori).lower())))),
                    "belum_dicari": False,
                    "pesan": "Saat ini belum ada produk yang memenuhi kriteria tersebut."
                }
                return ActionResult(aksi=ActionEnum.MINTA_REKOMENDASI, fakta=fakta, produk_list=[])

        user_msg = str(state.get("_pesan_pelanggan") or "")
        is_termurah = bool(
            re.search(r"\b(paling\s+murah|termurah|terjangkau|hemat|paling\s+hemat|harga\s+terendah|paling\s+rendah)\b", kebutuhan_teks or "", re.IGNORECASE)
            or re.search(r"\b(paling\s+murah|termurah|terjangkau|hemat|paling\s+hemat|harga\s+terendah|paling\s+rendah)\b", user_msg, re.IGNORECASE)
            or (str(getattr(args, "jenis", "")).lower() in ("termurah_dari_tampil", "lebih_murah"))
        )

        # B6: Tidak ada produk yang memenuhi spesifikasi minimum
        if candidates and all(not c["passed"] for c in candidates):
            if is_termurah:
                candidates.sort(key=lambda x: (get_product_price(x["product"]), -x["penalty"]))
            else:
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
                    "lembar_spesifikasi": build_lembar_spesifikasi(closest_prod),
                    "catatan_minimum": {
                        "memenuhi": False,
                        "alasan": ", ".join(unmet)
                    },
                    "kekurangan": unmet
                },
                "kategori_tersedia": sorted(list(set(str(p.get("kategori")).lower() for p in self.catalog.products if p.get("kategori")))),
                "merek_tersedia": sorted(list(set(get_product_brand(p) for p in self.catalog.products if get_product_brand(p) and (not kategori or str(p.get("kategori", "")).lower() == str(kategori).lower())))),
                "belum_dicari": False,
                "kontak_staf": KONTAK_STAF,
                "pesan": "Saat ini belum ada stok produk yang memenuhi syarat minimum kebutuhan tersebut."
            }
            return ActionResult(aksi=ActionEnum.MINTA_REKOMENDASI, fakta=fakta, produk_list=[])

        # Urutkan: lolos semua dulu. Jika ada intensi termurah -> urutkan harga menaik lebih dulu!
        if is_termurah:
            candidates.sort(key=lambda x: (not x["passed"], get_product_price(x["product"]), -x["penalty"]))
        else:
            candidates.sort(key=lambda x: (not x["passed"], -x["penalty"], get_product_price(x["product"])))
        top_matches = candidates[:3]

        formatted_prods = []
        for item in top_matches:
            p = item["product"]
            rep = item["report"]
            p_price = get_product_price(p)
            cat_min = {
                "memenuhi": bool(item["passed"]),
                "alasan": "Memenuhi seluruh spesifikasi minimum" if item["passed"] else (item.get("failure_reason") or "Belum memenuhi sebagian spesifikasi")
            }
            formatted_prods.append({
                "kode": p.get("kode"),
                "nama": p.get("nama"),
                "kategori": p.get("kategori"),
                "harga": p_price,
                "harga_formatted": format_rupiah(p_price),
                "spesifikasi": clean_specs(p),
                "lembar_spesifikasi": build_lembar_spesifikasi(p),
                "catatan_minimum": cat_min,
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
            "merek": merek,
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
        kriteria_pelanggan = state.get("kriteria_pelanggan", {}) or {}
        merek = args.merek or state.get("merek") or kriteria_pelanggan.get("merek")
        batas_bot = state.get("batas_bot", {}) or {}
        merek_kecuali = args.merek_kecuali or state.get("merek_kecuali") or kriteria_pelanggan.get("merek_kecuali")
        nama_model = args.nama_model
        gpu = args.gpu

        # Prioritaskan budget pelanggan di atas batas bot (F1)
        cust_max_harga = kriteria_pelanggan.get("max_harga")
        arg_max_harga = parse_int_safe(args.max_harga)
        state_budget = parse_int_safe(state.get("budget"))

        if arg_max_harga is not None:
            max_harga = arg_max_harga
        elif cust_max_harga is not None:
            max_harga = cust_max_harga
        elif state_budget is not None and (not batas_bot.get("max_harga") or state_budget != batas_bot.get("max_harga")):
            max_harga = state_budget
        elif batas_bot.get("max_harga") is not None:
            max_harga = batas_bot.get("max_harga")
        else:
            max_harga = None

        min_harga = parse_int_safe(args.min_harga or kriteria_pelanggan.get("min_harga"))
        ram_gb_min = parse_int_safe(args.ram_gb_min or kriteria_pelanggan.get("ram_gb_min"))
        storage_gb_min = parse_int_safe(args.storage_gb_min or kriteria_pelanggan.get("storage_gb_min"))
        ukuran_layar = parse_float_safe(args.ukuran_layar or kriteria_pelanggan.get("ukuran_layar"))

        # F1b: Deteksi kriteria spesifikasi yang tidak memiliki kolom di katalog
        kriteria_diabaikan = []
        if args.filter:
            known_cols = {
                "kode", "nama", "kategori", "harga", "harga_idr", "cpu", "cpu_tier",
                "ram", "ram_gb", "storage", "storage_ssd_gb", "gpu", "vram_gb",
                "display", "screen_inch", "brand", "merek"
            }
            if isinstance(args.filter, dict):
                for k_f, v_f in args.filter.items():
                    if str(k_f).strip().lower() not in known_cols:
                        kriteria_diabaikan.append(str(v_f))
            elif isinstance(args.filter, list):
                for item_f in args.filter:
                    kriteria_diabaikan.append(str(item_f))
            else:
                kriteria_diabaikan.append(str(args.filter))

        filter_dipakai = {
            "kategori": kategori,
        }
        if max_harga is not None:
            filter_dipakai["max_harga"] = max_harga
        if min_harga is not None:
            filter_dipakai["min_harga"] = min_harga
        if merek:
            filter_dipakai["merek"] = merek
        if merek_kecuali:
            filter_dipakai["merek_kecuali"] = merek_kecuali
        if ram_gb_min:
            filter_dipakai["ram_gb_min"] = ram_gb_min
        if storage_gb_min:
            filter_dipakai["storage_gb_min"] = storage_gb_min
        if gpu:
            filter_dipakai["gpu"] = gpu

        # B7: Anggaran di bawah harga terendah kategori
        if max_harga:
            cat_candidates = [p for p in self.catalog.products if not kategori or p.get("kategori", "").lower() == str(kategori).lower()]
            if cat_candidates:
                min_cat_price = min(get_product_price(p) for p in cat_candidates)
                if max_harga < min_cat_price:
                    fakta = {
                        "status": "tidak_ada_dalam_anggaran",
                        "filter_dipakai": filter_dipakai,
                        "budget_pelanggan": max_harga,
                        "budget_pelanggan_formatted": format_rupiah(max_harga),
                        "harga_termurah_kategori": min_cat_price,
                        "harga_termurah_kategori_formatted": format_rupiah(min_cat_price),
                        "kategori": kategori or "katalog",
                        "pesan": f"Belum ada produk dalam rentang anggaran {format_rupiah(max_harga)}. Opsi termurah adalah {format_rupiah(min_cat_price)}."
                    }
                    if kriteria_diabaikan:
                        fakta["kriteria_diabaikan_data_tak_ada"] = kriteria_diabaikan
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
                mk_list = [str(x).strip().lower() for x in (merek_kecuali if isinstance(merek_kecuali, list) else str(merek_kecuali).split(","))]
                if any(mk == p_brand or mk in p_brand or mk in p_nama for mk in mk_list):
                    continue
            if nama_model and nama_model.strip().lower() not in p_nama:
                continue
            if gpu:
                gpu_req = gpu.strip().lower()
                p_gpu = str(p.get("gpu", "")).strip().lower()
                is_discrete_req = any(kw in gpu_req for kw in ["dedicated", "diskrit", "kartu grafis", "vga eksternal", "vga terpisah"])
                is_discrete_prod = bool(
                    (p.get("vram_gb") and p.get("vram_gb") > 0) or
                    any(kw in p_gpu for kw in ["rtx", "gtx", "geforce", "radeon rx", "arc a"])
                )
                if is_discrete_req:
                    if not is_discrete_prod:
                        continue
                else:
                    if gpu_req not in p_gpu:
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
                "brand": get_product_brand(p),
                "merek": get_product_brand(p),
                "harga": p_price,
                "harga_formatted": format_rupiah(p_price),
                "spesifikasi": clean_specs(p),
                "lembar_spesifikasi": build_lembar_spesifikasi(p),
                "catatan_minimum": {"memenuhi": True, "alasan": "Sesuai kriteria pencarian"},
                "cpu": p.get("cpu"),
                "cpu_tier": p.get("cpu_tier"),
                "ram": p.get("ram"),
                "ram_gb": p.get("ram_gb"),
                "storage": p.get("storage"),
                "storage_ssd_gb": p.get("storage_ssd_gb"),
                "gpu": p.get("gpu"),
                "display": p.get("display"),
                "screen_inch": p.get("screen_inch"),
                "image_url": p.get("image_url")
            })

        if not formatted_prods:
            # E6 / B16: Jika merek atau nama_model di luar katalog, kembalikan status produk_tidak_di_katalog + padanan terdekat
            all_brands = set(get_product_brand(p) for p in self.catalog.products if get_product_brand(p))
            is_brand_outside = bool(merek and str(merek).strip().lower() not in all_brands)

            if is_brand_outside or (nama_model and not matches):
                target_cat = str(kategori).lower() if kategori else "laptop"
                cat_prods = [p for p in self.catalog.products if str(p.get("kategori", "")).lower() == target_cat]
                if not cat_prods:
                    cat_prods = [p for p in self.catalog.products if str(p.get("kategori", "")).lower() == "laptop"]
                if not cat_prods and self.catalog.products:
                    cat_prods = list(self.catalog.products)
                closest = min(cat_prods, key=lambda x: get_product_price(x)) if cat_prods else None
                padanan = {
                    "kode": closest.get("kode"),
                    "nama": closest.get("nama"),
                    "kategori": closest.get("kategori"),
                    "brand": get_product_brand(closest),
                    "merek": get_product_brand(closest),
                    "harga": get_product_price(closest),
                    "harga_formatted": format_rupiah(get_product_price(closest)),
                    "spesifikasi": clean_specs(closest),
                    "lembar_spesifikasi": build_lembar_spesifikasi(closest),
                    "catatan_minimum": {"memenuhi": True, "alasan": "Padanan terdekat di katalog"}
                } if closest else {}
                prod_diminta = merek or nama_model
                fakta = {
                    "status": "produk_tidak_di_katalog",
                    "produk_diminta": [prod_diminta],
                    "padanan_terdekat": padanan,
                    "kategori_tersedia": sorted(list(set(str(p.get("kategori")).lower() for p in self.catalog.products if p.get("kategori")))),
                    "merek_tersedia": sorted(list(set(get_product_brand(p) for p in self.catalog.products if get_product_brand(p) and (not kategori or str(p.get("kategori", "")).lower() == str(kategori).lower())))),
                    "belum_dicari": False,
                    "pesan": f"Produk/merek {prod_diminta} tidak tersedia di katalog ReIn Komputer. Pilihan padanan terdekat yang tersedia adalah {padanan.get('nama', '')}."
                }
                return ActionResult(aksi=ActionEnum.CARI_PRODUK, fakta=fakta, produk_list=[padanan] if padanan else [])

            fakta = {
                "status": "tidak_ditemukan",
                "filter_dipakai": filter_dipakai,
                "kriteria": {
                    "kategori": kategori, "merek": merek, "merek_kecuali": merek_kecuali,
                    "gpu": gpu, "max_harga": max_harga, "ram_gb_min": ram_gb_min
                },
                "kategori_tersedia": sorted(list(set(str(p.get("kategori")).lower() for p in self.catalog.products if p.get("kategori")))),
                "merek_tersedia": sorted(list(set(get_product_brand(p) for p in self.catalog.products if get_product_brand(p) and (not kategori or str(p.get("kategori", "")).lower() == str(kategori).lower())))),
                "belum_dicari": False
            }
            if kriteria_diabaikan:
                fakta["kriteria_diabaikan_data_tak_ada"] = kriteria_diabaikan
        else:
            # B2: Kategori saja atau merek saja -> tandai butuh dipersempit
            is_broad = bool((merek or kategori) and not (nama_model or gpu or ram_gb_min or max_harga))
            fakta = {
                "status": "sukses",
                "filter_dipakai": filter_dipakai,
                "merek_kecuali": merek_kecuali,
                "total_cocok": len(matches),
                "total_ditemukan": len(formatted_prods),
                "produk": formatted_prods,
                "butuh_persempit": is_broad,
                "belum_dicari": False
            }
            if kriteria_diabaikan:
                fakta["kriteria_diabaikan_data_tak_ada"] = kriteria_diabaikan

        return ActionResult(
            aksi=ActionEnum.CARI_PRODUK,
            fakta=fakta,
            produk_list=formatted_prods
        )

    # -------------------------------------------------------------------------
    # 3. evaluasi_kecocokan
    # -------------------------------------------------------------------------
    def _handle_evaluasi_kecocokan(self, args: ActionArguments, state: dict) -> ActionResult:
        # D1, D3, B14, B16: Gunakan resolve_produk untuk mendapatkan produk katalog lengkap
        catalog_products, resolved_codes = self.resolve_produk(args, state)
        kebutuhan_teks = args.kebutuhan_teks or state.get("kebutuhan_teks") or ""

        # B14: Jika tidak ada produk yang dievaluasi
        if not catalog_products and not resolved_codes:
            fakta = {
                "status": "belum_ada_produk",
                "pesan": "Belum ada produk yang dipilih atau ditampilkan untuk dievaluasi."
            }
            return ActionResult(aksi=ActionEnum.EVALUASI_KECOCOKAN, fakta=fakta)

        # D4: Jika ada kebutuhan_teks di giliran ini (args.kebutuhan_teks), prioritaskan resolusi baru
        # jangan gunakan profil lama yang basi di state.
        profil_id = None
        prof_data = None
        if args.kebutuhan_teks:
            try:
                reqs = get_usage_requirements(args.kebutuhan_teks)
                pls = reqs.get("profil", [])
                valid_pls = [p for p in pls if str(p.get("profil_id", "")).startswith("P")]
                if valid_pls:
                    profil_id = valid_pls[0]["profil_id"]
                    state["profil_aktif"] = profil_id
                    state["kebutuhan_teks"] = args.kebutuhan_teks
            except Exception as e:
                logger.error(f"Kegagalan Qdrant/embedding saat evaluasi kecocokan: {e}")
                fakta = {
                    "status": "sistem_error",
                    "kontak_staf": KONTAK_STAF,
                    "pesan": "Sistem basis data pengetahuan sedang mengalami gangguan sementara."
                }
                return ActionResult(aksi=ActionEnum.EVALUASI_KECOCOKAN, fakta=fakta)

        if not profil_id and state.get("profil_aktif"):
            profil_id = state.get("profil_aktif")

        if not profil_id and kebutuhan_teks:
            try:
                reqs = get_usage_requirements(kebutuhan_teks)
                pls = reqs.get("profil", [])
                valid_pls = [p for p in pls if str(p.get("profil_id", "")).startswith("P")]
                if valid_pls:
                    profil_id = valid_pls[0]["profil_id"]
                    state["profil_aktif"] = profil_id
            except Exception as e:
                logger.error(f"Kegagalan Qdrant/embedding saat evaluasi kecocokan: {e}")
                fakta = {
                    "status": "sistem_error",
                    "kontak_staf": KONTAK_STAF,
                    "pesan": "Sistem basis data pengetahuan sedang mengalami gangguan sementara."
                }
                return ActionResult(aksi=ActionEnum.EVALUASI_KECOCOKAN, fakta=fakta)

        if profil_id:
            prof_data = get_profile_by_id(profil_id)

        # B14: Tanpa profil kebutuhan yang valid
        if not profil_id or not prof_data:
            fakta = {
                "status": "profil_tidak_ditemukan",
                "pesan": "Kebutuhan penggunaan belum ditentukan atau profil tidak ditemukan untuk evaluasi kelayakan."
            }
            return ActionResult(aksi=ActionEnum.EVALUASI_KECOCOKAN, fakta=fakta)

        if not catalog_products:
            # E8 / B9: Jika rujukan adalah nomor ordinal di luar rentang atau rujukan_tidak_ada
            is_ordinal_fail = any(
                re.search(r"^(?:nomor\s*|unit\s*)?\d+$", str(c).strip(), re.IGNORECASE) or str(c) == "rujukan_tidak_ada"
                for c in (resolved_codes or args.rujukan_produk or [])
            )
            if is_ordinal_fail:
                fakta = {
                    "status": "rujukan_tidak_ada",
                    "pesan": "Nomor produk yang dirujuk tidak ada dalam daftar yang sedang ditampilkan."
                }
                return ActionResult(aksi=ActionEnum.EVALUASI_KECOCOKAN, fakta=fakta)

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
                "produk_diminta": resolved_codes or args.produk,
                "padanan_terdekat": padanan,
                "pesan": f"Produk {', '.join([str(c) for c in (resolved_codes or args.produk)])} tidak tersedia di katalog ReIn Komputer. Pilihan padanan terdekat yang tersedia adalah {padanan.get('nama', '')}."
            }
            return ActionResult(aksi=ActionEnum.EVALUASI_KECOCOKAN, fakta=fakta)

        filters = prof_data.get("filter", []) if prof_data else []

        eval_results = []
        for p in catalog_products:
            p_price = get_product_price(p)
            # D3: Gunakan nilai aktual dari katalog secara ketat, jangan gunakan fallback fiktif
            p_cpu_tier = p.get("cpu_tier") or (1 if p.get("cpu") else None)
            p_ram = p.get("ram_gb")
            p_ssd = p.get("storage_ssd_gb")
            p_vram = p.get("vram_gb") or p.get("gpu_vram_gb") or 0

            min_cpu = 1
            min_ram = 4
            min_ssd = 128
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

            diff_min = []
            if p_cpu_tier is not None:
                diff_min.append(p_cpu_tier - min_cpu)
            if p_ram is not None:
                diff_min.append(p_ram - min_ram)
            if p_ssd is not None:
                diff_min.append(p_ssd - min_ssd)
            if p_vram is not None:
                diff_min.append(p_vram - min_vram)

            diff_rec = []
            if p_cpu_tier is not None:
                diff_rec.append(p_cpu_tier - rec_cpu)
            if p_ram is not None:
                diff_rec.append(p_ram - rec_ram)
            if p_ssd is not None:
                diff_rec.append(p_ssd - rec_ssd)
            if p_vram is not None:
                diff_rec.append(p_vram - rec_vram)

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
                    "cpu_tier": (p_cpu_tier - min_cpu) if p_cpu_tier is not None else 0,
                    "ram_gb": (p_ram - min_ram) if p_ram is not None else 0,
                    "ssd_gb": (p_ssd - min_ssd) if p_ssd is not None else 0,
                    "gpu_vram_gb": (p_vram - min_vram) if p_vram is not None else 0
                },
                "selisih_terhadap_rekomendasi": {
                    "cpu_tier": (p_cpu_tier - rec_cpu) if p_cpu_tier is not None else 0,
                    "ram_gb": (p_ram - rec_ram) if p_ram is not None else 0,
                    "ssd_gb": (p_ssd - rec_ssd) if p_ssd is not None else 0,
                    "gpu_vram_gb": (p_vram - rec_vram) if p_vram is not None else 0
                },
                "lembar_spesifikasi": build_lembar_spesifikasi(p),
                "catatan_minimum": {
                    "memenuhi": (status_kecocokan != "di_bawah_minimum"),
                    "alasan": f"Status kecocokan: {status_kecocokan}"
                }
            })

        fakta = {
            "status": "sukses",
            "kebutuhan_teks": kebutuhan_teks,
            "profil_id": profil_id,
            "profil_judul": prof_data.get("judul") if prof_data else None,
            "evaluasi_produk": eval_results,
            "produk": eval_results,
            "rujukan_dipakai": [p.get("kode") for p in catalog_products]
        }
        return ActionResult(aksi=ActionEnum.EVALUASI_KECOCOKAN, fakta=fakta)

    # -------------------------------------------------------------------------
    # 4. tanya_spesifikasi (A5)
    # -------------------------------------------------------------------------
    def _handle_tanya_spesifikasi(self, args: ActionArguments, state: dict) -> ActionResult:
        # D1, D2, B14, B15, B16: Gunakan resolve_produk untuk mendapatkan produk katalog penuh
        catalog_products, resolved_codes = self.resolve_produk(args, state)
        attr = args.atribut

        if not catalog_products and not resolved_codes:
            fakta = {
                "status": "belum_ada_produk",
                "pesan": "Belum ada produk yang dipilih untuk ditanyakan spesifikasinya."
            }
            return ActionResult(aksi=ActionEnum.TANYA_SPESIFIKASI, fakta=fakta)

        if not catalog_products:
            # E8 / B9: Jika rujukan adalah nomor ordinal di luar rentang atau rujukan_tidak_ada
            is_ordinal_fail = any(
                re.search(r"^(?:nomor\s*|unit\s*)?\d+$", str(c).strip(), re.IGNORECASE) or str(c) == "rujukan_tidak_ada"
                for c in (resolved_codes or args.rujukan_produk or [])
            )
            if is_ordinal_fail:
                fakta = {
                    "status": "rujukan_tidak_ada",
                    "pesan": "Nomor produk yang dirujuk tidak ada dalam daftar yang sedang ditampilkan."
                }
                return ActionResult(aksi=ActionEnum.TANYA_SPESIFIKASI, fakta=fakta)

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
                "produk_diminta": resolved_codes or args.produk,
                "padanan_terdekat": padanan,
                "pesan": f"Produk {', '.join([str(c) for c in (resolved_codes or args.produk)])} tidak tersedia di katalog ReIn Komputer. Pilihan padanan terdekat yang tersedia adalah {padanan.get('nama', '')}."
            }
            return ActionResult(aksi=ActionEnum.TANYA_SPESIFIKASI, fakta=fakta)

        # F3: Kasus 1 - Atribut None / kosong -> Permintaan spesifikasi umum -> Ringkasan spek utama katalog
        if attr is None:
            fakta_items = []
            for p in catalog_products:
                spek_ringkas = clean_specs(p) or f"{p.get('cpu', '')} | {p.get('ram', '')} | {p.get('storage', '')} | {p.get('display', '')}"
                fakta_items.append({
                    "kode": p.get("kode"),
                    "nama": p.get("nama"),
                    "atribut": "spek_umum",
                    "nilai": spek_ringkas,
                    "nilai_spesifikasi": spek_ringkas,
                    "ringkasan_spek": spek_ringkas,
                    "spesifikasi_ringkas": spek_ringkas
                })
            fakta = {
                "status": "sukses",
                "atribut_ditanya": "spek_umum",
                "ringkasan_spek": fakta_items[0]["ringkasan_spek"] if fakta_items else "",
                "spesifikasi_ringkas": fakta_items[0]["spesifikasi_ringkas"] if fakta_items else "",
                "spesifikasi": fakta_items,
                "spesifikasi_produk": fakta_items,
                "rujukan_dipakai": [p.get("kode") for p in catalog_products]
            }
            return ActionResult(aksi=ActionEnum.TANYA_SPESIFIKASI, fakta=fakta, produk_list=catalog_products)

        # F3: Kasus 2 - Atribut LAINNYA -> Atribut spesifik tidak dikenal / tidak ada di katalog -> B15
        if attr == AtributSpesifikasiEnum.LAINNYA:
            fakta = {
                "status": "atribut_tidak_tersedia",
                "atribut_ditanya": "lainnya",
                "pesan": "Informasi mengenai spesifikasi tersebut belum tersedia di sistem kami. Kakak dapat langsung menanyakan ke staf toko kami di 0812-3456-7890 (WhatsApp).",
                "rujukan_dipakai": [p.get("kode") for p in catalog_products]
            }
            return ActionResult(aksi=ActionEnum.TANYA_SPESIFIKASI, fakta=fakta)

        # F3: Kasus 3 - Atribut spesifik yang dikenal
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
                attr_key = attr.value if hasattr(attr, "value") else str(attr)
                val = p.get(attr_key)

            if not val:
                ada_tidak_tersedia = True
            else:
                fakta_items.append({
                    "kode": p.get("kode"),
                    "nama": p.get("nama"),
                    "atribut": attr.value if hasattr(attr, "value") else str(attr),
                    "nilai": str(val),
                    "nilai_spesifikasi": str(val),
                    "ringkasan_spek": clean_specs(p),
                    "lembar_spesifikasi": build_lembar_spesifikasi(p),
                    "catatan_minimum": {"memenuhi": True, "alasan": f"Atribut {attr.value if hasattr(attr, 'value') else str(attr)} tersedia"}
                })

        if ada_tidak_tersedia and not fakta_items:
            fakta = {
                "status": "atribut_tidak_tersedia",
                "atribut_ditanya": attr.value if hasattr(attr, "value") else str(attr),
                "pesan": f"Informasi spesifikasi '{attr.value if hasattr(attr, 'value') else str(attr)}' tidak tersedia untuk produk tersebut.",
                "rujukan_dipakai": [p.get("kode") for p in catalog_products]
            }
        else:
            fakta = {
                "status": "sukses",
                "atribut_ditanya": attr.value if hasattr(attr, "value") else str(attr),
                "spesifikasi": fakta_items,
                "spesifikasi_produk": fakta_items,
                "produk": [dict(p, lembar_spesifikasi=build_lembar_spesifikasi(p), catatan_minimum={"memenuhi": True, "alasan": "Sesuai spesifikasi yang diminta"}) for p in catalog_products[:3]],
                "rujukan_dipakai": [p.get("kode") for p in catalog_products]
            }

        return ActionResult(aksi=ActionEnum.TANYA_SPESIFIKASI, fakta=fakta, produk_list=catalog_products if not ada_tidak_tersedia or fakta_items else [])

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
                "display": p.get("display") or f"{p.get('ukuran_layar', '')} inci",
                "lembar_spesifikasi": build_lembar_spesifikasi(p),
                "catatan_minimum": {"memenuhi": True, "alasan": "Unit pembanding"}
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
            "produk": items,
            "produk_luar_katalog": produk_luar,
            "catatan": catatan
        }
        prods = [self.get_product_by_code(code) for code in target_codes if self.get_product_by_code(code)]
        return ActionResult(aksi=ActionEnum.BANDINGKAN, fakta=fakta, produk_list=prods)

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

        raw_j = getattr(args, "jenis", None) or getattr(args, "jenis_lanjutan", None)
        if raw_j and str(raw_j).lower() != "none":
            jenis = raw_j.value if hasattr(raw_j, "value") else str(raw_j)
        else:
            jenis = "yang_lain"

        # B3: Kategori aktif diambil dari produk_tampil di sesi
        kategori = tampil[0].get("kategori") or state.get("kategori") or "laptop"

        candidates = [p for p in self.catalog.products if p.get("kategori", "").lower() == str(kategori).lower()]

        kriteria_pelanggan = state.get("kriteria_pelanggan", {}) or {}
        batas_bot = state.get("batas_bot", {}) or {}

        # Prioritaskan batas harga pelanggan di atas batas bot (F1)
        cust_max_harga = kriteria_pelanggan.get("max_harga")
        arg_max_harga = parse_int_safe(args.max_harga)
        state_budget = parse_int_safe(state.get("budget"))

        if arg_max_harga is not None:
            user_max_harga = arg_max_harga
        elif cust_max_harga is not None:
            user_max_harga = cust_max_harga
        elif state_budget is not None and (not batas_bot.get("max_harga") or state_budget != batas_bot.get("max_harga")):
            user_max_harga = state_budget
        elif batas_bot.get("max_harga") is not None:
            user_max_harga = batas_bot.get("max_harga")
        else:
            user_max_harga = None

        merek_kecuali = args.merek_kecuali or state.get("merek_kecuali") or kriteria_pelanggan.get("merek_kecuali")
        if jenis == "yang_lain" and not merek_kecuali:
            curr_brand = get_product_brand(tampil[0]) if tampil else None
            if curr_brand and not args.merek:
                merek_kecuali = curr_brand

        # E4: Pertahankan filter merek jika ada di args atau state (kecuali jika jenis yang_lain / ada merek_kecuali)
        if (jenis == "yang_lain" or merek_kecuali) and not args.merek:
            merek = None
        else:
            merek = args.merek or state.get("merek")

        if merek:
            m_clean = str(merek).strip().lower()
            candidates = [p for p in candidates if m_clean == get_product_brand(p) or m_clean in str(p.get("nama", "")).lower()]

        mk_list = [str(x).strip().lower() for x in (merek_kecuali if isinstance(merek_kecuali, list) else str(merek_kecuali).split(","))] if merek_kecuali else []
        if mk_list:
            candidates = [p for p in candidates if not any(mk == get_product_brand(p) or mk in get_product_brand(p) or mk in str(p.get("nama", "")).lower() for mk in mk_list)]

        filter_dipakai = {
            "kategori": kategori,
        }
        if user_max_harga is not None:
            filter_dipakai["max_harga"] = user_max_harga
        if merek:
            filter_dipakai["merek"] = merek
        if merek_kecuali:
            filter_dipakai["merek_kecuali"] = merek_kecuali

        batas_dipakai = None
        if jenis == "termurah_dari_tampil":
            target_source = tampil
            if args.rujukan_produk:
                ref_str = str(args.rujukan_produk[0]).lower()
                if any(w in ref_str for w in ["sebelumnya", "tadi", "riwayat", "kemarin", "dulu"]):
                    target_source = state.get("history_produk_tampil") or tampil
            if not target_source:
                target_source = state.get("history_produk_tampil", [])

            resolved_tampil = []
            for p in target_source:
                full_p = self.get_product_by_code(p.get("kode")) if p.get("kode") else p
                resolved_tampil.append(full_p or p)

            if not resolved_tampil:
                fakta = {
                    "status": "belum_ada_hasil",
                    "pesan": "Belum ada produk yang ditampilkan untuk dipilih yang paling murah.",
                    "total_ditemukan": 0,
                    "produk": []
                }
                return ActionResult(aksi=ActionEnum.LANJUTAN_HASIL, fakta=fakta, produk_list=[])

            cheapest_item = min(resolved_tampil, key=lambda x: get_product_price(x))
            cheapest_price = get_product_price(cheapest_item)
            formatted_item = {
                "kode": cheapest_item.get("kode"),
                "nama": cheapest_item.get("nama"),
                "kategori": cheapest_item.get("kategori"),
                "brand": get_product_brand(cheapest_item),
                "merek": get_product_brand(cheapest_item),
                "harga": cheapest_price,
                "harga_formatted": format_rupiah(cheapest_price),
                "spesifikasi": clean_specs(cheapest_item),
                "lembar_spesifikasi": build_lembar_spesifikasi(cheapest_item),
                "catatan_minimum": {"memenuhi": True, "alasan": "Opsi paling terjangkau di antara produk tampil"},
                "cpu": cheapest_item.get("cpu"),
                "cpu_tier": cheapest_item.get("cpu_tier"),
                "ram": cheapest_item.get("ram"),
                "ram_gb": cheapest_item.get("ram_gb"),
                "storage": cheapest_item.get("storage"),
                "storage_ssd_gb": cheapest_item.get("storage_ssd_gb"),
                "gpu": cheapest_item.get("gpu"),
                "display": cheapest_item.get("display"),
                "screen_inch": cheapest_item.get("screen_inch"),
                "image_url": cheapest_item.get("image_url")
            }
            fakta = {
                "status": "sukses",
                "jenis_lanjutan": "termurah_dari_tampil",
                "filter_dipakai": filter_dipakai,
                "produk_termurah": formatted_item,
                "rujukan_dipakai": [cheapest_item.get("kode")],
                "produk": [formatted_item],
                "total_ditemukan": 1,
                "pesan": f"Di antara produk yang sedang ditampilkan, opsi paling terjangkau adalah {formatted_item.get('nama', '')} dengan harga {formatted_item.get('harga_formatted', '')}."
            }
            return ActionResult(
                aksi=ActionEnum.LANJUTAN_HASIL,
                fakta=fakta,
                produk_list=[formatted_item]
            )

        if jenis == "lebih_murah":
            from services.catalog_search import parse_budget_from_text
            msg_budget = parse_budget_from_text(str(state.get("_pesan_pelanggan") or ""))
            budget_disertai = parse_int_safe(args.max_harga) or parse_int_safe(args.budget_max) or msg_budget

            if budget_disertai is not None:
                # Putaran 13 Butir D: perbarui budget state, JALANKAN ULANG minta_rekomendasi
                state["budget"] = budget_disertai
                if "kriteria_pelanggan" not in state or not isinstance(state["kriteria_pelanggan"], dict):
                    state["kriteria_pelanggan"] = {}
                state["kriteria_pelanggan"]["max_harga"] = budget_disertai

                if state.get("kebutuhan_teks") or getattr(args, "kebutuhan_teks", None):
                    args.max_harga = budget_disertai
                    args.budget_max = budget_disertai
                    if not args.kategori and kategori:
                        args.kategori = kategori
                    if not args.merek and merek:
                        args.merek = merek
                    return self._handle_minta_rekomendasi(args, state)
                else:
                    args.max_harga = budget_disertai
                    if not args.kategori and kategori:
                        args.kategori = kategori
                    if not args.merek and merek:
                        args.merek = merek
                    return self._handle_cari_produk(args, state)

            lowest_p = min((get_product_price(p) for p in tampil), default=10_000_000)
            target_max = user_max_harga if user_max_harga is not None else lowest_p
            matches = [p for p in candidates if get_product_price(p) < lowest_p and (user_max_harga is None or get_product_price(p) <= user_max_harga)]
            # Jika user_max_harga is None dan merek tidak punya opsi lebih murah, cari opsi lebih murah di seluruh kategori
            if not matches and user_max_harga is None and merek and not args.merek:
                cat_candidates = [p for p in self.catalog.products if p.get("kategori", "").lower() == str(kategori).lower()]
                if mk_list:
                    cat_candidates = [p for p in cat_candidates if not any(mk == get_product_brand(p) or mk in get_product_brand(p) or mk in str(p.get("nama", "")).lower() for mk in mk_list)]
                matches = [p for p in cat_candidates if get_product_price(p) < lowest_p]
            matches.sort(key=lambda x: get_product_price(x))

            # B7: Jika ada batas anggaran eksplisit dan tidak ada yang cocok
            if not matches and user_max_harga is not None:
                min_cat_price = min((get_product_price(p) for p in candidates), default=lowest_p)
                cheapest_p = min(candidates, key=lambda x: get_product_price(x)) if candidates else None
                formatted_cheap = [{
                    "kode": cheapest_p.get("kode"), "nama": cheapest_p.get("nama"),
                    "kategori": cheapest_p.get("kategori"),
                    "brand": get_product_brand(cheapest_p),
                    "merek": get_product_brand(cheapest_p),
                    "harga": get_product_price(cheapest_p),
                    "harga_formatted": format_rupiah(get_product_price(cheapest_p)),
                    "spesifikasi": clean_specs(cheapest_p)
                }] if cheapest_p else []
                fakta = {
                    "status": "tidak_ada_dalam_anggaran",
                    "filter_dipakai": filter_dipakai,
                    "budget_pelanggan": user_max_harga,
                    "budget_pelanggan_formatted": format_rupiah(user_max_harga),
                    "batas_dipakai": user_max_harga,
                    "harga_termurah_kategori": min_cat_price,
                    "harga_termurah_kategori_formatted": format_rupiah(min_cat_price),
                    "kategori": kategori,
                    "pesan": f"Belum ada opsi produk di bawah {format_rupiah(user_max_harga)}. Pilihan paling terjangkau yang tersedia adalah {format_rupiah(min_cat_price)}."
                }
                return ActionResult(aksi=ActionEnum.LANJUTAN_HASIL, fakta=fakta, produk_list=formatted_cheap)

            # B8: Tidak ada opsi lebih murah
            if not matches:
                min_cat_price = min((get_product_price(p) for p in candidates), default=lowest_p)
                fakta = {
                    "status": "tidak_ada_lebih_murah",
                    "filter_dipakai": filter_dipakai,
                    "harga_termurah_saat_ini": lowest_p,
                    "harga_termurah_saat_ini_formatted": format_rupiah(lowest_p),
                    "harga_termurah_kategori": min_cat_price,
                    "harga_termurah_kategori_formatted": format_rupiah(min_cat_price),
                    "kategori": kategori,
                    "kategori_dipakai": kategori,
                    "pesan": f"Produk yang ditampilkan sebelumnya sudah merupakan opsi paling terjangkau di katalog kami ({format_rupiah(lowest_p)})."
                }
                return ActionResult(aksi=ActionEnum.LANJUTAN_HASIL, fakta=fakta, produk_list=[])
            batas_dipakai = target_max

        elif jenis == "lebih_mahal":
            highest_p = max((get_product_price(p) for p in tampil), default=5_000_000)
            matches = [p for p in candidates if get_product_price(p) > highest_p]
            matches.sort(key=lambda x: get_product_price(x))

            # B8: Tidak ada opsi lebih mahal
            if not matches:
                max_cat_price = max((get_product_price(p) for p in candidates), default=highest_p)
                fakta = {
                    "status": "tidak_ada_lebih_mahal",
                    "filter_dipakai": filter_dipakai,
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

        elif jenis in ("yang_lain", "filter_tambahan") or merek_kecuali or args.filter:
            seen_kodes = {p.get("kode") for p in tampil}
            matches = [p for p in candidates if p.get("kode") not in seen_kodes]
            if user_max_harga is not None:
                matches = [p for p in matches if get_product_price(p) <= user_max_harga]
            if not matches and not seen_kodes:
                matches = [p for p in candidates if user_max_harga is None or get_product_price(p) <= user_max_harga]
            matches.sort(key=lambda x: get_product_price(x))
        else:
            matches = []

        top = matches[:3]
        formatted = []
        for p in top:
            p_price = get_product_price(p)
            formatted.append({
                "kode": p.get("kode"),
                "nama": p.get("nama"),
                "kategori": p.get("kategori"),
                "brand": get_product_brand(p),
                "merek": get_product_brand(p),
                "harga": p_price,
                "harga_formatted": format_rupiah(p_price),
                "spesifikasi": clean_specs(p),
                "lembar_spesifikasi": build_lembar_spesifikasi(p),
                "catatan_minimum": {"memenuhi": True, "alasan": "Sesuai filter lanjutan hasil"},
                "cpu": p.get("cpu"),
                "cpu_tier": p.get("cpu_tier"),
                "ram": p.get("ram"),
                "ram_gb": p.get("ram_gb"),
                "storage": p.get("storage"),
                "storage_ssd_gb": p.get("storage_ssd_gb"),
                "gpu": p.get("gpu"),
                "display": p.get("display"),
                "screen_inch": p.get("screen_inch"),
                "image_url": p.get("image_url")
            })

        if not formatted:
            fakta = {
                "status": "tidak_ditemukan",
                "filter_dipakai": filter_dipakai,
                "kategori": kategori,
                "kategori_dipakai": kategori,
                "pesan": "Tidak ada pilihan lain yang tersedia di katalog dengan kriteria tersebut."
            }
            return ActionResult(aksi=ActionEnum.LANJUTAN_HASIL, fakta=fakta, produk_list=[])

        fakta = {
            "status": "sukses",
            "filter_dipakai": filter_dipakai,
            "jenis": jenis,
            "kategori": kategori,
            "kategori_dipakai": kategori,
            "batas_harga": batas_dipakai or user_max_harga,
            "merek_kecuali": merek_kecuali,
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
            "belum_dicari": True,
            "arahan": f"Berikan kontak staf toko di {kontak_staf} secara sopan tanpa menyebut estimasi durasi respons atau janji spesifik."
        }
        return ActionResult(aksi=ActionEnum.TANYA_INFO_TOKO, fakta=fakta, produk_list=[])

    # -------------------------------------------------------------------------
    # 8. jawab_pertanyaan_bot (A7)
    # -------------------------------------------------------------------------
    def _handle_jawab_pertanyaan_bot(self, args: ActionArguments, state: dict) -> ActionResult:
        slot = args.slot.value if hasattr(args.slot, "value") else (str(args.slot) if args.slot else None)
        slot_val = args.nilai

        # Perbarui slot state yang relevan
        if slot in ("kategori", "category"):
            val_cat = str(slot_val).strip().lower()
            if val_cat in ("laptop", "desktop", "printer"):
                old_kat = state.get("kategori")
                state["kategori"] = val_cat
                if old_kat and val_cat != old_kat:
                    state["merek"] = None
                    state["kebutuhan_teks"] = None
                    state["budget"] = None
                    state["produk_tampil"] = []
                    state["produk_terakhir_dibahas"] = None
                    state["history_produk_tampil"] = []
                    state["profil_aktif"] = None
                    state["batas_bot"] = {}
                    if "kriteria_pelanggan" in state and isinstance(state["kriteria_pelanggan"], dict):
                        state["kriteria_pelanggan"] = {"kategori": val_cat}
            else:
                logger.warning(f"B1: Kategori '{slot_val}' tak dikenal katalog, diabaikan.")
        elif slot in ("budget", "anggaran"):
            state["budget"] = parse_int_safe(slot_val)
        elif slot in ("persona",):
            state["persona"] = str(slot_val).strip().lower()
        elif slot in ("kebutuhan", "aktivitas"):
            state["kebutuhan_teks"] = str(slot_val).strip()
        elif slot in ("merek", "brand"):
            all_brands = set(get_product_brand(p) for p in self.catalog.products if get_product_brand(p))
            val_m = str(slot_val).strip().lower()
            if val_m in all_brands:
                state["merek"] = val_m
            else:
                logger.warning(f"B1: Merek '{slot_val}' tak dikenal katalog, diabaikan.")

        state["pending_question"] = None

        # B1: Jika persona / pemakai, jangan buka produk -> tanya_kebutuhan
        if slot in ("persona", "pemakai", "sebutan"):
            fakta = {
                "status": "tanya_kebutuhan",
                "persona": state.get("persona") or slot_val,
                "slot_diisi": slot,
                "belum_dicari": True,
                "pesan": f"Informasi pemakai '{slot_val}' telah dicatat. Tanyakan kebutuhan atau aktivitas spesifik yang akan dijalankan."
            }
            return ActionResult(aksi=ActionEnum.JAWAB_PERTANYAAN_BOT, fakta=fakta, produk_list=[])

        # Jika bukan kriteria produk eksplisit -> jangan membuka pencarian produk
        if not slot or slot not in ("kategori", "category", "budget", "anggaran", "kebutuhan", "aktivitas", "merek", "brand"):
            fakta = {
                "status": "jawaban_dicatat",
                "slot_diisi": slot,
                "nilai": slot_val,
                "belum_dicari": True,
                "pesan": "Jawaban telah dicatat."
            }
            return ActionResult(aksi=ActionEnum.JAWAB_PERTANYAAN_BOT, fakta=fakta, produk_list=[])

        # Jalankan ulang aksi hanya jika ada kriteria produk baru yang diisi pada giliran ini
        if slot in ("kebutuhan", "aktivitas") and state.get("kebutuhan_teks"):
            return self._handle_minta_rekomendasi(args, state)
        elif slot in ("budget", "anggaran", "merek", "brand", "kategori", "category"):
            if state.get("kebutuhan_teks"):
                return self._handle_minta_rekomendasi(args, state)
            elif state.get("kategori") or state.get("merek"):
                return self._handle_cari_produk(args, state)
            else:
                fakta = {
                    "status": "jawaban_dicatat",
                    "slot_diisi": slot,
                    "nilai": slot_val,
                    "pesan": "Jawaban telah dicatat."
                }
                return ActionResult(aksi=ActionEnum.JAWAB_PERTANYAAN_BOT, fakta=fakta, produk_list=[])
        else:
            fakta = {
                "status": "jawaban_dicatat",
                "slot_diisi": slot,
                "nilai": slot_val,
                "pesan": "Jawaban telah dicatat."
            }
            return ActionResult(aksi=ActionEnum.JAWAB_PERTANYAAN_BOT, fakta=fakta, produk_list=[])

    # -------------------------------------------------------------------------
    # 9. perbaiki_percakapan
    # -------------------------------------------------------------------------
    def _handle_perbaiki_percakapan(self, args: ActionArguments, state: dict, parsed: Optional[ParserOutput] = None) -> ActionResult:
        jenis = args.jenis.value if hasattr(args.jenis, "value") else str(args.jenis)
        state_up = parsed.pembaruan_state if parsed else None

        # Terapkan pembaruan state jika ada
        catalog_cats = {"laptop", "desktop", "printer"}
        new_kategori = None
        if args.kategori and str(args.kategori).lower() in catalog_cats:
            new_kategori = str(args.kategori).lower()
        elif state_up and state_up.kategori and str(state_up.kategori).lower() in catalog_cats:
            new_kategori = str(state_up.kategori).lower()

        old_kategori = state.get("kategori")
        if new_kategori and old_kategori and new_kategori != old_kategori:
            state["kategori"] = new_kategori
            # B2: Reset saat kategori berganti
            if not args.merek and not (state_up and state_up.merek):
                state["merek"] = None
                if "kriteria_pelanggan" in state and isinstance(state["kriteria_pelanggan"], dict):
                    state["kriteria_pelanggan"].pop("merek", None)
            if args.max_harga is None and not (state_up and state_up.budget):
                state["budget"] = None
                if "kriteria_pelanggan" in state and isinstance(state["kriteria_pelanggan"], dict):
                    state["kriteria_pelanggan"].pop("max_harga", None)
            if not args.kebutuhan_teks and not (state_up and state_up.kebutuhan_teks):
                state["kebutuhan_teks"] = None
            state["produk_tampil"] = []
            state["produk_terakhir_dibahas"] = None
            state["history_produk_tampil"] = []
            state["profil_aktif"] = None
            state["batas_bot"] = {}
        elif new_kategori:
            state["kategori"] = new_kategori

        if state_up:
            if state_up.budget in (0, -1):
                state["budget"] = None
                if "kriteria_pelanggan" in state and isinstance(state["kriteria_pelanggan"], dict):
                    state["kriteria_pelanggan"].pop("max_harga", None)
            elif state_up.budget:
                state["budget"] = state_up.budget
            if state_up.persona:
                state["persona"] = state_up.persona
            if state_up.kebutuhan_teks:
                state["kebutuhan_teks"] = state_up.kebutuhan_teks
        if args.merek:
            state["merek"] = args.merek
        if args.max_harga in (0, -1):
            state["budget"] = None
            if "kriteria_pelanggan" in state and isinstance(state["kriteria_pelanggan"], dict):
                state["kriteria_pelanggan"].pop("max_harga", None)
        elif args.max_harga is not None:
            state["budget"] = parse_int_safe(args.max_harga)
        if args.persona:
            state["persona"] = args.persona
        if args.kebutuhan_teks:
            state["kebutuhan_teks"] = args.kebutuhan_teks

        has_criteria = bool(
            args.kategori or args.merek or (args.max_harga is not None) or args.kebutuhan_teks or args.persona or args.gpu or args.ram_gb_min or
            state.get("_cabut_budget") or
            (state_up and (state_up.kategori or (state_up.budget is not None) or state_up.persona or state_up.kebutuhan_teks))
        )

        # C1: Jika ada kriteria produk di perbaiki_percakapan (koreksi, keluhan, salah_paham), jalankan pencarian;
        # keluhan hanya mengubah nada (flag ke generator), bukan membuang permintaan.
        if has_criteria:
            if state.get("kebutuhan_teks"):
                search_res = self._handle_minta_rekomendasi(args, state)
            else:
                search_res = self._handle_cari_produk(args, state)

            fakta = dict(search_res.fakta)
            fakta.update({
                "jenis": jenis,
                "rujukan": args.rujukan,
                "kebutuhan": state.get("kebutuhan_teks") or state.get("kebutuhan_diketahui"),
                "merek": state.get("merek"),
                "kategori": state.get("kategori"),
                "pemakai": state.get("persona") or state.get("pemakai"),
                "produk_tampil": state.get("produk_tampil", []),
                "pending_question": state.get("pending_question")
            })
            if jenis in ("keluhan", "salah_paham") or state.get("_ada_keluhan_pesan"):
                fakta["ada_keluhan"] = True
                fakta["nada"] = "keluhan"

            return ActionResult(
                aksi=ActionEnum.PERBAIKI_PERCAKAPAN,
                fakta=fakta,
                produk_list=search_res.produk_list,
                profil_id=search_res.profil_id
            )

        fakta = {
            "status": "sukses",
            "jenis": jenis,
            "rujukan": args.rujukan,
            "kebutuhan": state.get("kebutuhan_teks") or state.get("kebutuhan_diketahui"),
            "merek": state.get("merek"),
            "kategori": state.get("kategori"),
            "pemakai": state.get("persona") or state.get("pemakai"),
            "produk_tampil": state.get("produk_tampil", []),
            "pending_question": state.get("pending_question"),
            "belum_dicari": True
        }
        return ActionResult(aksi=ActionEnum.PERBAIKI_PERCAKAPAN, fakta=fakta, produk_list=[])

    # -------------------------------------------------------------------------
    # 10. sapa, basa_basi, tidak_jelas (B12)
    # -------------------------------------------------------------------------
    def _handle_sapa(self, args: ActionArguments, state: dict) -> ActionResult:
        fakta = {
            "status": "sapaan",
            "sebutan": state.get("sebutan"),
            "belum_dicari": True
        }
        return ActionResult(aksi=ActionEnum.SAPA, fakta=fakta, produk_list=[])

    def _handle_basa_basi(self, args: ActionArguments, state: dict) -> ActionResult:
        jenis = args.jenis.value if hasattr(args.jenis, "value") else str(args.jenis)
        fakta = {
            "status": "basa_basi",
            "jenis": jenis,
            "belum_dicari": True
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
            "status": "sistem_error" if alasan == "sistem_error" else "tidak_jelas",
            "alasan": alasan,
            "kontak_staf": KONTAK_STAF,
            "pesan": pesan_map.get(alasan, pesan_map["tidak_dipahami"]),
            "belum_dicari": True
        }
        return ActionResult(aksi=ActionEnum.TIDAK_JELAS, fakta=fakta, produk_list=[])

    def build_deterministic_fallback(self, aksi: ActionEnum | str, fakta: dict, state: dict = None) -> str:
        """Merakit kalimat fallback deterministik dari fakta (F5)."""
        from services.llm_generator import build_deterministic_fallback_text
        aksi_str = aksi.value if hasattr(aksi, "value") else str(aksi)
        return build_deterministic_fallback_text(aksi_str, fakta)
