import pytest
from services.agentic_tool_engine import check_fast_path, should_skip_rag
from core.catalog import Catalog
import urllib.request
import json
from services.intent_classifier import classify_intent_llm

def test_ood_retention():
    # Make sure we don't accidentally reject valid computer queries that have general words
    assert classify_intent_llm("laptop baterai awet")[0] == True
    assert classify_intent_llm("ada diskon laptop gaming")[0] == True
    assert classify_intent_llm("install apa saja untuk laptop kuliah")[0] == True
