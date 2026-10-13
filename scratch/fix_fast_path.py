import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

# Update signature
text = text.replace(
    "active_profile_id: str | None = None,",
    "active_profile_id: str | None = None,\n    previous_lowest_price: int | None = None,"
)

# Update check_fast_path call
text = text.replace(
    "is_fast, fast_reply, fast_tool = check_fast_path(user_text, catalog)",
    "is_fast, fast_reply, fast_tool = check_fast_path(user_text, catalog, current_category, previous_lowest_price)"
)

# Update check_fast_path signature
text = text.replace(
    "def check_fast_path(text: str, catalog: Catalog) -> tuple[bool, str, dict]:",
    "def check_fast_path(text: str, catalog: Catalog, current_category=None, previous_lowest_price=None) -> tuple[bool, str, dict]:"
)

# Update check_fast_path logic for inheritance
old_fast_logic = """        for p in catalog.products:
            if explicit_cat and p["kategori"] != explicit_cat: continue
            p_price = p.get("harga_idr") or 0
            if max_harga and p_price > max_harga: continue
            if min_harga and p_price < min_harga: continue"""
new_fast_logic = """        # Inherit category if available and not overridden
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
text = text.replace(old_fast_logic, new_fast_logic)

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
