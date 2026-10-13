import sys

with open("d:/RAG/services/chat_service.py", "r", encoding="utf-8") as f:
    text = f.read()

old_lowest = """    previous_lowest_price = min([p["harga_idr"] for p in state.get("offered_products_details", []) if p.get("harga_idr")], default=None)"""

new_lowest = """    previous_lowest_price = min([cat.by_code[k]["harga_idr"] for k in current_offered if k in cat.by_code and cat.by_code[k].get("harga_idr")] or [None], default=None)"""

text = text.replace(old_lowest, new_lowest)

with open("d:/RAG/services/chat_service.py", "w", encoding="utf-8") as f:
    f.write(text)
