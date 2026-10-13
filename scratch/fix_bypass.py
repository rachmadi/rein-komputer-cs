import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_bypass = """    if BYPASS_LLM1_ON_RAG and reqs.get("profil"):
        # Bypass LLM-1 completely, go straight to Tool
        t0_tool = time.time()
        ans_str, prods, cat, prof = execute_tool("search_catalog", {"kebutuhan": user_text}, catalog, current_offered_products or [], user_text, active_profile_id)"""

new_bypass = """    if BYPASS_LLM1_ON_RAG and reqs.get("profil"):
        # Bypass LLM-1 completely, go straight to Tool
        t0_tool = time.time()
        
        args = {"kebutuhan": user_text}
        if current_category: args["kategori"] = current_category
        if any(k in user_text for k in ["lebih murah"]) and previous_lowest_price:
             args["max_harga"] = previous_lowest_price - 1
             
        ans_str, prods, cat, prof = execute_tool("search_catalog", args, catalog, current_offered_products or [], user_text, active_profile_id)"""

text = text.replace(old_bypass, new_bypass)

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
