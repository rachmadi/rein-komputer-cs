import pytest
from core.catalog import Catalog
from services.agentic_tool_engine import should_skip_rag, check_fast_path

def test_fast_path_rog_vs_programming():
    catalog = Catalog.from_dummy()
    
    # "rog" is a brand -> should trigger fast path (skip RAG)
    fast, reply, tool = check_fast_path("aku cari rog", catalog)
    assert fast == True
    
    # "programming" contains "rog" but should NOT trigger brand fast path
    fast_prog, reply_prog, tool_prog = check_fast_path("laptop buat programming", catalog)
    assert fast_prog == False
    
    # Check should_skip_rag (which skips RAG during tool execution)
    assert should_skip_rag("rog", catalog) == True
    assert should_skip_rag("programming", catalog) == False
