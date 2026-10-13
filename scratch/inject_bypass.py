import re

with open(r"d:\RAG\services\agentic_tool_engine.py", "r", encoding="utf-8") as f:
    code = f.read()

bypass_logic = """
    # Bypass LLM-1 for Usage Intent
    from services.knowledge_service import get_usage_requirements
    is_rag_skipped = should_skip_rag(user_text, catalog)
    reqs = {}
    if not is_rag_skipped:
        reqs = get_usage_requirements(user_text)
        
    if BYPASS_LLM1_ON_RAG and reqs.get("profil"):
        # Bypass LLM-1 completely, go straight to Tool
        t0_tool = time.time()
        ans_str, prods, cat, prof = execute_tool("search_catalog", {"kebutuhan": user_text}, catalog, current_offered_products or [], user_text, active_profile_id)
        t_tool = time.time() - t0_tool
        
        final_reply = "Baik, ini rekomendasi dari sistem kami berdasarkan kebutuhan Anda:\\n\\n" + ans_str
        total = time.time() - t_start
        metrics = {"llm1": 0.0, "tool": t_tool, "llm2": 0.0, "total": total}
        logger.info(f"[PERF] Bypass LLM-1 total={total:.2f}s")
        return {"reply": final_reply.strip(), "products": prods, "category": cat, "route": "AGENTIC", "tool_calls": [{"name": "search_catalog", "args": {"kebutuhan": user_text}}], "active_profile_id": prof, "metrics": metrics}

    # 2. Persiapan Prompt LLM
"""

code = code.replace("    # 2. Persiapan Prompt LLM\n", bypass_logic)

with open(r"d:\RAG\services\agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(code)
