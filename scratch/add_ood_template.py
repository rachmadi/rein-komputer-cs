import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_block = """            pls = reqs.get("profil", [])
            if pls:
                if len(pls) == 1:
                    profil_id = pls[0]["profil_id"]"""

new_block = """            pls = reqs.get("profil", [])
            if pls:
                if pls[0].get("tipe") == "di_luar_topik":
                    import os
                    contact = os.getenv("TOKO_CONTACT", "0812-3456-7890 (WhatsApp)")
                    return f"Maaf, pertanyaan Anda di luar konteks rekomendasi spesifikasi. Silakan hubungi staf toko kami di {contact}.", [], explicit_cat, pls[0]["profil_id"]
                if len(pls) == 1:
                    profil_id = pls[0]["profil_id"]"""

text = text.replace(old_block, new_block)

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
