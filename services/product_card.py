# -*- coding: utf-8 -*-
"""
services/product_card.py
Perakit Kartu Produk Telegram HTML untuk ReIn Komputer (Antigravity v2).

Aturan:
- Format Telegram HTML aman (dengan html.escape).
- Menampilkan: nama, harga, spesifikasi singkat.
- Label ✅ HANYA jika syarat profil diperiksa dan terpenuhi (dari match_report.lolos_semua == True).
- Pencarian biasa/tanpa kebutuhan memakai format netral tanpa label ✅.
- Tidak ada klaim garansi atau stok pada kartu.
"""
from __future__ import annotations

import html
import re
from typing import Any, Dict, List, Optional


def format_product_card(product: dict, index: int | None = None) -> str:
    """Merakit 1 kartu produk dalam format Telegram HTML."""
    nama = html.escape(str(product.get("nama", "Produk Komputer")))
    harga_val = product.get("harga_formatted")
    if not harga_val:
        p_price = product.get("harga") or product.get("harga_idr")
        if p_price:
            from services.action_engine import format_rupiah
            harga_val = format_rupiah(p_price)
        else:
            harga_val = "Harga hubungi kami"
    harga = html.escape(str(harga_val))
    spek_val = product.get("spesifikasi") or product.get("spek_ringkas")
    if not spek_val:
        from services.catalog_search import clean_specs
        spek_val = clean_specs(product)
        if not spek_val:
            from services.action_engine import build_lembar_spesifikasi
            lembar = build_lembar_spesifikasi(product)
            if lembar:
                spek_val = " | ".join(f"{v}" for v in lembar.values() if v)
    spek = html.escape(str(spek_val or "-"))

    match_report = product.get("match_report") or {}
    lolos = match_report.get("lolos_semua") is True

    prefix = f"{index}. " if index is not None else ""
    check_badge = " ✅" if lolos else ""

    lines = [
        f"<b>{prefix}{nama}{check_badge}</b>",
        f"💰 Harga: <b>{harga}</b>",
        f"⚙️ Spek: {spek}"
    ]

    # Jika ada catatan belum terpenuhi pada evaluasi
    unmet = match_report.get("tidak_terpenuhi")
    if unmet and not lolos:
        unmet_text = html.escape(", ".join(str(x) for x in unmet[:2]))
        lines.append(f"ℹ️ Catatan: {unmet_text}")

    return "\n".join(lines)


def format_product_cards_message(
    products: List[Dict[str, Any]],
    judul_rekomendasi: Optional[str] = None
) -> str:
    """Merakit daftar kartu produk (maksimal 3) menjadi 1 pesan Telegram HTML yang rapi."""
    if not products:
        return ""

    cards = []
    has_match_badge = any((p.get("match_report") or {}).get("lolos_semua") is True for p in products)

    clean_judul = None
    if judul_rekomendasi:
        clean_judul = re.sub(r"^[A-Z]\d{2}\s*[-–—:]\s*", "", str(judul_rekomendasi)).strip()

    header = ""
    if clean_judul and has_match_badge:
        header = f"<b>Rekomendasi untuk {html.escape(clean_judul)}:</b>\n\n"
    elif products:
        header = "<b>Daftar Pilihan Produk:</b>\n\n"

    for i, p in enumerate(products[:3], 1):
        cards.append(format_product_card(p, index=i))

    return header + "\n\n".join(cards)
