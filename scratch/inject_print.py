import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("t_start = time.time()", 'print(f"[DEBUG run_agentic] received active_profile_id={active_profile_id}"); t_start = time.time()')

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
