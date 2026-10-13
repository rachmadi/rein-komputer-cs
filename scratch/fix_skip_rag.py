import sys
import re

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_skip = """    for b in brands:
        if b in t and "buat" not in t and "untuk" not in t and "kebutuhan" not in t:
            return True"""

new_skip = """    for b in brands:
        if re.search(r"\\b" + b + r"\\b", t) and "buat" not in t and "untuk" not in t and "kebutuhan" not in t:
            return True"""

text = text.replace(old_skip, new_skip)

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
