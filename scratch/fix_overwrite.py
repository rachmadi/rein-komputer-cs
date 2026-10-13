import sys

with open("d:/RAG/services/agentic_tool_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_logic = """        pls = reqs.get("profil", [])
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
            if kebutuhan: profil_id = active_profile_id"""

old_orig = """        pls = reqs.get("profil", [])
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

text = text.replace(old_orig, old_logic)

with open("d:/RAG/services/agentic_tool_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
