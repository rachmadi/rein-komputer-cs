# -*- coding: utf-8 -*-
"""
services/agentic_tool_engine.py
Mesin AI Agent Customer Care ReIn Komputer berbasis Tool Calling (Ollama /api/chat).

PRINSIP:
1. LLM memimpin percakapan dan menanggapi pelanggan seperti staf toko yang ramah.
2. Kode TIDAK menentukan maksud pelanggan, TIDAK memilih aksi, TIDAK memaksa slot.
3. Fakta produk dan kebijakan toko hanya dari isi alat, bukan pemblokir jawaban.
4. Balasan LLM dikirim utuh tanpa pemotongan kode.
5. Kartu produk dan foto hanya untuk produk yang disebut di balasan akhir dan berasal dari hasil alat giliran itu.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from core.catalog import Catalog
from services.catalog_service import get_active_catalog
from services.agent_tools import AGENT_TOOLS_SCHEMA, execute_agent_tool, get_agent_tools_schema
from services.product_card import format_product_cards_message
from services.catalog_search import clean_specs

logger = logging.getLogger("agentic_tool_engine")

PROMPT_VARIAN = os.getenv("PROMPT_VARIAN", "V4")

# =============================================================================
# KOMPONEN-KOMPONEN PROMPT (Putaran 19b Butir 2)
# =============================================================================

KOMPONEN_KEPUTUSAN = (
    "Untuk setiap pesan pelanggan, putuskan dulu: jika menyangkut produk, harga, "
    "spesifikasi, ketersediaan, atau jumlah produk, panggil alat katalog; jika "
    "menyangkut penjelasan produk, panduan memilih, atau kebijakan toko, panggil "
    "alat pengetahuan; jika tidak, jawab langsung. Jangan menulis bahwa kamu akan "
    "mengecek; langsung panggil alatnya."
)

KOMPONEN_J = (
    " Kalimat seperti saya cek dulu tidak menjalankan apa pun: pelanggan hanya mendapat "
    "jawaban bila kamu benar-benar memanggil alat di giliran ini."
)

KOMPONEN_PERSONA_18E = (
    'Kamu staf toko ReIn Komputer yang melayani pelanggan lewat chat. Ramah, '
    'sopan, gaya chat Indonesia sehari-hari, sapa pelanggan "Kak".\n'
)

KOMPONEN_R = (
    'Kamu adalah Reni, staf customer service ReIn Komputer yang melayani pelanggan lewat chat. '
    'Saat menyapa pelanggan pertama kali dalam percakapan, perkenalkan dirimu sebagai Reni. '
    'Jangan menyebut dirimu chatbot, bot, AI, atau asisten virtual. Namun bila pelanggan bertanya '
    'apakah sedang berbicara dengan manusia atau bot, jawab jujur, misalnya: Saya Reni, '
    'chatbot CS dari ReIn Komputer. Ramah, sopan, gaya chat Indonesia sehari-hari, sapa pelanggan "Kak".\n'
)

KOMPONEN_R2 = (
    'Namamu Reni, staf customer service ReIn Komputer yang melayani pelanggan lewat chat. '
    'Bila pesan pertama pelanggan hanya salam, balas salamnya dan perkenalkan dirimu sebagai Reni. '
    'Bila pesan pertama sudah berisi pertanyaan atau permintaan, tetap panggil alat yang '
    'dibutuhkan lebih dulu, lalu sebut namamu singkat di jawabanmu. Jangan menyebut dirimu chatbot, '
    'bot, AI, atau asisten virtual. Namun bila pelanggan bertanya apakah sedang berbicara dengan '
    'manusia atau bot, jawab jujur, misalnya: Saya Reni, chatbot CS dari ReIn Komputer. Ramah, '
    'sopan, gaya chat Indonesia sehari-hari, sapa pelanggan "Kak".\n'
)

# Putaran 25 Butir 4a: Komponen persona R3
KOMPONEN_R3 = (
    'Namamu Reni, staf customer service ReIn Komputer yang melayani pelanggan lewat chat. '
    'Perkenalkan dirimu sebagai Reni hanya di awal percakapan; bila pesan pertama pelanggan '
    'sudah berisi pertanyaan atau permintaan, tetap panggil alat yang dibutuhkan lebih dulu, '
    'lalu perkenalkan diri singkat di balasan itu. Sesudah itu, sebut namamu hanya bila pelanggan '
    'menanyakan namamu, dan jangan memperkenalkan diri ulang. Jangan menyebut dirimu chatbot, '
    'bot, AI, atau asisten virtual. Namun bila pelanggan bertanya apakah sedang berbicara dengan '
    'manusia atau bot, jawab jujur, misalnya: Saya Reni, chatbot CS dari ReIn Komputer. Ramah, '
    'sopan, gaya chat Indonesia sehari-hari, sapa pelanggan "Kak".\n'
)

KOMPONEN_LAYANI_DAN_ALAT = (
    'Layani obrolan, permintaan, dan pertanyaan pelanggan secara manusiawi, dan '
    'penuhi permintaan pelanggan secara langsung.\n'
    'Kamu punya dua alat: katalog untuk produk yang dijual, harga, spesifikasi, '
    'ketersediaan, dan jumlah produk; pengetahuan untuk penjelasan produk, '
    'panduan memilih sesuai kebutuhan, dan kebijakan toko.\n'
)

KOMPONEN_K = (
    'Untuk pertanyaan kebijakan toko (kelengkapan paket, garansi, retur, pengiriman, '
    'pembayaran, nego harga) atau pengetahuan produk (perbedaan jenis, kegunaan, cara '
    'memilih), panggil pengetahuan atas inisiatifmu sendiri dan padukan hasilnya ke '
    'jawabanmu. Sampaikan kebijakan toko dengan tegas sesuai hasil, tanpa kata umumnya '
    'atau biasanya. Jika hasilnya tidak memuat jawaban, katakan terus terang bahwa '
    'informasinya belum ada.\n'
)

KOMPONEN_T = (
    "Setiap nama produk, angka, ukuran, jumlah, atau spesifikasi yang kamu sebut "
    "harus tertulis di hasil alat yang sudah kamu terima. Jika belum ada, panggil "
    "alat dulu; jangan menebak dari nama produk atau dari ingatan. Jangan mengatakan "
    "sudah mengecek bila di giliran ini kamu tidak memanggil alat. Jumlah produk yang "
    "kamu sebut harus sama dengan jumlah produk yang kamu namai."
)

KOMPONEN_P = (
    "Pengingat: putuskan lagi untuk pesan terbaru ini. Jika jawabannya menyangkut "
    "produk, harga, spesifikasi, jumlah, foto, atau kebijakan toko dan faktanya belum "
    "ada di hasil alat yang kamu terima, panggil alat sekarang."
)

KOMPONEN_V6_TAMBAHAN = (
    "Tulis hanya kalimat untuk pelanggan: jangan menulis pertimbangan atau alasan internalmu, "
    "dan jangan menyebut alat, katalog, pengetahuan, sistem, atau data kepada pelanggan. "
    "Jangan menyarankan pelanggan mengecek bagian, halaman, atau kebijakan sendiri; "
    "bila jawabannya belum ada di hasil alat, panggil alat, atau katakan terus terang "
    "bahwa informasinya belum ada.\n"
    "Bila pelanggan menanyakan foto, lihat ada_foto di hasil alat: foto produk yang bernilai "
    "true terkirim otomatis bersama kartunya, sedangkan untuk yang false katakan fotonya belum tersedia."
)

KOMPONEN_POS = (
    "Reni selalu menjawab dalam balasan yang sama: setiap balasanmu langsung terkirim ke pelanggan "
    "dan giliranmu selesai, jadi tidak ada kesempatan kembali nanti. Karena itu, bila perlu mengecek, "
    "Reni mengecek saat itu juga dengan memanggil alat, lalu menjawab. Bila ragu apakah perlu alat, panggil alat."
)


def build_agent_system_prompt(
    varian: Optional[str] = None,
    with_pos: Optional[bool] = None,
    persona_nama_r3: Optional[bool] = None,
    aturan_pribadi_atribut: Optional[bool] = None,
    kirim_foto_oleh_llm: Optional[bool] = None,
    aturan_layanan_p28: Optional[bool] = None,
) -> str:
    from core.db import get_catalog_inventory
    inv = get_catalog_inventory()
    kategori_str = ", ".join(inv.get("kategori", []))
    merek_str = ", ".join(inv.get("merek", []))

    sisa_text = (
        'Setiap kali jawabanmu menyangkut produk, harga, spesifikasi, jumlah, atau '
        'kebijakan toko, panggil alat dulu dan jawab berdasarkan hasilnya. Jangan '
        'menyebut data yang tidak ada di hasil alat.\n'
        'Bila pelanggan meminta pilihan atau daftar produk, sebutkan nama dan harga '
        'produknya dari hasil katalog.\n'
        'Tanyakan kebutuhan hanya bila membantu memilih, dan jangan menjadikannya '
        'syarat untuk melayani. Jangan menebak kebutuhan yang belum disebut '
        'pelanggan.\n'
        'Balas maksimal 4 kalimat, tanpa markdown, emoji, atau daftar berpoin.\n'
        f'Kategori yang tersedia: {kategori_str}.\n'
        f'Merek yang tersedia: {merek_str}.\n'
        'Saat menawarkan atau menyebut produk, sebut paling banyak 3 produk. Sebut '
        'lebih banyak, paling banyak 5, hanya jika pelanggan memintanya.\n'
        'Kartu produk berisi spesifikasi tampil otomatis untuk produk yang kamu sebut '
        'namanya, beserta fotonya bila ada_foto bernilai true. Sebut nama produknya; '
        'tidak perlu menyalin semua spesifikasi ke teks.\n'
        'Alat adalah urusan internalmu: jangan menyebut alat, katalog, atau '
        'pengetahuan kepada pelanggan, dan jangan menyuruh pelanggan memeriksa '
        'sendiri. Carikan jawabannya untuk pelanggan.\n'
        'Jika detail yang ditanyakan (spesifikasi, ukuran, harga, kebijakan) tidak '
        'ada di hasil alat yang sudah kamu terima, panggil alat lagi; jangan menjawab '
        'dari ingatan.'
    )

    v = (varian or PROMPT_VARIAN).upper()

    # Putaran 26 Butir 2: Aturan data pribadi dan atribut produk di akhir SISA sebelum T
    active_pribadi = (
        aturan_pribadi_atribut if aturan_pribadi_atribut is not None
        else (ATURAN_PRIBADI_ATRIBUT and v not in ("V0", "V1", "V2", "V3"))
    )
    if active_pribadi:
        sisa_text += (
            "\nKamu tidak punya data pribadi seperti alamat rumah, umur, atau kehidupan di luar pekerjaan, "
            "jadi jangan mengarangnya; bila pelanggan menanyakan hal pribadi, tolak dengan sopan dan ramah lalu kembali membantu. "
            "Jangan menyebut website, alamat, atau kontak toko yang tidak tertulis di hasil alat.\n"
            "Atribut satu produk, misalnya barebone, tangki tinta, ukuran, atau port, tidak berlaku untuk produk lain "
            "kecuali tertulis di hasil alat untuk produk itu; bila belum ada, panggil katalog untuk produk itu."
        )

    # Putaran 26 Butir 3c: Aturan foto diputuskan Reni di akhir SISA sebelum T
    active_foto_llm = (
        kirim_foto_oleh_llm if kirim_foto_oleh_llm is not None
        else (KIRIM_FOTO_OLEH_LLM and v not in ("V0", "V1", "V2", "V3"))
    )
    if active_foto_llm:
        sisa_text += (
            "\nFoto produk terkirim hanya untuk produk di foto_tersedia yang namanya kamu tulis di balasan; "
            "jangan menulis bahwa foto sudah terkirim untuk produk yang tidak kamu sebut namanya. "
            "Bila pelanggan bilang foto belum muncul, panggil katalog lagi dengan kirim_foto untuk produk itu dan sebut namanya; "
            "jangan menyebut kendala teknis. "
            "Bila pelanggan meminta spesifikasi produk spesifik atau meminta spek lengkap dari satu produk, "
            "selalu panggil katalog dengan kode_atau_nama dan sertakan kirim_foto=True agar gambar produk langsung terkirim bersama spesifikasinya."
        )

    # Putaran 30 Butir 2: Aturan pemanggilan katalog saat menyebut kategori/profil kebutuhan
    if v not in ("V0", "V1", "V2", "V3"):
        sisa_text += (
            "\nBila jawabanmu menyebut kategori atau profil kebutuhan produk, "
            "kamu wajib memanggil katalog pada giliran yang sama sebelum menjawab, "
            "memakai kata kunci atau tag kategori dari profil yang cocok. "
            "Jangan menjawab rekomendasi produk hanya dari panduan tanpa memeriksa katalog."
        )

    # Putaran 28 Butir 6: Varian prompt layanan (F + G), flag ATURAN_LAYANAN_P28 (hanya uji A/B)
    active_layanan_p28 = (
        aturan_layanan_p28 if aturan_layanan_p28 is not None
        else (ATURAN_LAYANAN_P28 and v not in ("V0", "V1", "V2", "V3"))
    )
    if active_layanan_p28:
        sisa_text += (
            "\nBila pelanggan bertanya apakah toko menjual sesuatu atau meminta rekomendasi, panggil katalog dan sebut produknya; panduan boleh ditambahkan singkat. "
            "Bila hasil alat tidak memuat informasi yang ditanyakan, katakan terus terang bahwa datanya belum tersedia; jangan menyuruh pelanggan melihat dokumen, tautan, atau tampilan lain. "
            "Bila pernyataan pelanggan benar, akui; bila kamu salah paham, minta maaf singkat lalu jawab pertanyaannya. "
            "Jangan menyarankan menaikkan budget bila pelanggan tidak menyebut budget. "
            "Sebut dirimu chatbot hanya bila pelanggan bertanya apakah sedang berbicara dengan manusia atau bot."
        )

    active_r3 = persona_nama_r3 if persona_nama_r3 is not None else (PERSONA_NAMA_R3 or v in ("R3", "V4_R3"))
    with_j = (v == "V5")
    with_v6 = (v == "V6")
    use_pos = with_pos if with_pos is not None else (v in ("P", "PB1", "V4_POS", "POS"))

    if v == "V0":
        persona = KOMPONEN_PERSONA_18E
        with_k = False
        with_t = False
    elif v == "V1":
        persona = KOMPONEN_R
        with_k = False
        with_t = False
    elif v == "V2":
        persona = KOMPONEN_R
        with_k = True
        with_t = False
    elif v in ("V3", "C"):
        persona = KOMPONEN_R
        with_k = True
        with_t = True
    elif v in ("V4", "V5", "V6", "P", "PB1", "B", "B1", "B1F", "R3", "V4_R3"):
        persona = KOMPONEN_R3 if active_r3 else KOMPONEN_R2
        with_k = True
        with_t = True
    else:
        persona = KOMPONEN_R3 if active_r3 else KOMPONEN_R
        with_k = True
        with_t = True

    keputusan = KOMPONEN_KEPUTUSAN + (KOMPONEN_J if with_j else "")
    if use_pos:
        prompt = f"{keputusan}\n\n{KOMPONEN_POS}\n\n{persona}{KOMPONEN_LAYANI_DAN_ALAT}"
    else:
        prompt = f"{keputusan}\n\n{persona}{KOMPONEN_LAYANI_DAN_ALAT}"

    if with_k:
        prompt += KOMPONEN_K
    prompt += sisa_text
    if with_v6:
        prompt += f"\n{KOMPONEN_V6_TAMBAHAN}"
    if with_t:
        prompt += f"\n\n{KOMPONEN_T}"
    return prompt


def variant_has_reminder(varian: Optional[str] = None) -> bool:
    """Apakah varian memakai pesan pengingat sistem P sebelum pesan user terbaru."""
    v = (varian or PROMPT_VARIAN).upper()
    return v in ("V3", "V4", "V5", "V6", "C", "P", "PB1", "B", "B1", "B1F", "R3", "V4_R3")


PERSONA_NAMA_R3: bool = True
ATURAN_PRIBADI_ATRIBUT: bool = False
KIRIM_FOTO_OLEH_LLM: bool = True
ATURAN_LAYANAN_P28: bool = False
CATATAN_PENGETAHUAN_KATALOG: bool = True
PRODUK_TERDEKAT: bool = True
PEMERIKSAAN_ULANG_JANJI: bool = False
MODE_BERPIKIR: bool = False
MODE_BERPIKIR_SEBAGIAN: bool = True
PENGURAI_ALAT_MENTAH: bool = True

SYSTEM_PROMPT = build_agent_system_prompt()


FALLBACK_EMERGENCY_REPLY = "Mohon maaf Kak, sistem kami sedang mengalami kendala teknis sesaat. Boleh tolong ulangi pertanyaannya?"


def summarize_tool_result(fn_name: str, result: Any) -> str:
    """Membuat ringkasan singkat dari hasil alat untuk pencatatan log."""
    if not isinstance(result, dict):
        return str(result)[:100]
    if fn_name in ("cari_produk", "katalog"):
        prods = result.get("produk", [])
        if prods:
            codes = [p.get("kode", "") for p in prods if p.get("kode")]
            return f"Ditemukan {len(prods)} produk: {', '.join(codes)}"
        termurah = result.get("harga_termurah_katalog")
        if termurah:
            return f"0 produk. Harga termurah katalog: {termurah}"
        details = result.get("detail", [])
        if details:
            codes = [it.get("kode", "") for it in details if it.get("kode")]
            return f"Detail lembar spesifikasi: {', '.join(codes)}"
        return f"{result.get('total_cocok', 0)} produk ditemukan"
    elif fn_name == "detail_produk":
        items = result.get("detail", [])
        codes = [it.get("kode", "") for it in items if it.get("kode")]
        return f"Detail lembar spesifikasi: {', '.join(codes)}"
    elif fn_name in ("pengetahuan_kebutuhan", "pengetahuan"):
        items = result.get("pengetahuan", [])
        if items:
            juduls = [it.get("judul", "") for it in items if it.get("judul")]
            return f"Pengetahuan: {', '.join(juduls[:2])}"
        sumber = result.get("sumber", "")
        profil = result.get("profil_id") or result.get("judul", "")
        return f"Pengetahuan: {profil} ({sumber})"
    elif fn_name == "info_toko":
        topik = result.get("topik", "")
        return f"Info toko topik: {topik}"
    return str(result)[:100]


_PRODUCT_KEYS_CACHE: dict[int, dict[str, list[str]]] = {}


def build_product_key_index(catalog: Optional[Catalog] = None) -> dict[str, list[str]]:
    """Membangun indeks kunci produk dari katalog sekali saja (Putaran 19 Butir 4)."""
    global _PRODUCT_KEYS_CACHE
    cat_inst = catalog or get_active_catalog()
    cat_id = id(cat_inst)
    if cat_id in _PRODUCT_KEYS_CACHE:
        return _PRODUCT_KEYS_CACHE[cat_id]

    product_keys: dict[str, set[str]] = {}
    token_to_codes: dict[str, set[str]] = {}
    phrase_to_codes: dict[str, set[str]] = {}

    for code, p in cat_inst.by_code.items():
        product_keys[code] = set()

        # 1. Kode produk
        product_keys[code].add(code.lower())

        nama = str(p.get("nama") or "").strip()
        brand = str(p.get("brand") or p.get("merek") or "").strip()

        # 2. Nama lengkap
        if nama:
            product_keys[code].add(nama.lower())

        # 3. Nama tanpa merek di depannya
        if brand and nama.lower().startswith(brand.lower()):
            nama_no_brand = nama[len(brand):].strip().lstrip("-").strip()
            if nama_no_brand and len(nama_no_brand) >= 3 and nama_no_brand.lower() != nama.lower():
                product_keys[code].add(nama_no_brand.lower())

        # 4. Token alfanumerik khas (termasuk potongan di kiri/kanan tanda hubung)
        raw_tokens = re.split(r"\s+", nama)
        sub_tokens = set()
        for rt in raw_tokens:
            cleaned = rt.strip(".,;:()\"'[]{}")
            if cleaned:
                parts = cleaned.split("-")
                if len(parts) > 1:
                    for part in parts:
                        p_clean = part.strip(".,;:()\"'[]{}")
                        if p_clean:
                            sub_tokens.add(p_clean)
                sub_tokens.add(cleaned)

        for tok in sub_tokens:
            tok_low = tok.lower()
            if len(tok) >= 3 and any(c.isalpha() for c in tok) and any(c.isdigit() for c in tok):
                token_to_codes.setdefault(tok_low, set()).add(code)

        # 5. Frasa dua kata berurutan dari nama (tanpa merek, hanya bagian sebelum "+")
        nama_pre_plus = nama.split("+")[0].strip()
        if brand and nama_pre_plus.lower().startswith(brand.lower()):
            nama_pre_plus = nama_pre_plus[len(brand):].strip().lstrip("-").strip()

        words = [w.strip(".,;:()\"'[]{}") for w in re.split(r"\s+", nama_pre_plus) if w.strip(".,;:()\"'[]{}")]
        for i in range(len(words) - 1):
            w1 = words[i]
            w2 = words[i + 1]
            if len(w1) >= 2 and len(w2) >= 2:
                phrase = f"{w1} {w2}".strip()
                phrase_to_codes.setdefault(phrase.lower(), set()).add(code)

    # Tambahkan token alfanumerik unik
    for tok_low, codes in token_to_codes.items():
        if len(codes) == 1:
            c = next(iter(codes))
            product_keys[c].add(tok_low)

    # Tambahkan frasa dua kata unik
    for phr_low, codes in phrase_to_codes.items():
        if len(codes) == 1:
            c = next(iter(codes))
            product_keys[c].add(phr_low)

    final_index = {
        code: sorted(list(keys), key=lambda k: len(k), reverse=True)
        for code, keys in product_keys.items()
    }
    _PRODUCT_KEYS_CACHE[cat_id] = final_index
    return final_index


def get_product_mention_position(product: dict, reply_text: str, catalog: Optional[Catalog] = None) -> int:
    """
    Mengembalikan posisi indeks kemunculan kunci produk paling awal di teks balasan (atau -1 jika tidak disebut).
    (Putaran 19 Butir 4).
    """
    if not reply_text or not product:
        return -1
    code = product.get("kode")
    if not code:
        return -1

    index = build_product_key_index(catalog)
    keys = list(index.get(code, []))
    if not keys:
        keys = [code.lower()]

    earliest_pos = -1
    for k in keys:
        pattern = rf"(?<!\w){re.escape(k)}(?!\w)"
        m = re.search(pattern, reply_text, re.IGNORECASE)
        if m:
            if earliest_pos == -1 or m.start() < earliest_pos:
                earliest_pos = m.start()

    return earliest_pos


def is_product_mentioned_in_reply(product: dict, reply_text: str, catalog: Optional[Catalog] = None) -> bool:
    """Mengecek apakah produk secara spesifik disebut di balasan akhir LLM."""
    return get_product_mention_position(product, reply_text, catalog=catalog) >= 0


def pilih_foto_yang_akan_dikirim(
    foto_tersedia: list[str] | None = None,
    produk_disebut: list[dict] | list[str] | None = None,
    reply_text: str = "",
    catalog_by_code: dict[str, dict] | None = None,
    max_foto: int = 5,
    foto_akan_dikirim: list[str] | None = None
) -> list[str]:
    """
    Fungsi murni untuk menentukan daftar kode produk yang fotonya akan dikirim (Putaran 28 Butir 3, diperbarui Putaran 29 Butir 1).
    Foto yang dikirim = irisan foto_tersedia dengan produk yang disebut di balasan akhir
    (menggunakan pencocok yang sama dengan kartu produk).
    Produk hasil pencarian yang tidak disebut tidak dikirim fotonya.
    """
    target_foto = foto_tersedia if foto_tersedia is not None else (foto_akan_dikirim or [])
    if not target_foto:
        return []

    foto_set = set(target_foto)
    hasil: list[str] = []
    seen: set[str] = set()

    # Kasus 1: Bila produk_disebut diberikan langsung (misal res.get("products") dari giliran)
    if produk_disebut is not None and len(produk_disebut) > 0:
        for item in produk_disebut:
            c = item.get("kode") if isinstance(item, dict) else str(item).strip()
            if c and c in foto_set and c not in seen:
                seen.add(c)
                hasil.append(c)
                if len(hasil) >= max_foto:
                    break
        return hasil

    # Kasus 2: Bila produk_disebut kosong / tidak diberikan, gunakan reply_text + pencocok kartu
    if reply_text:
        cat_map = catalog_by_code
        if not cat_map:
            from services.catalog_service import get_active_catalog
            cat_map = get_active_catalog().by_code

        candidates = []
        for c in target_foto:
            if c not in seen and c in cat_map:
                p = cat_map[c]
                pos = get_product_mention_position(p, reply_text)
                if pos >= 0:
                    candidates.append((pos, c))
                    seen.add(c)
        candidates.sort(key=lambda x: x[0])
        return [c for _, c in candidates[:max_foto]]

    return []


def call_ollama_chat_raw(
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str = "gemma4:e4b",
    url: str = "http://127.0.0.1:11434",
    num_predict: int = 1024,
    num_ctx: int = 8192,
    timeout: int = 120,
    think: bool = False
) -> dict:
    """Memanggil endpoint /api/chat Ollama secara langsung dan mengembalikan respons mentah & metrik."""
    t0 = time.perf_counter()
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": think,
        "options": {
            "num_predict": num_predict,
            "num_ctx": num_ctx,
            "temperature": 0.2
        }
    }
    if tools:
        payload["tools"] = tools

    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{url.rstrip('/')}/api/chat",
        data=req_data,
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        data = json.loads(body)
        latency_ms = (time.perf_counter() - t0) * 1000
        data["_latency_ms"] = latency_ms
        data["_raw_output"] = body
        return data


def format_tool_history_message(recent_tool_turns: list[dict]) -> str | None:
    """Menyusun ringkasan hasil alat dari giliran sebelumnya sebagai satu pesan system singkat (Putaran 19 Butir 3b)."""
    if not recent_tool_turns:
        return None
    lines = ["Ringkasan hasil alat 3 giliran terakhir:"]
    for turn in recent_tool_turns:
        for tc in turn.get("tool_calls", []):
            t_name = tc.get("nama")
            t_args = json.dumps(tc.get("argumen", {}), ensure_ascii=False)
            total = tc.get("total_cocok", 0)
            prods = tc.get("produk", [])
            if prods:
                p_items = []
                for p in prods[:5]:
                    kode = p.get("kode", "")
                    nama = p.get("nama", "")
                    harga = p.get("harga", "")
                    spek = p.get("spek", "")
                    ada_foto = p.get("ada_foto", False)
                    foto_suffix = ", ada foto" if ada_foto else ""
                    if spek:
                        p_items.append(f"{kode} {nama} ({harga}; {spek}{foto_suffix})".strip())
                    else:
                        p_items.append(f"{kode} {nama} ({harga}{foto_suffix})".strip())
                p_str = "; ".join(p_items)
                if total > len(p_items):
                    p_str += f" (total {total} produk cocok)"
                lines.append(f"- {t_name}({t_args}): {p_str}")
            elif tc.get("pengetahuan"):
                k_items = []
                for it in tc.get("pengetahuan", []):
                    judul = it.get("judul", "")
                    cuplikan = it.get("cuplikan", "")
                    if cuplikan:
                        k_items.append(f"{judul}: {cuplikan}")
                    else:
                        k_items.append(f"{judul}")
                k_str = "; ".join(k_items)
                if total > len(k_items):
                    k_str += f" (total {total} cocok)"
                lines.append(f"- {t_name}({t_args}): {k_str}")
            else:
                lines.append(f"- {t_name}({t_args}): total {total} cocok")
    return "\n".join(lines)


def parse_raw_tool_call(text: str) -> Optional[tuple[str, dict[str, Any]]]:
    """
    Mengurai panggilan alat mentah dari token Ollama seperti:
    katalog{kategori:<|"|>monitor<|"|>,kata_kunci:<|"|>24 inci<|"|>}<tool_call|><|tool_response>
    (Putaran 23 Butir 2).
    """
    m = re.search(r"(katalog|pengetahuan)\s*\{(.*?)\}", text, re.DOTALL)
    if not m:
        return None
    fn_name = m.group(1)
    body = m.group(2).strip()
    args: dict[str, Any] = {}
    pair_pattern = re.compile(
        r'([a-zA-Z0-9_]+)\s*:\s*(?:<\|"\|>(.*?)<\|"\|>|"([^"]*)"|\'([^\']*)\'|([^,}]+))'
    )
    for match in pair_pattern.finditer(body):
        k = match.group(1)
        v = match.group(2) if match.group(2) is not None else (
            match.group(3) if match.group(3) is not None else (
                match.group(4) if match.group(4) is not None else match.group(5)
            )
        )
        if v is not None:
            v = v.strip()
            if v.isdigit():
                v = int(v)
            args[k] = v
    if not args and body:
        return None
    return fn_name, args


def run_agentic_tool(
    user_text: str,
    history: list[dict],
    catalog: Optional[Catalog] = None,
    model: str = "gemma4:e4b",
    url: str = "http://127.0.0.1:11434",
    session_state: Optional[dict] = None,
    varian: Optional[str] = None,
    menunggu_menit: Optional[int] = None,
    pemeriksaan_ulang_janji: Optional[bool] = None,
    mode_berpikir: Optional[bool] = None,
    mode_berpikir_sebagian: Optional[bool] = None,
    pengurai_alat_mentah: Optional[bool] = None,
    persona_nama_r3: Optional[bool] = None,
    aturan_pribadi_atribut: Optional[bool] = None,
    kirim_foto_oleh_llm: Optional[bool] = None,
    aturan_layanan_p28: Optional[bool] = None,
    catatan_pengetahuan_katalog: Optional[bool] = None,
    produk_terdekat: Optional[bool] = None,
    **kwargs
) -> dict[str, Any]:
    """
    Menjalankan 1 giliran percakapan dengan AI agent ReIn Komputer.
    Alur:
      1. Rakit pesan: prompt sistem + konteks produk riwayat + riwayat chat + pesan user
      2. Loop tool calling (maksimal 3 putaran):
         - LLM membalas langsung ATAU memanggil alat
         - Sistem mengeksekusi alat dan mengembalikan hasilnya ke LLM
         - LLM meramu jawaban akhir
      3. Ambil kartu produk & foto HANYA untuk produk yang disebut di balasan akhir dan berasal dari hasil alat giliran ini.
      4. Balasan LLM dikirim utuh tanpa dipotong kode.
    """
    t_start = time.perf_counter()
    cat = catalog or get_active_catalog()
    state = session_state if session_state is not None else kwargs.get("state") or {}

    # Siapkan catatan riwayat produk yang pernah disebut sebelumnya
    mentioned_history: list[dict] = state.get("mentioned_products") or []
    mentioned_notes = ""
    if mentioned_history:
        lines = ["\nCatatan riwayat produk yang pernah dibahas sebelumnya:"]
        seen_codes = set()
        for mp in reversed(mentioned_history):
            c = mp.get("kode")
            if c and c not in seen_codes:
                seen_codes.add(c)
                lines.append(f"- {c}: {mp.get('nama')}")
            if len(seen_codes) >= 5:
                break
        mentioned_notes = "\n".join(lines)

    cat_synonyms_map = {
        "pc": "desktop", "komputer": "desktop", "all-in-one": "desktop", "aio": "desktop", "desktop": "desktop",
        "notebook": "laptop", "laptop": "laptop",
        "printer": "printer", "print": "printer", "cetak": "printer",
        "monitor": "monitor", "layar": "monitor"
    }
    detected_cat = None
    u_tokens = [w for w in re.findall(r"\w+", user_text.lower())]
    for tok in u_tokens:
        if tok in cat_synonyms_map:
            detected_cat = cat_synonyms_map[tok]
            break

    if not detected_cat and session_state:
        s_cat = session_state.get("category") or session_state.get("kategori")
        if s_cat and str(s_cat).lower() in ("laptop", "desktop", "printer", "monitor"):
            detected_cat = str(s_cat).lower()

    if not detected_cat and history:
        for h in reversed(history[-12:]):
            h_text = (h.get("content") or h.get("text") or "").lower()
            for tok in re.findall(r"\w+", h_text):
                if tok in cat_synonyms_map:
                    detected_cat = cat_synonyms_map[tok]
                    break
            if detected_cat:
                break

    active_var = (varian or kwargs.get("varian") or PROMPT_VARIAN).upper()
    active_r3 = (
        persona_nama_r3 if persona_nama_r3 is not None
        else kwargs.get("persona_nama_r3", PERSONA_NAMA_R3 or active_var in ("R3", "V4_R3"))
    )
    active_pribadi = (
        aturan_pribadi_atribut if aturan_pribadi_atribut is not None
        else kwargs.get("aturan_pribadi_atribut", ATURAN_PRIBADI_ATRIBUT)
    )
    active_foto_llm = (
        kirim_foto_oleh_llm if kirim_foto_oleh_llm is not None
        else kwargs.get("kirim_foto_oleh_llm", KIRIM_FOTO_OLEH_LLM)
    )
    active_layanan_p28 = (
        aturan_layanan_p28 if aturan_layanan_p28 is not None
        else kwargs.get("aturan_layanan_p28", ATURAN_LAYANAN_P28)
    )
    active_catatan_pengetahuan = (
        catatan_pengetahuan_katalog if catatan_pengetahuan_katalog is not None
        else kwargs.get("catatan_pengetahuan_katalog", CATATAN_PENGETAHUAN_KATALOG)
    )
    active_produk_terdekat = (
        produk_terdekat if produk_terdekat is not None
        else kwargs.get("produk_terdekat", PRODUK_TERDEKAT)
    )
    system_content = build_agent_system_prompt(
        varian=active_var,
        persona_nama_r3=active_r3,
        aturan_pribadi_atribut=active_pribadi,
        kirim_foto_oleh_llm=active_foto_llm,
        aturan_layanan_p28=active_layanan_p28,
    )
    if mentioned_notes:
        system_content += "\n" + mentioned_notes

    # Format riwayat pesan: prompt sistem + ringkasan hasil alat 3 giliran terakhir + riwayat pesan
    messages: list[dict] = [{"role": "system", "content": system_content}]

    recent_tools = (state.get("riwayat_alat") or [])[-3:]
    hist_tool_msg = format_tool_history_message(recent_tools)
    if hist_tool_msg:
        messages.append({"role": "system", "content": hist_tool_msg})

    for m in history[-8:]:
        role = m.get("role") or ("assistant" if m.get("sender") in ("bot", "assistant") else "user")
        content = m.get("content") or m.get("text") or ""
        if m.get("terkirim") is False:
            prefix = "(Balasan ini TIDAK sampai ke pelanggan karena gangguan koneksi.) "
            if not content.startswith(prefix):
                content = prefix + content
        if content:
            messages.append({"role": role, "content": content})

    if variant_has_reminder(active_var):
        rem_content = KOMPONEN_P
        if active_var == "B1F":
            rem_content += " Tulis balasan dalam satu paragraf, maksimal 4 kalimat, tanpa daftar dan tanpa baris baru."
        messages.append({"role": "system", "content": rem_content})

    menunggu_val = menunggu_menit if menunggu_menit is not None else kwargs.get("menunggu_menit")
    if menunggu_val is not None and menunggu_val >= 5:
        pesan_tertunda = (
            f"Catatan: pesan pelanggan berikut sudah menunggu sekitar {menunggu_val} menit "
            "karena layanan sempat tidak aktif. Kamu boleh meminta maaf atas keterlambatannya "
            "dengan wajar, lalu layani seperti biasa."
        )
        messages.append({"role": "system", "content": pesan_tertunda})

    # Putaran 25 Butir 4b: Fakta awal percakapan bila PERSONA_NAMA_R3 aktif
    if active_r3:
        ada_pesan_bot = any(
            m.get("sender") in ("bot", "assistant") or m.get("role") == "assistant"
            for m in history
        )
        if not ada_pesan_bot:
            fakta_awal = "Ini awal percakapan; kamu belum memperkenalkan diri."
        else:
            fakta_awal = "Kamu sudah memperkenalkan diri di percakapan ini."
        messages.append({"role": "system", "content": fakta_awal})

    messages.append({"role": "user", "content": user_text})

    MAX_TOOL_ROUNDS = 3
    all_tool_calls_logged: list[dict[str, Any]] = []
    all_llm_calls_logged: list[dict[str, Any]] = []
    all_tools_products_returned: list[dict[str, Any]] = []
    this_turn_tool_summaries: list[dict[str, Any]] = []
    foto_tersedia_turn: list[str] = []
    seen_foto_turn: set[str] = set()
    is_emergency_fallback = False
    emergency_error = None

    active_pemeriksaan = PEMERIKSAAN_ULANG_JANJI if pemeriksaan_ulang_janji is None else bool(pemeriksaan_ulang_janji)
    active_berpikir = MODE_BERPIKIR if mode_berpikir is None else bool(mode_berpikir)
    active_sebagian = MODE_BERPIKIR_SEBAGIAN if mode_berpikir_sebagian is None else bool(mode_berpikir_sebagian)
    active_pengurai = PENGURAI_ALAT_MENTAH if pengurai_alat_mentah is None else bool(pengurai_alat_mentah)
    raw_tool_events: list[str] = []

    # Bila B dan B1 sama-sama nyala, B yang berlaku
    if active_berpikir:
        active_sebagian = False

    JANJI_POLA = re.compile(r"\b(cek|periksa|carikan|cari dulu|lihat dulu|saya cari|saya carikan)\b", re.IGNORECASE)

    def _execute_tool_rounds(current_msgs: list[dict], max_rounds: int = 3) -> tuple[str, bool, Optional[str]]:
        nonlocal is_emergency_fallback, emergency_error
        round_idx = 0
        current_reply = ""
        active_tools_schema = get_agent_tools_schema(active_foto_llm)

        while round_idx < max_rounds:
            call_num = len(all_llm_calls_logged) + 1
            is_first_call_of_turn = (len(all_llm_calls_logged) == 0)

            if active_berpikir:
                call_think = True
                call_num_predict = 2048
            elif active_sebagian:
                if is_first_call_of_turn:
                    call_think = True
                    call_num_predict = 2048
                else:
                    call_think = False
                    call_num_predict = 1024
            else:
                call_think = False
                call_num_predict = 1024

            try:
                llm_resp = call_ollama_chat_raw(
                    messages=current_msgs,
                    tools=active_tools_schema,
                    model=model,
                    url=url,
                    num_predict=call_num_predict,
                    num_ctx=8192,
                    timeout=120,
                    think=call_think
                )

            except Exception as e:
                logger.error(f"Ollama chat error pada putaran {round_idx + 1}: {e}", exc_info=True)
                emergency_error = str(e)
                is_emergency_fallback = True
                all_llm_calls_logged.append({
                    "urutan": call_num,
                    "prompt_eval_count": None,
                    "eval_count": None,
                    "done_reason": "error",
                    "latensi_ms": 0.0,
                    "latensi": 0.0,
                    "raw_output": str(e),
                    "error": str(e),
                    "thinking_chars": 0
                })
                return "", True, str(e)

            msg = llm_resp.get("message", {})
            tool_calls = msg.get("tool_calls")
            latency_call = llm_resp.get("_latency_ms", 0.0)

            msg_content = msg.get("content", "") or ""
            thinking_str = msg.get("thinking") or ""
            if not thinking_str and "<think>" in msg_content and "</think>" in msg_content:
                m = re.search(r"<think>(.*?)</think>", msg_content, flags=re.DOTALL)
                if m:
                    thinking_str = m.group(1)
            if "<think>" in msg_content:
                msg_content = re.sub(r"<think>.*?</think>", "", msg_content, flags=re.DOTALL).strip()

            thinking_chars = len(thinking_str)

            all_llm_calls_logged.append({
                "urutan": call_num,
                "prompt_eval_count": llm_resp.get("prompt_eval_count"),
                "eval_count": llm_resp.get("eval_count"),
                "done_reason": llm_resp.get("done_reason"),
                "latensi_ms": round(latency_call, 2),
                "latensi": round(latency_call, 2),
                "raw_output": llm_resp.get("_raw_output", ""),
                "thinking_chars": thinking_chars
            })

            if not tool_calls:
                # Bila pengurai alat mentah aktif dan teks memuat token alat mentah (Putaran 23 Butir 2)
                if active_pengurai and ("<tool_call|>" in msg_content or "<|" in msg_content):
                    parsed = parse_raw_tool_call(msg_content)
                    if parsed:
                        fn_name, fn_args = parsed
                        logger.info(f"alat_mentah_diurai: {fn_name}({fn_args})")
                        raw_tool_events.append("alat_mentah_diurai")
                        tool_calls = [{
                            "function": {
                                "name": fn_name,
                                "arguments": fn_args
                            }
                        }]
                        # Teks mentah tidak pernah disimpan ke riwayat percakapan
                        msg = {"role": "assistant", "content": "", "tool_calls": tool_calls}
                    else:
                        logger.warning("alat_mentah_gagal: pola panggilan alat mentah tidak dapat diurai")
                        raw_tool_events.append("alat_mentah_gagal")
                        # Ulangi panggilan model sekali; bila masih gagal, pakai balasan darurat
                        try:
                            call_num_retry = len(all_llm_calls_logged) + 1
                            llm_resp_retry = call_ollama_chat_raw(
                                 messages=current_msgs,
                                 tools=active_tools_schema,
                                 model=model,
                                 url=url,
                                 num_predict=call_num_predict,
                                 num_ctx=8192,
                                 timeout=120,
                                 think=call_think
                            )
                            msg_retry = llm_resp_retry.get("message", {})
                            retry_tools = msg_retry.get("tool_calls")
                            retry_content = (msg_retry.get("content", "") or "").strip()
                            all_llm_calls_logged.append({
                                "urutan": call_num_retry,
                                "prompt_eval_count": llm_resp_retry.get("prompt_eval_count"),
                                "eval_count": llm_resp_retry.get("eval_count"),
                                "done_reason": llm_resp_retry.get("done_reason"),
                                "latensi_ms": round(llm_resp_retry.get("_latency_ms", 0.0), 2),
                                "latensi": round(llm_resp_retry.get("_latency_ms", 0.0), 2),
                                "raw_output": llm_resp_retry.get("_raw_output", ""),
                                "thinking_chars": len(msg_retry.get("thinking") or "")
                            })
                            if retry_tools:
                                tool_calls = retry_tools
                                msg = msg_retry
                            elif "<tool_call|>" in retry_content or "<|" in retry_content:
                                parsed_retry = parse_raw_tool_call(retry_content)
                                if parsed_retry:
                                    fn_name, fn_args = parsed_retry
                                    logger.info(f"alat_mentah_diurai: {fn_name}({fn_args})")
                                    raw_tool_events.append("alat_mentah_diurai")
                                    tool_calls = [{
                                        "function": {
                                            "name": fn_name,
                                            "arguments": fn_args
                                        }
                                    }]
                                    msg = {"role": "assistant", "content": "", "tool_calls": tool_calls}
                                else:
                                    logger.warning("alat_mentah_gagal: retry tetap gagal diurai")
                                    raw_tool_events.append("alat_mentah_gagal")
                                    is_emergency_fallback = True
                                    emergency_error = "alat_mentah_gagal"
                                    return FALLBACK_EMERGENCY_REPLY, True, emergency_error
                            else:
                                current_reply = retry_content
                                return current_reply, False, None
                        except Exception as e:
                            logger.error(f"Ollama chat retry error: {e}", exc_info=True)
                            is_emergency_fallback = True
                            emergency_error = f"alat_mentah_gagal: {e}"
                            return FALLBACK_EMERGENCY_REPLY, True, emergency_error

            if not tool_calls:
                # LLM langsung memberikan jawaban akhir
                current_reply = msg_content.strip()
                if current_reply:
                    return current_reply, False, None
                logger.warning(
                    f"LLM putaran {round_idx + 1} tidak memanggil alat tetapi mengembalikan balasan kosong; "
                    "melanjutkan ke sintesis balasan akhir."
                )
                break

            # LLM memanggil alat
            current_msgs.append(msg)
            for tc in tool_calls:
                fn = tc.get("function", {})
                fn_name = fn.get("name", "")
                fn_args = fn.get("arguments", {})
                if isinstance(fn_args, str):
                    try:
                        fn_args = json.loads(fn_args)
                    except Exception:
                        fn_args = {}

                # Auto-inject kirim_foto=True jika menanyakan produk spesifik / spek lengkap
                if fn_name in ("katalog", "detail_produk") and active_foto_llm:
                    is_specific_prod = bool(
                        fn_args.get("kode_atau_nama") or fn_args.get("kode") or fn_args.get("nama")
                    )
                    user_asks_specs = any(
                        kw in user_text.lower()
                        for kw in ("spek", "spesifikasi", "detail", "lengkap", "lembar", "gambar", "foto")
                    )
                    if not is_specific_prod and user_asks_specs and fn_args.get("kata_kunci"):
                        kw_val = str(fn_args.get("kata_kunci")).strip().upper()
                        if kw_val in cat.by_code or any(kw_val.lower() == p.get("nama", "").lower() for p in cat.by_code.values()):
                            is_specific_prod = True

                    if is_specific_prod and fn_args.get("kirim_foto") is not False:
                        fn_args["kirim_foto"] = True

                t0_tool = time.perf_counter()
                tool_res = execute_agent_tool(
                    fn_name,
                    fn_args,
                    catalog=catalog,
                    kirim_foto_oleh_llm=active_foto_llm,
                    catatan_pengetahuan_katalog=active_catatan_pengetahuan,
                    produk_terdekat=active_produk_terdekat
                )
                t_tool = (time.perf_counter() - t0_tool) * 1000

                prod_summary_list = []
                pengetahuan_summary_list = []
                total_cocok = 0
                if isinstance(tool_res, dict):
                    total_cocok = tool_res.get("total_cocok", 0)
                    if "produk" in tool_res and tool_res.get("produk"):
                        prods = tool_res.get("produk", [])
                        if isinstance(prods, list) and prods:
                            all_tools_products_returned.extend(prods)
                            for p in prods:
                                spek_val = p.get("spek_ringkas")
                                if not spek_val:
                                    cat_p = cat.by_code.get(p.get("kode")) if p.get("kode") else None
                                    spek_val = clean_specs(cat_p or p)
                                prod_summary_list.append({
                                    "kode": p.get("kode"),
                                    "nama": p.get("nama"),
                                    "harga": p.get("harga") or p.get("harga_idr"),
                                    "spek": spek_val,
                                    "ada_foto": bool(p.get("ada_foto"))
                                })
                    elif "produk_terdekat" in tool_res:
                        prods_terdekat = tool_res.get("produk_terdekat", [])
                        if isinstance(prods_terdekat, list):
                            all_tools_products_returned.extend(prods_terdekat)
                            for p in prods_terdekat:
                                spek_val = p.get("spek_ringkas")
                                if not spek_val:
                                    cat_p = cat.by_code.get(p.get("kode")) if p.get("kode") else None
                                    spek_val = clean_specs(cat_p or p)
                                prod_summary_list.append({
                                    "kode": p.get("kode"),
                                    "nama": p.get("nama"),
                                    "harga": p.get("harga") or p.get("harga_idr"),
                                    "spek": spek_val,
                                    "ada_foto": bool(p.get("ada_foto"))
                                })
                    elif "produk_di_kategori" in tool_res:
                        prods_kat = tool_res.get("produk_di_kategori", [])
                        if isinstance(prods_kat, list):
                            all_tools_products_returned.extend(prods_kat)
                            for p in prods_kat:
                                spek_val = p.get("spek_ringkas")
                                if not spek_val:
                                    cat_p = cat.by_code.get(p.get("kode")) if p.get("kode") else None
                                    spek_val = clean_specs(cat_p or p)
                                prod_summary_list.append({
                                    "kode": p.get("kode"),
                                    "nama": p.get("nama"),
                                    "harga": p.get("harga") or p.get("harga_idr"),
                                    "spek": spek_val,
                                    "ada_foto": bool(p.get("ada_foto"))
                                })
                    elif "detail" in tool_res:
                        details = tool_res.get("detail", [])
                        if isinstance(details, list):
                            all_tools_products_returned.extend(details)
                            for d in details:
                                spek_val = d.get("spek_ringkas")
                                if not spek_val:
                                    cat_d = cat.by_code.get(d.get("kode")) if d.get("kode") else None
                                    spek_val = clean_specs(cat_d or d)
                                prod_summary_list.append({
                                    "kode": d.get("kode"),
                                    "nama": d.get("nama"),
                                    "harga": d.get("harga"),
                                    "spek": spek_val,
                                    "ada_foto": bool(d.get("ada_foto"))
                                })
                    elif "pengetahuan" in tool_res:
                        k_items = tool_res.get("pengetahuan", [])
                        if isinstance(k_items, list):
                            for it in k_items:
                                chunk_teks = str(it.get("teks") or it.get("konten") or it.get("isi") or "").strip()
                                cuplikan = chunk_teks[:200]
                                pengetahuan_summary_list.append({
                                    "id": it.get("id"),
                                    "judul": it.get("judul"),
                                    "cuplikan": cuplikan
                                })

                tool_sum = {
                    "nama": fn_name,
                    "argumen": fn_args,
                    "total_cocok": total_cocok,
                    "produk": prod_summary_list,
                    "pengetahuan": pengetahuan_summary_list
                }
                if isinstance(tool_res, dict):
                    if "sumber" in tool_res:
                        tool_sum["sumber"] = tool_res["sumber"]
                    if "alasan_cadangan" in tool_res:
                        tool_sum["alasan_cadangan"] = tool_res["alasan_cadangan"]
                    if "catatan" in tool_res:
                        tool_sum["catatan"] = tool_res["catatan"]
                    if "produk_terdekat" in tool_res:
                        tool_sum["produk_terdekat"] = prod_summary_list
                this_turn_tool_summaries.append(tool_sum)

                if active_foto_llm and isinstance(tool_res, dict):
                    raw_fc = tool_res.get("foto_tersedia") or tool_res.get("foto_akan_dikirim") or []
                    for fc in raw_fc:
                        if fc and fc not in seen_foto_turn:
                            seen_foto_turn.add(fc)
                            foto_tersedia_turn.append(fc)
                            if len(foto_tersedia_turn) >= 5:
                                break

                ringkasan = summarize_tool_result(fn_name, tool_res)
                tool_call_log = {
                    "nama": fn_name,
                    "argumen": fn_args,
                    "ringkasan_hasil": ringkasan,
                    "hasil": tool_res,
                    "latensi_ms": round(t_tool, 2),
                    "latensi": round(t_tool, 2),
                }
                if isinstance(tool_res, dict):
                    if "sumber" in tool_res:
                        tool_call_log["sumber"] = tool_res["sumber"]
                    if "alasan_cadangan" in tool_res:
                        tool_call_log["alasan_cadangan"] = tool_res["alasan_cadangan"]
                all_tool_calls_logged.append(tool_call_log)

                current_msgs.append({
                    "role": "tool",
                    "content": json.dumps(tool_res, ensure_ascii=False)
                })

            round_idx += 1

        # Jika setelah loop belum ada final_reply dan tidak ada error, minta balasan akhir sintetis tanpa alat
        if not current_reply and not is_emergency_fallback:
            call_num = len(all_llm_calls_logged) + 1
            if active_berpikir:
                synth_think = True
                synth_num_predict = 2048
            else:
                synth_think = False
                synth_num_predict = 1024

            try:
                synth_msgs = list(current_msgs)
                synth_msgs.append({
                    "role": "system",
                    "content": (
                        "Berdasarkan hasil pemeriksaan alat di atas, berikan jawaban akhir yang ramah, "
                        "jelas, dan informatif kepada pelanggan. Rekomendasikan produk yang relevan dari katalog jika ada. "
                        "Jawab langsung tanpa memanggil alat lagi."
                    )
                })
                llm_resp_final = call_ollama_chat_raw(
                    messages=synth_msgs,
                    tools=None,
                    model=model,
                    url=url,
                    num_predict=synth_num_predict,
                    num_ctx=8192,
                    timeout=120,
                    think=synth_think
                )
                msg_final = llm_resp_final.get("message", {})
                final_content = msg_final.get("content", "") or ""
                final_thinking = msg_final.get("thinking") or ""
                if not final_thinking and "<think>" in final_content and "</think>" in final_content:
                    m = re.search(r"<think>(.*?)</think>", final_content, flags=re.DOTALL)
                    if m:
                        final_thinking = m.group(1)
                if "<think>" in final_content:
                    final_content = re.sub(r"<think>.*?</think>", "", final_content, flags=re.DOTALL).strip()

                if active_pengurai and ("<tool_call|>" in final_content or "<|" in final_content):
                    logger.warning("alat_mentah_gagal: token mentah muncul pada sintesis akhir")
                    raw_tool_events.append("alat_mentah_gagal")
                    is_emergency_fallback = True
                    emergency_error = "alat_mentah_gagal"
                    final_content = FALLBACK_EMERGENCY_REPLY

                current_reply = final_content.strip()
                all_llm_calls_logged.append({
                    "urutan": call_num,
                    "prompt_eval_count": llm_resp_final.get("prompt_eval_count"),
                    "eval_count": llm_resp_final.get("eval_count"),
                    "done_reason": llm_resp_final.get("done_reason"),
                    "latensi_ms": round(llm_resp_final.get("_latency_ms", 0.0), 2),
                    "latensi": round(llm_resp_final.get("_latency_ms", 0.0), 2),
                    "raw_output": llm_resp_final.get("_raw_output", ""),
                    "thinking_chars": len(final_thinking)
                })
            except Exception as e:
                logger.error(f"Ollama final synthesis error: {e}", exc_info=True)
                is_emergency_fallback = True
                emergency_error = str(e)
                all_llm_calls_logged.append({
                    "urutan": call_num,
                    "prompt_eval_count": None,
                    "eval_count": None,
                    "done_reason": "error",
                    "latensi_ms": 0.0,
                    "latensi": 0.0,
                    "raw_output": str(e),
                    "error": str(e),
                    "thinking_chars": 0
                })

        # Jika balasan masih kosong, gunakan teks asisten dari putaran sebelumnya bila ada
        if not current_reply and not is_emergency_fallback:
            for m in reversed(current_msgs):
                if m.get("role") == "assistant" and (m.get("content") or "").strip():
                    prev_txt = m.get("content").strip()
                    if not prev_txt.startswith("<tool_call") and not prev_txt.startswith("{"):
                        current_reply = prev_txt
                        logger.info("Menggunakan teks asisten dari putaran sebelumnya sebagai balasan: %s", current_reply[:60])
                        break

        return current_reply, is_emergency_fallback, emergency_error

    final_reply, is_emergency_fallback, emergency_error = _execute_tool_rounds(messages, max_rounds=MAX_TOOL_ROUNDS)

    pemeriksaan_ulang_terpicu = False
    balasan_sebelum_periksa = None

    if (
        active_pemeriksaan
        and not is_emergency_fallback
        and len(this_turn_tool_summaries) == 0
        and final_reply
        and bool(JANJI_POLA.search(final_reply.lower()))
    ):
        pemeriksaan_ulang_terpicu = True
        balasan_sebelum_periksa = final_reply
        messages.append({"role": "assistant", "content": final_reply})
        messages.append({
            "role": "system",
            "content": (
                "Balasanmu menyatakan akan mengecek, tetapi di giliran ini kamu belum memanggil alat. "
                "Panggil alat yang dibutuhkan sekarang, atau tulis ulang balasanmu tanpa janji mengecek "
                "dan tanpa menyuruh pelanggan mengecek sendiri."
            )
        })
        new_reply, is_emergency_fallback, emergency_error = _execute_tool_rounds(messages, max_rounds=MAX_TOOL_ROUNDS)
        if new_reply:
            final_reply = new_reply

    # Putaran 30 Butir 2: Pengaman pemanggilan katalog otomatis bila alat pengetahuan dipanggil
    # dan memuat catatan, tapi alat katalog sama sekali tidak dipanggil sampai balasan akhir giliran itu.
    pengetahuan_calls_with_catatan = [
        tc for tc in all_tool_calls_logged
        if tc.get("nama") in ("pengetahuan", "pengetahuan_kebutuhan")
        and isinstance(tc.get("hasil"), dict)
        and "catatan" in tc.get("hasil", {})
    ]
    katalog_sudah_dipanggil = any(
        tc.get("nama") in ("katalog", "cari_produk", "detail_produk")
        for tc in all_tool_calls_logged
    )

    # Jangan picu pengaman otomatis jika pengguna sedang bertanya alasan / komplain atas balasan sebelumnya
    is_meta_or_complaint = bool(re.search(r"^\s*(kenapa|mengapa|kok|kenape|ngapain)\b", user_text.lower()))

    if (
        pengetahuan_calls_with_catatan
        and not katalog_sudah_dipanggil
        and not is_emergency_fallback
        and not is_meta_or_complaint
        and final_reply
    ):
        # Ekstrak Tag katalog dari profil yang paling cocok di hasil pengetahuan
        tag_kata_kunci = None
        for pt in pengetahuan_calls_with_catatan:
            p_items = pt.get("hasil", {}).get("pengetahuan", [])
            for chunk in p_items:
                tk = chunk.get("tag_katalog")
                if tk:
                    if isinstance(tk, list) and tk:
                        tag_kata_kunci = ", ".join(tk)
                        break
                    elif isinstance(tk, str) and tk.strip() and tk.strip() != "-":
                        tag_kata_kunci = tk.strip()
                        break
                c_text = chunk.get("teks", "")
                m_tag = re.search(r"\*\*Tag katalog:\*\*\s*([^|\n]+)", c_text)
                if m_tag:
                    raw_tags = m_tag.group(1).strip()
                    if raw_tags and raw_tags != "-":
                        tag_kata_kunci = raw_tags
                        break
            if tag_kata_kunci:
                break

        # Jika belum terdeteksi dari user_text, session_state, atau history, ambil petunjuk perangkat dari chunk pengetahuan
        if not detected_cat:
            for pt in pengetahuan_calls_with_catatan:
                p_items = pt.get("hasil", {}).get("pengetahuan", [])
                for chunk in p_items:
                    c_text = chunk.get("teks", "")
                    m_perangkat = re.search(r"\*\*Perangkat:\*\*\s*([^\n]+)", c_text)
                    if m_perangkat:
                        raw_per = m_perangkat.group(1).lower()
                        for tok in re.findall(r"\w+", raw_per):
                            if tok in cat_synonyms_map:
                                detected_cat = cat_synonyms_map[tok]
                                break
                    if detected_cat:
                        break
                if detected_cat:
                    break

        if not detected_cat:
            logger.info("Pengaman P30 Butir 2 dilewati: kategori tidak terdeteksi dari pesan, riwayat, atau sesi.")
        else:
            katalog_guard_args: dict[str, Any] = {"kategori": detected_cat}
            if tag_kata_kunci:
                katalog_guard_args["kata_kunci"] = tag_kata_kunci
            else:
                katalog_guard_args["kata_kunci"] = user_text

            logger.info(f"Pengaman P30 Butir 2 terpicu: memanggil katalog otomatis {katalog_guard_args}")

            t0_guard = time.perf_counter()
            guard_catalog_res = execute_agent_tool(
                "katalog",
                katalog_guard_args,
                catalog=cat,
                kirim_foto_oleh_llm=active_foto_llm,
                catatan_pengetahuan_katalog=active_catatan_pengetahuan,
                produk_terdekat=active_produk_terdekat
            )
            t_guard = (time.perf_counter() - t0_guard) * 1000

            ringkasan_guard = summarize_tool_result("katalog", guard_catalog_res)
            tool_log_guard = {
                "nama": "katalog",
                "argumen": katalog_guard_args,
                "ringkasan_hasil": ringkasan_guard,
                "hasil": guard_catalog_res,
                "latensi_ms": round(t_guard, 2),
                "latensi": round(t_guard, 2),
                "pengaman_otomatis": True
            }
            all_tool_calls_logged.append(tool_log_guard)

            # Masukkan ke tool summaries dan pool produk turn
            this_turn_tool_summaries.append({
                "nama": "katalog",
                "argumen": katalog_guard_args,
                "total_cocok": guard_catalog_res.get("total_cocok", 0) if isinstance(guard_catalog_res, dict) else 0,
                "produk": guard_catalog_res.get("produk", []) if isinstance(guard_catalog_res, dict) else []
            })

            if isinstance(guard_catalog_res, dict):
                if "produk" in guard_catalog_res and guard_catalog_res.get("produk"):
                    all_tools_products_returned.extend(guard_catalog_res["produk"])
                elif "produk_terdekat" in guard_catalog_res and guard_catalog_res.get("produk_terdekat"):
                    all_tools_products_returned.extend(guard_catalog_res["produk_terdekat"])
                elif "produk_di_kategori" in guard_catalog_res and guard_catalog_res.get("produk_di_kategori"):
                    all_tools_products_returned.extend(guard_catalog_res["produk_di_kategori"])

                if active_foto_llm:
                    raw_fc = guard_catalog_res.get("foto_tersedia") or guard_catalog_res.get("foto_akan_dikirim") or []
                    for fc in raw_fc:
                        if fc and fc not in seen_foto_turn:
                            seen_foto_turn.add(fc)
                            foto_tersedia_turn.append(fc)
                            if len(foto_tersedia_turn) >= 5:
                                break

            # Berikan hasil katalog ke model untuk merevisi balasan dengan guardrail ketat
            messages.append({"role": "assistant", "content": final_reply})
            messages.append({
                "role": "system",
                "content": (
                    f"Hasil pemeriksaan katalog toko untuk '{tag_kata_kunci or user_text}':\n"
                    f"{json.dumps(guard_catalog_res, ensure_ascii=False)}\n\n"
                    "Berdasarkan hasil pemeriksaan katalog di atas, revisi balasanmu sebelumnya dengan menyertakan "
                    "rekomendasi produk nyata yang relevan dari katalog (sebutkan nama produk, spesifikasi ringkas, dan harganya). "
                    "PENTING: Hanya sebutkan produk yang BENAR-BENAR SESUAI dengan kategori dan profil kebutuhan pelanggan. "
                    "Jangan menawarkan produk di luar kategori yang sedang dicari (misalnya jangan menawarkan desktop/mini PC jika pelanggan mencari laptop), "
                    "dan jangan menawarkan produk yang spesifikasinya jelas tidak memadai untuk kebutuhan tersebut."
                )
            })

            call_num_rev = len(all_llm_calls_logged) + 1
            try:
                llm_resp_rev = call_ollama_chat_raw(
                    messages=messages,
                    tools=None,
                    model=model,
                    url=url,
                    num_predict=1024,
                    num_ctx=8192,
                    timeout=120,
                    think=False
                )
                rev_msg = llm_resp_rev.get("message", {})
                rev_content = rev_msg.get("content", "") or ""
                if "<think>" in rev_content:
                    rev_content = re.sub(r"<think>.*?</think>", "", rev_content, flags=re.DOTALL).strip()
                if rev_content.strip():
                    final_reply = rev_content.strip()

                all_llm_calls_logged.append({
                    "urutan": call_num_rev,
                    "prompt_eval_count": llm_resp_rev.get("prompt_eval_count"),
                    "eval_count": llm_resp_rev.get("eval_count"),
                    "done_reason": llm_resp_rev.get("done_reason"),
                    "latensi_ms": round(llm_resp_rev.get("_latency_ms", 0.0), 2),
                    "latensi": round(llm_resp_rev.get("_latency_ms", 0.0), 2),
                    "raw_output": llm_resp_rev.get("_raw_output", ""),
                    "thinking_chars": len(rev_msg.get("thinking") or "")
                })
            except Exception as e:
                logger.warning(f"Gagal revisi balasan dengan pengaman katalog P30: {e}")

    if is_emergency_fallback or not final_reply:
        final_reply = FALLBACK_EMERGENCY_REPLY

    # Saring produk yang disebut di balasan akhir dan berasal dari hasil alat giliran ini (maksimal 5, urut sebutan)
    mentioned_candidates: list[tuple[int, dict]] = []
    seen_turn_codes = set()
    for p in all_tools_products_returned:
        code = p.get("kode")
        if code and code not in seen_turn_codes:
            seen_turn_codes.add(code)
            pos = get_product_mention_position(p, final_reply)
            if pos >= 0:
                # Ambil spesifikasi lengkap dari katalog resmi jika tersedia
                cat_p = cat.by_code.get(code)
                prod_data = dict(cat_p) if cat_p else dict(p)
                # Pastikan key standar tersedia
                if "harga" not in prod_data and "harga_idr" in prod_data:
                    prod_data["harga"] = prod_data["harga_idr"]
                mentioned_candidates.append((pos, prod_data))

    # Urutkan berdasarkan urutan kemunculan di teks balasan dan batasi maksimal 5
    mentioned_candidates.sort(key=lambda item: item[0])
    mentioned_this_turn: list[dict] = [item[1] for item in mentioned_candidates[:5]]

    # Susun kartu produk Telegram HTML (hanya jika ada produk yang disebut)
    kartu_html = format_product_cards_message(mentioned_this_turn) if mentioned_this_turn else None

    # Perbarui riwayat produk yang pernah dibahas di session_state
    new_mentioned = list(mentioned_history)
    for p in mentioned_this_turn:
        if not any(x.get("kode") == p.get("kode") for x in new_mentioned):
            new_mentioned.append({
                "kode": p.get("kode"),
                "nama": p.get("nama"),
                "harga": p.get("harga") or p.get("harga_idr")
            })

    # Simpan di state ringkasan hasil alat giliran ini (Putaran 18b Butir 4)
    if this_turn_tool_summaries:
        riwayat_alat = state.setdefault("riwayat_alat", [])
        riwayat_alat.append({
            "tool_calls": this_turn_tool_summaries
        })
        state["riwayat_alat"] = riwayat_alat[-10:]

    # GroundingChecker LOG SAJA (Butir 4b): tidak memblokir, tidak memicu retry, tidak mengganti balasan
    pemeriksa_catatan: list[str] = []
    try:
        from services.grounding_checker import GroundingChecker
        checker = GroundingChecker()
        fakta_log = {
            "produk": mentioned_this_turn or all_tools_products_returned,
            "produk_tampil": mentioned_this_turn or all_tools_products_returned,
            "hasil_alat_produk": all_tools_products_returned,
            "tool_calls": all_tool_calls_logged,
            "status": "sukses" if not is_emergency_fallback else "sistem_error",
        }
        _, violations = checker.check(final_reply, fakta=fakta_log, state=state)
        pemeriksa_catatan = violations
    except Exception as check_err:
        logger.warning(f"GroundingChecker log-only error: {check_err}")
        pemeriksa_catatan = [f"checker_error: {check_err}"]

    total_latency_ms = (time.perf_counter() - t_start) * 1000

    turn_category = detected_cat or state.get("category") or state.get("kategori")
    if not turn_category:
        for tc in all_tool_calls_logged:
            if tc.get("nama") == "katalog":
                c_arg = tc.get("argumen", {}).get("kategori")
                if c_arg:
                    turn_category = c_arg
                    break
    if not turn_category and all_tools_products_returned:
        turn_category = all_tools_products_returned[0].get("kategori")

    return {
        "reply": final_reply,
        "products": mentioned_this_turn,
        "category": turn_category,
        "kartu_produk_html": kartu_html,
        "route": "AGENTIC_TOOL",
        "tool_calls": all_tool_calls_logged,
        "tools_called": [tc["nama"] for tc in all_tool_calls_logged],
        "llm_calls": all_llm_calls_logged,
        "generator_calls": all_llm_calls_logged,
        "latency_ms": round(total_latency_ms, 2),
        "is_emergency_fallback": is_emergency_fallback,
        "emergency_error": emergency_error,
        "error_darurat": emergency_error if is_emergency_fallback else None,
        "hasil_alat_giliran": this_turn_tool_summaries,
        "mentioned_products": new_mentioned,
        "pemeriksa_catatan": pemeriksa_catatan,
        "pemeriksaan_ulang": pemeriksaan_ulang_terpicu,
        "balasan_sebelum_periksa": balasan_sebelum_periksa,
        "alat_mentah_events": raw_tool_events,
        "foto_tersedia": foto_tersedia_turn[:5],
        "foto_akan_dikirim": foto_tersedia_turn[:5],
    }
