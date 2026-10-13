import sys
import re

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. op == "="
text = text.replace('elif op == "==": passed = str(pval).lower() == str(val).lower()', 'elif op in ("==", "="): passed = str(pval).lower() == str(val).lower()')

# 2 & 3. RAM/Storage parsing + None fix
old_query_logic = """        scored_products = []
        relaxed_products = []
        for p in catalog.products:"""
new_query_logic = """        search_text = (query + " " + user_text).lower()
        req_ram = None
        req_storage = None
        
        ram_match = re.search(r'ram[^\\d]*(\\d{1,3})\\s*(gb)?', search_text)
        if ram_match: req_ram = int(ram_match.group(1))
        
        storage_match = re.search(r'(ssd|hdd|storage|memori)[^\\d]*(\\d{1,4})\\s*(gb|tb)?', search_text)
        if storage_match:
            val = int(storage_match.group(2))
            if storage_match.group(3) == 'tb' or val < 10: val *= 1000
            req_storage = val

        scored_products = []
        relaxed_products = []
        for p in catalog.products:
            if req_ram and (p.get("ram_gb") or 0) < req_ram: continue
            if req_storage and (p.get("storage_ssd_gb") or 0) < req_storage: continue
"""
text = text.replace(old_query_logic, new_query_logic)

# 4. empty resp
old_empty = """        if not top_prods:
            top_relaxed = [p for s, p in relaxed_products[:2]]
            res_str = f"{info_profil}⚠️ Tidak ada produk ASUS (atau merek terkait) yang memenuhi syarat mutlak. Kandidat terdekat:\\n" if query and "asus" in query.lower() else f"{info_profil}⚠️ Tidak ada yang memenuhi syarat mutlak. Kandidat terdekat:\\n"
            for p in top_relaxed:
                res_str += format_product_item("-", p)
            return res_str, top_relaxed, explicit_cat, profil_id"""
new_empty = """        if not top_prods:
            if not relaxed_products:
                return "Maaf, produk tidak tersedia berdasarkan kriteria yang diberikan.", [], explicit_cat, profil_id
            top_relaxed = [p for s, p in relaxed_products[:2]]
            res_str = f"{info_profil}⚠️ Tidak ada produk ASUS (atau merek terkait) yang memenuhi syarat mutlak. Kandidat terdekat:\\n" if query and "asus" in query.lower() else f"{info_profil}⚠️ Tidak ada yang memenuhi syarat mutlak. Kandidat terdekat:\\n"
            for p in top_relaxed:
                res_str += format_product_item("-", p)
            return res_str, top_relaxed, explicit_cat, profil_id"""
text = text.replace(old_empty, new_empty)

# 5. format icon
old_format = """        def format_product_item(idx_str, p):
            mr = p.get("match_report", {})
            fails = mr.get("tidak_terpenuhi", [])
            unk = mr.get('tidak_diketahui', [])
            icon = "✅" if not fails else "⚠️"
            if len(fails) >= 2 or "alasan_gagal" in p and "Belum memenuhi minimum" in str(p.get("alasan_gagal", "")):
                icon = "❌"
            if p.get("alasan_gagal") == "VRAM belum tercantum, mohon konfirmasi ke staf":
                icon = "⚠️"
"""
new_format = """        def format_product_item(idx_str, p):
            mr = p.get("match_report", {})
            fails = mr.get("tidak_terpenuhi", [])
            unk = mr.get('tidak_diketahui', [])
            icon = "✅" if not fails and not unk else "⚠️"
            if len(fails) >= 2 or ("alasan_gagal" in p and "Belum memenuhi minimum" in str(p.get("alasan_gagal", ""))):
                icon = "❌"
            if p.get("alasan_gagal") == "VRAM belum tercantum, mohon konfirmasi ke staf":
                icon = "⚠️"
"""
text = text.replace(old_format, new_format)

# 6. bypass llm args
text = text.replace('args = {"kebutuhan": user_text}', 'args = {"query": user_text}')

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
