# -*- coding: utf-8 -*-
"""
tests/test_putaran15_synthetic.py
Pengujian sintetis Putaran 15: Impor katalog v2, CPU Apple, data kosong, lepas ketergantungan dummy, pilihan dalam budget, dan kesetaraan kategori.
"""
import pytest
from scripts.migrate_derived_fields import cpu_tier


# =============================================================================
# BUTIR 2 — Tingkat CPU Apple (KB G01)
# =============================================================================
@pytest.mark.parametrize("cpu_str,expected_tier", [
    # Apple M dasar -> Tier 2
    ("Apple M1 8-core", 2),
    ("Apple M2 8-core", 2),
    ("Apple M3", 2),
    ("Apple M4 10-core", 2),
    # Apple M Pro -> Tier 3
    ("Apple M1 Pro", 3),
    ("Apple M2 Pro 10-core", 3),
    ("Apple M3 Pro 11-core", 3),
    # Apple M Max -> Tier 4
    ("Apple M1 Max", 4),
    ("Apple M2 Max 12-core", 4),
    ("Apple M3 Max 14-core", 4),
    # Varian lain (mis. Ultra) -> None (NULL)
    ("Apple M1 Ultra", None),
    ("Apple M2 Ultra", None),
    # Intel & AMD tetap sesuai aturan
    ("Intel Core Ultra 7 155H", 3),
    ("Intel Core i5-12400", 2),
    ("AMD Ryzen 7 7735HS", 3),
    ("Intel Celeron N4500", 1),
    ("Intel Processor N100", 1),
    ("", None),
    (None, None),
])
def test_butir2_cpu_tier_apple_dan_pc(cpu_str, expected_tier):
    assert cpu_tier(cpu_str) == expected_tier
