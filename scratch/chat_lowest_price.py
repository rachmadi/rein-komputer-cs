import sys

with open("d:/RAG/services/chat_service.py", "r", encoding="utf-8") as f:
    text = f.read()

old_call = """    tool_res = run_agentic_tool(
        user_text=user_text,
        history=history,
        catalog=cat,
        current_category=current_category,
        current_offered_products=current_offered,
        active_profile_id=active_profile,
        model=active_model
    )"""

new_call = """    previous_lowest_price = min([p["harga_idr"] for p in state.get("offered_products_details", []) if p.get("harga_idr")], default=None)

    tool_res = run_agentic_tool(
        user_text=user_text,
        history=history,
        catalog=cat,
        current_category=current_category,
        current_offered_products=current_offered,
        active_profile_id=active_profile,
        previous_lowest_price=previous_lowest_price,
        model=active_model
    )"""

text = text.replace(old_call, new_call)

with open("d:/RAG/services/chat_service.py", "w", encoding="utf-8") as f:
    f.write(text)
