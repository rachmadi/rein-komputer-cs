import sys
import re

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_query_logic = """        scored_products = []
        relaxed_products = []
        for p in catalog.products:"""

new_query_logic = """        search_text = (query + " " + user_text).lower()
        req_ram = None
        req_storage = None
        
        ram_match = re.search(r'ram[^\d]*(\\d{1,3})\\s*(gb)?', search_text)
        if ram_match: req_ram = int(ram_match.group(1))
        
        storage_match = re.search(r'(ssd|hdd|storage|memori)[^\\d]*(\\d{1,4})\\s*(gb|tb)?', search_text)
        if storage_match:
            val = int(storage_match.group(2))
            if storage_match.group(3) == 'tb' or val < 10: val *= 1000
            req_storage = val

        scored_products = []
        relaxed_products = []
        for p in catalog.products:
            if req_ram and p.get("ram_gb", 0) < req_ram: continue
            if req_storage and p.get("storage_ssd_gb", 0) < req_storage: continue
"""

text = text.replace(old_query_logic, new_query_logic)

# Also fix the "ada yang lebih murah?" price bug! Wait, I already did "previous_lowest_price". 
# But wait, (d) "game berat tapi kasir" harus memetakan P05 + P15 dan menggabungkan syarat terberat!
# "game berat tapi kasir" -> P16 + P15? No, the requirement says P05 + P15! 
# Let's check `get_usage_requirements` to see how it maps.

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
