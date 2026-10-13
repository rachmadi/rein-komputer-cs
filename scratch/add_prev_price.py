import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

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

check_fast_old = """def check_fast_path(text: str, catalog: Catalog, current_category=None) -> tuple[bool, str, dict]:"""
check_fast_new = """def check_fast_path(text: str, catalog: Catalog, current_category=None, previous_lowest_price=None) -> tuple[bool, str, dict]:"""

text = text.replace(check_fast_old, check_fast_new)

fast_call_old = """is_fast, fast_reply, fast_tool = check_fast_path(user_text, catalog, current_category)"""
fast_call_new = """is_fast, fast_reply, fast_tool = check_fast_path(user_text, catalog, current_category, previous_lowest_price)"""

text = text.replace(fast_call_old, fast_call_new)

bypass_old = """    if active_profile_id and any(k in t_text for k in ["lebih murah", "yang lain", "kalo", "kalau"]):
        args = {"query": user_text}
        
        t0_tool = time.time()"""

bypass_new = """    if active_profile_id and any(k in t_text for k in ["lebih murah", "yang lain", "kalo", "kalau"]):
        args = {"query": user_text}
        if any(k in user_text for k in ["lebih murah"]) and previous_lowest_price:
             args["max_harga"] = previous_lowest_price - 1
        t0_tool = time.time()"""

text = text.replace(bypass_old, bypass_new)

fast_args_old = """    if is_pure_query:
        args = {"query": text}
        if current_category: args["kategori"] = current_category
        return True, "Berikut hasil pencarian dari katalog kami:", {"name": "search_catalog", "args": args}"""
fast_args_new = """    if is_pure_query:
        args = {"query": text}
        if current_category: args["kategori"] = current_category
        if any(k in text for k in ["lebih murah", "yang murah"]):
            if previous_lowest_price: args["max_harga"] = previous_lowest_price - 1
            else: args["max_harga"] = 10000000
        return True, "Berikut hasil pencarian dari katalog kami:", {"name": "search_catalog", "args": args}"""

text = text.replace(fast_args_old, fast_args_new)

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
