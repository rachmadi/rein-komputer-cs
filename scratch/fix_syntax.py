import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('print(f"[DEBUG run_agentic] t_prof={t_prof}"); if t_prof: new_profile_id = t_prof', 'print(f"[DEBUG run_agentic] t_prof={t_prof}")\n            if t_prof: new_profile_id = t_prof')

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
