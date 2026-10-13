# -*- coding: utf-8 -*-
"""
Level 3: LLM Integration via Ollama (§17, §20)
Dipanggil HANYA saat deterministik Level 1 menghasilkan UNKNOWN / tidak paham.
Menghasilkan respons alami, ramah, dan manusiawi untuk menangani chit-chat,
keluhan pelanggan, atau ungkapan santai tanpa halusinasi produk.
"""
from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "gemma4:e4b"

SYSTEM_PROMPT_OPENING = (
    "Kamu adalah Bobby CS, Customer Service toko komputer 'Bobby Computer'.\n"
    "Karakter: Ramah, santun, bersahabat khas CS toko online Indonesia, selalu panggil pelanggan 'Kak'.\n"
    "Toko Bobby Computer resmi menjual perangkat Laptop, Desktop PC, dan Printer bergaransi resmi.\n\n"
    "Tugasmu: Menyapa pelanggan secara santun dan ramah, serta menanyakan perangkat komputer dan kebutuhan apa yang sedang dicari.\n"
    "Aturan Respon CS:\n"
    "1. Jawab santai, ramah, manusiawi, dan ringkas (1-2 kalimat saja).\n"
    "2. JANGAN PERNAH mengulang salam pembuka ('Halo Kak', 'Hai Kak', 'Selamat datang') jika percakapan sudah berjalan!\n"
    "3. JANGAN langsung menyemburkan daftar spesifikasi panjang atau mengarang harga produk sebelum pelanggan menjelaskan kebutuhannya.\n"
    "4. Jika pelanggan bertanya 'jual apa' atau menanyakan barang toko, jelaskan dengan ramah bahwa Bobby Computer menjual laptop, desktop, dan printer, lalu tanyakan santai sedang mencari perangkat apa."
)

SYSTEM_PROMPT = (
    "Kamu adalah Bobby CS, Customer Service toko komputer 'Bobby Computer'.\n"
    "Karakter: Ramah, santun, gaul khas CS toko online Indonesia, panggil pelanggan 'Kak'.\n"
    "Katalog Toko: Bobby Computer HANYA menjual Laptop, Desktop, dan Printer (total 20 produk).\n"
    "Panduan tanggapan:\n"
    "- DILARANG mengarang spesifikasi produk di luar katalog atau mengarang nama produk.\n"
    "- Jika pelanggan mengeluh atau salah paham, minta maaf dengan santai dan tawarkan bantuan seputar laptop, desktop, atau printer.\n"
    "- Jawab singkat dan padat (1-2 kalimat saja), jangan bertele-tele."
)

SYSTEM_PROMPT_PRODUCT = (
    "Kamu adalah Bobby CS, Customer Service toko komputer 'Bobby Computer'.\n"
    "Karakter: Ramah, santun, gaul khas CS toko online Indonesia, panggil pelanggan 'Kak'.\n\n"
    "Produk yang sedang dibahas dalam percakapan ini:\n"
    "{product_context}\n\n"
    "Aturan:\n"
    "1. Jawab singkat dan luwes (1-2 kalimat saja).\n"
    "2. Gunakan data spesifikasi di atas jika relevan. JANGAN karang spesifikasi lain.\n"
    "3. Untuk pertanyaan teknis umum (misal 'NVMe itu apa?', 'layar 15 inci itu gede gak?'), "
    "jawab dengan bahasa sederhana dan ramah — tidak perlu sebut ulang seluruh spek.\n"
    "4. Jika pelanggan bercanda atau bercerita, tanggapi santai lalu arahkan kembali ke produk.\n"
    "5. JANGAN mengulang salam pembuka seperti 'Halo Kak' atau 'Selamat datang'.\n"
    "6. Jika pelanggan bertanya di luar topik produk ini (minta rekomendasi produk lain, "
    "minta kategori berbeda), jawab bahwa info itu akan dicarikan — jangan rekomendasikan sendiri.\n"
    "7. Jika pelanggan bertanya tentang peran GPU / VGA, jelaskan bahwa GPU dedicated (NVIDIA RTX) "
    "penting untuk 3D rendering, engineering, video editing, dan gaming berat, sedangkan GPU terintegrasi "
    "lebih hemat daya untuk dokumen dan browsing."
)

def query_llm_opening(
    user_text: str,
    state: dict,
    chat_history: list[tuple[str, str]] | None = None,
    url: str = DEFAULT_OLLAMA_URL,
    model: str = DEFAULT_MODEL,
    timeout: float = 20.0
) -> str | None:
    """
    Kirim percakapan awal/chit-chat ke model kecil Ollama untuk respons alami, ramah, dan manusiawi.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT_OPENING}]
    
    brand = state.get("constraints", {}).get("brand") if state.get("constraints") else None
    if brand:
        messages.append({"role": "system", "content": f"PENTING: Pelanggan secara spesifik membahas merek {brand.upper()}. HANYA bahas produk dari merek {brand.upper()} yang ada di toko kami! JANGAN sebutkan merek lain."})

    if chat_history:
        for role, text in chat_history[-6:]:
            messages.append({"role": role, "content": text})
            
    cat = state.get("category")
    persona = state.get("persona_name") or state.get("persona")
    ctx_parts = []
    if persona:
        ctx_parts.append(f"peruntukan: {persona}")
    if cat:
        ctx_parts.append(f"kategori: {cat}")
    if brand:
        ctx_parts.append(f"merek: {brand}")
    cat_info = f" [Konteks: {', '.join(ctx_parts)}]" if ctx_parts else ""
    messages.append({"role": "user", "content": f"{user_text}{cat_info}"})
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 250,
            "repeat_penalty": 1.25
        }
    }
    
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                result = json.loads(resp.read().decode("utf-8"))
                reply = result.get("message", {}).get("content", "").strip()
                if reply.startswith("CS:"):
                    reply = reply[3:].strip()
                # Jika percakapan sudah berjalan, bersihkan sapaan pembuka berulang dari model kecil
                if chat_history:
                    import re
                    reply = re.sub(r"^(?:halo|hai|selamat datang(?: di bobby computer)?)[!.,\s]*(?:kak[!,.\s]*)?", "", reply, flags=re.IGNORECASE).strip()
                    if reply:
                        reply = reply[0].upper() + reply[1:]
                if reply:
                    return reply
    except Exception as e:
        logger.debug(f"LLM opening query skipped/failed: {e}")
        return None
        
    return None

def query_llm_product_chat(
    user_text: str,
    state: dict,
    products: list[dict],
    chat_history: list[tuple[str, str]] | None = None,
    url: str = DEFAULT_OLLAMA_URL,
    model: str = DEFAULT_MODEL,
    timeout: float = 20.0
) -> str | None:
    """
    Percakapan lanjutan setelah produk spesifik ditawarkan.
    Spek produk diinjeksikan ke system prompt agar LLM tidak mengarang.
    """
    # Bangun deskripsi singkat setiap produk yang sedang dibahas
    lines = []
    for p in products[:3]:
        use = f" Kegunaan: {p['usage_text']}." if p.get("usage_text") else ""
        if p["kategori"] == "monitor":
            lines.append(
                f"- {p['nama']}: {p['panel']}, layar {p['display']}, "
                f"harga {_fmt(p['harga_idr'])}.{use}"
            )
        elif p["kategori"] == "printer":
            lines.append(
                f"- {p['nama']}: {p.get('fungsi', '-')}, teknologi {p.get('teknologi', '-')}, "
                f"kecepatan {p.get('kecepatan', '-')}, koneksi {p.get('konektivitas', '-')}, "
                f"harga {_fmt(p['harga_idr'])}.{use}"
            )
        else:
            lines.append(
                f"- {p['nama']}: {p['cpu']}, RAM {p['ram_gb']} GB {p['ram_type']}, "
                f"storage {p['storage']}, GPU {p['gpu']}, layar {p['display']}, "
                f"harga {_fmt(p['harga_idr'])}.{use}"
            )
    product_context = "\n".join(lines)
    system = SYSTEM_PROMPT_PRODUCT.format(product_context=product_context)

    messages = [{"role": "system", "content": system}]
    if chat_history:
        for role, text in chat_history[-4:]:
            messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": user_text})

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.2, "num_predict": 300}
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                result = json.loads(resp.read().decode("utf-8"))
                reply = result.get("message", {}).get("content", "").strip()
                if reply.startswith("CS:"):
                    reply = reply[3:].strip()
                import re
                reply = re.sub(
                    r"^(?:halo|hai|selamat datang(?: di bobby computer)?)[!.,\s]*(?:kak[!,.\s]*)?",
                    "", reply, flags=re.IGNORECASE
                ).strip()
                if reply:
                    return reply[0].upper() + reply[1:]
    except Exception as e:
        logger.debug(f"LLM product_chat skipped/failed: {e}")
        return None
    return None

def _fmt(v: int) -> str:
    return "Rp" + f"{v:,}".replace(",", ".")


def query_llm_fallback(
    user_text: str,
    state: dict,
    chat_history: list[tuple[str, str]] | None = None,
    url: str = DEFAULT_OLLAMA_URL,
    model: str = DEFAULT_MODEL,
    timeout: float = 20.0
) -> str | None:

    """
    Kirim percakapan ke LLM lokal Ollama saat FSM deterministik tidak menangkap maksud pengguna.
    Mengembalikan string respons jika berhasil, atau None jika gagal/timeout.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Masukkan riwayat percakapan singkat jika ada
    if chat_history:
        for role, text in chat_history[-4:]:
            messages.append({"role": role, "content": text})
            
    # Konteks state saat ini
    cat = state.get("category")
    cat_info = f" (Kategori yang sedang dibahas pelanggan: {cat})" if cat else ""
    user_prompt = f"{user_text}{cat_info}"
    messages.append({"role": "user", "content": user_prompt})
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 250
        }
    }
    
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                result = json.loads(resp.read().decode("utf-8"))
                reply = result.get("message", {}).get("content", "").strip()
                if reply.startswith("CS:"):
                    reply = reply[3:].strip()
                if reply:
                    return reply
    except Exception as e:
        logger.debug(f"LLM fallback query skipped/failed: {e}")
        return None
        
    return None
