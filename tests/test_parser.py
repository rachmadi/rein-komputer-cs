import pytest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.ingest_knowledge import parse_kb, KNOWLEDGE_FILE

def get_parsed_data():
    return {c['id']: c for c in parse_kb(KNOWLEDGE_FILE)}

def test_parser_p02():
    data = get_parsed_data()
    p02 = data.get('P02')
    assert p02 is not None
    assert p02['filter'] == [
        {'field': 'ram_gb', 'op': '>=', 'value': 16, 'strength': 'hard'},
        {'field': 'storage_ssd_gb', 'op': '>=', 'value': 512, 'strength': 'hard'},
        {'field': 'cpu_tier', 'op': '>=', 'value': 2, 'strength': 'hard'},
        {'field': 'panel', 'op': '=', 'value': 'IPS', 'strength': 'hard'},
        {'field': 'srgb_pct', 'op': '>=', 'value': 100, 'strength': 'hard'}
    ]

def test_parser_p03():
    data = get_parsed_data()
    p03 = data.get('P03')
    assert p03 is not None
    assert p03['filter'] == [
        {'field': 'ram_gb', 'op': '>=', 'value': 32, 'strength': 'hard'},
        {'field': 'storage_ssd_gb', 'op': '>=', 'value': 1000, 'strength': 'hard'},
        {'field': 'cpu_tier', 'op': '>=', 'value': 3, 'strength': 'hard'},
        {'field': 'gpu_dedicated', 'op': '=', 'value': 1, 'strength': 'hard'},
        {'field': 'vram_gb', 'op': '>=', 'value': 8, 'strength': 'hard'}
    ]

def test_parser_p06():
    data = get_parsed_data()
    p06 = data.get('P06')
    assert p06 is not None
    assert p06['filter'] == [
        {'field': 'ram_gb', 'op': '>=', 'value': 16, 'strength': 'hard'},
        {'field': 'storage_ssd_gb', 'op': '>=', 'value': 512, 'strength': 'hard'},
        {'field': 'cpu_tier', 'op': '>=', 'value': 2, 'strength': 'hard'}
    ]

def test_parser_p13():
    data = get_parsed_data()
    p13 = data.get('P13')
    assert p13 is not None
    assert p13['filter'] == [
        {'field': 'ram_gb', 'op': '>=', 'value': 16, 'strength': 'hard'},
        {'field': 'storage_ssd_gb', 'op': '>=', 'value': 1000, 'strength': 'hard'},
        {'field': 'cpu_tier', 'op': '>=', 'value': 3, 'strength': 'hard'},
        {'field': 'gpu_dedicated', 'op': '=', 'value': 1, 'strength': 'soft', 'gpu_vendor_hint': 'nvidia'},
        {'field': 'vram_gb', 'op': '>=', 'value': 8, 'strength': 'hard'}
    ]
