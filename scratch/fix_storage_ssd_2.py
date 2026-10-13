import sys
import re

with open("d:/RAG/core/catalog.py", "r", encoding="utf-8") as f:
    text = f.read()

old_str = '''        "storage": clean_val(fields.get("storage")) if jenis != "printer" else None,
        "gpu": gpu,'''

new_str = '''        "storage": clean_val(fields.get("storage")) if jenis != "printer" else None,
        "storage_ssd_gb": int(re.search(r"(\\d+)\\s*(GB|TB)", clean_val(fields.get("storage")) or "").group(1)) * (1024 if re.search(r"(\\d+)\\s*(GB|TB)", clean_val(fields.get("storage")) or "").group(2).upper() == "TB" else 1) if re.search(r"(\\d+)\\s*(GB|TB)", clean_val(fields.get("storage")) or "", re.I) else None,
        "gpu": gpu,'''

text = text.replace(old_str, new_str)

with open("d:/RAG/core/catalog.py", "w", encoding="utf-8") as f:
    f.write(text)
