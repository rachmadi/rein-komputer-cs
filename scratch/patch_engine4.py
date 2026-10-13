import re

with open(r"d:\RAG\services\agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

field_map = """        friendly_map = {
            "ram_gb": "Kapasitas RAM",
            "vram_gb": "Kapasitas VRAM (VGA)",
            "storage_ssd_gb": "Kapasitas SSD",
            "cpu_tier": "Tingkatan Prosesor",
            "gpu_class": "Kelas Kartu Grafis",
            "gpu_dedicated": "Kartu Grafis Dedicated"
        }
        fname = friendly_map.get(field, field)"""

old_code = """        if passed:
            report["terpenuhi"].append(field)
        else:
            report["tidak_terpenuhi"].append(f"{field} {op} {val} (got {pval})")
            if mandatory:
                failed_reasons.append(field)"""

new_code = f"""{field_map}
        if passed:
            report["terpenuhi"].append(field)
        else:
            report["tidak_terpenuhi"].append(f"{{fname}} belum memadai (butuh: {{val}}, saat ini: {{pval}})")
            if mandatory:
                failed_reasons.append(fname)"""

text = text.replace(old_code, new_code)

with open(r"d:\RAG\services\agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
