import sys
import re

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_loop = """        if not top_prods:
            top_relaxed = [p for s, p in relaxed_products[:2]]
            res_str = f"{info_profil}⚠️ Tidak ada yang memenuhi syarat mutlak. Kandidat terdekat:\\n"
            for p in top_relaxed:
                mr = p.get("match_report", {})
                res_str += f"- {p['nama']} | Rp{p.get('harga_idr',0):,} | {p.get('cpu')} {p.get('gpu')}\\n  {p.get('alasan_gagal', '')}\\n"
            return res_str, top_relaxed, explicit_cat, profil_id
            
        res_str = f"{info_profil}\\n✅ Berikut rekomendasi yang memenuhi syarat:\\n"
        for idx, p in enumerate(top_prods):
            mr = p.get("match_report", {})
            unk = mr.get('tidak_diketahui', [])
            unk_str = f"\\n  (Tidak Diketahui: {', '.join(unk)})" if unk else ""
            peringatan = f"\\n  ⚠️  {p['alasan_gagal']}" if "alasan_gagal" in p else ""
            res_str += f"{idx+1}. **{p['nama']}** | Rp{p.get('harga_idr',0):,}\\n  Spesifikasi: {p.get('cpu')} | {p.get('gpu')} | {p.get('ram')} | {p.get('storage')}{unk_str}{peringatan}\\n\\n"
        return res_str, top_prods, explicit_cat, profil_id"""

new_loop = """        def format_product_item(idx_str, p):
            mr = p.get("match_report", {})
            fails = mr.get("tidak_terpenuhi", [])
            unk = mr.get('tidak_diketahui', [])
            icon = "✅" if not fails else "⚠️"
            if len(fails) >= 2 or "alasan_gagal" in p and "Belum memenuhi minimum" in str(p.get("alasan_gagal", "")):
                icon = "❌"
            if p.get("alasan_gagal") == "VRAM belum tercantum, mohon konfirmasi ke staf":
                icon = "⚠️"
                
            unk_str = f"\\n  (Tidak Diketahui: {', '.join(unk)})" if unk else ""
            peringatan = ""
            if fails:
                peringatan += f"\\n  {icon} Kekurangan: {', '.join(fails)}"
            if "alasan_gagal" in p and p["alasan_gagal"] != "VRAM belum tercantum, mohon konfirmasi ke staf":
                 pass # sudah tercover di fails
            elif "alasan_gagal" in p:
                 peringatan += f"\\n  {icon} {p['alasan_gagal']}"
                 
            return f"{idx_str} {icon} **{p['nama']}** | Rp{p.get('harga_idr',0):,}\\n  Spesifikasi: {p.get('cpu')} | {p.get('gpu')} | {p.get('ram')} | {p.get('storage')}{unk_str}{peringatan}\\n\\n"

        if not top_prods:
            top_relaxed = [p for s, p in relaxed_products[:2]]
            res_str = f"{info_profil}⚠️ Tidak ada produk ASUS (atau merek terkait) yang memenuhi syarat mutlak. Kandidat terdekat:\\n" if query and "asus" in query.lower() else f"{info_profil}⚠️ Tidak ada yang memenuhi syarat mutlak. Kandidat terdekat:\\n"
            for p in top_relaxed:
                res_str += format_product_item("-", p)
            return res_str, top_relaxed, explicit_cat, profil_id
            
        res_str = f"{info_profil}\\nBerikut rekomendasi yang ditemukan:\\n"
        for idx, p in enumerate(top_prods):
            res_str += format_product_item(f"{idx+1}.", p)
        return res_str, top_prods, explicit_cat, profil_id"""

text = text.replace(old_loop, new_loop)

# Also fix the sorting logic for `relaxed_products`
old_sort = """        scored_products.sort(key=lambda x: x[0], reverse=True)
        relaxed_products.sort(key=lambda x: x[0], reverse=True)"""

new_sort = """        scored_products.sort(key=lambda x: x[0], reverse=True)
        # Sort relaxed_products by: 
        # 1. number of failed constraints (len(tidak_terpenuhi)) ASCENDING
        # 2. score DESCENDING
        relaxed_products.sort(key=lambda x: (len(x[1].get("match_report", {}).get("tidak_terpenuhi", [])), -x[0]))"""

text = text.replace(old_sort, new_sort)

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
