import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_fast_path = """def check_fast_path(text: str, catalog: Catalog) -> tuple[bool, str, dict]:
    t = text.lower().strip()
    greetings = ["halo", "hi", "hai", "p", "terima kasih", "makasih", "apa kabar"]
    if any(t == k or t.startswith(k + " ") for k in greetings):
        return True, "Halo Kak! Ada produk yang sedang dicari hari ini?", {}
        
    brands = ["acer", "asus", "lenovo", "hp", "nitro", "vivobook", "tuf", "ideapad", "legion", "macbook", "apple", "rog"]
    has_brand = any(b in f" {t} " for b in brands)
    is_pure_query = (has_brand or "laptop" in t or "komputer" in t or "pc" in t) and "buat" not in t and "untuk" not in t and "kebutuhan" not in t
    
    if is_pure_query:
        return True, "Berikut hasil pencarian dari katalog kami:", {"name": "search_catalog", "args": {"query": text}}
        
    return False, "", {}"""

new_fast_path = """def check_fast_path(text: str, catalog: Catalog, previous_lowest_price: int | None = None) -> tuple[bool, str, dict]:
    t = text.lower().strip()
    greetings = ["halo", "hi", "hai", "p", "terima kasih", "makasih", "apa kabar"]
    if any(t == k or t.startswith(k + " ") for k in greetings):
        return True, "Halo Kak! Ada produk yang sedang dicari hari ini?", {}
        
    brands = ["acer", "asus", "lenovo", "hp", "nitro", "vivobook", "tuf", "ideapad", "legion", "macbook", "apple", "rog"]
    has_brand = any(b in f" {t} " for b in brands)
    
    narrowing_keywords = ["lebih murah", "yang lain", "yang asus", "yang ssd", "yang ram", "kalo", "kalau", "aja"]
    is_narrowing = any(k in t for k in narrowing_keywords)
    
    is_pure_query = (has_brand or "laptop" in t or "komputer" in t or "pc" in t or is_narrowing) and "buat" not in t and "untuk" not in t and "kebutuhan" not in t
    
    if is_pure_query:
        args = {"query": text}
        if "lebih murah" in t or "yang murah" in t:
            args["max_harga"] = (previous_lowest_price - 1) if previous_lowest_price else 10000000
        return True, "Berikut hasil pencarian dari katalog kami:", {"name": "search_catalog", "args": args}
        
    return False, "", {}"""

text = text.replace(old_fast_path, new_fast_path)

sig_old = """def run_agentic_tool(
    user_text: str,
    history: list[dict],
    catalog: Catalog,
    current_category: str | None = None,
    current_offered_products: list[str] | None = None,
    active_profile_id: str | None = None,
    model: str = "gemma4:e4b",
    url: str = "http://localhost:11434"
) -> dict:"""

sig_new = """def run_agentic_tool(
    user_text: str,
    history: list[dict],
    catalog: Catalog,
    current_category: str | None = None,
    current_offered_products: list[str] | None = None,
    active_profile_id: str | None = None,
    previous_lowest_price: int | None = None,
    model: str = "gemma4:e4b",
    url: str = "http://localhost:11434"
) -> dict:"""

text = text.replace(sig_old, sig_new)

call_old = """    is_fast, fast_reply, fast_tool = check_fast_path(user_text, catalog)"""
call_new = """    is_fast, fast_reply, fast_tool = check_fast_path(user_text, catalog, previous_lowest_price)"""

text = text.replace(call_old, call_new)

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
