import sys
import re

with open("d:/RAG/core/catalog.py", "r", encoding="utf-8") as f:
    text = f.read()

# Replace the broken reference in parse_product_text
old_ret = """        "vram_gb": gpu_vram,
        "cpu_tier": cpu_tier if jenis != "printer" else None,"""
new_ret = """        "vram_gb": gpu_vram,"""

text = text.replace(old_ret, new_ret)

# Now add cpu_tier calculation inside parse_product_text
old_cpu = 'vendor = "intel" if "intel" in low else "amd" if ("amd" in low or "ryzen" in low) else None'
new_cpu = """vendor = "intel" if "intel" in low else "amd" if ("amd" in low or "ryzen" in low) else None
        
        is_cpu_budget = any(x in low for x in ("n100", "celeron", "pentium", "i3", "ryzen 3"))
        is_cpu_high_tdp = any(x in low for x in ("13420h", "7735hs", "12450hx", "14650hx", "14700f", "13400f", "13400", "13620h", "7840hs"))
        is_cpu_top = any(x in low for x in ("14650hx", "14700", "14700f", "i9", "ryzen 9", "7900"))
        cpu_tier = 3 if is_cpu_top else 2 if is_cpu_high_tdp else 1 if not is_cpu_budget else 0"""
        
text = text.replace(old_cpu, new_cpu)

old_ret2 = """        "vram_gb": gpu_vram,"""
new_ret2 = """        "vram_gb": gpu_vram,
        "cpu_tier": cpu_tier if cpu else None,"""

text = text.replace(old_ret2, new_ret2)

with open("d:/RAG/core/catalog.py", "w", encoding="utf-8") as f:
    f.write(text)
