import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_cp = """    if is_pure_query:
        return True, "Berikut hasil pencarian dari katalog kami:", {"name": "search_catalog", "args": {"query": text}}
        
    return False, "", {}"""

new_cp = """    if is_pure_query:
        args = {"query": text}
        if current_category: args["kategori"] = current_category
        if any(k in t for k in ["lebih murah", "yang murah"]):
            if previous_lowest_price: args["max_harga"] = previous_lowest_price - 1
            else: args["max_harga"] = 10000000
        return True, "Berikut hasil pencarian dari katalog kami:", {"name": "search_catalog", "args": args}
        
    return False, "", {}"""

text = text.replace(old_cp, new_cp)

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
