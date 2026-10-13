import re

with open(r"d:\RAG\services\agentic_tool_engine.py", "r", encoding="utf-8") as f:
    code = f.read()

anti_hallu_logic = """
    t_llm1 = time.time() - t0_llm1
    msg = res_data.get("message", {})
    
    # Anti-hallucination guard
    content_text = msg.get("content", "") or ""
    has_hallucinated_price = bool(re.search(r"Rp\\s*\\d+", content_text))
    has_hallucinated_brand = any(b in content_text.lower() for b in ["asus", "acer", "lenovo", "hp", "macbook", "rog"])
    
    if not msg.get("tool_calls"):
        if reqs.get("profil") or reqs.get("mandatory_specs") or has_hallucinated_price or (has_hallucinated_brand and "laptop" in content_text.lower()):
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("[GUARD] LLM-1 omitted tool call despite usage/product intent. Forcing search_catalog.")
            msg["tool_calls"] = [{"function": {"name": "search_catalog", "arguments": {"kebutuhan": user_text}}}]
            msg["content"] = ""
            
    messages.append(msg)
"""

code = code.replace("""
    t_llm1 = time.time() - t0_llm1
    msg = res_data.get("message", {})
    messages.append(msg)""", anti_hallu_logic)

with open(r"d:\RAG\services\agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(code)
