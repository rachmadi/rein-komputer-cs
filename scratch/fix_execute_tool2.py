import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

bad_block = """        scored_products = []
        relaxed_products = []
        # Inherit category if available and not overridden
        if not explicit_cat and current_category:
            explicit_cat = current_category
            
        # Inherit budget for "lebih murah"
        if any(k in t for k in ["lebih murah", "yang murah"]):
            if previous_lowest_price: max_harga = previous_lowest_price - 1
            elif not max_harga: max_harga = 10000000 # default fallback
            
        for p in catalog.products:
            if explicit_cat and p["kategori"] != explicit_cat: continue
            p_price = p.get("harga_idr") or 0
            if max_harga and p_price > max_harga: continue
            if min_harga and p_price < min_harga: continue"""

good_block = """        scored_products = []
        relaxed_products = []
        for p in catalog.products:
            if explicit_cat and p["kategori"] != explicit_cat: continue
            p_price = p.get("harga_idr") or 0
            if max_harga and p_price > max_harga: continue
            if min_harga and p_price < min_harga: continue"""

text = text.replace(bad_block, good_block)

# Let me ensure check_fast_path uses it correctly. check_fast_path does not have explicit_cat, max_harga, min_harga locally before!
# The check_fast_path function only loops over brands!
with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
