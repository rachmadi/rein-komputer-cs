import pytest
from services.agentic_tool_engine import execute_tool, apply_filters
from core.catalog import Catalog

def test_golden_edit_video_4k_operator_bug():
    # Simulate LLM extracting kebutuhan="laptop buat edit video 4k"
    # This translates to P03, which needs gpu_dedicated = 1
    
    
    # We'll just test apply_filters for Legion Pro 5
    p = {"kode": "KB-L10", "nama": "Legion Pro 5", "gpu_dedicated": 1}
    # P03 filter requires gpu_dedicated = 1
    filters = [{"field": "gpu_dedicated", "op": "=", "value": 1, "strength": "hard"}]
    
    passed, reason, penalty, report = apply_filters(p, filters)
    assert passed, f"Legion Pro 5 should pass P03, but failed with reason: {reason}"

