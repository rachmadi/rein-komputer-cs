# -*- coding: utf-8 -*-
"""
Dynamic Context RAG Engine for Bobby Computer Customer Care
Arsitektur LLM-First:
- LLM (Gemma 4:e4b) mengontrol percakapan, memori multi-turn, emosi, dan penyesuaian konteks.
- RAG Retriever menyuplai data katalog produk resmi dari SQLite / Qdrant secara real-time.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.request
from typing import Any

from core.catalog import Catalog
from services.catalog_service import get_active_catalog

logger = logging.getLogger("dynamic_rag_engine")

DEFAULT_MODEL = os.getenv("CHAT_LLM_MODEL", "gemma4:e4b")
DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

# Pemetaan sinonim kategori
CATEGORY_KEYWORDS = {
    "printer": ["printer", "print", "cetak", "tinta", "cartridge", "ink tank", "ecotank", "scan", "fotokopi", "copy"],
    "laptop": ["laptop", "notebook", "komputer jinjing"],
    "desktop": ["desktop", "pc", "komputer", "mini pc", "all-in-one", "aio", "tower"],
}

BRAND_KEYWORDS = {
    "canon": ["canon", "pixma"],
    "epson": ["epson", "ecotank"],
    "brother": ["brother"],
    "acer": ["acer", "aspire", "nitro", "predator", "swift"],
    "asus": ["asus", "vivobook", "zenbook", "rog", "tuf"],
    "lenovo": ["lenovo", "ideapad", "thinkpad", "legion", "loq", "thinkcentre"],
    "hp": ["hp", "victus", "pavilion", "omen", "probook"],
    "dell": ["dell", "inspiron", "latitude", "alienware", "optiplex"]
}


def _extract_category_context(user_text: str, history: list[dict]) -> str | None:
    """Mendeteksi kategori produk aktif berdasarkan input user atau histori chat."""
    t = user_text.lower()
    
    # Deteksi sanggahan / protes: jika user menyangkal "kok laptop?", jangan jadikan laptop
    if any(p in t for p in ["kok laptop", "bukan laptop", "kenapa laptop", "kan printer", "kan tanya printer"]):
        return "printer"
    if any(p in t for p in ["kok printer", "bukan printer", "kan laptop", "kan tanya laptop"]):
        return "laptop"

    # Cek input user saat ini
    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if re.search(rf"\b{re.escape(kw)}\b", t):
                return cat

    # Cek pesan terakhir user atau bot di histori percakapan
    for m in reversed(history[-6:]):
        content = m.get("content", "") or m.get("text", "")
        c_low = content.lower()
        for cat, kws in CATEGORY_KEYWORDS.items():
            for kw in kws:
                if re.search(rf"\b{re.escape(kw)}\b", c_low):
                    return cat

    return None


def _extract_budget(user_text: str) -> tuple[int | None, int | None]:
    """Mengekstrak batas budget (max, min) dalam rupiah."""
    t = user_text.lower()
    b_max = None
    b_min = None

    # Pola x juta
    m_juta = re.findall(r"(\d+(?:[.,]\d+)?)\s*(?:juta|jt)", t)
    if m_juta:
        val = int(float(m_juta[0].replace(",", ".")) * 1_000_000)
        if any(w in t for w in ["di bawah", "dibawah", "kurang dari", "maksimal", "max", "mentok", "paling mahal", "budget"]):
            b_max = val
        elif any(w in t for w in ["di atas", "diatas", "lebih dari", "minimal", "min", "paling murah"]):
            b_min = val
        else:
            b_max = val

    # Pola x ribu / rb
    m_rb = re.findall(r"(\d+)\s*(?:ribu|rb)", t)
    if m_rb:
        val = int(m_rb[0]) * 1_000
        if any(w in t for w in ["di bawah", "dibawah", "kurang dari", "maksimal", "max"]):
            b_max = val
        elif any(w in t for w in ["di atas", "diatas", "lebih dari", "minimal"]):
            b_min = val
        else:
            b_max = val

    return b_max, b_min


def _find_recently_mentioned_products(history: list[dict], catalog: Catalog) -> list[dict]:
    """Mencari produk yang sempat disebut oleh asisten atau user pada giliran terbaru."""
    mentioned = []
    seen = set()
    for m in reversed(history[-4:]):
        content = (m.get("content", "") or m.get("text", "")).lower()
        for p in catalog.products:
            p_name = p["nama"].lower()
            p_code = p["kode"].lower()
            if (p_name in content or p_code in content) and p["kode"] not in seen:
                mentioned.append(p)
                seen.add(p["kode"])
    return mentioned


def retrieve_products_for_query(
    user_text: str,
    history: list[dict],
    catalog: Catalog,
    current_category: str | None = None,
    current_offered_products: list[str] | None = None
) -> tuple[list[dict], str | None]:
    """
    RAG Retriever:
    Mengambil produk yang relevan berdasarkan query user dan riwayat percakapan.
    """
    t = user_text.lower()
    cat = _extract_category_context(user_text, history) or current_category
    b_max, b_min = _extract_budget(user_text)
    recent_prods = _find_recently_mentioned_products(history, catalog)
    if not recent_prods and current_offered_products:
        recent_prods = [catalog.by_code[c] for c in current_offered_products if c in catalog.by_code]

    pool = catalog.products
    if cat:
        pool = [p for p in pool if p.get("kategori") == cat]

    # Cek brand spesifik yang diminta
    requested_brand = None
    for brand, kws in BRAND_KEYWORDS.items():
        if any(kw in t for kw in kws):
            requested_brand = brand
            break
    if requested_brand:
        pool_brand = [p for p in pool if requested_brand in p.get("nama", "").lower() or requested_brand == p.get("brand", "").lower()]
        if pool_brand:
            pool = pool_brand

    from core.normalizer import normalize
    from core.acts import extract_needs
    from core.catalog import has_tag

    # Deteksi kebutuhan spesifik pengguna dari teks saat ini & riwayat
    norm_text = normalize(user_text)
    needs = extract_needs(norm_text)
    if any(w in t for w in ["game", "gaming", "main game"]):
        if "gaming" not in needs:
            needs.append("gaming")
    if any(w in t for w in ["interior", "arsitek", "gambar teknik", "autocad", "sketchup", "render", "rendering", "3d"]):
        if "rendering_3d" not in needs:
            needs.append("rendering_3d")
        if "design" not in needs:
            needs.append("design")

    # Filter berdasarkan kebutuhan (gaming, office, design, dll.)
    if "gaming" in needs or "rendering_3d" in needs:
        gpu_pool = [
            p for p in pool
            if has_tag(p, "gaming") or has_tag(p, "rendering_3d") or any(x in str(p.get("gpu", "")).lower() for x in ("rtx", "gtx", "geforce", "rx"))
        ]
        if gpu_pool:
            pool = gpu_pool
    elif any(n in needs for n in ("design", "video_editing")):
        des_pool = [p for p in pool if has_tag(p, "design") or has_tag(p, "video_editing")]
        if des_pool:
            pool = des_pool
    elif any(n in needs for n in ("office", "daily", "student")):
        daily_pool = [p for p in pool if has_tag(p, "daily") or has_tag(p, "office") or has_tag(p, "student")]
        if daily_pool:
            pool = daily_pool

    # Filter fitur printer jika kategori printer
    if cat == "printer":
        if any(w in t for w in ("ink tank", "ecotank", "tangki")):
            tank_pool = [p for p in pool if "ink tank" in p.get("teknologi", "").lower()]
            if tank_pool: pool = tank_pool
        elif any(w in t for w in ("cartridge", "kartrid")):
            cart_pool = [p for p in pool if "cartridge" in p.get("teknologi", "").lower()]
            if cart_pool: pool = cart_pool
        elif any(w in t for w in ("scan", "copy", "fotokopi", "all in one", "multifungsi")):
            scan_pool = [p for p in pool if "scan" in p.get("fungsi", "").lower()]
            if scan_pool: pool = scan_pool
        elif "print only" in t:
            po_pool = [p for p in pool if "print only" in p.get("fungsi", "").lower()]
            if po_pool: pool = po_pool

    # 0. Hardware / GPU / Component Matching Langsung
    # Jika user menanyakan spesifikasi atau model khusus: "rtx 3050", "gpu", "vga", "nvidia", "geforce", "oled", "nitro", dll.
    spec_matches = []
    for p in pool:
        p_str = f"{p['nama']} {p.get('gpu', '')} {p.get('cpu', '')} {p.get('storage', '')} {p.get('display', '')}".lower()
        score = 0
        for rtx_num in ("2050", "3050", "4050", "4060", "4070"):
            if rtx_num in t and rtx_num in p_str:
                score += 25
        if "rtx" in t and "rtx" in p_str: score += 15
        if "nvidia" in t and "nvidia" in p_str: score += 15
        if "geforce" in t and "geforce" in p_str: score += 20
        if any(w in t for w in ("discrete", "dedicated", "vga dedicated", "gpu dedicated")) and any(x in str(p.get("gpu", "")).lower() for x in ("rtx", "gtx", "geforce", "rx")):
            score += 20
        if ("gpu" in t or "vga" in t) and any(x in str(p.get("gpu", "")).lower() for x in ("rtx", "gtx", "geforce", "rx")):
            score += 10
        if "oled" in t and "oled" in p_str: score += 15
        if "144" in t and "144" in p_str: score += 15
        if "nitro" in t and "nitro" in p_str: score += 20
        if "tuf" in t and "tuf" in p_str: score += 20
        if "loq" in t and "loq" in p_str: score += 20
        if "legion" in t and "legion" in p_str: score += 20
        if "vivobook" in t and "vivobook" in p_str: score += 15
        if score > 0:
            spec_matches.append((score, p))

    if spec_matches:
        spec_matches.sort(key=lambda x: -x[0])
        return [p for _, p in spec_matches[:3]], cat

    # 1. Kasus tanya spesifik / gambar / harga / spek: "Berapa harganya?", "Speknya apa?", "Gambarnya mana?"
    is_price_or_spec_query = any(w in t for w in [
        "berapa", "harganya", "berapahan", "spek", "spesifikasi",
        "gambar", "gambarnya", "foto", "fotonya", "lihat", "liat",
        "tampilin", "bentuk", "bentuknya", "fisik", "fisiknya", "penampakan"
    ])
    if is_price_or_spec_query and recent_prods:
        if requested_brand:
            matched_recent = [p for p in recent_prods if requested_brand in p["nama"].lower()]
            if matched_recent:
                return matched_recent, cat
        return [recent_prods[0]], cat

    # 2. Kasus minta opsi lebih mahal / kelas di atas: "Yang kelas di atas itu?", "Yang lebih mahal dikit"
    is_upgrade_query = any(w in t for w in ["di atas", "diatas", "kelas atas", "lebih mahal", "tinggi", "atasnya", "upgrade"])
    if is_upgrade_query and recent_prods:
        base_price = min(p["harga_idr"] for p in recent_prods)
        higher_prods = [p for p in pool if p["harga_idr"] > base_price]
        if higher_prods:
            higher_prods.sort(key=lambda p: p["harga_idr"])
            return higher_prods[:3], cat
        else:
            sorted_p = sorted(pool, key=lambda p: -p["harga_idr"])
            return sorted_p[:3], cat

    # 3. Kasus minta opsi lebih murah: "Ada yang lebih murah?", "Budget kurang"
    is_cheaper_query = any(w in t for w in ["lebih murah", "murahan", "hemat", "terjangkau"])
    if is_cheaper_query and recent_prods:
        base_price = max(p["harga_idr"] for p in recent_prods)
        cheaper_prods = [p for p in pool if p["harga_idr"] < base_price]
        if cheaper_prods:
            cheaper_prods.sort(key=lambda p: -p["harga_idr"])
            return cheaper_prods[:3], cat

    # 4. Kasus minta alternatif lain: "Pilihan lain?", "Ada tipe lain?", "Selain tipe ini"
    is_alt_query = any(w in t for w in ["pilihan lain", "opsi lain", "tipe lain", "selain", "ada lagi"])
    if is_alt_query and recent_prods:
        recent_codes = {p["kode"] for p in recent_prods}
        alt_prods = [p for p in pool if p["kode"] not in recent_codes]
        if alt_prods:
            alt_prods.sort(key=lambda p: p["harga_idr"])
            return alt_prods[:3], cat

    # 5. Filter berdasarkan budget
    if b_max is not None:
        under = [p for p in pool if p["harga_idr"] <= b_max]
        if under:
            under.sort(key=lambda p: -p["harga_idr"])
            return under[:3], cat
        else:
            cheapest = sorted(pool, key=lambda p: p["harga_idr"])[:2]
            return cheapest, cat

    if b_min is not None:
        above = [p for p in pool if p["harga_idr"] >= b_min]
        if above:
            above.sort(key=lambda p: p["harga_idr"])
            return above[:3], cat

    # Default: Kembalikan representasi pool kategori (urut harga)
    sorted_pool = sorted(pool, key=lambda p: p["harga_idr"])
    return sorted_pool[:3], cat


def format_product_rag_context(products: list[dict]) -> str:
    """Memformat daftar produk ke teks konteks yang rapi dan padat untuk LLM."""
    if not products:
        return ""

    lines = ["DATA KATALOG RESMI BOBBY COMPUTER (Gunakan hanya informasi ini):"]
    for p in products:
        price_str = f"Rp{p['harga_idr']:,}".replace(",", ".")
        kategori = p.get("kategori", "")
        usage = f" | Rekomendasi: {p['usage_text']}" if p.get("usage_text") else ""
        if kategori == "printer":
            lines.append(
                f"- [{p['kode']}] {p['nama']}: Harga {price_str} | Fungsi: {p.get('fungsi', '-')} | "
                f"Teknologi: {p.get('teknologi', '-')} | Kecepatan: {p.get('kecepatan', '-')} | "
                f"Konektivitas: {p.get('konektivitas', '-')}{usage}"
            )
        elif kategori == "laptop":
            gpu_str = p.get('gpu', '-')
            hint = " (Laptop Gaming dengan GPU Dedicated)" if any(x in gpu_str.lower() for x in ("rtx", "gtx", "geforce", "rx")) else ""
            lines.append(
                f"- [{p['kode']}] {p['nama']}: Harga {price_str} | CPU: {p.get('cpu', '-')} | "
                f"RAM: {p.get('ram_gb', '-')} GB {p.get('ram_type', '')} | Storage: {p.get('storage', '-')} | "
                f"GPU: {gpu_str}{hint} | Layar: {p.get('display', '-')}{usage}"
            )
        elif kategori == "desktop":
            lines.append(
                f"- [{p['kode']}] {p['nama']}: Harga {price_str} | CPU: {p.get('cpu', '-')} | "
                f"RAM: {p.get('ram_gb', '-')} GB | Storage: {p.get('storage', '-')} | "
                f"GPU: {p.get('gpu', '-')} (Monitor tidak termasuk){usage}"
            )
        elif kategori == "monitor":
            lines.append(
                f"- [{p['kode']}] {p['nama']}: Harga {price_str} | Ukuran: {p.get('display', '-')} | "
                f"Panel: {p.get('panel', '-')} | Refresh Rate: {p.get('refresh_rate', '-')}{usage}"
            )
        else:
            lines.append(f"- [{p['kode']}] {p['nama']}: Harga {price_str}{usage}")

    return "\n".join(lines)


def run_dynamic_rag(
    user_text: str,
    history: list[dict],
    catalog: Catalog | None = None,
    current_category: str | None = None,
    current_offered_products: list[str] | None = None,
    model: str = DEFAULT_MODEL,
    url: str = DEFAULT_OLLAMA_URL,
    timeout: float = 35.0
) -> dict[str, Any]:
    """
    Eksekusi 1-turn Dynamic Context RAG dengan LLM lokal (Gemma 4:e4b).
    Mengembalikan dict: {"reply": str, "products": list[dict], "category": str | None, "route": str}
    """
    cat_instance = catalog or get_active_catalog()
    t0 = time.time()

    # 1. RAG Retrieval
    matched_prods, active_cat = retrieve_products_for_query(
        user_text, history, cat_instance,
        current_category=current_category,
        current_offered_products=current_offered_products
    )
    rag_context = format_product_rag_context(matched_prods)

    # 2. System Prompt
    system_prompt = (
        "Kamu adalah Bobby CS, Customer Service toko komputer 'Bobby Computer' (menjual laptop, desktop PC, printer, monitor).\n"
        "Karakter: Ramah, santun, responsif, panggil pelanggan 'Kak'.\n\n"
        "PANDUAN UTAMA:\n"
        "1. Jawab santai, luwes, dan ringkas (2-3 kalimat saja).\n"
        "2. Gunakan DATA KATALOG RESMI di bawah ini. Rekomendasikan produk yang cocok dengan kebutuhan pelanggan (misal: jika minta game, rekomendasikan laptop gaming ber-GPU NVIDIA RTX dari daftar).\n"
        "3. DILARANG MENGARANG harga atau tipe produk yang tidak ada di data katalog di bawah.\n"
        "4. Jika pelanggan protes atau bot sebelumnya salah sebut (misal 'Kok laptop?'), minta maaf secara wajar dan kembalikan fokus ke kebutuhan pelanggan tanpa defensif.\n"
        "5. JANGAN mengulang salam pembuka ('Halo Kak', 'Selamat datang') jika percakapan sudah berjalan.\n"
        "6. Jawab to the point dan bantu pelanggan memilih opsi terbaik.\n"
        "7. GAYA BAHASA: Bicaralah murni seperti manusia CS toko yang natural. DILARANG KERAS menuliskan teks meta dalam kurung seperti '*(Sistem bot...)*', '*(Melampirkan foto...)*', atau catatan sistem lainnya. Tulis langsung apa yang ingin disampaikan ke pelanggan.\n"
        "8. GPU & GEFORCE: Bobby Computer memiliki stok laptop dengan GPU dedicated NVIDIA GeForce RTX (misal ASUS Vivobook Pro 15 OLED RTX 3050, Acer Nitro V 15, Lenovo LOQ 15, ASUS TUF, Legion). Jika pelanggan mencari GeForce atau kartu grafis dedicated, gunakan data katalog tersebut!\n\n"
        f"{rag_context}"
    )

    # 3. Format Messages
    messages = [{"role": "system", "content": system_prompt}]
    for m in history[-8:]:
        role = m.get("role") or ("assistant" if m.get("sender") in ("bot", "assistant") else "user")
        text = m.get("content") or m.get("text", "")
        if text:
            messages.append({"role": role, "content": text})

    if not messages or messages[-1].get("role") != "user" or messages[-1].get("content") != user_text:
        messages.append({"role": "user", "content": user_text})

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 300,
            "repeat_penalty": 1.2
        }
    }

    try:
        req = urllib.request.Request(
            f"{url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_reply = data.get("message", {}).get("content", "").strip()

            # Bersihkan prefix "CS:" jika ada
            if raw_reply.startswith("CS:"):
                raw_reply = raw_reply[3:].strip()

            # Bersihkan salam berulang jika sudah ada histori
            if history:
                raw_reply = re.sub(
                    r"^(?:halo|hai|selamat datang(?: di bobby computer)?)[!.,\s]*(?:kak[!,.\s]*)?",
                    "", raw_reply, flags=re.IGNORECASE
                ).strip()
                if raw_reply:
                    raw_reply = raw_reply[0].upper() + raw_reply[1:]

            # Bersihkan teks meta/tiruan instruksi foto otomatis dan kalimat menggantung
            raw_reply = re.sub(r'(?i)\*?\s*\([^)\n]*?(?:sistem|bot)[^)\n]*?\)\s*\*?', '', raw_reply)
            raw_reply = re.sub(r'(?i)\[[^\]\n]*?(?:sistem|bot)[^\]\n]*?\]', '', raw_reply)
            raw_reply = re.sub(r'(?mi)^\s*\*?\(?.*?(?:sistem bot|bot secara otomatis).*?\)?\*?\s*$', '', raw_reply)
            if not any(w in user_text.lower() for w in ("foto", "gambar", "lihat", "liat", "tampilin", "pic")):
                raw_reply = re.sub(r'(?mi)^\s*(?:ini|berikut)\s+(?:foto|gambar)\s+produknya[^\n]*:?\s*$', '', raw_reply)

            # Bersihkan penolakan foto jika ada (karena sistem kita selalu mengirimkan fotonya secara visual)
            raw_reply = re.sub(
                r'(?i)(?:mohon\s+maaf\s+kak[!,.\s]*)?saya\s+(?:tidak|belum)\s+bisa\s+(?:menampilkan|mengirim|memberikan)\s+(?:foto|gambar)[^.\n]*[.\s]*',
                '', raw_reply
            ).strip()
            if raw_reply.lower().startswith("tapi "):
                raw_reply = raw_reply[5:].strip()
            if raw_reply:
                raw_reply = raw_reply[0].upper() + raw_reply[1:]

            elapsed_ms = (time.time() - t0) * 1000
            logger.info(f"Dynamic RAG success ({elapsed_ms:.1f}ms): {raw_reply[:60]}...")

            return {
                "reply": raw_reply,
                "products": matched_prods,
                "category": active_cat,
                "route": "DYNAMIC_RAG",
                "latency_ms": elapsed_ms
            }

    except Exception as e:
        logger.error(f"Dynamic RAG failed/timed out: {e}")
        # Fallback ramah jika Ollama offline
        fallback_reply = (
            "Mohon maaf Kak, sistem AI kami sedang sedikit sibuk. "
            "Ada tipe produk atau kebutuhan spesifik yang bisa saya bantu cek secara manual?"
        )
        return {
            "reply": fallback_reply,
            "products": matched_prods,
            "category": active_cat,
            "route": "DYNAMIC_RAG_FALLBACK",
            "latency_ms": (time.time() - t0) * 1000
        }
