import sys
import re

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

# I need to unindent everything from `if pls:` down to `profil_id = active_profile_id`
target_regex = r'(\s*)pls = reqs\.get\("profil", \[\]\)\s*if pls:\s*if len\(pls\) == 1:\s*profil_id = pls\[0\]\["profil_id"\]\s*elif len\(pls\) >= 2:\s*p1 = get_profile_by_id\(pls\[0\]\["profil_id"\]\)\s*p2 = get_profile_by_id\(pls\[1\]\["profil_id"\]\)\s*if p1 and p2:\s*filters_to_apply = merge_filters\(p1\.get\("filter", \[\]\), p2\.get\("filter", \[\]\)\)\s*info_profil = f"Kebutuhan gabungan: \{p1\[\'judul\'\]\} & \{p2\[\'judul\'\]\}\. "\s*profil_id = f"\{pls\[0\]\[\'profil_id\'\]\},\{pls\[1\]\[\'profil_id\'\]\}"\s*else:\s*profil_id = active_profile_id\s*else:\s*profil_id = active_profile_id'

new_block = """        pls = reqs.get("profil", [])
        if pls:
            if len(pls) == 1:
                profil_id = pls[0]["profil_id"]
            elif len(pls) >= 2:
                p1 = get_profile_by_id(pls[0]["profil_id"])
                p2 = get_profile_by_id(pls[1]["profil_id"])
                if p1 and p2:
                    filters_to_apply = merge_filters(p1.get("filter", []), p2.get("filter", []))
                    info_profil = f"Kebutuhan gabungan: {p1['judul']} & {p2['judul']}. "
                    profil_id = f"{pls[0]['profil_id']},{pls[1]['profil_id']}"
            else:
                profil_id = active_profile_id
        else:
            profil_id = active_profile_id"""

text = re.sub(target_regex, "\n" + new_block, text)

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
