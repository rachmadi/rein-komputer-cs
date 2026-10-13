import sys
import re

with open("d:/RAG/core/catalog.py", "r", encoding="utf-8") as f:
    text = f.read()

old_gpu_ret = """        "gpu": gpu,
        "gpu_type": gpu_type,
        "gpu_vram": gpu_vram,"""

new_gpu_ret = """        "gpu": gpu,
        "gpu_type": gpu_type,
        "gpu_dedicated": 1 if gpu_type == "discrete" else 0,
        "gpu_vram": gpu_vram,
        "vram_gb": gpu_vram,"""

text = text.replace(old_gpu_ret, new_gpu_ret)

# Also fix cpu tier if it's not set
if '"cpu_tier":' not in text:
    old_cpu = 'is_cpu_top = any(x in cpu for x in ("14650hx", "14700", "14700f", "i9", "ryzen 9"))'
    new_cpu = 'is_cpu_top = any(x in cpu for x in ("14650hx", "14700", "14700f", "i9", "ryzen 9"))\n    cpu_tier = 3 if is_cpu_top else 2 if is_cpu_high_tdp else 1 if not is_cpu_budget else 0'
    text = text.replace(old_cpu, new_cpu)
    
    old_ret_add = '"vram_gb": gpu_vram,'
    new_ret_add = '"vram_gb": gpu_vram,\n        "cpu_tier": cpu_tier if jenis != "printer" else None,'
    text = text.replace(old_ret_add, new_ret_add)

with open("d:/RAG/core/catalog.py", "w", encoding="utf-8") as f:
    f.write(text)
