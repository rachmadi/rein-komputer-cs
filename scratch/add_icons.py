import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_res = """        res_str = f"{info_profil}\\n"
        for idx, p in enumerate(top_prods):
            mr = p.get("match_report", {})
            unk = mr.get('tidak_diketahui', [])
            unk_str = f"\\n  (Tidak Diketahui: {', '.join(unk)})" if unk else ""
            res_str += f"{idx+1}. **{p['nama']}** | Rp{p.get('harga_idr',0):,}\\n  Spesifikasi: {p.get('cpu')} | {p.get('gpu')} | {p.get('ram')} | {p.get('storage')}{unk_str}\\n\\n"
        return res_str, top_prods, explicit_cat, profil_id"""

new_res = """        res_str = f"{info_profil}\\n"
        for idx, p in enumerate(top_prods):
            mr = p.get("match_report", {})
            fails = mr.get("tidak_terpenuhi", [])
            unk = mr.get('tidak_diketahui', [])
            
            icon = "✅" if not fails else "⚠️"
            if len(fails) >= 2 or ("alasan_gagal" in p and "Belum memenuhi minimum" in str(p.get("alasan_gagal", ""))):
                icon = "❌"
            if p.get("alasan_gagal") == "VRAM belum tercantum, mohon konfirmasi ke staf":
                icon = "⚠️"
                
            unk_str = f"\\n  (Tidak Diketahui: {', '.join(unk)})" if unk else ""
            res_str += f"{icon} {idx+1}. **{p['nama']}** | Rp{p.get('harga_idr',0):,}\\n  Spesifikasi: {p.get('cpu')} | {p.get('gpu')} | {p.get('ram')} | {p.get('storage')}{unk_str}\\n\\n"
        return res_str, top_prods, explicit_cat, profil_id"""

text = text.replace(old_res, new_res)

old_fail = """        if not top_prods:
            if not relaxed_products:
                return "Maaf, produk tidak tersedia berdasarkan kriteria yang diberikan.", [], explicit_cat, profil_id
            top_relaxed = [p for s, p in relaxed_products[:2]]
            res_str = f"{info_profil}Tidak ada yang memenuhi syarat mutlak. Kandidat terdekat:\\n"
            for p in top_relaxed:
                mr = p.get("match_report", {})
                res_str += f"- {p['nama']} | Rp{p.get('harga_idr',0):,} | {p.get('cpu')} {p.get('gpu')}\\n  {p.get('alasan_gagal', '')}\\n"
            return res_str, top_relaxed, explicit_cat, profil_id"""

new_fail = """        if not top_prods:
            if not relaxed_products:
                return "Maaf, produk tidak tersedia berdasarkan kriteria yang diberikan.", [], explicit_cat, profil_id
            top_relaxed = [p for s, p in relaxed_products[:2]]
            res_str = f"{info_profil}Tidak ada yang memenuhi syarat mutlak. Kandidat terdekat:\\n"
            for p in top_relaxed:
                mr = p.get("match_report", {})
                fails = mr.get("tidak_terpenuhi", [])
                unk = mr.get('tidak_diketahui', [])
                
                icon = "✅" if not fails else "⚠️"
                if len(fails) >= 2 or ("alasan_gagal" in p and "Belum memenuhi minimum" in str(p.get("alasan_gagal", ""))):
                    icon = "❌"
                if p.get("alasan_gagal") == "VRAM belum tercantum, mohon konfirmasi ke staf":
                    icon = "⚠️"
                    
                res_str += f"{icon} - **{p['nama']}** | Rp{p.get('harga_idr',0):,} | {p.get('cpu')} {p.get('gpu')}\\n  {p.get('alasan_gagal', '')}\\n"
            return res_str, top_relaxed, explicit_cat, profil_id"""

text = text.replace(old_fail, new_fail)

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
