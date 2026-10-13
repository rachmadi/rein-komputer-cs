import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_query = """            if query:
                if not explicit_cat and not _match_legacy_query(p, query):
                    if "gaming" in query and not has_tag(p, "gaming"): continue
                    if "desain" in query and not has_tag(p, "desain"): continue
                    if "murah" in query and p_price > 10000000: continue
                    if "144hz" in query and p.get("refresh_hz", 60) < 144: continue"""

new_query = """            if query:
                if not _match_legacy_query(p, query):
                    if "gaming" in query and not has_tag(p, "gaming"): continue
                    if "desain" in query and not has_tag(p, "desain"): continue
                    if "murah" in query and p_price > 10000000: continue
                    if "144hz" in query and p.get("refresh_hz", 60) < 144: continue
                    continue"""

text = text.replace(old_query, new_query)

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)

with open("d:/RAG/tests/test_vram_admin.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('assert report["tidak_terpenuhi"]', 'assert report["tidak_diketahui"]')

with open("d:/RAG/tests/test_vram_admin.py", "w", encoding="utf-8") as f:
    f.write(text)
