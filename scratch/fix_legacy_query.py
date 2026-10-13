import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_match = """def _match_legacy_query(product: dict, query: str) -> bool:
    q = query.lower()
    return q in product["nama"].lower() or q in product["kategori"].lower() or q in str(product.get("brand", "")).lower()"""

new_match = """def _match_legacy_query(product: dict, query: str) -> bool:
    q = query.lower()
    brands = ["acer", "asus", "lenovo", "hp", "nitro", "vivobook", "tuf", "ideapad", "legion", "macbook", "apple", "rog"]
    for b in brands:
        if b in q and b in (product["nama"].lower() + " " + str(product.get("brand", "")).lower()):
            return True
    return q in product["nama"].lower() or q in product["kategori"].lower() or q in str(product.get("brand", "")).lower()"""

text = text.replace(old_match, new_match)

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
