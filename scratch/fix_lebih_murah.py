import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_preamble = """        if not top_prods:
            if not top_relaxed:
                return "Produk tidak tersedia.", [], explicit_cat, profil_id
            res_str = "Tidak ada yang memenuhi syarat mutlak. Kandidat terdekat:\n"
            for p in top_relaxed:"""

new_preamble = """        if not top_prods:
            if not top_relaxed:
                if "lebih murah" in user_text.lower() or "yang murah" in user_text.lower():
                    return "Tidak ada yang lebih murah yang memenuhi kebutuhan ini.", [], explicit_cat, profil_id
                return "Produk tidak tersedia.", [], explicit_cat, profil_id
            
            if "lebih murah" in user_text.lower() or "yang murah" in user_text.lower():
                res_str = "Tidak ada yang lebih murah yang memenuhi kebutuhan ini. Kandidat terdekat:\\n"
            else:
                res_str = "Tidak ada yang memenuhi syarat mutlak. Kandidat terdekat:\\n"
                
            for p in top_relaxed:"""

text = text.replace(old_preamble, new_preamble.replace("\\n", "\n"))

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
