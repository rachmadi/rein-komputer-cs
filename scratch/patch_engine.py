import re

with open(r"d:\RAG\services\agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_code = """        if field == "vram_gb":
            if product.get("gpu_dedicated") == 0:
                pval = 0
            elif product.get("gpu_dedicated") == 1 and pval is None:
                report["tidak_diketahui"].append("VRAM_GB")
                unknown_details.append("VRAM_GB (Dedicated)")
                penalty -= 10
                continue"""

new_code = """        if field == "vram_gb":
            if product.get("gpu_dedicated") == 0:
                pval = 0
            elif product.get("gpu_dedicated") == 1 and pval is None:
                report["tidak_diketahui"].append("VRAM_GB")
                unknown_details.append("VRAM_GB (Dedicated)")
                penalty -= 10
                report["peringatan_khusus"] = "VRAM belum tercantum, mohon konfirmasi ke staf"
                failed_reasons.append("vram_gb_null_dedicated")
                continue"""

text = text.replace(old_code, new_code)

with open(r"d:\RAG\services\agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
