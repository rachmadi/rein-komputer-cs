import os
import json
import urllib.request
import logging
import re
import time
from core.catalog import Catalog
from services.knowledge_service import get_profile_by_id

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Anda asisten AI Bobby Computer.
TUGAS ANDA: Panggil tool `search_catalog` atau jawab sapaan.
JANGAN RAKIT ULANG HASIL TOOL KE DALAM TEKS!
Sistem akan melampirkan daftar produk secara otomatis.
Jika tool dipanggil, TULIS HANYA 1 KALIMAT PENGANTAR. (Misal: "Berikut rekomendasi yang cocok:")
JANGAN halusinasi harga/spek.
"""

TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "search_catalog",
            "description": "Cari produk dari katalog Bobby Computer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kategori": {"type": "string", "enum": ["laptop", "desktop", "printer", "monitor", "all"]},
                    "kebutuhan": {"type": "string", "description": "HANYA isi dengan peruntukan/kegiatan. Contoh: 'edit video', 'gaming', 'kasir', 'anak sekolah'."},
                    "query": {"type": "string", "description": "HANYA isi dengan nama merek, model, atau kata kunci eksplisit (misal: 'asus', '128gb', 'RTX')."},
                    "profil_id": {"type": "string", "description": "Isi jika user meminta opsi 'lain' atau 'lebih murah'."},
                    "min_harga": {"type": "integer"},
                    "max_harga": {"type": "integer"}
                }
            }
        }
    }
]

from services.catalog_search import (
    parse_budget_from_text,
    has_tag,
    _match_legacy_query,
    format_natural_unmet_requirements,
    clean_specs,
    _clean_specs,
    apply_filters,
    merge_filters,
    should_skip_rag,
    check_fast_path,
    execute_tool,
)

BYPASS_LLM1_ON_RAG = True
USE_LLM_FRAMING = os.getenv("USE_LLM_FRAMING", "false").lower() in ("true", "1", "yes")

def format_conversational_frame(
    user_text: str,
    facts_str: str,
    prods: list[dict],
    category: str | None = None,
    active_profile_id: str | None = None,
    use_llm: bool = False,
    model: str = "gemma4:e4b",
    url: str = "http://localhost:11434",
    persona_name: str | None = None
) -> tuple[str, dict]:
    """
    Lapisan percakapan Customer Care Bobby Computer:
    - Kode menyusun fakta (daftar produk, status kelolosan, spesifikasi, harga).
    - Membingkai dengan 1-2 kalimat pembuka & penutup yang natural ala Customer Care.
    - Menggunakan templat ramah untuk kasus cepat/sederhana (latensi ~0.00ms),
      atau memanggil LLM (terukur latensinya) saat use_llm=True.
    - Melarang seluruh kode internal (P0x, M0x, G0x).
    - Mengukur latensi pembingkaian.
    """
    t0 = time.perf_counter()
    cat_label = category or "perangkat"
    if not facts_str or not facts_str.strip():
        return facts_str, {"frame_latency": 0.0, "frame_mode": "none"}

    body = facts_str.strip()
    body = re.sub(r"^Berikut adalah rekomendasi produk yang cocok untuk kebutuhan Anda:\s*", "", body).strip()
    body = re.sub(r"^Beberapa pilihan produk kami:\s*", "", body).strip()

    if use_llm:
        t0_llm = time.time()
        prompt = (
            f"Kamu adalah staf Customer Care toko Bobby Computer.\n"
            f"Tulis 1 kalimat pembuka ramah dan 1 kalimat penutup singkat untuk menyapa pelanggan.\n"
            f"Dilarang mengulang spesifikasi atau merangkum daftar produk.\n"
            f"Pertanyaan user: '{user_text}'\n\n"
            f"Keluarkan HANYA format JSON:\n"
            f"{{\"intro\": \"<1 kalimat pembuka>\", \"outro\": \"<1 kalimat penutup>\"}}"
        )
        try:
            req_data = json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"num_ctx": 1024, "num_predict": 100, "temperature": 0.3}
            }).encode("utf-8")
            req = urllib.request.Request(f"{url}/api/chat", data=req_data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                cnt = res.get("message", {}).get("content", "").strip()
                m_json = re.search(r"\{.*\}", cnt, re.DOTALL)
                if m_json:
                    parsed = json.loads(m_json.group(0))
                    intro = parsed.get("intro", "").strip()
                    outro = parsed.get("outro", "").strip()
                    t_frame = time.time() - t0_llm
                    reply = f"{intro}\n\n{body}\n\n{outro}".strip()
                    reply = re.sub(r"\b(?:P\d{2}|M\d{2}|G0[1-4])\b\s*[—–\-:]?\s*", "", reply)
                    reply = re.sub(r"\b(?:P\d{2}|M\d{2}|G0[1-4])\b", "", reply)
                    reply = re.sub(r"\n{3,}", "\n\n", reply)
                    return reply, {"frame_latency": t_frame, "frame_mode": "llm"}
        except Exception as e:
            logger.warning(f"Fallback to template framing: {e}")

    facts_lower = body.lower()
    has_qualified = "✅" in body

    if "tidak ada yang lebih murah" in facts_lower:
        intro = f"Saat ini belum ada {cat_label} yang lebih terjangkau yang memenuhi seluruh spesifikasi mutlak kebutuhan ini, Kak."
        outro = "Kandidat terdekat di atas bisa dipertimbangkan jika Kakak bersedia menyesuaikan anggaran atau spesifikasi. Mau kami bantu cek opsi lainnya?"
    elif "tidak ada yang memenuhi syarat mutlak" in facts_lower or "kandidat terdekat" in facts_lower:
        intro = f"Mohon maaf Kak, untuk spesifikasi tersebut saat ini belum ada {cat_label} yang memenuhi seluruh syarat mutlak secara sempurna di katalog kami. Berikut kandidat terdekat yang paling mendekati:"
        outro = "Pilihan di atas bisa jadi pertimbangan jika Kakak bersedia menyesuaikan sedikit spesifikasi atau budget. Ada yang ingin ditanyakan lagi?"
    elif "produk tidak tersedia" in facts_lower or "tidak tersedia" in facts_lower:
        intro = f"Mohon maaf Kak, produk {cat_label} dengan kriteria tersebut saat ini belum tersedia di katalog kami."
        outro = "Apakah Kakak ingin kami rekomendasikan pilihan alternatif lain yang mendekati kebutuhan tersebut?"
    elif any(k in user_text.lower() for k in ["baterai awet", "daya tahan baterai", "batre awet", "baterai tahan lama", "batre tahan lama", "baterainya awet"]):
        intro = f"Data kapasitas dan daya tahan baterai tidak tercantum secara spesifik di katalog kami. Namun, untuk efisiensi daya, kami sarankan laptop tipis dengan kartu grafis terintegrasi (tanpa GPU dedicated). Berikut beberapa pilihannya:"
        outro = "Boleh kami tahu berapa perkiraan budget atau preferensi merek yang Kakak cari? Kami siap bantu pilihkan yang paling sesuai!"
    elif not has_qualified:
        target_str = f" untuk {persona_name}" if persona_name else ""
        intro = f"Berikut beberapa pilihan {cat_label}{target_str} yang tersedia di Bobby Computer:"
        outro = f"Silakan beri tahu kami jika ada kebutuhan khusus atau rentang anggaran tertentu untuk {persona_name} ya!" if persona_name else "Silakan beri tahu kami jika ada kebutuhan khusus atau rentang anggaran tertentu ya!"
    else:
        target_str = f" untuk {persona_name}" if persona_name else " Kakak"
        intro = f"Berikut rekomendasi {cat_label} yang memenuhi kriteria kebutuhan{target_str} di Bobby Computer:"
        outro = f"Apakah ada merek atau tipe tertentu yang ingin ditanyakan lebih detail untuk {persona_name}?" if persona_name else "Apakah ada merek atau tipe tertentu yang ingin Kakak tanyakan lebih detail?"

    # Hilangkan duplikasi kalimat header kandidat terdekat di awal body
    if "kandidat terdekat" in intro.lower() and "kandidat terdekat" in body.lower():
        body = re.sub(r"^(?:(?:Tidak ada yang|Belum ada yang)[^\n]*\n+)?(?:Kandidat terdekat[^\n]*\n+)?", "", body, flags=re.IGNORECASE).strip()

    # Bersihkan nama kolom teknis agar tidak muncul di teks pelanggan
    for col_raw, col_nat in [
        ("ram_gb", "RAM"),
        ("vram_gb", "VRAM"),
        ("storage_ssd_gb", "SSD"),
        ("cpu_tier", "tingkat prosesor"),
        ("gpu_dedicated", "GPU dedicated"),
    ]:
        body = re.sub(r"\b" + col_raw + r"\b", col_nat, body)

    # Hilangkan duplikasi kalimat/baris yang berurutan
    lines = body.split("\n")
    dedup_lines = []
    for l in lines:
        stripped = l.strip()
        if stripped and dedup_lines and dedup_lines[-1].strip() == stripped:
            continue
        dedup_lines.append(l)
    body = "\n".join(dedup_lines)

    framed = f"{intro}\n\n{body}\n\n{outro}".strip()
    framed = re.sub(r"\b(?:P\d{2}|M\d{2}|G0[1-4])\b\s*[—–\-:]?\s*", "", framed)
    framed = re.sub(r"\b(?:P\d{2}|M\d{2}|G0[1-4])\b", "", framed)
    framed = re.sub(r"\n{3,}", "\n\n", framed)
    # Hapus klaim tak berdasar
    framed = framed.replace(" bergaransi resmi dan siap pakai.", ".")
    framed = framed.replace(" bergaransi resmi.", ".")
    framed = framed.replace(" siap pakai.", ".")

    t_frame = time.perf_counter() - t0
    return framed, {"frame_latency": t_frame, "frame_mode": "template"}

def run_agentic_tool(
    user_text: str,
    history: list[dict],
    catalog: Catalog,
    current_category: str | None = None,
    current_offered_products: list[str] | None = None,
    shown_products: list[str] | None = None,
    known_needs: list[str] | None = None,
    active_profile_id: str | None = None,
    previous_lowest_price: int | None = None,
    persona_name: str | None = None,
    pending_question: str | None = None,
    slots: dict | None = None,
    model: str = "gemma4:e4b",
    url: str = "http://localhost:11434",
    use_llm_framing: bool | None = None
) -> dict:
    t_start = time.time()
    t_llm1 = 0.0
    t_tool = 0.0
    t_llm2 = 0.0
    effective_llm_framing = USE_LLM_FRAMING if use_llm_framing is None else use_llm_framing
    
    # 0. PELACAK STATUS DIALOG (DST) & NLU BERBASIS SLOT
    from services.slot_nlu_service import (
        understand_message_with_llm,
        map_activity_to_profile,
        get_catalog_brands
    )
    from core.acts import extract_persona_name
    from services.intent_router import detect_brand, classify_intent

    user_msgs = [m for m in history if m.get("role") == "user"]
    is_initial_turn = (len(user_msgs) <= 1)

    current_slots = dict(slots or {})
    if current_category and not current_slots.get("kategori"):
        current_slots["kategori"] = current_category
    if persona_name and not current_slots.get("persona"):
        current_slots["persona"] = persona_name.lower()

    nlu_res = understand_message_with_llm(
        user_text=user_text,
        pending_question=pending_question,
        current_slots=current_slots,
        model=model
    )
    intent = nlu_res.get("intent", "kebutuhan")
    slots = nlu_res.get("slots", {})
    t_nlu_latency = nlu_res.get("latency_ms", 0.0)

    # Sinkronisasi persona dengan kata asli pelanggan jika ada
    p_detected = extract_persona_name(user_text)
    if p_detected:
        persona_name = p_detected
        slots["persona"] = p_detected.lower()
    elif slots.get("persona"):
        persona_name = slots["persona"].capitalize()

    if slots.get("kategori"):
        current_category = slots["kategori"]

    low = user_text.lower().strip()

    # Kebijakan Dialog 1: SAPAAN (Salam HANYA untuk turn awal, dilarang salam berulang)
    if intent == "sapaan":
        if is_initial_turn:
            reply = "Halo, Kak! Selamat datang di Bobby Computer 😊 Sedang mencari laptop, PC desktop, monitor, atau printer hari ini? Silakan beri tahu kami, kami siap bantu carikan yang paling sesuai kebutuhan!"
            pq = "kebutuhan"
            route = "GREETING"
        else:
            reply = "Halo Kak! Ada spesifikasi atau pilihan perangkat tertentu yang ingin ditanyakan lagi seputar kebutuhan sebelumnya?"
            pq = pending_question or "kebutuhan"
            route = "GREETING_CONTINUATION"
        return {
            "reply": reply,
            "products": [],
            "category": current_category,
            "route": route,
            "active_profile_id": None,
            "persona_name": persona_name,
            "pending_question": pq,
            "slots": slots,
            "metrics": {"total": time.time() - t_start, "nlu_ms": t_nlu_latency}
        }

    # Kebijakan Dialog 2: MEREK-STOK ("Ada asus?", "jual laptop acer?")
    brand_req = slots.get("merek") or detect_brand(user_text)
    if intent in ("merek-stok", "tanya_merek_stok") or (brand_req and any(k in low for k in ["ada ", "jual ", "punya ", "tersedia "])):
        if brand_req:
            slots["merek"] = brand_req

        explicit_cat = slots.get("kategori") or current_category or "laptop"
        matched_products = []
        if catalog and brand_req:
            b_norm = brand_req.lower()
            b_target = "apple" if b_norm == "macbook" else b_norm

            for p in catalog.products:
                p_brand = (p.get("brand") or "").lower()
                p_name = (p.get("nama") or "").lower()
                if b_target in p_brand or b_target in p_name:
                    if explicit_cat and p.get("kategori") != explicit_cat:
                        continue
                    matched_products.append(p)

        brand_disp = brand_req.upper() if brand_req in ("hp", "asus", "msi") else brand_req.capitalize() if brand_req else "tersebut"
        cat_disp = f" {explicit_cat}" if explicit_cat else ""

        if matched_products:
            top_prods = matched_products[:3]
            reply = f"Ya Kak, kami menjual{cat_disp} merek {brand_disp} di Bobby Computer. Berikut beberapa pilihannya di katalog kami:\n\n"
            for idx, p in enumerate(top_prods):
                reply += f"{idx+1}. **{p['nama']}** | Rp{p.get('harga_idr', 0):,}\n  Spesifikasi: {_clean_specs(p)}\n\n"
            reply += f"Apakah ada tipe {brand_disp} tertentu atau rentang budget yang sedang Kakak cari?"
            return {
                "reply": reply.strip(),
                "products": top_prods,
                "category": explicit_cat or current_category,
                "route": "BRAND_STOCK",
                "active_profile_id": None,
                "persona_name": persona_name,
                "pending_question": "aktivitas",
                "slots": slots,
                "metrics": {"total": time.time() - t_start, "nlu_ms": t_nlu_latency}
            }
        else:
            reply = (
                f"Mohon maaf Kak, saat ini kami belum menyediakan produk merek {brand_disp} di Bobby Computer 🙏\n\n"
                "Di katalog kami saat ini tersedia lengkap untuk merek Lenovo, ASUS, HP, dan Acer (serta printer Canon, Epson, dan Brother). "
                "Apakah Kakak berkenan jika kami bantu carikan produk dengan spesifikasi setara dari merek yang tersedia?"
            )
            return {
                "reply": reply.strip(),
                "products": [],
                "category": explicit_cat or current_category,
                "route": "BRAND_STOCK_UNAVAILABLE",
                "active_profile_id": None,
                "persona_name": persona_name,
                "pending_question": "kebutuhan",
                "slots": slots,
                "metrics": {"total": time.time() - t_start, "nlu_ms": t_nlu_latency}
            }

    # Kebijakan Dialog 3: PERSONA CLARIFICATION (Persona terisi tapi aktivitas kosong)
    if slots.get("persona") and not slots.get("aktivitas") and intent in ("kebutuhan", "kategori-saja"):
        p_word = slots.get("persona")
        is_sepuh = any(k in user_text.lower() for k in ["sepuh", "tua", "kakek", "nenek"])
        target_persona_label = f"{p_word} tercinta yang sudah sepuh" if is_sepuh else f"{p_word}"
        cat_disp = current_category or "laptop"
        m_val = slots.get("merek") or ""
        brand_name = m_val.upper() if m_val in ("hp", "asus", "msi") else m_val.capitalize()
        brand_str = f" {brand_name}" if brand_name else ""

        reply = (
            f"Baik Kak, untuk {target_persona_label}, rencananya {cat_disp}{brand_str} ini akan digunakan untuk aktivitas apa saja "
            f"(misalnya menonton video/browsing santai, mengetik dokumen, atau ada pekerjaan khusus) dan berapa perkiraan anggarannya?"
        )
        return {
            "reply": reply,
            "products": [],
            "category": cat_disp,
            "route": "CLARIFY_CATEGORY",
            "active_profile_id": None,
            "persona_name": persona_name,
            "pending_question": "aktivitas",
            "slots": slots,
            "metrics": {"total": time.time() - t_start, "nlu_ms": t_nlu_latency}
        }

    # Kebijakan Dialog 4: KATEGORI-SAJA (tanpa persona dan tanpa aktivitas)
    if intent == "kategori-saja" and not slots.get("aktivitas"):
        cat_name = current_category or "laptop"
        if any(k in low for k in ["desktop", "komputer", "pc", "aio"]): cat_name = "desktop"
        elif any(k in low for k in ["printer", "cetak"]): cat_name = "printer"
        elif any(k in low for k in ["monitor", "layar"]): cat_name = "monitor"

        reply = (
            f"Kami memiliki beragam pilihan {cat_name} berkualitas di Bobby Computer.\n\n"
            f"Agar rekomendasinya pas, boleh kami tahu rencananya {cat_name} ini akan digunakan untuk kebutuhan apa saja "
            f"(misalnya kerja kantor, kuliah, desain grafis, atau game) dan berapa perkiraan anggarannya?"
        )
        return {
            "reply": reply,
            "products": [],
            "category": cat_name,
            "route": "CLARIFY_CATEGORY",
            "active_profile_id": None,
            "persona_name": persona_name,
            "pending_question": "aktivitas",
            "slots": slots,
            "metrics": {"total": time.time() - t_start, "nlu_ms": t_nlu_latency}
        }

    # Kebijakan Dialog 5: META / PROTES ("Kan sudah dibilang buat hiburan", dll)
    if any(k in low for k in ["kan sudah dibilang", "kan buat hiburan", "kan tadi kubilang", "kan sudah kubilang"]):
        p_word = slots.get("persona") or "ibu"
        act_word = slots.get("aktivitas") or "hiburan santai"
        prof_to_use = active_profile_id or map_activity_to_profile(act_word, p_word) or "P11"
        
        ans_str, prods, cat, prof = execute_tool(
            "search_catalog",
            {"profil_id": prof_to_use, "kategori": current_category or "laptop", "brand": slots.get("merek")},
            catalog, current_offered_products or [], user_text, prof_to_use, current_category
        )
        reply = (
            f"Mohon maaf sekali atas kebingungannya tadi ya Kak 🙏 Sesuai yang Kakak sampaikan untuk {p_word} dan kebutuhan {act_word} "
            f"(seperti menonton video dan browsing), laptop yang paling pas dan nyaman tanpa kartu grafis berat yang bising adalah:\n\n"
        )
        for idx, p in enumerate(prods[:2]):
            reply += f"{idx+1}. **{p['nama']}** | Rp{p.get('harga_idr', 0):,}\n  Spesifikasi: {_clean_specs(p)}\n\n"
        reply += "Laptop ini sangat hening, hemat daya, dan bobotnya ringan sehingga nyaman dipakai. Apakah pilihan ini sudah sesuai dengan yang dicari?"
        return {
            "reply": reply.strip(),
            "products": prods[:2],
            "category": current_category or "laptop",
            "route": "META_CORRECTION",
            "active_profile_id": prof_to_use,
            "persona_name": persona_name,
            "pending_question": None,
            "slots": slots,
            "metrics": {"total": time.time() - t_start, "nlu_ms": t_nlu_latency}
        }

    # Kebijakan Dialog 6: LANJUTAN ("Mana?", dll)
    if low in ("mana?", "mana", "mana laptopnya?", "mana produknya?"):
        if slots.get("aktivitas") or active_profile_id:
            prof_to_use = active_profile_id or map_activity_to_profile(slots.get("aktivitas"), slots.get("persona")) or "P11"
            ans_str, prods, cat, prof = execute_tool(
                "search_catalog",
                {"profil_id": prof_to_use, "kategori": current_category or "laptop", "brand": slots.get("merek")},
                catalog, current_offered_products or [], user_text, prof_to_use, current_category
            )
            framed_reply, frame_meta = format_conversational_frame(
                user_text, ans_str, prods, cat or current_category, prof_to_use,
                use_llm=effective_llm_framing, model=model, url=url, persona_name=persona_name
            )
            return {
                "reply": framed_reply.strip(),
                "products": prods,
                "category": cat or current_category,
                "route": "FOLLOWUP_RECOMMENDATION",
                "active_profile_id": prof_to_use,
                "persona_name": persona_name,
                "pending_question": "budget",
                "slots": slots,
                "metrics": {"total": time.time() - t_start, "nlu_ms": t_nlu_latency}
            }
        else:
            reply = "Sebelumnya belum ada perangkat yang dipilih, Kak. Boleh ceritakan perangkat apa yang sedang dicari dan untuk aktivitas apa?"
            return {
                "reply": reply,
                "products": [],
                "category": current_category,
                "route": "CLARIFY_FOLLOWUP",
                "active_profile_id": None,
                "persona_name": persona_name,
                "pending_question": "kebutuhan",
                "slots": slots,
                "metrics": {"total": time.time() - t_start, "nlu_ms": t_nlu_latency}
            }

    # Kelas 3: META ("Dari mana kamu tahu kebutuhanku?", kritik spek kegedean, komplain CS, dll)
    if intent in ("meta", "meta_protes"):
        low = user_text.lower()
        effective_persona = extract_persona_name(user_text) or persona_name
        target_label = f" untuk {effective_persona}" if effective_persona else ""

        # Rujuk produk yang sudah ditampilkan dari state
        target_codes = current_offered_products or shown_products or []
        shown_names = []
        if catalog and target_codes:
            for c in target_codes:
                p_obj = catalog.by_code.get(c)
                if p_obj:
                    shown_names.append(p_obj.get("nama") or c)
        prod_ref = f" ({shown_names[0]})" if shown_names else ""

        # Rujuk kebutuhan yang sudah diketahui dari state
        needs_ref = ""
        if known_needs:
            clean_needs = [n for n in known_needs if n and len(n.split()) <= 6]
            if clean_needs:
                needs_ref = f" seputar {clean_needs[-1]}"

        if any(k in low for k in ["kegedean", "kebesaran", "kemahalan", "ketinggian", "keberatan", "terlalu", "overkill"]):
            reply = (
                f"Betul Kak, mohon maaf jika rekomendasi{prod_ref} sebelumnya spesifikasinya terasa terlalu tinggi atau berlebih{target_label} 🙏\n\n"
                f"Untuk penggunaan santai dan harian (seperti mengetik, browsing, atau menonton video), laptop kelas harian/office biasa tentu sudah sangat cukup dan harganya jauh lebih terjangkau. "
                f"Boleh tahu berapa perkiraan rentang anggaran yang diinginkan agar bisa kami carikan pilihan yang lebih pas dan hemat?"
            )
        elif any(k in low for k in ["kok ditawarin", "kok malah", "aku kan nanya", "aku tadi tanya", "kurang nangkap", "bukan itu maksud"]):
            reply = (
                f"Mohon maaf sekali atas ketergesa-gesaannya tadi ya Kak 🙏 Saya tadi terlalu cepat menyodorkan opsi lain tanpa menjawab langsung keraguan Kakak.\n\n"
                f"Terkait pertanyaan Kakak, betul sekali bahwa spesifikasi laptop{prod_ref} sebelumnya memang kelas berat dan terasa berlebih{target_label}. "
                f"Kami siap membantu menyesuaikan dengan pilihan yang lebih ringan dan pas di budget. Boleh kami tahu aktivitas apa saja yang paling sering dijalankan{target_label}?"
            )
        else:
            if known_needs:
                reply = (
                    f"Saya sebenarnya belum mengetahui kebutuhan pasti Kakak secara mendalam 😊 "
                    f"Catatan yang kami miliki baru{needs_ref}, dan rekomendasi{prod_ref} sebelumnya merupakan rekomendasi umum dari katalog kami.\n\n"
                    f"Boleh ceritakan lebih detail aktivitas harian apa saja yang paling sering dijalankan dan berapa perkiraan budgetnya? Kami siap bantu pilihkan yang paling pas!"
                )
            else:
                reply = (
                    "Saya sebenarnya belum mengetahui kebutuhan pasti Kakak 😊 Pilihan yang kami tampilkan sebelumnya adalah rekomendasi umum dari katalog kami.\n\n"
                    "Boleh ceritakan perangkat ini rencananya akan digunakan untuk aktivitas apa saja dan berapa perkiraan budgetnya? Kami siap membantu carikan yang paling pas!"
                )
        return {
            "reply": reply,
            "products": [],
            "category": current_category,
            "route": "META_CLARIFY",
            "active_profile_id": None,
            "persona_name": effective_persona,
            "metrics": {"total": time.time() - t_start}
        }

    # Kelas 4: DI-LUAR-TOPIK
    if intent == "di-luar-topik":
        low = user_text.lower()
        if any(k in low for k in ["jam buka", "buka jam", "tutup jam"]):
            reply = "Toko Bobby Computer buka setiap hari Senin - Sabtu pukul 09.00 - 20.00 WIB, dan Minggu pukul 10.00 - 17.00 WIB. Ada yang bisa kami bantu terkait perangkat komputer atau laptop?"
        elif any(k in low for k in ["alamat", "lokasi"]):
            reply = "Toko fisik kami beralamat di Jalan Komputer No. 45. Kakak juga bisa berkonsultasi langsung dengan staf toko kami di WhatsApp: 0812-3456-7890."
        elif any(k in low for k in ["cicil", "kredit", "paylater"]):
            reply = "Kami melayani pembayaran tunai, transfer bank, serta cicilan melalui rekanan e-commerce resmi kami. Mau kami bantu carikan spesifikasi perangkatnya terlebih dahulu, Kak?"
        else:
            reply = "Untuk informasi layanan purna jual, toko fisik, atau pertanyaan umum lainnya, Kakak bisa menghubungi staf toko kami di 0812-3456-7890 (WhatsApp). Ada produk laptop atau PC yang sedang dicari hari ini?"
        return {
            "reply": reply,
            "products": [],
            "category": current_category,
            "route": "OUT_OF_DOMAIN",
            "active_profile_id": active_profile_id,
            "metrics": {"total": time.time() - t_start}
        }

    # Kelas 5: LANJUTAN ("cuma itu?", "yang lain?", "lebih murah", "yang ASUS aja")
    if intent == "lanjutan":
        low = user_text.lower()
        # Kasus A: Pertanyaan jumlah / variasi opsi ("cuma itu?", "ada yang lain?")
        if any(k in low for k in ["cuma itu", "hanya itu", "yang lain ada", "ada yang lain", "yang lain?", "ada lagi", "pilihan lain", "opsi lain"]):
            offered_count = len(current_offered_products or [])
            if offered_count == 0:
                reply = (
                    "Sebelumnya belum ada rekomendasi yang kami tampilkan Kak 😊\n\n"
                    "Boleh ceritakan perangkat apa yang sedang Kakak cari, untuk kebutuhan apa, atau berapa perkiraan anggarannya? Kami siap bantu pilihkan yang paling pas!"
                )
            elif offered_count == 1:
                p_code = (current_offered_products or [])[0]
                p_obj = catalog.by_code.get(p_code) if catalog else None
                p_name = p_obj["nama"] if p_obj else "Lenovo Legion Pro 5 16"
                reply = (
                    f"Iya Kak, saat ini di katalog kami baru ada 1 model yang benar-benar memenuhi seluruh spesifikasi keras untuk kebutuhan tersebut secara maksimal ({p_name}).\n\n"
                    "Jika ingin melihat pilihan alternatif dengan harga lebih terjangkau, kita bisa mempertimbangkan laptop dengan RAM 16 GB atau kartu grafis setingkat di bawahnya. Apakah Kakak ingin kami tampilkan pilihan alternatif terdekatnya?"
                )
            else:
                reply = f"Saat ini ada {offered_count} pilihan utama di katalog kami yang paling memenuhi kriteria tersebut. Apakah Kakak ingin melihat opsi merek tertentu, atau mempertimbangkan rentang anggaran yang berbeda?"
            return {
                "reply": reply,
                "products": [],
                "category": current_category,
                "route": "FOLLOWUP_OPTIONS",
                "active_profile_id": active_profile_id,
                "metrics": {"total": time.time() - t_start}
            }

        # Kasus B: "lebih murah" -> Filter harga batas atas eksklusif
        if "lebih murah" in low or "yang murah" in low:
            max_p = (previous_lowest_price - 1) if previous_lowest_price else 10000000
            t0 = time.time()
            ans_str, prods, cat, prof = execute_tool(
                "search_catalog",
                {"query": user_text, "max_harga": max_p, "profil_id": active_profile_id},
                catalog, current_offered_products or [], user_text, active_profile_id, current_category
            )
            t_tool = time.time() - t0
            framed_reply, frame_meta = format_conversational_frame(
                user_text, ans_str, prods, cat or current_category, prof or active_profile_id,
                use_llm=effective_llm_framing, model=model, url=url
            )
            return {
                "reply": framed_reply.strip(),
                "products": prods,
                "category": cat or current_category,
                "route": "FAST_AGENTIC",
                "active_profile_id": prof or active_profile_id,
                "metrics": {"tool": t_tool, "frame": frame_meta, "total": time.time() - t_start}
            }

        # Kasus C: "yang ASUS aja" / penyempit brand / spesifikasi
        t0 = time.time()
        ans_str, prods, cat, prof = execute_tool(
            "search_catalog",
            {"query": user_text, "profil_id": active_profile_id},
            catalog, current_offered_products or [], user_text, active_profile_id, current_category
        )
        t_tool = time.time() - t0
        framed_reply, frame_meta = format_conversational_frame(
            user_text, ans_str, prods, cat or current_category, prof or active_profile_id,
            use_llm=effective_llm_framing, model=model, url=url
        )
        return {
            "reply": framed_reply.strip(),
            "products": prods,
            "category": cat or current_category,
            "route": "FAST_AGENTIC",
            "active_profile_id": prof or active_profile_id,
            "metrics": {"tool": t_tool, "frame": frame_meta, "total": time.time() - t_start}
        }

    # Deteksi pergantian kategori pada pesan kebutuhan/produk baru
    new_cat = None
    low = user_text.lower()
    if any(k in low for k in ["laptop", "notebook"]): new_cat = "laptop"
    elif any(k in low for k in ["desktop", "komputer", "pc", "aio"]): new_cat = "desktop"
    elif any(k in low for k in ["printer", "cetak"]): new_cat = "printer"
    elif any(k in low for k in ["monitor", "layar"]): new_cat = "monitor"

    if new_cat and current_category and new_cat != current_category:
        # Kategori berganti -> reset profil aktif!
        active_profile_id = None
        current_category = new_cat
    elif new_cat and not current_category:
        current_category = new_cat

    if BYPASS_LLM1_ON_RAG:
        prof_arg = map_activity_to_profile(slots.get("aktivitas"), slots.get("persona"))
        if not prof_arg and not should_skip_rag(user_text, catalog):
            from services.knowledge_service import get_usage_requirements
            reqs = get_usage_requirements(user_text)
            pls = reqs.get("profil", [])
            if pls and pls[0].get("tipe") != "di_luar_topik":
                p_ids = [p["profil_id"] for p in pls]
                prof_arg = ",".join(p_ids)

        if prof_arg:
            t0_tool = time.time()
            ans_str, prods, cat, new_profile_id = execute_tool(
                "search_catalog",
                {"profil_id": prof_arg, "kategori": current_category, "brand": slots.get("merek")},
                catalog,
                current_offered_products or [],
                user_text,
                active_profile_id
            )
            t_tool = time.time() - t0_tool
            total = time.time() - t_start
            final_reply, frame_meta = format_conversational_frame(
                user_text, ans_str, prods, cat or current_category, new_profile_id,
                use_llm=effective_llm_framing, model=model, url=url, persona_name=persona_name
            )
            metrics = {
                "llm1": 0.0,
                "tool": t_tool,
                "llm2": 0.0,
                "frame": frame_meta,
                "total": total,
                "bypassed": True
            }
            logger.info(f"[PERF] Bypassed LLM-1 on RAG tool={t_tool:.3f}s frame={frame_meta.get('frame_latency',0):.4f}s total={total:.2f}s")
            return {
                "reply": final_reply.strip(),
                "products": prods,
                "category": cat or current_category,
                "route": "FAST_AGENTIC",
                "tool_calls": [{"name": "search_catalog", "args": {"profil_id": prof_arg}}],
                "active_profile_id": new_profile_id,
                "persona_name": persona_name,
                "pending_question": "budget" if prods else "kebutuhan",
                "slots": slots,
                "metrics": metrics
            }

    # 2. Persiapan Prompt LLM
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in history:
        if m.get("role") in ["user", "assistant"]:
            content = m.get("content") or m.get("text") or ""
            messages.append({"role": m["role"], "content": content})
            
    t_text = user_text.lower()
    if active_profile_id and any(k in t_text for k in ["lebih murah", "yang lain", "kalo", "kalau"]):
        messages[0]["content"] += f"\nPROFIL AKTIF: {active_profile_id}. Sertakan di profil_id!"
        
    messages.append({"role": "user", "content": user_text})
    
    # 3. LLM-1 (Tool Calling)
    t0_llm1 = time.time()
    req_body = {
        "model": model,
        "messages": messages,
        "tools": TOOLS_DEFINITION,
        "stream": False,
        "options": {"num_ctx": 4096, "num_predict": 128},
        "keep_alive": "60m"
    }
    
    try:
        req = urllib.request.Request(f"{url}/api/chat", data=json.dumps(req_body).encode("utf-8"), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as response:
            res_data = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        logger.error(f"Error LLM-1 call: {e}")
        return {"reply": "Maaf, sistem sedang sibuk.", "products": [], "category": None, "route": "AGENTIC", "active_profile_id": active_profile_id}
        
    t_llm1 = time.time() - t0_llm1
    msg = res_data.get("message", {})
    
    if not msg.get("tool_calls"):
        ut_lower = user_text.lower()
        if "laptop" in ut_lower or "buat" in ut_lower or "kebutuhan" in ut_lower or "untuk" in ut_lower:
            msg["tool_calls"] = [{"function": {"name": "search_catalog", "arguments": {"kebutuhan": user_text}}}]

    messages.append(msg)
    
    prods = []
    cat = None
    executed_tools = []
    new_profile_id = active_profile_id
    tool_outputs = []
    
    if msg.get("tool_calls"):
        t0_tool = time.time()
        for tc in msg.get("tool_calls", []):
            func = tc.get("function", {})
            t_name = func.get("name")
            t_args = func.get("arguments", {})
            if slots.get("merek") and isinstance(t_args, dict) and not t_args.get("brand"):
                t_args["brand"] = slots.get("merek")
            ans_str, p_list, t_cat, t_prof = execute_tool(t_name, t_args, catalog, current_offered_products or [], user_text, new_profile_id)
            if p_list: prods.extend(p_list)
            if t_cat: cat = t_cat
            if t_prof: new_profile_id = t_prof
            tool_outputs.append(ans_str)
            executed_tools.append({"name": t_name, "args": t_args})
            messages.append({"role": "tool", "content": ans_str, "tool_call_id": tc.get("id")})
        t_tool = time.time() - t0_tool
        
        # 4. Pembingkaian Percakapan
        combined_facts = "\n\n".join(tool_outputs)
        final_reply, frame_meta = format_conversational_frame(
            user_text, combined_facts, prods, cat, new_profile_id,
            use_llm=effective_llm_framing, model=model, url=url, persona_name=persona_name
        )
        t_llm2 = frame_meta.get("frame_latency", 0.0)
    else:
        final_reply = msg.get("content", "").strip()
        if not final_reply:
            final_reply = "Berikut rekomendasi untuk Anda."
            
    total = time.time() - t_start
    metrics = {"llm1": t_llm1, "tool": t_tool, "llm2": t_llm2, "total": total}
    logger.info(f"[PERF] LLM-1: {t_llm1:.2f}s | Tool: {t_tool:.2f}s | LLM-2: {t_llm2:.2f}s | Total: {total:.2f}s")
    
    return {
        "reply": final_reply.strip(),
        "products": prods,
        "category": cat,
        "route": "AGENTIC",
        "tool_calls": executed_tools,
        "active_profile_id": new_profile_id,
        "persona_name": persona_name,
        "pending_question": "budget" if prods else "kebutuhan",
        "slots": slots,
        "metrics": metrics
    }
