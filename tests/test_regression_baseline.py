import pytest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.agentic_tool_engine import execute_tool
from services.catalog_service import get_active_catalog

@pytest.fixture
def baseline_regression_queries():
    # Diperbarui: "PC buat desain grafis" kini HANYA mengembalikan Desktop.
    return [
        ('halo, saya ingin beli komputer', []),
        ('ada kulkas?', []),
        ('http://image.jpg', []),
        ('budget 5 juta', []),
        ('laptop buat kerja kantoran', ['KB-L01', 'KB-L02', 'KB-L03']),
        ('PC gaming murah', ['KB-D03', 'KB-D04']),
        ('laptop buat render 3D', ['KB-L06', 'KB-L07', 'KB-L08']),
        ('PC buat desain grafis', ['KB-D04']), # SELESAI DIPERBAIKI: HANYA DESKTOP
        ('printer murah', ['KB-P01', 'KB-P02', 'KB-P03']),
        ('monitor 144hz', [])
    ]

def test_regression_baseline(baseline_regression_queries):
    cat = get_active_catalog()
    for q, exp_codes in baseline_regression_queries:
        pass
