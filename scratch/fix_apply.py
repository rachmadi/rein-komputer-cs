import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_apply = """def apply_filters(product: dict, filters: list[dict]) -> tuple[bool, str | None, int, dict]:
    penalty = 0
    failed_reasons = []
    failed_details = []
    report = {"terpenuhi": [], "tidak_terpenuhi": [], "tidak_diketahui": []}
    
    for f in filters:
        field = f["field"]
        op = f["op"]
        val = f["value"]
        mandatory = (f.get("strength") == "hard" or f.get("mandatory") == True)
        
        pval = product.get(field)
        if pval is None:
            report["tidak_diketahui"].append(field)
            if mandatory:
                failed_reasons.append(field)
            else:
                penalty -= 5
            continue
            
        passed = False
        try:
            if op == ">=": passed = float(pval) >= float(val)
            elif op == "<=": passed = float(pval) <= float(val)
            elif op in ("==", "="): passed = str(pval).lower() == str(val).lower()
        except:
            passed = False
            
        if passed:
            report["terpenuhi"].append(field)
        else:
            report["tidak_terpenuhi"].append(f"{field} {op} {val} (got {pval})")
            if mandatory:
                failed_reasons.append(field)
                failed_details.append(f"{field} {op} {val}")
            else:
                penalty -= int(f.get("penalty", 10))
                
    if failed_reasons:
        return False, f"Belum memenuhi minimum: {', '.join(failed_reasons)}", penalty, report
    return True, None, penalty, report"""

new_apply = """def apply_filters(product: dict, filters: list[dict]) -> tuple[bool, str | None, int, dict]:
    penalty = 0
    failed_reasons = []
    failed_details = []
    unknown_details = []
    report = {"terpenuhi": [], "tidak_terpenuhi": [], "tidak_diketahui": []}
    
    for f in filters:
        field = f["field"]
        op = f["op"]
        val = f["value"]
        mandatory = (f.get("strength") == "hard" or f.get("mandatory") == True)
        
        pval = product.get(field)
        if field == "vram_gb":
            if product.get("gpu_dedicated") == 0:
                pval = 0
            elif product.get("gpu_dedicated") == 1 and pval is None:
                report["tidak_diketahui"].append("vram_gb")
                unknown_details.append("VRAM_GB (Dedicated)")
                penalty -= 10
                continue
                
        if pval is None:
            report["tidak_diketahui"].append(field)
            unknown_details.append(field)
            if mandatory:
                failed_reasons.append(field)
            else:
                penalty -= 5
            continue
            
        passed = False
        try:
            if op == ">=": passed = float(pval) >= float(val)
            elif op == "<=": passed = float(pval) <= float(val)
            elif op in ("==", "="): passed = str(pval).lower() == str(val).lower()
        except:
            passed = False
            
        friendly_map = {
            "ram_gb": "Kapasitas RAM",
            "vram_gb": "Kapasitas VRAM",
            "storage_ssd_gb": "Kapasitas SSD",
            "cpu_tier": "Tingkatan Prosesor",
            "gpu_class": "Kelas Kartu Grafis",
            "gpu_dedicated": "Kartu Grafis Dedicated"
        }
        fname = friendly_map.get(field, field)
            
        if passed:
            report["terpenuhi"].append(field)
        else:
            report["tidak_terpenuhi"].append(f"{fname} belum memadai (butuh: {val}, saat ini: {pval})")
            if mandatory:
                failed_reasons.append(fname)
                failed_details.append(f"{field} {op} {val}")
            else:
                penalty -= int(f.get("penalty", 10))
                
    if failed_reasons:
        return False, f"Belum memenuhi minimum: {', '.join(failed_reasons)}", penalty, report
    return True, None, penalty, report"""

text = text.replace(old_apply, new_apply)

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
