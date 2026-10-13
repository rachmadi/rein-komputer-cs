import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

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

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
