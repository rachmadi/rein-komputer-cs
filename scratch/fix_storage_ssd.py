import sys
import re

with open("d:/RAG/core/catalog.py", "r", encoding="utf-8") as f:
    text = f.read()

old_storage = '"storage": clean_val(fields.get("storage")) if jenis != "printer" else None,'
new_storage = """storage_val = clean_val(fields.get("storage")) if jenis != "printer" else None
        storage_ssd_gb = None
        if storage_val:
            sm = re.search(r"(\\d+)\\s*(GB|TB)", storage_val, re.I)
            if sm:
                v = int(sm.group(1))
                if sm.group(2).upper() == "TB":
                    v *= 1024
                storage_ssd_gb = v
        rec = {
            "kode": code,
            "nama": name,
            "kategori": jenis,
            "is_accessory": jenis == "monitor",
            "harga_idr": price,
            "cpu": cpu,
            "cpu_vendor": vendor,
            "ram_gb": ram_gb,
            "ram_type": ram_type,
            "storage": storage_val,
            "storage_ssd_gb": storage_ssd_gb,"""

text = text.replace('        rec = {\n            "kode": code,\n            "nama": name,\n            "kategori": jenis,\n            "is_accessory": jenis == "monitor",\n            "harga_idr": price,\n            "cpu": cpu,\n            "cpu_vendor": vendor,\n            "ram_gb": ram_gb,\n            "ram_type": ram_type,\n            "storage": clean_val(fields.get("storage")) if jenis != "printer" else None,', new_storage)

with open("d:/RAG/core/catalog.py", "w", encoding="utf-8") as f:
    f.write(text)
