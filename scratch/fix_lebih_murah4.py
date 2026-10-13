import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_str = '            res_str = f"{info_profil}Tidak ada yang memenuhi syarat mutlak. Kandidat terdekat:\\n"'
new_str = '''            if "lebih murah" in user_text.lower() or "yang murah" in user_text.lower():
                res_str = f"{info_profil}Tidak ada yang lebih murah yang memenuhi kebutuhan ini. Kandidat terdekat:\\n"
            else:
                res_str = f"{info_profil}Tidak ada yang memenuhi syarat mutlak. Kandidat terdekat:\\n"'''

text = text.replace(old_str, new_str)

old_str2 = '        if not scored_products and not relaxed_products:\n            return "Produk tidak tersedia.", [], explicit_cat, profil_id'
new_str2 = '''        if not scored_products and not relaxed_products:
            if "lebih murah" in user_text.lower() or "yang murah" in user_text.lower():
                return "Tidak ada yang lebih murah yang memenuhi kebutuhan ini.", [], explicit_cat, profil_id
            return "Produk tidak tersedia.", [], explicit_cat, profil_id'''

text = text.replace(old_str2, new_str2)

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
