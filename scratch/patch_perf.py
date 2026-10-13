import re

with open(r"d:\RAG\services\agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

# Add profiling imports and vars
if "import time" not in text:
    text = "import time\n" + text

old_exec = """        if kebutuhan and not should_skip_rag(kebutuhan, catalog):
            from services.knowledge_service import get_usage_requirements
            reqs = get_usage_requirements(kebutuhan)"""

new_exec = """        t_emb_start = time.time()
        if kebutuhan and not should_skip_rag(kebutuhan, catalog):
            from services.knowledge_service import get_usage_requirements
            reqs = get_usage_requirements(kebutuhan)
            t_emb_end = time.time()
            logger.info(f"[PERF] Tool.Embedding+Qdrant: {t_emb_end - t_emb_start:.2f}s")
        else:
            t_emb_end = time.time()"""

text = text.replace(old_exec, new_exec)

old_loop = """        scored_products = []
        relaxed_products = []
        for p in catalog.products:"""

new_loop = """        t_db_start = time.time()
        scored_products = []
        relaxed_products = []
        for p in catalog.products:"""

text = text.replace(old_loop, new_loop)

old_ret = """        res_str = f"{info_profil}\\n✅ Berikut rekomendasi yang memenuhi syarat:\\n"
        for idx, p in enumerate(top_prods):"""

new_ret = """        t_db_end = time.time()
        logger.info(f"[PERF] Tool.FilterSQLite: {t_db_end - t_db_start:.2f}s")
        res_str = f"{info_profil}\\n✅ Berikut rekomendasi yang memenuhi syarat:\\n"
        for idx, p in enumerate(top_prods):"""

text = text.replace(old_ret, new_ret)

with open(r"d:\RAG\services\agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
