import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

if "BYPASS_LLM1_ON_RAG = True" not in text:
    text = text.replace("def run_agentic_tool(", "BYPASS_LLM1_ON_RAG = True\n\ndef run_agentic_tool(")

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
