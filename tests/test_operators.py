import pytest
from services.agentic_tool_engine import apply_filters

def test_operator_unknown():
    with pytest.raises(ValueError, match="Unknown operator: <<"):
        apply_filters({"ram_gb": 16}, [{"field": "ram_gb", "op": "<<", "value": 8}])

def test_operator_known():
    passed, _, _, _ = apply_filters({"ram_gb": 16}, [{"field": "ram_gb", "op": ">=", "value": 16}])
    assert passed
    
    passed, _, _, _ = apply_filters({"ram_gb": 16}, [{"field": "ram_gb", "op": "<=", "value": 16}])
    assert passed
    
    passed, _, _, _ = apply_filters({"ram_gb": 16}, [{"field": "ram_gb", "op": "==", "value": 16}])
    assert passed
    
    passed, _, _, _ = apply_filters({"ram_gb": 16}, [{"field": "ram_gb", "op": "=", "value": 16}])
    assert passed
