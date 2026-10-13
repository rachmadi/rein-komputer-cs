import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

bad_block = """        else:
            t_emb_end = time.time()
            pls = reqs.get("profil", [])"""

good_block = """        else:
            t_emb_end = time.time()
            
        pls = reqs.get("profil", [])"""

text = text.replace(bad_block, good_block)

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
