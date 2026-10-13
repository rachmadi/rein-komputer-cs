import sys
import re

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

# Update execute_tool signature
old_exec = 'def execute_tool(name: str, args: dict, catalog: Catalog, session_offered: list[str] = [], user_text: str = "", active_profile_id: str | None = None) -> tuple[str, list[dict], str | None, str | None]:'
new_exec = 'def execute_tool(name: str, args: dict, catalog: Catalog, session_offered: list[str] = [], user_text: str = "", active_profile_id: str | None = None, active_category: str | None = None) -> tuple[str, list[dict], str | None, str | None]:'
text = text.replace(old_exec, new_exec)

# Inside execute_tool:
old_cat = 'explicit_cat = args.get("kategori")\n        if explicit_cat == "all": explicit_cat = None'
new_cat = 'explicit_cat = args.get("kategori") or active_category\n        if explicit_cat == "all": explicit_cat = None'
text = text.replace(old_cat, new_cat)

# Update run_agentic_tool signature
old_run = 'def run_agentic_tool(\n    user_text: str,\n    history: list[dict],\n    catalog: Catalog,\n    current_offered_products: list[str] | None = None,\n    active_profile_id: str | None = None,\n    previous_lowest_price: int | None = None\n) -> dict:'
new_run = 'def run_agentic_tool(\n    user_text: str,\n    history: list[dict],\n    catalog: Catalog,\n    current_offered_products: list[str] | None = None,\n    active_profile_id: str | None = None,\n    previous_lowest_price: int | None = None,\n    active_category: str | None = None\n) -> dict:'
text = text.replace(old_run, new_run)

# Update execute_tool calls in run_agentic_tool
old_call1 = 'ans_str, p_list, t_cat, t_prof = execute_tool(fast_tool["name"], fast_tool["args"], catalog, current_offered_products or [], user_text, active_profile_id)'
new_call1 = 'ans_str, p_list, t_cat, t_prof = execute_tool(fast_tool["name"], fast_tool["args"], catalog, current_offered_products or [], user_text, active_profile_id, active_category)'
text = text.replace(old_call1, new_call1)

old_call2 = 'ans_str, p_list, t_cat, t_prof = execute_tool(tool["name"], tool["args"], catalog, current_offered_products or [], user_text, active_profile_id)'
new_call2 = 'ans_str, p_list, t_cat, t_prof = execute_tool(tool["name"], tool["args"], catalog, current_offered_products or [], user_text, active_profile_id, active_category)'
text = text.replace(old_call2, new_call2)

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)


with open("d:/RAG/services/chat_service.py", "r", encoding="utf-8") as f:
    text = f.read()

# Add active_category to session state
if '"active_category": None' not in text:
    text = text.replace('"active_profile": None,', '"active_profile": None,\n            "active_category": None,')

# Pass active_category to run_agentic_tool
old_run_call = """agent_result = run_agentic_tool(
            user_text=text,
            history=history_for_agent,
            catalog=_catalog,
            current_offered_products=current_offered,
            active_profile_id=sess["state"]["active_profile"],
            previous_lowest_price=sess["state"].get("lowest_price")
        )"""
new_run_call = """agent_result = run_agentic_tool(
            user_text=text,
            history=history_for_agent,
            catalog=_catalog,
            current_offered_products=current_offered,
            active_profile_id=sess["state"]["active_profile"],
            previous_lowest_price=sess["state"].get("lowest_price"),
            active_category=sess["state"].get("active_category")
        )"""
text = text.replace(old_run_call, new_run_call)

# Update session state with new active_category
old_update = """new_profile_id = agent_result.get("active_profile_id")
        if new_profile_id:
            sess["state"]["active_profile"] = new_profile_id"""
new_update = """new_profile_id = agent_result.get("active_profile_id")
        if new_profile_id:
            sess["state"]["active_profile"] = new_profile_id
        new_cat = agent_result.get("category")
        if new_cat:
            sess["state"]["active_category"] = new_cat"""
text = text.replace(old_update, new_update)

with open("d:/RAG/services/chat_service.py", "w", encoding="utf-8") as f:
    f.write(text)
