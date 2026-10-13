# -*- coding: utf-8 -*-
"""
services/llm_generator.py
Generator Bahasa Alami (LLM) untuk Bobby Computer di Telegram.

Sesuai Antigravity v2:
- Model: gemma4:e4b
- Temperature: 0.4, num_predict: 160, think: False
- Structured Output: JSON {teks: str, pertanyaan_diajukan: str | None}
- Menghasilkan maksimal 3 kalimat, ramah, santai, dan berpijak murni pada FAKTA.
"""
from __future__ import annotations

import os
import json
import time
import urllib.request
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
GENERATOR_MODEL = os.getenv("GENERATOR_MODEL", "gemma4:e4b")

GENERATOR_SYSTEM_PROMPT = """Kamu adalah pelayan toko ReIn Komputer di Telegram yang ramah, hangat, dan alami.
Jawab pesan pelanggan secara manusiawi dalam bahasa Indonesia:
1. Tanggapi dulu apa yang pelanggan katakan secara wajar, baru sampaikan faktanya.
2. Informasi angka, harga, spesifikasi, dan produk HANYA bersumber dari FAKTA (termasuk lembar_spesifikasi) atau produk_tampil. Klaim kemampuan/kualitas produk HANYA dari spesifikasi teknis atau KB; dilarang membuat klaim kemampuan di luar lembar spesifikasi/KB. Jika produk memiliki catatan_minimum memenuhi=false, JANGAN sebut produk tersebut cocok, sangat membantu, atau memadai (jelaskan batasannya secara jujur dan objektif). Jika atribut tidak ada, katakan terus terang informasinya belum tersedia tanpa klaim umum. JANGAN menyebut 'data belum tercatat/belum lengkap' untuk kategori yang ada di katalog (laptop, desktop, printer). Jika penanda 'belum_dicari' bernilai true, DILARANG menyatakan produk 'ada' atau 'tidak ada' tanpa lookup katalog. Untuk status tidak_ditemukan, gunakan 'merek_tersedia' atau 'kategori_tersedia' dari FAKTA untuk menawarkan alternatif.
3. JANGAN menyebut kode internal produk (seperti KB-L01, P01), istilah teknis sistem/database, atau frasa 'sistem mendeteksi' / 'sistem kami mendeteksi'.
4. JANGAN mengulang salam jika percakapan sudah berjalan.
5. Panggil pelanggan dengan 'Kak' atau 'Kakak', dan sebut pemakai perangkat sesuai sebutan pelanggan (misal: 'Papa', 'Adik', 'Ibu').
6. Bertanya balik HANYA jika ada informasi kebutuhan yang benar-benar kurang atau ambigu, dan gunakan kalimat yang berbeda dari pertanyaan di riwayat obrolan sebelumnya. Jika FAKTA memuat pilihan_konkret, tawarkan 2–3 pilihan konkret tersebut agar pelanggan mudah memilih. Jika bot menyebut 'ada pilihan lain' atau menawarkan alternatif, wajib menyebut nama produk dari FAKTA (alternatif_cocok), bukan hanya bertanya apakah pelanggan mau melihat pilihan lain.
7. Format jawaban mengalir alami, wajar (maksimal sekitar 600 karakter), tanpa daftar butir berpoin.
8. Jaring pengaman: jika FAKTA terasa tidak nyambung dengan pesan pelanggan, utamakan memahami maksud pesan pelanggan, jangan mengarang fakta, dan ajukan klarifikasi secara sopan.
9. Gaya & Variasi: Maaf paling banyak sekali per beberapa giliran, lalu langsung bertindak; jika 'sudah_minta_maaf' bernilai true, jangan minta maaf lagi; jangan mengulang pembuka yang sama dengan daftar 'pembuka_terakhir'.
10. Batas budget pelanggan adalah FILTER KERAS: DILARANG menawarkan, menyebut, atau merekomendasikan produk dengan harga di atas budget pelanggan sebagai pilihan. Jika tidak ada yang memenuhi seluruh syarat minimum, tampilkan produk di dalam budget yang paling mendekati dengan catatan jujur kekurangannya. Jika tidak ada produk sama sekali di dalam budget, katakan jujur dan tanyakan apakah pelanggan bersedia menaikkan budget — jangan menawarkan produk di luar budget tanpa diminta.
11. Kontrak Konteks Toko: (a) Jika status != 'sukses', jangan menyatakan produk tersedia atau merekomendasikan produk. (b) Jika status 'tidak_dijual', sampaikan barang/merek tidak dijual di ReIn Komputer, sebutkan isi Konteks Toko, dan jangan menawarkan produk pengganti kecuali diminta. (c) Jangan pernah mengklaim pelanggan menginginkan kriteria atau peruntukan yang tidak ada di Permintaan Pelanggan Giliran Ini atau riwayat obrolan. (d) Jangan pernah menyebut kategori atau merek di luar Konteks Toko kecuali mengonfirmasi toko tidak menjualnya. (e) Pertanyaan tentang toko menjual apa dijawab langsung dari Konteks Toko tanpa mencari produk.
12. Pertanyaan spesifikasi berbasis data (tanya_spesifikasi): Jawab HANYA dari lembar_spesifikasi atau data produk di FAKTA. Jika informasinya tidak ada di data (status 'atribut_tidak_tersedia'), katakan terus terang informasinya belum tersedia dalam data kami tanpa menebak dan tanpa mengalihkan ke spesifikasi lain. Jika menanyakan spesifikasi umum ('spesifikasinya?'), jawab dengan ringkasan lembar spesifikasi. Jika menanyakan kelebihan ('kelebihannya?'), jawab dengan perbandingan terhadap produk pembanding yang sedang dibahas, hanya dari data.
13. Dilarang Mengatribusikan Kebutuhan Yang Tidak Dinyatakan (Putaran 16 Butir 2): Jika pelanggan belum menyatakan kebutuhan atau peruntukan penggunaan perangkat (kebutuhan_teks kosong), DILARANG KERAS mengarang, menduga, atau mengklaim peruntukan/kebutuhan pelanggan (misal: 'berdasarkan kebutuhan Kakak untuk kerja kantor dan kuliah', 'untuk penggunaan harian dan office', atau 'kriteria minimum yang Kakak cari'). Jangan menebak peruntukan; bila relevan, tanyakan secara terbuka. Jika kebutuhan_teks ada, peruntukan yang disebut harus sesuai isinya.
14. Penanganan Salah Paham & Koreksi (perbaiki_percakapan): Jika pelanggan mengoreksi asumsi bot atau mengeluhkan salah paham (misal belum menyebutkan kebutuhan atau salah tangkap), akui salah paham dengan singkat dan sopan, jangan mengulangi asumsi yang salah tersebut, dan tawarkan produk yang sedang tampil atau tanyakan kebutuhan/keinginan pelanggan secara terbuka.

Contoh respons sintetis saat pelanggan kecewa:
- Contoh 1: Pelanggan: "Lama sekali responnya, butuh laptop kerja segera!" | FAKTA: {"status": "sukses", "produk_list": [{"nama": "Acro 14", "harga": 7000000, "ram": "16 GB"}]}
  Jawaban: {"teks": "Tentu Kak, kami bantu rekomendasikan unitnya. Maaf sempat menunggu ya. Di katalog ada Acro 14 dengan RAM 16 GB seharga Rp7.000.000.", "pertanyaan_diajukan": null, "penilaian": null, "tampilkan_kartu": true, "produk_dibahas": "Acro 14"}
- Contoh 2: Pelanggan: "Mana laptop merek X yang saya tanya?" | FAKTA: {"status": "tidak_ditemukan", "merek_tersedia": ["Alpha", "Beta"]}
  Jawaban: {"teks": "Baik Kak, untuk merek tersebut belum tersedia di katalog kami. Kami ada pilihan unit dari merek Alpha dan Beta jika Kakak berkenan mempertimbangkannya.", "pertanyaan_diajukan": null, "penilaian": null, "tampilkan_kartu": false, "produk_dibahas": null}

Kembalikan format JSON persis sesuai skema:
{"teks": "<jawaban ramah dan alami>", "pertanyaan_diajukan": "<slot: 'kebutuhan' | 'budget' | 'kategori' | null>", "penilaian": null, "tampilkan_kartu": null, "produk_dibahas": null}"""


from core.config import KONTAK_STAF
EMERGENCY_FALLBACK_TEXT = (
    f"Maaf Kak, saya belum bisa menjawab ini dengan tepat. "
    f"Boleh dicoba sekali lagi, atau Kakak bisa menghubungi {KONTAK_STAF}."
)


def build_deterministic_fallback_text(aksi: str, fakta: dict) -> str:
    """
    Merakit teks cadangan terstruktur langsung dari fakta_eksekusi secara deterministik (B10, B13, F5).
    Menangani seluruh 12 aksi ActionEnum tanpa jatuh ke EMERGENCY_FALLBACK_TEXT kecuali status sistem_error.
    """
    from core.db import format_daftar_kategori, extract_kategori_from_products
    from services.validator import get_catalog_categories, get_catalog_brands

    status = fakta.get("status")
    alasan = fakta.get("alasan")
    aksi_clean = str(aksi).lower().strip()

    # 1. SATU-SATUNYA kondisi yang boleh mengembalikan EMERGENCY_FALLBACK_TEXT
    if status == "sistem_error" or alasan == "sistem_error":
        return EMERGENCY_FALLBACK_TEXT

    # 2. Kasus-kasus spesifik status / kondisi katalog
    if status == "tidak_dijual":
        cats = ", ".join(fakta.get("kategori_tersedia") or get_catalog_categories())
        brands = ", ".join(fakta.get("merek_tersedia") or get_catalog_brands())
        ditolak_list = fakta.get("argumen_ditolak", [])
        nama_ditolak = ", ".join([str(d.get("nilai", "")) for d in ditolak_list if d.get("nilai")]) or "barang tersebut"
        return f"Mohon maaf Kak, {nama_ditolak} saat ini tidak dijual di ReIn Komputer. Kami menyediakan kategori {cats} dari merek {brands}."

    if status == "produk_tidak_di_katalog":
        prod_diminta = fakta.get("produk_diminta", [])
        nama_diminta = ", ".join([str(p) for p in prod_diminta]) if prod_diminta else "tersebut"
        padanan = fakta.get("padanan_terdekat", {})
        nama_padanan = padanan.get("nama") if isinstance(padanan, dict) else None
        if nama_padanan:
            return f"Produk {nama_diminta} belum tersedia di katalog ReIn Komputer, Kak. Sebagai alternatif terdekat yang tersedia, kami merekomendasikan {nama_padanan}."
        return f"Produk {nama_diminta} belum tersedia di katalog ReIn Komputer, Kak. Boleh ceritakan spesifikasi atau kebutuhan yang Kakak cari?"

    if status == "tidak_ada_dalam_anggaran":
        min_p = fakta.get("harga_termurah_kategori_formatted") or f"Rp{fakta.get('harga_termurah_kategori', 0):,}".replace(",", ".")
        return f"Belum ada produk dalam rentang anggaran tersebut, Kak. Pilihan paling terjangkau di katalog kami saat ini mulai dari {min_p}."

    if status == "belum_ada_yang_memenuhi":
        prods = fakta.get("produk", [])
        if prods and isinstance(prods, list):
            top_p = prods[0]
            nama = top_p.get("nama", "perangkat terdekat")
            raw_kekurangan = top_p.get("kekurangan", [])
            from services.catalog_search import format_natural_unmet_list
            if isinstance(raw_kekurangan, list):
                natural_k = format_natural_unmet_list([str(x) for x in raw_kekurangan])
                kek_str = ", ".join(natural_k) if natural_k else "spesifikasi masih di bawah kebutuhan minimum"
            else:
                kek_str = str(raw_kekurangan)
            return f"Saat ini belum ada produk dalam budget tersebut yang memenuhi seluruh spesifikasi minimum yang dibutuhkan, Kak. Pilihan dalam budget yang paling mendekati adalah {nama} ({kek_str})."

        p_close = fakta.get("produk_terdekat", {})
        nama = p_close.get("nama", "perangkat terdekat") if isinstance(p_close, dict) else "perangkat terdekat"
        raw_kekurangan = p_close.get("kekurangan", []) if isinstance(p_close, dict) else []
        from services.catalog_search import format_natural_unmet_list
        if isinstance(raw_kekurangan, list):
            natural_k = format_natural_unmet_list([str(x) for x in raw_kekurangan])
            kek_str = ", ".join(natural_k) if natural_k else "spesifikasi masih di bawah kebutuhan"
        else:
            kek_str = str(raw_kekurangan)
        return f"Saat ini belum ada produk yang memenuhi seluruh spesifikasi minimum yang dibutuhkan, Kak. Pilihan terdekat kami adalah {nama} ({kek_str})."

    if fakta.get("jenis_lanjutan") == "termurah_dari_tampil" and fakta.get("produk_termurah"):
        pt = fakta.get("produk_termurah", {})
        return f"Di antara produk yang tampil, opsi paling terjangkau adalah {pt.get('nama', '')} seharga {pt.get('harga_formatted', '')}, Kak."

    if status == "tidak_ada_lebih_murah":
        min_p = fakta.get("harga_termurah_saat_ini_formatted") or "harga tersebut"
        return f"Produk yang ditampilkan sebelumnya sudah merupakan opsi paling terjangkau di katalog kami ({min_p}), Kak."

    if status == "tidak_ada_lebih_mahal":
        return "Produk yang ditampilkan sebelumnya sudah merupakan opsi spesifikasi tertinggi di katalog kami, Kak."

    if status == "tanya_kebutuhan":
        persona = fakta.get("persona", "pengguna")
        return f"Baik Kak, kebutuhan untuk {persona} sudah dicatat. Boleh tahu biasanya akan lebih sering dipakai untuk aktivitas apa saja?"

    if status == "profil_tidak_ditemukan":
        return "Kami belum dapat memetakan kebutuhan tersebut ke rekomendasi spesifik, Kak. Boleh ceritakan aktivitas atau software utama yang akan sering digunakan?"

    if status == "profil_tidak_ditemukan_berulang":
        return f"Kebutuhan tersebut belum teridentifikasi di sistem kami, Kak. Kakak bisa menyebutkan kategori dan anggaran langsung, atau berkonsultasi dengan {KONTAK_STAF}."

    if status == "rujukan_tidak_ada":
        return "Produk yang dirujuk tidak ditemukan di daftar yang sedang tampil, Kak. Silakan sebutkan kebutuhan atau perangkat yang dicari."

    if status == "tidak_ditemukan":
        merek_alt = fakta.get("merek_tersedia", [])
        merek_text = f" Namun kami memiliki opsi merek {', '.join(merek_alt[:3])}." if merek_alt else ""
        return f"Maaf Kak, produk yang sesuai kriteria tersebut saat ini belum ditemukan di katalog kami.{merek_text} Boleh diceritakan kebutuhan perangkat yang dicari?"

    # 3. Penanganan per-aksi ActionEnum
    if aksi_clean in ("sapa", "sapaan") or status in ("sapa", "sapaan"):
        cats = format_daftar_kategori(konjungsi="atau")
        return f"Halo! Selamat datang di ReIn Komputer. Ada yang bisa kami bantu seputar kebutuhan {cats} hari ini?"

    if aksi_clean == "basa_basi" or status == "basa_basi":
        cats = format_daftar_kategori(konjungsi="atau")
        return f"Sama-sama Kak! Senang bisa membantu di ReIn Komputer. Jangan ragu bertanya kembali jika butuh informasi lain seputar {cats}."

    if aksi_clean == "tanya_info_toko" or status == "info_toko":
        topik = str(fakta.get("topik", "")).lower()
        if topik in ("produk", "katalog", "kategori", "merek", "jual_apa", "barang") or fakta.get("data_tersedia"):
            cats = ", ".join(fakta.get("kategori_tersedia") or get_catalog_categories())
            brands = ", ".join(fakta.get("merek_tersedia") or get_catalog_brands())
            return f"Di ReIn Komputer kami menyediakan produk dengan kategori {cats} dari merek {brands}. Ada yang bisa kami bantu carikan, Kak?"
        return f"Untuk informasi lebih lanjut mengenai toko kami, Kakak dapat menghubungi staf kami di {KONTAK_STAF}."

    if aksi_clean == "tanya_spesifikasi" or status in ("atribut_tidak_tersedia", "spek_umum") or fakta.get("spesifikasi_produk"):
        if status == "atribut_tidak_tersedia":
            attr = fakta.get("atribut_ditanya") or "tersebut"
            return f"Informasi mengenai spesifikasi {attr} belum tersedia dalam data kami, Kak."
        if fakta.get("tipe_jawaban") == "kelebihan":
            ringkasan = fakta.get("ringkasan_kelebihan") or fakta.get("pesan") or ""
            return f"Kelebihan {fakta.get('nama', 'produk tersebut')}: {ringkasan}."
        prods = fakta.get("spesifikasi_produk") or fakta.get("spesifikasi") or []
        if prods:
            item = prods[0]
            if item.get("atribut") in ("spek_umum", "spesifikasi") or fakta.get("tipe_jawaban") == "ringkasan_spesifikasi":
                return f"Berikut spesifikasi {item.get('nama', 'produk ini')}: {item.get('nilai') or item.get('ringkasan_spek', '')}."
            return f"Spesifikasi {item.get('atribut', 'perangkat')} untuk {item.get('nama', 'produk ini')} adalah {item.get('nilai', '')}."
        return "Informasi spesifikasi untuk produk tersebut belum tersedia dalam data kami, Kak."

    if aksi_clean == "evaluasi_kecocokan":
        eval_list = fakta.get("evaluasi_produk") or fakta.get("evaluasi") or []
        if isinstance(eval_list, list) and eval_list:
            item = eval_list[0]
            if isinstance(item, dict):
                nama = item.get("nama") or "Produk tersebut"
                cocok = item.get("cocok")
                catatan = item.get("catatan_minimum") or item.get("alasan")
                if cocok:
                    keb = fakta.get("kebutuhan_teks")
                    keb_str = f" untuk kebutuhan {keb}" if keb else ""
                    return f"{nama} sudah memenuhi spesifikasi minimum{keb_str}, Kak."
                else:
                    cat_str = f": {catatan}" if catatan else " masih berada di bawah kebutuhan spesifikasi minimum"
                    return f"{nama}{cat_str}, Kak."
        prods = fakta.get("produk", [])
        if prods and isinstance(prods, list) and isinstance(prods[0], dict):
            nama = prods[0].get("nama", "produk ini")
            return f"Untuk produk {nama}, spesifikasinya dapat disesuaikan dengan kebutuhan penggunaan Kakak."
        return "Produk yang Kakak tanyakan dapat disesuaikan dengan kebutuhan penggunaan yang diinginkan, Kak."

    if aksi_clean == "bandingkan":
        prods = fakta.get("perbandingan") or fakta.get("produk") or []
        if isinstance(prods, list) and len(prods) >= 2:
            n1 = prods[0].get("nama", "pilihan pertama") if isinstance(prods[0], dict) else str(prods[0])
            n2 = prods[1].get("nama", "pilihan kedua") if isinstance(prods[1], dict) else str(prods[1])
            return f"Berikut perbandingan antara {n1} dan {n2} di katalog kami. Keduanya memiliki perbedaan spesifikasi dan harga yang dapat disesuaikan dengan kebutuhan Kakak."
        elif isinstance(prods, list) and len(prods) == 1:
            n = prods[0].get("nama", "produk") if isinstance(prods[0], dict) else str(prods[0])
            return f"Di katalog kami tersedia {n}. Untuk membandingkan, boleh sebutkan produk pembanding lainnya, Kak?"
        return "Data perbandingan untuk produk yang dimaksud belum tersedia di katalog kami, Kak."

    if aksi_clean == "jawab_pertanyaan_bot":
        prods = fakta.get("produk", [])
        if prods and isinstance(prods, list):
            nama_list = [p.get("nama") for p in prods[:3] if isinstance(p, dict) and p.get("nama")]
            if nama_list:
                kat = fakta.get("kategori") or extract_kategori_from_products(prods) or format_daftar_kategori(konjungsi="atau")
                if fakta.get("kebutuhan_teks"):
                    return f"Berikut rekomendasi {kat} yang sesuai kebutuhan di katalog kami: {', '.join(nama_list)}. Apakah ada model yang ingin Kakak ketahui lebih detail?"
                return f"Berikut rekomendasi {kat} di katalog kami: {', '.join(nama_list)}. Apakah ada model yang ingin Kakak ketahui lebih detail?"
        kat = fakta.get("kategori") or format_daftar_kategori(konjungsi="atau")
        slot = str(fakta.get("slot") or "").lower()
        if "budget" in slot or fakta.get("budget"):
            return f"Baik Kak, anggaran sudah dicatat. Ada kriteria khusus untuk {kat} yang dicari?"
        elif any(s in slot for s in ("kebutuhan", "aktivitas")) or fakta.get("kebutuhan"):
            return f"Baik Kak, kebutuhan tersebut sudah dicatat. Sedang mencari {kat} dengan anggaran berapa kira-kira?"
        return f"Terima kasih atas informasinya, Kak. Ada kriteria atau anggaran tertentu untuk {kat} yang ingin dicari?"

    if aksi_clean == "perbaiki_percakapan":
        keluhan_beruntun = fakta.get("keluhan_beruntun", 0)
        if fakta.get("tawarkan_staf") or (isinstance(keluhan_beruntun, int) and keluhan_beruntun >= 2):
            return f"Mohon maaf atas ketidaknyamanannya ya Kak. Kami siap membantu mencarikan opsi yang tepat, atau Kakak dapat langsung berkonsultasi dengan staf kami di {KONTAK_STAF}."
        prods = fakta.get("produk") or fakta.get("produk_tampil") or []
        kat = fakta.get("kategori") or extract_kategori_from_products(prods) or format_daftar_kategori(konjungsi="atau")
        if prods and isinstance(prods, list):
            nama_list = [p.get("nama") for p in prods[:3] if isinstance(p, dict) and p.get("nama")]
            if nama_list:
                return f"Mohon maaf atas salah paham sebelumnya, Kak. Di katalog kami tersedia pilihan {kat}: {', '.join(nama_list)}. Boleh ceritakan penggunaan atau kriteria yang sedang dicari?"
        return f"Mohon maaf atas salah paham sebelumnya, Kak. Boleh diceritakan kembali kebutuhan atau spesifikasi {kat} yang sedang Kakak cari?"

    if aksi_clean == "lanjutan_hasil":
        prods = fakta.get("produk", [])
        if prods and isinstance(prods, list):
            nama_list = [p.get("nama") for p in prods[:3] if isinstance(p, dict) and p.get("nama")]
            if nama_list:
                kat = fakta.get("kategori") or extract_kategori_from_products(prods) or "perangkat"
                return f"Berikut opsi {kat} pilihan lainnya di katalog kami: {', '.join(nama_list)}. Ada model yang ingin Kakak ketahui lebih detail?"
        return "Belum ada opsi pilihan lain dengan harga lebih terjangkau yang tersedia di katalog kami, Kak."

    if aksi_clean in ("cari_produk", "minta_rekomendasi"):
        prods = fakta.get("produk", [])
        if prods and isinstance(prods, list):
            nama_list = [p.get("nama") for p in prods[:3] if isinstance(p, dict) and p.get("nama")]
            if nama_list:
                kat = fakta.get("kategori") or extract_kategori_from_products(prods) or format_daftar_kategori(konjungsi="atau")
                if fakta.get("kebutuhan_teks"):
                    return f"Berikut rekomendasi {kat} yang sesuai kebutuhan di katalog kami: {', '.join(nama_list)}. Apakah ada model yang ingin Kakak ketahui lebih detail?"
                return f"Berikut rekomendasi {kat} di katalog kami: {', '.join(nama_list)}. Apakah ada model yang ingin Kakak ketahui lebih detail?"
        merek_alt = fakta.get("merek_tersedia", [])
        merek_text = f" Namun kami memiliki opsi merek {', '.join(merek_alt[:3])}." if merek_alt else ""
        return f"Maaf Kak, produk yang sesuai kriteria tersebut saat ini belum ditemukan di katalog kami.{merek_text} Boleh diceritakan kebutuhan perangkat yang dicari?"

    if aksi_clean == "tidak_jelas" or status == "tidak_jelas":
        if alasan == "rujukan_tidak_ada":
            return "Produk yang dirujuk tidak ditemukan di daftar yang sedang tampil, Kak. Boleh sebutkan perangkat yang Kakak cari?"
        elif alasan == "bertentangan":
            return "Informasinya agak membingungkan nih, Kak. Boleh diperjelas kembali kebutuhan atau spesifikasi yang diinginkan?"
        cats = format_daftar_kategori(konjungsi="atau")
        return f"Boleh diceritakan lebih detail kebutuhan {cats} yang sedang Kakak cari?"

    # 4. Fallback jika membawa produk
    prods = fakta.get("produk", [])
    if prods and isinstance(prods, list):
        nama_list = [p.get("nama") for p in prods[:3] if isinstance(p, dict) and p.get("nama")]
        if nama_list:
            kat = fakta.get("kategori") or extract_kategori_from_products(prods) or format_daftar_kategori(konjungsi="atau")
            return f"Berikut rekomendasi {kat} di katalog kami: {', '.join(nama_list)}. Ada yang ingin Kakak ketahui lebih detail?"

    # 5. Fallback ramah jika aksi tidak dikenal tapi BUKAN sistem_error
    cats = format_daftar_kategori(konjungsi="atau")
    return f"Baik Kak, kami siap membantu menemukan pilihan {cats} di ReIn Komputer. Boleh ceritakan lebih detail kebutuhan atau anggaran yang Kakak rencanakan?"


class GeneratorOutput(BaseModel):
    teks: str = Field(description="Jawaban percakapan untuk pelanggan.")
    pertanyaan_diajukan: Optional[str] = Field(default=None, description="Slot yang ditanyakan bot jika ada, misal 'kebutuhan', 'budget', atau null.")
    penilaian: Optional[Dict[str, str]] = Field(default=None, description="Untuk evaluasi_kecocokan: mapping kode produk ke status kecocokan.")
    tampilkan_kartu: Optional[bool] = Field(default=None, description="Apakah kartu produk perlu ditampilkan ke pelanggan.")
    produk_dibahas: Optional[Union[str, List[str], None]] = Field(default=None, description="Kode produk yang sedang dibahas jika ada.")

    model_config = {
        "extra": "ignore"
    }


def build_generator_messages(
    aksi: str,
    fakta: dict,
    state: dict,
    history: list[dict] | None = None,
    pesan_pelanggan: str | None = None,
    feedback_note: str | None = None
) -> List[Dict[str, str]]:
    messages = [
        {"role": "system", "content": GENERATOR_SYSTEM_PROMPT}
    ]

    # Format ringkas riwayat (maks 8 entri)
    if history:
        hist_text = "\n".join([f"- {h.get('role', 'user')}: {h.get('content') or h.get('text') or ''}" for h in history[-8:]])
        messages.append({
            "role": "user",
            "content": f"Riwayat percakapan terakhir:\n{hist_text}"
        })

    # Konteks giliran ini: sebutan lawan bicara selalu 'Kak' kecuali pelanggan menyebut sebutan untuk diri sendiri
    sebutan = state.get("sebutan") or "Kak"

    # Hal yang sudah diketahui tentang pelanggan
    hal_diketahui = {
        "kategori": state.get("kategori"),
        "persona": state.get("persona"),
        "pemakai": state.get("persona") or state.get("pemakai"),
        "kebutuhan": state.get("kebutuhan_teks") or state.get("kebutuhan_diketahui") or state.get("profil_aktif"),
        "merek": state.get("merek") or (state.get("kriteria_pelanggan") or {}).get("merek"),
        "budget": state.get("budget"),
        "pertanyaan_terakhir_bot": state.get("pending_question") or state.get("last_asked_slot")
    }

    # Format produk_tampil (nama, harga; tanpa kode internal)
    raw_prods = state.get("produk_tampil", []) or fakta.get("produk", [])
    user_budget = state.get("budget")
    if user_budget and isinstance(user_budget, (int, float)) and user_budget > 0:
        raw_prods = [
            p for p in raw_prods
            if (p.get("harga") or p.get("harga_idr") or 0) <= user_budget
        ]
    prods_clean = []
    if isinstance(raw_prods, list):
        for idx, p in enumerate(raw_prods[:5]):
            if isinstance(p, dict):
                p_harga = p.get("harga_formatted")
                if not p_harga and (p.get("harga") or p.get("harga_idr")):
                    p_harga = f"Rp{int(p.get('harga') or p.get('harga_idr')):,}".replace(",", ".")
                prods_clean.append({
                    "no": idx + 1,
                    "nama": p.get("nama") or "Produk Komputer",
                    "harga": p_harga or "Harga hubungi kami"
                })

    # Bersihkan kode internal dari fakta agar generator tidak melihat kode internal (KB-xxx, Pxx)
    def _sanitize_codes(obj):
        if isinstance(obj, dict):
            return {k: _sanitize_codes(v) for k, v in obj.items() if not (k in ("kode", "kode_produk", "profil_id") and isinstance(v, str) and (v.startswith("KB-") or v.startswith("P0") or v.startswith("P1")))}
        elif isinstance(obj, list):
            return [_sanitize_codes(x) for x in obj]
        return obj

    clean_fakta = _sanitize_codes(fakta)

    # E1: sudah_minta_maaf dan pembuka_terakhir dari riwayat 3 balasan bot terakhir
    bot_replies = [
        h.get("content") or h.get("text") or ""
        for h in (history or [])
        if h.get("role") in ("assistant", "bot")
    ]
    last_3_bot = bot_replies[-3:]
    maaf_pattern = re.compile(r"\b(maaf|mohon\s+maaf|minta\s+maaf)\b", re.IGNORECASE)
    sudah_minta_maaf = any(bool(maaf_pattern.search(r)) for r in last_3_bot)

    pembuka_terakhir = []
    for r in last_3_bot:
        words = re.findall(r"\b\w+\b", r)
        if words:
            pembuka_terakhir.append(" ".join(words[:2]))

    # Format produk fokus saat ini (nama, bukan kode)
    fokus_codes = state.get("produk_dibahas", [])
    if isinstance(fokus_codes, str):
        fokus_codes = [fokus_codes]
    fokus_names = []

    # Format tumpukan fokus lama (nama, bukan kode; sertakan label_kebutuhan)
    prev_stack_raw = state.get("produk_dibahas_sebelumnya", [])
    prev_stack_clean = []

    # Helper cari nama dari kode
    cat_inst = None
    try:
        from services.catalog_service import get_active_catalog
        cat_inst = get_active_catalog()
    except Exception:
        pass

    def _code_to_name(c):
        if not c:
            return ""
        if cat_inst and cat_inst.by_code.get(c.upper()):
            return cat_inst.by_code[c.upper()].get("nama", c)
        for pt in state.get("produk_tampil", []):
            if isinstance(pt, dict) and pt.get("kode", "").upper() == str(c).upper():
                return pt.get("nama", c)
        return str(c)

    for fc in (fokus_codes or []):
        nm = _code_to_name(fc)
        if nm and nm not in fokus_names:
            fokus_names.append(nm)

    if isinstance(prev_stack_raw, list):
        for entry in prev_stack_raw:
            if isinstance(entry, dict):
                e_codes = entry.get("kode", [])
                if isinstance(e_codes, str):
                    e_codes = [e_codes]
                e_names = [_code_to_name(c) for c in e_codes if c]
                prev_stack_clean.append({
                    "nama_produk": e_names,
                    "label_kebutuhan": entry.get("label_kebutuhan", ""),
                    "giliran": entry.get("giliran")
                })

    from core.db import get_catalog_inventory
    inv = get_catalog_inventory()
    konteks_toko = {
        "kategori_dijual": inv.get("kategori", []),
        "merek_dijual": inv.get("merek", [])
    }

    permintaan_asli = clean_fakta.get("permintaan") or state.get("_permintaan_asli") or {}
    permintaan_giliran_ini = {
        "intent": aksi,
        "argumen_asli": permintaan_asli,
        "pesan_pelanggan": pesan_pelanggan
    }

    context_data = {
        "Konteks Toko": konteks_toko,
        "Permintaan Pelanggan Giliran Ini": permintaan_giliran_ini,
        "status_hasil": clean_fakta.get("status"),
        "pesan_pelanggan_giliran_ini": pesan_pelanggan,
        "aksi": aksi,
        "fakta": clean_fakta,
        "produk_tampil": prods_clean,
        "produk_fokus_saat_ini": fokus_names,
        "produk_dibahas_sebelumnya": prev_stack_clean,
        "hal_yang_sudah_diketahui": hal_diketahui,
        "sebutan_pelanggan": sebutan,
        "persona_pengguna_perangkat": state.get("persona"),
        "sudah_minta_maaf": sudah_minta_maaf,
        "pembuka_terakhir": pembuka_terakhir,
    }

    turn_prompt = f"Konteks giliran ini:\n{json.dumps(context_data, ensure_ascii=False, indent=2)}"
    if feedback_note:
        turn_prompt += f"\n\nCATATAN PERBAIKAN DARI PEMERIKSA (Wajib diperbaiki):\n{feedback_note}"

    messages.append({
        "role": "user",
        "content": turn_prompt
    })

    return messages


def generate_response(
    aksi: str,
    fakta: dict,
    state: dict,
    history: list[dict] | None = None,
    pesan_pelanggan: str | None = None,
    feedback_note: str | None = None,
    model: str = GENERATOR_MODEL,
    ollama_url: str = OLLAMA_BASE_URL,
    timeout: float = 25.0
) -> Tuple[GeneratorOutput, Dict[str, Any]]:
    """
    Menghasilkan jawaban percakapan via Ollama gemma4:e4b.
    Mengembalikan (GeneratorOutput, metrics_dict).
    """
    t0 = time.perf_counter()
    messages = build_generator_messages(
        aksi, fakta, state, history=history, pesan_pelanggan=pesan_pelanggan, feedback_note=feedback_note
    )
    schema = GeneratorOutput.model_json_schema()

    req_data = {
        "model": model,
        "messages": messages,
        "format": schema,
        "stream": False,
        "think": False,
        "keep_alive": "30m",
        "options": {
            "temperature": 0.4,
            "num_predict": 1024,
            "num_ctx": 4096
        }
    }

    raw_content = None
    json_valid = False
    error_msg = None
    done_reason = None
    prompt_eval_count = None
    eval_count = None
    load_duration = 0
    prompt_eval_duration = 0
    eval_duration = 0
    try:
        req = urllib.request.Request(
            f"{ollama_url}/api/chat",
            data=json.dumps(req_data).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_content = data.get("message", {}).get("content", "")
            prompt_eval_count = data.get("prompt_eval_count")
            eval_count = data.get("eval_count")
            done_reason = data.get("done_reason")
            load_duration = data.get("load_duration", 0)
            prompt_eval_duration = data.get("prompt_eval_duration", 0)
            eval_duration = data.get("eval_duration", 0)

        parsed_json = json.loads(raw_content)
        out = GeneratorOutput.model_validate(parsed_json)
        json_valid = True
    except Exception as e:
        logger.error(f"Gagal generate respons via Ollama: {e}")
        error_msg = str(e)
        fallback_teks = build_deterministic_fallback_text(aksi, fakta)
        out = GeneratorOutput(
            teks=fallback_teks,
            pertanyaan_diajukan=None
        )

    if out.teks:
        out.teks = re.sub(r"\bfilter\b", "pencarian", out.teks, flags=re.IGNORECASE)
        out.teks = re.sub(r"\btier\b", "tingkat", out.teks, flags=re.IGNORECASE)
        out.teks = re.sub(r"\bselisih\b", "perbedaan", out.teks, flags=re.IGNORECASE)

    # Batas wajar respons: maksimal ~600 karakter
    if len(out.teks) > 600:
        truncated = out.teks[:600]
        last_punct = max(truncated.rfind("."), truncated.rfind("?"), truncated.rfind("!"))
        if last_punct > 200:
            out.teks = truncated[:last_punct + 1].strip()
        else:
            out.teks = truncated.rstrip()

    dt_ms = (time.perf_counter() - t0) * 1000.0
    sumber_balasan = "llm" if not error_msg else ("emergency_fallback" if out.teks == EMERGENCY_FALLBACK_TEXT else "fallback_deterministik")
    metrics = {
        "latency_ms": round(dt_ms, 2),
        "latensi_ms": round(dt_ms, 2),
        "json_valid": json_valid,
        "error": error_msg,
        "sumber_balasan": sumber_balasan,
        "raw_content": raw_content,
        "raw_output": raw_content,
        "prompt_eval_count": prompt_eval_count,
        "eval_count": eval_count,
        "done_reason": done_reason,
        "num_predict": req_data["options"]["num_predict"],
        "num_ctx": req_data["options"]["num_ctx"],
        "load_duration_ms": round(load_duration / 1e6, 2) if load_duration else 0.0,
        "prompt_eval_duration_ms": round(prompt_eval_duration / 1e6, 2) if prompt_eval_duration else 0.0,
        "eval_duration_ms": round(eval_duration / 1e6, 2) if eval_duration else 0.0
    }
    return out, metrics
