import re

with open(r"d:\RAG\services\agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_code = """        for idx, p in enumerate(top_prods):
            mr = p.get("match_report", {})
            unk = mr.get('tidak_diketahui', [])
            unk_str = f"\\n  (Tidak Diketahui: {', '.join(unk)})" if unk else ""
            res_str += f"{idx+1}. **{p['nama']}** | Rp{p.get('harga_idr',0):,}\\n  Spesifikasi: {p.get('cpu')} | {p.get('gpu')} | {p.get('ram')} | {p.get('storage')}{unk_str}\\n\\n\""""

new_code = """        for idx, p in enumerate(top_prods):
            mr = p.get("match_report", {})
            unk = mr.get('tidak_diketahui', [])
            unk_str = f"\\n  (Tidak Diketahui: {', '.join(unk)})" if unk else ""
            peringatan = f"\\n  ⚠️ {p['alasan_gagal']}" if "alasan_gagal" in p else ""
            res_str += f"{idx+1}. **{p['nama']}** | Rp{p.get('harga_idr',0):,}\\n  Spesifikasi: {p.get('cpu')} | {p.get('gpu')} | {p.get('ram')} | {p.get('storage')}{unk_str}{peringatan}\\n\\n\""""

text = text.replace(old_code, new_code)

with open(r"d:\RAG\services\agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
