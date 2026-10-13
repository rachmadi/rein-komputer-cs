import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_guard = """        msg = res1.get("message", {})
        
        prods = []
        cat = None
        executed_tools = []
        new_profile_id = None
        
        if msg.get("tool_calls"):"""

new_guard = """        msg = res1.get("message", {})
        
        # GUARD ANTI-HALUSINASI
        if not msg.get("tool_calls"):
            ut_lower = user_text.lower()
            if "laptop" in ut_lower or "buat" in ut_lower or "kebutuhan" in ut_lower or "untuk" in ut_lower:
                msg["tool_calls"] = [{"function": {"name": "search_catalog", "arguments": {"kebutuhan": user_text}}}]
                
        prods = []
        cat = None
        executed_tools = []
        new_profile_id = None
        
        if msg.get("tool_calls"):"""

text = text.replace(old_guard, new_guard)

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
