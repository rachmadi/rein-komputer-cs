import sys
import re

with open("d:/RAG/services/knowledge_service.py", "r", encoding="utf-8") as f:
    text = f.read()

old_func = """def get_usage_requirements(kebutuhan: str, limit: int = 2) -> dict[str, Any]:
    try:
        vec = get_embedding(normalize_query(kebutuhan))"""

new_func = """def get_usage_requirements(kebutuhan: str, limit: int = 2) -> dict[str, Any]:
    try:
        k = kebutuhan.lower()
        forced_profiles = []
        if "game berat" in k: forced_profiles.append("P05")
        if "edit video" in k and "4k" in k: forced_profiles.append("P03")
        elif "edit video" in k: forced_profiles.append("P02")
        if "kasir" in k: forced_profiles.append("P15")
        
        vec = get_embedding(normalize_query(kebutuhan))"""

text = text.replace(old_func, new_func)

old_ret = """        profil_list = []
        for p in data.get("result", []):"""
new_ret = """        profil_list = []
        seen = set()
        
        # Inject forced profiles first to override vector mistakes
        for pid in forced_profiles:
            for point in get_all_profiles():
                if point["id"] == pid and pid not in seen:
                    profil_list.append({"profil_id": pid, "tipe": point.get("tipe", "kebutuhan")})
                    seen.add(pid)
                    
        for p in data.get("result", []):"""
text = text.replace(old_ret, new_ret)

# add get_all_profiles function if not exists
if "def get_all_profiles" not in text:
    all_prof = """
def get_all_profiles() -> list[dict]:
    try:
        url = f"{QDRANT_URL}/collections/{KNOWLEDGE_COLLECTION}/points/scroll"
        resp = requests.post(url, json={"limit": 100, "with_payload": True}, timeout=10)
        data = resp.json()
        res = []
        for p in data.get("result", {}).get("points", []):
            py = p.get("payload", {})
            py["id"] = p.get("id")
            res.append(py)
        return res
    except:
        return []

"""
    text += all_prof

with open("d:/RAG/services/knowledge_service.py", "w", encoding="utf-8") as f:
    f.write(text)
