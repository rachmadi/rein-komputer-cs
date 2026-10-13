import pytest
from core.catalog import Catalog
from services.agentic_tool_engine import execute_tool

def test_fast_path_inherits_profile():
    catalog = Catalog.from_dummy()
    
    # Simulate first turn
    ans, prods, cat, prof = execute_tool(
        "search_catalog", 
        {"kebutuhan": "edit video 4k"}, 
        catalog, 
        [], 
        "laptop buat edit video 4k", 
        None
    )
    # The profile ID should be returned (e.g. P03)
    assert prof is not None
    
    # Simulate second turn: "yang ASUS aja" (fast path returns args: {"query": "yang ASUS aja"})
    ans2, prods2, cat2, prof2 = execute_tool(
        "search_catalog",
        {"query": "yang ASUS aja"},
        catalog,
        [],
        "yang ASUS aja",
        active_profile_id=prof
    )
    # The active profile ID must be inherited
    assert prof2 == prof
    # Also verify that it applied the profile's constraints (e.g. RTX 3050 etc)
    # If it inherited the profile, it wouldn't return a cheap integrated graphics Asus if there's any.
