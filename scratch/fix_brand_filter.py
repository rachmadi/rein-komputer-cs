import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_query_logic = """            if query:
                if not _match_legacy_query(p, query):
                    if "gaming" in query and not has_tag(p, "gaming"): continue
                    if "desain" in query and not has_tag(p, "desain"): continue
                    if "murah" in query and p_price > 10000000: continue
                    if "144hz" in query and p.get("refresh_hz", 60) < 144: continue"""

new_query_logic = """            if query:
                brands_list = ["acer", "asus", "lenovo", "hp", "nitro", "vivobook", "tuf", "ideapad", "legion", "macbook", "apple", "rog"]
                brand_in_query = [b for b in brands_list if b in query.lower().split()]
                if brand_in_query:
                    if not any(b in p["nama"].lower() for b in brand_in_query):
                        continue
                if not _match_legacy_query(p, query):
                    if "gaming" in query and not has_tag(p, "gaming"): continue
                    if "desain" in query and not has_tag(p, "desain"): continue
                    if "murah" in query and p_price > 10000000: continue
                    if "144hz" in query and p.get("refresh_hz", 60) < 144: continue"""

text = text.replace(old_query_logic, new_query_logic)

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
