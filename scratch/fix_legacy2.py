import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_match = """def _match_legacy_query(p: dict, q: str) -> bool:
    q = q.lower()
    return q in p["nama"].lower() or q in p.get("kategori", "").lower() or q in str(p.get("tags", "")).lower()"""

new_match = """def _match_legacy_query(p: dict, q: str) -> bool:
    q = q.lower()
    brands = ["acer", "asus", "lenovo", "hp", "nitro", "vivobook", "tuf", "ideapad", "legion", "macbook", "apple", "rog"]
    for b in brands:
        if b in q and b in p["nama"].lower():
            return True
    return q in p["nama"].lower() or q in p.get("kategori", "").lower() or q in str(p.get("tags", "")).lower()"""

text = text.replace(old_match, new_match)

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
