import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_apply = """        passed = False
        try:
            if op == ">=": passed = float(pval) >= float(val)
            elif op == "<=": passed = float(pval) <= float(val)
            elif op in ("==", "="): passed = str(pval).lower() == str(val).lower()
        except:
            passed = False"""

new_apply = """        passed = False
        if op not in (">=", "<=", "==", "="):
            raise ValueError(f"Unknown operator: {op}")
        try:
            if op == ">=": passed = float(pval) >= float(val)
            elif op == "<=": passed = float(pval) <= float(val)
            elif op in ("==", "="): passed = str(pval).lower() == str(val).lower()
        except Exception:
            passed = False"""

text = text.replace(old_apply, new_apply)

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
