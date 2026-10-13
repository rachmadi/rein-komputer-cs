import pytest
from core.catalog import Catalog
from services.agentic_tool_engine import run_agentic_tool, BYPASS_LLM1_ON_RAG
import services.agentic_tool_engine


def test_anti_hallucination():
    # Force bypass to False so LLM-1 is used
    services.agentic_tool_engine.BYPASS_LLM1_ON_RAG = False
    try:
        catalog = Catalog.from_dummy()
        
        # We will simulate a prompt where LLM might try to answer without tool (e.g. by mocking urllib to return plain text)
        # But since it's an end-to-end test, we can just patch urllib.request.urlopen to return a hallucinated text
        import urllib.request
        import json
        from unittest.mock import patch, MagicMock

        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps({
                "message": {
                    "role": "assistant",
                    "content": "Ini laptop Asus ROG harganya Rp20.000.000",
                    # No tool calls!
                }
            }).encode("utf-8")
            mock_urlopen.return_value.__enter__.return_value = mock_response

            # Kebutuhan jelas tapi LLM halusinasi
            res = run_agentic_tool("laptop buat mahasiswa", [], catalog)
            
            # The guard should force search_catalog, which means route will be AGENTIC and tools are called!
            assert res["route"] == "AGENTIC"
            assert len(res.get("tool_calls", [])) > 0
            assert res["tool_calls"][0]["name"] == "search_catalog"
            assert "Rp" in res["reply"] # Should have tool output formatted in reply, not the hallucinated text
    finally:
        services.agentic_tool_engine.BYPASS_LLM1_ON_RAG = True

