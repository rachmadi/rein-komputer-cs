import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

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

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
