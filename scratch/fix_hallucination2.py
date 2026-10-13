import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_code = """    msg = res_data.get("message", {})
    messages.append(msg)
    
    prods = []"""

new_code = """    msg = res_data.get("message", {})
    
    if not msg.get("tool_calls"):
        ut_lower = user_text.lower()
        if "laptop" in ut_lower or "buat" in ut_lower or "kebutuhan" in ut_lower or "untuk" in ut_lower:
            msg["tool_calls"] = [{"function": {"name": "search_catalog", "arguments": {"kebutuhan": user_text}}}]

    messages.append(msg)
    
    prods = []"""

text = text.replace(old_code, new_code)

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
