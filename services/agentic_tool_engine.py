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
                        info_profil = f"Kebutuhan gabungan: {p1['judul']} & {p2['judul']}. "
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
                    n1 = p1.get("judul") or ids[0]
                    n2 = p2.get("judul") or ids[1]
                    info_profil = f"Kebutuhan gabungan: {n1} + {n2}, memakai syarat terberat\n"

        
        check_text = (query + " " + user_text).lower()
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
            
        scored_products.sort(key=lambda x: x[0], reverse=True)
        # Urut kandidat relaksasi: sedikit kegagalan dulu (naik), skor tiebreaker (turun)
        relaxed_products.sort(
            key=lambda x: (len(x[1].get("match_report", {}).get("tidak_terpenuhi", [])), -x[0])
        )
        top_prods = [p for s, p in scored_products[:3]]
        
        if not top_prods:
            top_relaxed = [p for s, p in relaxed_products[:2]]
            if "lebih murah" in user_text.lower() or "yang murah" in user_text.lower():
                res_str = f"{info_profil}Tidak ada yang lebih murah yang memenuhi kebutuhan ini. Kandidat terdekat:\n"
            else:
                res_str = f"{info_profil}Tidak ada yang memenuhi syarat mutlak. Kandidat terdekat:\n"
            for p in top_relaxed:
                mr = p.get("match_report", {})
                res_str += f"- {p['nama']} | Rp{p.get('harga_idr',0):,} | {p.get('cpu')} {p.get('gpu')}\n  {p.get('alasan_gagal', '')}\n"
            return res_str, top_relaxed, explicit_cat, profil_id
            
        res_str = f"{info_profil}\n"
        for idx, p in enumerate(top_prods):
            mr = p.get("match_report", {})
            fails = mr.get("tidak_terpenuhi", [])
            unk = mr.get('tidak_diketahui', [])
            
            icon = "✅" if not fails else "⚠️"
            if len(fails) >= 2 or ("alasan_gagal" in p and "Belum memenuhi minimum" in str(p.get("alasan_gagal", ""))):
                icon = "❌"
            if p.get("alasan_gagal") == "VRAM belum tercantum, mohon konfirmasi ke staf":
                icon = "⚠️"
                
            unk_str = f"\n  (Tidak Diketahui: {', '.join(unk)})" if unk else ""
            res_str += f"{icon} {idx+1}. **{p['nama']}** | Rp{p.get('harga_idr',0):,}\n  Spesifikasi: {p.get('cpu')} | {p.get('gpu')} | {p.get('ram')} | {p.get('storage')}{unk_str}\n\n"
        return res_str, top_prods, explicit_cat, profil_id
        
    return json.dumps({"status": "error", "message": f"Tool '{name}' tidak dikenal."}), [], None, None

def merge_filters(f1, f2):
    return f1 + f2

BYPASS_LLM1_ON_RAG = True

def run_agentic_tool(
    user_text: str,
    history: list[dict],
    catalog: Catalog,
    current_category: str | None = None,
    current_offered_products: list[str] | None = None,
    active_profile_id: str | None = None,
    previous_lowest_price: int | None = None,
    model: str = "gemma4:e4b",
    url: str = "http://localhost:11434"
) -> dict:
    t_start = time.time()
    t_llm1 = 0.0
    t_tool = 0.0
    t_llm2 = 0.0
    
    # 1. Jalur Cepat (Fast Path)
    is_fast, fast_reply, fast_tool = check_fast_path(user_text, catalog, previous_lowest_price)
    if is_fast:
        t_llm1 = 0
        ans_str = ""
        prods = []
        cat = None
        prof = None
        if fast_tool:
            t0 = time.time()
            ans_str, prods, cat, prof = execute_tool(fast_tool["name"], fast_tool["args"], catalog, current_offered_products or [], user_text, active_profile_id)
            t_tool = time.time() - t0
        t_llm2 = 0
        final_reply = fast_reply + "\n\n" + ans_str if ans_str else fast_reply
        total = time.time() - t_start
        metrics = {"llm1": t_llm1, "tool": t_tool, "llm2": t_llm2, "total": total}
        logger.info(f"[PERF] FastPath total={total:.2f}s")
        return {"reply": final_reply.strip(), "products": prods, "category": cat, "route": "FAST_AGENTIC", "active_profile_id": prof, "metrics": metrics}

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
        
        # 4. LLM-2 (Generating Intro)
        t0_llm2 = time.time()
        req_body["messages"] = messages
        try:
            req = urllib.request.Request(f"{url}/api/chat", data=json.dumps(req_body).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as response:
                res2 = json.loads(response.read().decode("utf-8"))
                final_intro = res2.get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.error(f"Error LLM-2 call: {e}")
            final_intro = "Berikut adalah rekomendasi produk untuk Anda:"
        t_llm2 = time.time() - t0_llm2
        
        final_reply = final_intro + "\n\n" + "\n\n".join(tool_outputs)
    else:
        final_reply = msg.get("content", "").strip()
        if not final_reply:
            final_reply = "Berikut rekomendasi untuk Anda."
            
    total = time.time() - t_start
    metrics = {"llm1": t_llm1, "tool": t_tool, "llm2": t_llm2, "total": total}
    logger.info(f"[PERF] LLM-1: {t_llm1:.2f}s | Tool: {t_tool:.2f}s | LLM-2: {t_llm2:.2f}s | Total: {total:.2f}s")
    
    return {"reply": final_reply.strip(), "products": prods, "category": cat, "route": "AGENTIC", "tool_calls": executed_tools, "active_profile_id": new_profile_id, "metrics": metrics}
