import re

with open(r"d:\RAG\services\agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_code = """        top_prods = [p for s, p in scored_products[:3]]
        
        if not top_prods:"""

new_code = """        top_prods = [p for s, p in scored_products[:3]]
        
        # Rule 2: GPU dedicated dgn VRAM NULL muncul di bawah bila < 3
        if len(top_prods) < 3:
            for s, p in relaxed_products:
                if p.get("match_report", {}).get("peringatan_khusus") == "VRAM belum tercantum, mohon konfirmasi ke staf":
                    if p not in top_prods:
                        # Hapus alasan_gagal agar tidak tampil seperti produk gagal biasa, ganti label
                        p["alasan_gagal"] = p["match_report"]["peringatan_khusus"]
                        top_prods.append(p)
                    if len(top_prods) >= 3:
                        break
        
        if not top_prods:"""

text = text.replace(old_code, new_code)

with open(r"d:\RAG\services\agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
