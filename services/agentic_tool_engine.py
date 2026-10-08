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

def parse_budget_from_text(text: str) -> int | None:
    text = text.lower().replace('.', '').replace(',', '')
    m = re.search(r'(\d+)\s*(?:-?an\s*)?juta', text)
    if m: return int(m.group(1)) * 1000000
    return None

def has_tag(product: dict, tag_str: str) -> bool:
    tags = product.get("tags") or []
    return any(tag_str.lower() in str(t).lower() for t in tags)

def _match_legacy_query(p: dict, q: str) -> bool:
    q = q.lower()
    brands = ["acer", "asus", "lenovo", "hp", "nitro", "vivobook", "tuf", "ideapad", "legion", "macbook", "apple", "rog"]
    for b in brands:
        if b in q and b in p["nama"].lower():
            return True
    return q in p["nama"].lower() or q in p.get("kategori", "").lower() or q in str(p.get("tags", "")).lower()

def apply_filters(product: dict, filters: list[dict]) -> tuple[bool, str | None, int, dict]:
    penalty = 0
    failed_reasons = []
    failed_details = []
    unknown_details = []
    report = {"terpenuhi": [], "tidak_terpenuhi": [], "tidak_diketahui": []}
    
    for f in filters:
        field = f["field"]
        op = f["op"]
        val = f["value"]
        mandatory = (f.get("strength") == "hard" or f.get("mandatory") == True)
        
        pval = product.get(field)
        if field == "vram_gb":
            if product.get("gpu_dedicated") == 0:
                pval = 0
            elif product.get("gpu_dedicated") == 1 and pval is None:
                report["tidak_diketahui"].append("VRAM_GB")
                unknown_details.append("VRAM_GB (Dedicated)")
                penalty -= 10
                continue
                
        if pval is None:
            report["tidak_diketahui"].append(field)
            unknown_details.append(field)
            if mandatory:
                failed_reasons.append(field)
            else:
                penalty -= 5
            continue
            
        passed = False
        if op not in (">=", "<=", "==", "="):
            raise ValueError(f"Unknown operator: {op}")
        try:
            if op == ">=": passed = float(pval) >= float(val)
            elif op == "<=": passed = float(pval) <= float(val)
            elif op in ("==", "="): passed = str(pval).lower() == str(val).lower()
        except Exception:
            passed = False
            
        if passed:
            report["terpenuhi"].append(field)
        else:
            report["tidak_terpenuhi"].append(f"{field} {op} {val} (got {pval})")
            if mandatory:
                failed_reasons.append(field)
                failed_details.append(f"{field} {op} {val}")
            else:
                penalty -= int(f.get("penalty", 10))
                
    if failed_reasons:
        return False, f"Belum memenuhi minimum: {', '.join(failed_reasons)}", penalty, report
    return True, None, penalty, report

def should_skip_rag(text: str, catalog: Catalog) -> bool:
    t = text.lower()
    non_intents = ["harga", "cicilan", "jam buka", "lokasi", "diskon", "garansi", "cara bayar", "klaim"]
    greetings = ["halo", "hi", "hai", "p", "terima kasih", "makasih", "apa kabar"]
    if any(f" {k} " in f" {t} " for k in non_intents): return True
    if any(f" {k} " in f" {t} " for k in greetings): return True
    brands = ["acer", "asus", "lenovo", "hp", "nitro", "vivobook", "tuf", "ideapad", "legion", "macbook", "apple", "rog"]
    for p in catalog.products:
        if p["kode"].lower() in t: return True
    for b in brands:
        if re.search(r"\b" + b + r"\b", t) and "buat" not in t and "untuk" not in t and "kebutuhan" not in t:
            return True
    return False

def check_fast_path(text: str, catalog: Catalog, previous_lowest_price: int | None = None) -> tuple[bool, str, dict]:
    t = text.lower().strip()
    greetings = ["halo", "hi", "hai", "p", "terima kasih", "makasih", "apa kabar"]
    if any(t == k or t.startswith(k + " ") for k in greetings):
        return True, "Halo Kak! Ada produk yang sedang dicari hari ini?", {}
        
    brands = ["acer", "asus", "lenovo", "hp", "nitro", "vivobook", "tuf", "ideapad", "legion", "macbook", "apple", "rog"]
    has_brand = any(b in f" {t} " for b in brands)
    
    narrowing_keywords = ["lebih murah", "yang lain", "yang asus", "yang ssd", "yang ram", "kalo", "kalau", "aja"]
    is_narrowing = any(k in t for k in narrowing_keywords)
    
    is_pure_query = (has_brand or "laptop" in t or "komputer" in t or "pc" in t or is_narrowing) and "buat" not in t and "untuk" not in t and "kebutuhan" not in t
    
    if is_pure_query:
        args = {"query": text}
        if "lebih murah" in t or "yang murah" in t:
            args["max_harga"] = (previous_lowest_price - 1) if previous_lowest_price else 10000000
        return True, "Berikut hasil pencarian dari katalog kami:", {"name": "search_catalog", "args": args}
        
    return False, "", {}

def execute_tool(name: str, args: dict, catalog: Catalog, session_offered: list[str] = [], user_text: str = "", active_profile_id: str | None = None, active_category: str | None = None) -> tuple[str, list[dict], str | None, str | None]:
    if name == "search_catalog":
        if not isinstance(args, dict):
            return json.dumps({"status": "error", "message": "Argumen LLM bukan JSON"}), [], None, None
        explicit_cat = args.get("kategori") or active_category
        if explicit_cat == "all": explicit_cat = None
        profil_id = str(args.get("profil_id", ""))
        min_harga = args.get("min_harga")
        max_harga = args.get("max_harga")
        query = str(args.get("query", "")).lower()
        kebutuhan = str(args.get("kebutuhan", ""))
        if not max_harga: max_harga = parse_budget_from_text(user_text)
        
        filters_to_apply = []
        info_profil = ""
        
        if kebutuhan and not should_skip_rag(kebutuhan, catalog):
            from services.knowledge_service import get_usage_requirements
            reqs = get_usage_requirements(kebutuhan)
            pls = reqs.get("profil", [])
            if pls:
                if pls[0].get("tipe") == "di_luar_topik":
                    import os
                    contact = os.getenv("TOKO_CONTACT", "0812-3456-7890 (WhatsApp)")
                    return f"Maaf, pertanyaan Anda di luar konteks rekomendasi spesifikasi. Silakan hubungi staf toko kami di {contact}.", [], explicit_cat, pls[0]["profil_id"]
                if len(pls) == 1:
                    profil_id = pls[0]["profil_id"]
                elif len(pls) >= 2:
                    p1 = get_profile_by_id(pls[0]["profil_id"])
                    p2 = get_profile_by_id(pls[1]["profil_id"])
                    if p1 and p2:
                        filters_to_apply = merge_filters(p1.get("filter", []), p2.get("filter", []))
                        n1 = re.sub(r"^[A-Z]\d{2}\s*[—–\-:]\s*", "", p1.get("judul", "")).strip()
                        n2 = re.sub(r"^[A-Z]\d{2}\s*[—–\-:]\s*", "", p2.get("judul", "")).strip()
                        info_profil = f"Kebutuhan gabungan: {n1} & {n2} (memakai syarat terberat)\n"
                        profil_id = f"{pls[0]['profil_id']},{pls[1]['profil_id']}"
                else:
                    profil_id = active_profile_id
            else:
                profil_id = active_profile_id
                
        if not profil_id and not kebutuhan and active_profile_id:
            profil_id = active_profile_id
            
        if profil_id and not filters_to_apply:
            ids = [x.strip() for x in profil_id.split(",") if x.strip()]
            if len(ids) == 1:
                prof_data = get_profile_by_id(ids[0])
                if prof_data:
                    filters_to_apply = prof_data.get("filter", [])
            elif len(ids) >= 2:
                p1 = get_profile_by_id(ids[0])
                p2 = get_profile_by_id(ids[1])
                if p1 and p2:
                    filters_to_apply = merge_filters(p1.get("filter", []), p2.get("filter", []))
                    n1 = re.sub(r"^[A-Z]\d{2}\s*[—–\-:]\s*", "", p1.get("judul") or ids[0]).strip()
                    n2 = re.sub(r"^[A-Z]\d{2}\s*[—–\-:]\s*", "", p2.get("judul") or ids[1]).strip()
                    info_profil = f"Kebutuhan gabungan: {n1} & {n2} (memakai syarat terberat)\n"
        check_text = (query + " " + user_text).lower()

        # Cek spesifikasi RAM eksplisit (misal "ram 128gb")
        m_ram_req = re.search(r"\bram\s*(\d+)\s*gb\b|\b(\d+)\s*gb\s*ram\b", check_text)
        if m_ram_req:
            req_ram_val = int(m_ram_req.group(1) or m_ram_req.group(2))
            if req_ram_val > 64:
                return "Produk tidak tersedia.", [], explicit_cat, profil_id
            filters_to_apply.append({"field": "ram_gb", "op": ">=", "value": req_ram_val, "strength": "hard"})
        if not explicit_cat:
            cat_keywords = {
                "laptop": ("laptop", "notebook"),
                "desktop": ("desktop", "pc meja", "komputer meja", "tower", "all-in-one", "aio", "pc", "komputer"),
                "printer": ("printer", "cetak", "print", "tinta", "ink tank"),
                "monitor": ("monitor", "layar", "display")
            }
            earliest_idx = 9999
            for cname, kwords in cat_keywords.items():
                for kw in kwords:
                    idx = check_text.find(kw)
                    if idx != -1 and idx < earliest_idx:
                        earliest_idx = idx
                        explicit_cat = cname
                        
        scored_products = []
        relaxed_products = []
        for p in catalog.products:
            if explicit_cat and p["kategori"] != explicit_cat: continue
            p_price = p.get("harga_idr") or 0
            if max_harga and p_price > max_harga: continue
            if min_harga and p_price < min_harga: continue
            
            passed, reason, penalty, report = apply_filters(p, filters_to_apply)
            
            if query:
                if not _match_legacy_query(p, query):
                    if "gaming" in query and not has_tag(p, "gaming"): continue
                    if "desain" in query and not has_tag(p, "desain"): continue
                    if "murah" in query and p_price > 10000000: continue
                    if "144hz" in query and p.get("refresh_hz", 60) < 144: continue
                    continue
                    
            score = 50 + penalty
            if p["kode"] not in session_offered: score += 15
            score += (p.get("cpu_tier") or 0) * 2
            if p.get("gpu_dedicated") == 1: score += 5
            
            p_output = {
                "kode": p["kode"],
                "nama": p["nama"],
                "harga_idr": p.get("harga_idr"),
                "cpu": p.get("cpu"),
                "gpu": p.get("gpu"),
                "vram_gb": p.get("vram_gb"),
                "ram": p.get("ram"),
                "ram_gb": p.get("ram_gb"),
                "ram_type": p.get("ram_type"),
                "storage": p.get("storage"),
                "match_report": report
            }
            if passed: scored_products.append((score, p_output))
            else:
                p_output["alasan_gagal"] = reason
                relaxed_products.append((score, p_output))
                
        if not scored_products and not relaxed_products:
            if "lebih murah" in user_text.lower() or "yang murah" in user_text.lower():
                return "Tidak ada yang lebih murah yang memenuhi kebutuhan ini.", [], explicit_cat, profil_id
            return "Produk tidak tersedia.", [], explicit_cat, profil_id
            
        def _clean_specs(p_item: dict) -> str:
            parts = []
            if p_item.get("cpu"): parts.append(str(p_item["cpu"]))
            if p_item.get("gpu"): parts.append(str(p_item["gpu"]))
            r = p_item.get("ram") or (f"{p_item.get('ram_gb')} GB" + (f" {p_item.get('ram_type')}" if p_item.get("ram_type") else "") if p_item.get("ram_gb") else None)
            if r: parts.append(f"RAM {r}")
            if p_item.get("storage"): parts.append(str(p_item["storage"]))
            return " | ".join(parts) if parts else "Spesifikasi standar"

        scored_products.sort(key=lambda x: x[0], reverse=True)
        # Urut kandidat relaksasi: sedikit kegagalan dulu (naik), skor tiebreaker (turun)
        relaxed_products.sort(
            key=lambda x: (len(x[1].get("match_report", {}).get("tidak_terpenuhi", [])), -x[0])
        )
        top_prods = [p for s, p in scored_products[:3]]
        
        has_filter_checked = bool(filters_to_apply)

        if not top_prods:
            top_relaxed = [p for s, p in relaxed_products[:2]]
            if "lebih murah" in user_text.lower() or "yang murah" in user_text.lower():
                res_str = f"{info_profil}Tidak ada yang lebih murah yang memenuhi kebutuhan ini. Kandidat terdekat:\n"
            else:
                res_str = f"{info_profil}Tidak ada yang memenuhi syarat mutlak. Kandidat terdekat:\n"
            for p in top_relaxed:
                res_str += f"- {p['nama']} | Rp{p.get('harga_idr',0):,} | {_clean_specs(p)}\n  {p.get('alasan_gagal', '')}\n"
            return res_str, top_relaxed, explicit_cat, profil_id
            
        if not has_filter_checked:
            res_str = "Beberapa pilihan produk kami:\n\n"
        else:
            res_str = f"{info_profil}\n"

        for idx, p in enumerate(top_prods):
            mr = p.get("match_report", {})
            fails = mr.get("tidak_terpenuhi", [])
            unk = mr.get('tidak_diketahui', [])
            
            if not has_filter_checked:
                icon_prefix = f"{idx+1}."
            else:
                icon = "✅" if not fails else "⚠️"
                if len(fails) >= 2 or ("alasan_gagal" in p and "Belum memenuhi minimum" in str(p.get("alasan_gagal", ""))):
                    icon = "❌"
                if p.get("alasan_gagal") == "VRAM belum tercantum, mohon konfirmasi ke staf":
                    icon = "⚠️"
                icon_prefix = f"{icon} {idx+1}."
                
            unk_str = f"\n  (Tidak Diketahui: {', '.join(unk)})" if unk else ""
            res_str += f"{icon_prefix} **{p['nama']}** | Rp{p.get('harga_idr',0):,}\n  Spesifikasi: {_clean_specs(p)}{unk_str}\n\n"
        return res_str, top_prods, explicit_cat, profil_id
        
    return json.dumps({"status": "error", "message": f"Tool '{name}' tidak dikenal."}), [], None, None

def merge_filters(f1, f2):
    return f1 + f2

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
    url: str = "http://localhost:11434"
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
                    reply = re.sub(r"\b[PMG]\d{2}\b\s*[—–\-:]?\s*", "", reply)
                    reply = re.sub(r"\b[PMG]\d{2}\b", "", reply)
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
    elif not has_qualified:
        intro = f"Tentu Kak! Berikut beberapa pilihan {cat_label} yang tersedia di Bobby Computer:"
        outro = "Semua unit di atas bergaransi resmi. Silakan beri tahu kami jika ada kebutuhan khusus atau rentang anggaran tertentu ya!"
    else:
        intro = f"Tentu Kak! Berikut rekomendasi {cat_label} yang paling cocok dan sudah memenuhi seluruh syarat kebutuhan Kakak di Bobby Computer:"
        outro = "Semua unit di atas bergaransi resmi dan siap pakai. Apakah ada merek atau tipe tertentu yang ingin Kakak tanyakan lebih detail?"

    framed = f"{intro}\n\n{body}\n\n{outro}".strip()
    framed = re.sub(r"\b[PMG]\d{2}\b\s*[—–\-:]?\s*", "", framed)
    framed = re.sub(r"\b[PMG]\d{2}\b", "", framed)
    framed = re.sub(r"\n{3,}", "\n\n", framed)

    t_frame = time.perf_counter() - t0
    return framed, {"frame_latency": t_frame, "frame_mode": "template"}

def run_agentic_tool(
    user_text: str,
    history: list[dict],
    catalog: Catalog,
    current_category: str | None = None,
    current_offered_products: list[str] | None = None,
    active_profile_id: str | None = None,
    previous_lowest_price: int | None = None,
    persona_name: str | None = None,
    model: str = "gemma4:e4b",
    url: str = "http://localhost:11434",
    use_llm_framing: bool | None = None
) -> dict:
    t_start = time.time()
    t_llm1 = 0.0
    t_tool = 0.0
    t_llm2 = 0.0
    effective_llm_framing = USE_LLM_FRAMING if use_llm_framing is None else use_llm_framing
    
    # 0. ROUTER NIAT SEBELUM PENCARIAN
    from services.intent_router import classify_intent
    from core.acts import extract_persona_name
    intent = classify_intent(user_text, bool(active_profile_id or history))

    # Kelas 1: SAPAAN
    if intent == "sapaan":
        reply = "Halo, Kak! Selamat datang di Bobby Computer 😊 Sedang mencari laptop, PC desktop, monitor, atau printer hari ini? Silakan beri tahu kami, kami siap bantu carikan yang paling sesuai kebutuhan!"
        return {
            "reply": reply,
            "products": [],
            "category": current_category,
            "route": "GREETING",
            "active_profile_id": None,
            "persona_name": persona_name,
            "metrics": {"total": time.time() - t_start}
        }

    # Kelas 2: KATEGORI-SAJA ("laptop", "ada laptop?", "desktop", dll)
    if intent == "kategori-saja":
        low = user_text.lower()
        cat_name = current_category or "laptop"
        if any(k in low for k in ["desktop", "komputer", "pc", "aio"]): cat_name = "desktop"
        elif any(k in low for k in ["printer", "cetak"]): cat_name = "printer"
        elif any(k in low for k in ["monitor", "layar"]): cat_name = "monitor"

        p_name = extract_persona_name(user_text) or persona_name

        if p_name:
            reply = (
                f"Tentu ada, Kak! Kami memiliki beragam pilihan {cat_name} yang cocok dan nyaman untuk {p_name} di toko kami.\n\n"
                f"Agar rekomendasinya pas, boleh kami tahu rencananya {cat_name} ini akan digunakan oleh {p_name} untuk aktivitas apa saja "
                f"(misalnya menonton video/browsing santai, mengetik dokumen, atau ada pekerjaan khusus) dan berapa perkiraan anggarannya?"
            )
        else:
            reply = (
                f"Tentu ada, Kak! Kami memiliki beragam pilihan {cat_name} berkualitas di toko kami.\n\n"
                f"Agar rekomendasinya pas, boleh kami tahu rencananya {cat_name} ini akan digunakan untuk kebutuhan apa saja "
                f"(misalnya kerja kantor, kuliah, desain grafis, atau game) dan berapa perkiraan anggarannya?"
            )
        return {
            "reply": reply,
            "products": [],
            "category": cat_name,
            "route": "CLARIFY_CATEGORY",
            "active_profile_id": None,
            "persona_name": p_name,
            "metrics": {"total": time.time() - t_start}
        }

    # Kelas 3: META ("Dari mana kamu tahu kebutuhanku?", kritik spek kegedean, komplain CS, dll)
    if intent == "meta":
        low = user_text.lower()
        effective_persona = extract_persona_name(user_text) or persona_name
        target_label = f" untuk {effective_persona}" if effective_persona else ""

        if any(k in low for k in ["kegedean", "kebesaran", "kemahalan", "ketinggian", "keberatan", "terlalu", "overkill"]):
            reply = (
                f"Betul Kak, mohon maaf jika rekomendasi sebelumnya spesifikasinya terasa terlalu tinggi atau berlebih{target_label} 🙏\n\n"
                f"Untuk penggunaan santai dan harian (seperti mengetik, browsing, atau menonton video), laptop kelas harian/office biasa tentu sudah sangat cukup dan harganya jauh lebih terjangkau. "
                f"Boleh tahu berapa perkiraan rentang anggaran yang diinginkan agar bisa kami carikan pilihan yang lebih pas dan hemat?"
            )
        elif any(k in low for k in ["kok ditawarin", "kok malah", "aku kan nanya", "aku tadi tanya", "kurang nangkap", "bukan itu maksud"]):
            reply = (
                f"Mohon maaf sekali atas ketergesa-gesaannya tadi ya Kak 🙏 Saya tadi terlalu cepat menyodorkan opsi lain tanpa menjawab langsung keraguan Kakak.\n\n"
                f"Terkait pertanyaan Kakak, betul sekali bahwa spesifikasi laptop sebelumnya memang kelas berat dan terasa berlebih{target_label}. "
                f"Kami siap membantu menyesuaikan dengan pilihan yang lebih ringan dan pas di budget. Boleh kami tahu aktivitas apa saja yang paling sering dijalankan{target_label}?"
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
            if offered_count <= 1:
                reply = (
                    "Iya Kak, saat ini di katalog kami baru ada 1 model yang benar-benar memenuhi seluruh spesifikasi keras untuk kebutuhan tersebut secara maksimal (yaitu Lenovo Legion Pro 5 16).\n\n"
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

    # 1.5 Pangkas LLM-1 untuk peruntukan (jika BYPASS_LLM1_ON_RAG aktif dan retrieval lolos ambang)
    if BYPASS_LLM1_ON_RAG and not should_skip_rag(user_text, catalog):
        from services.knowledge_service import get_usage_requirements
        reqs = get_usage_requirements(user_text)
        pls = reqs.get("profil", [])
        if pls and pls[0].get("tipe") != "di_luar_topik":
            p_ids = [p["profil_id"] for p in pls]
            prof_arg = ",".join(p_ids)
            t0_tool = time.time()
            ans_str, prods, cat, new_profile_id = execute_tool(
                "search_catalog",
                {"profil_id": prof_arg, "kategori": current_category},
                catalog,
                current_offered_products or [],
                user_text,
                active_profile_id
            )
            t_tool = time.time() - t0_tool
            total = time.time() - t_start
            final_reply, frame_meta = format_conversational_frame(
                user_text, ans_str, prods, cat or current_category, new_profile_id,
                use_llm=effective_llm_framing, model=model, url=url
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
            use_llm=effective_llm_framing, model=model, url=url
        )
        t_llm2 = frame_meta.get("frame_latency", 0.0)
    else:
        final_reply = msg.get("content", "").strip()
        if not final_reply:
            final_reply = "Berikut rekomendasi untuk Anda."
            
    total = time.time() - t_start
    metrics = {"llm1": t_llm1, "tool": t_tool, "llm2": t_llm2, "total": total}
    logger.info(f"[PERF] LLM-1: {t_llm1:.2f}s | Tool: {t_tool:.2f}s | LLM-2: {t_llm2:.2f}s | Total: {total:.2f}s")
    
    return {"reply": final_reply.strip(), "products": prods, "category": cat, "route": "AGENTIC", "tool_calls": executed_tools, "active_profile_id": new_profile_id, "metrics": metrics}
