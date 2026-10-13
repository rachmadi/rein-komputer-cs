import sys
import re

with open("d:/RAG/services/chat_service.py", "r", encoding="utf-8") as f:
    text = f.read()

old_call = """        tool_res = run_agentic_tool(
            user_text=user_text,
            history=sess["messages"],
            catalog=catalog,
            current_category=state.get("category"),
            current_offered_products=state.get("offered_products"),
            model=active_model
        )"""

new_call = """        tool_res = run_agentic_tool(
            user_text=user_text,
            history=sess["messages"],
            catalog=catalog,
            current_category=state.get("category"),
            current_offered_products=state.get("offered_products"),
            active_profile_id=state.get("active_profile"),
            previous_lowest_price=state.get("lowest_price"),
            model=active_model
        )"""

text = text.replace(old_call, new_call)

old_save = """        state["category"] = tool_res.get("category")"""
new_save = """        if tool_res.get("category"):
            state["category"] = tool_res.get("category")
        if tool_res.get("active_profile_id"):
            state["active_profile"] = tool_res.get("active_profile_id")
        
        # update lowest price
        op = tool_res.get("offered_products")
        if op and isinstance(op, list):
            lowest = None
            for p in op:
                if isinstance(p, dict) and p.get("harga_idr"):
                    if lowest is None or p["harga_idr"] < lowest:
                        lowest = p["harga_idr"]
            if lowest is not None:
                state["lowest_price"] = lowest"""

text = text.replace(old_save, new_save)

with open("d:/RAG/services/chat_service.py", "w", encoding="utf-8") as f:
    f.write(text)
