import os
import requests
import logging
import re
from typing import Any
from services.catalog_service import QDRANT_URL, get_embedding

logger = logging.getLogger(__name__)

KNOWLEDGE_COLLECTION = os.getenv("QDRANT_KNOWLEDGE_COLLECTION", "computer_knowledge")
RAG_SCORE_THRESHOLD = float(os.getenv("RAG_SCORE_THRESHOLD", "0.40"))

_PROFILE_CACHE = {}

def normalize_query(text: str) -> str:
    """Normalisasi sederhana teks kueri kebutuhan."""
    return text.strip().lower()

def get_usage_requirements(kebutuhan: str, limit: int = 2) -> dict[str, Any]:
    try:
        vec = get_embedding(normalize_query(kebutuhan))
        if not vec:
            return {"profil": [], "alasan": "layanan_pengetahuan_error"}
            
        url = f"{QDRANT_URL}/collections/{KNOWLEDGE_COLLECTION}/points/search"
        payload = {
            "vector": vec,
            "limit": limit * 3,
            "filter": {
                "must": [{"key": "tipe", "match": {"value": "profil"}}]
            },
            "with_payload": True
        }
        
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        
        points = resp.json().get("result", [])
        
        if not points:
            return {"profil": [], "alasan": "tidak_ada_profil_cocok"}
            
        top_points = [p for p in points if p.get("score", 0) >= RAG_SCORE_THRESHOLD]
        if not top_points:
            return {"profil": [], "alasan": "tidak_ada_profil_cocok_di_atas_ambang"}
            
        profil_list = []
        for p in top_points:
            payload_data = p.get("payload", {})
            profil_id = str(payload_data.get("id") or "")
            tipe = payload_data.get("tipe")
            # Chunk G (panduan umum) dan M (panduan kategori) dilarang keras menjadi profil aktif!
            if tipe != "profil" or not profil_id.startswith("P") or profil_id.startswith(("G", "M")):
                continue

            if profil_id and profil_id not in _PROFILE_CACHE:
                _PROFILE_CACHE[profil_id] = payload_data
                
            profil_list.append({
                "profil_id": profil_id,
                "nama": payload_data.get("judul"),
                "ringkasan": payload_data.get("text"),
                "score": p.get("score", 0),
                "tipe": tipe
            })
            
        # Delta Rule
        if len(profil_list) >= 2:
            delta = profil_list[0]["score"] - profil_list[1]["score"]
            if delta < 0.03 and profil_list[0]["profil_id"] != profil_list[1]["profil_id"]:
                # Kembalikan keduanya
                profil_list = profil_list[:2]
            else:
                # Ambil hanya top 1
                profil_list = [profil_list[0]]
        elif len(profil_list) == 1:
            profil_list = profil_list[:1]
        else:
            return {"profil": [], "alasan": "tidak_ada_profil_cocok_di_atas_ambang"}
            
        # Clean up score from response
        for p in profil_list:
            p.pop("score", None)
            
        return {"profil": profil_list, "alasan": None}
        
    except Exception as e:
        logger.error(f"Error di get_usage_requirements: {e}")
        return {"profil": [], "alasan": "layanan_pengetahuan_error"}

def get_profile_by_id(profil_id: str) -> dict[str, Any] | None:
    if not str(profil_id).startswith("P") or str(profil_id).startswith(("G", "M")):
        return None

    if profil_id in _PROFILE_CACHE:
        return _PROFILE_CACHE[profil_id]
        
    try:
        url = f"{QDRANT_URL}/collections/{KNOWLEDGE_COLLECTION}/points/scroll"
        payload = {
            "filter": {
                "must": [{"key": "id", "match": {"value": profil_id}}]
            },
            "limit": 1,
            "with_payload": True
        }
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        points = resp.json().get("result", {}).get("points", [])
        if points:
            p_data = points[0].get("payload", {})
            _PROFILE_CACHE[profil_id] = p_data
            return p_data
    except Exception as e:
        logger.error(f"Error fetch profile by id: {e}")
        
    return None

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


_KB_CATEGORY_RULES = None

def load_kb_category_rules() -> list[dict[str, Any]]:
    global _KB_CATEGORY_RULES
    if _KB_CATEGORY_RULES is not None:
        return _KB_CATEGORY_RULES
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    kb_path = os.path.join(base_dir, "data", "knowledge", "panduan_kebutuhan_v2.md")
    rules = []
    if os.path.exists(kb_path):
        with open(kb_path, "r", encoding="utf-8") as f:
            text = f.read()
        sections = text.split("\n## ")
        for sec in sections:
            if not sec.strip():
                continue
            cid_m = re.search(r"\*\*ID:\*\*\s*([A-Z0-9]+)", sec)
            if not cid_m:
                continue
            cid = cid_m.group(1)
            perangkat = re.search(r"\*\*(?:Perangkat|Kategori katalog):\*\*\s*([^\n\r|]+)", sec)
            dev = perangkat.group(1).lower().strip() if perangkat else ""
            kat = None
            if "monitor" in dev:
                kat = "monitor"
            elif "printer" in dev:
                kat = "printer"
            elif "desktop (utama)" in dev or "desktop atau" in dev or "desktop (ideal)" in dev or dev.startswith("desktop"):
                kat = "desktop"
            elif "laptop" in dev:
                kat = "laptop"

            kw_m = re.search(r"\*\*Kata kunci pelanggan:\*\*\s*([^\n\r]+)", sec)
            kws = [k.strip().lower() for k in kw_m.group(1).split(",")] if kw_m else []
            char_m = re.search(r"\*\*Karakteristik yang dicari:\*\*\s*([^\n\r]+)", sec)
            if char_m:
                kws.extend([w.strip().lower() for w in char_m.group(1).split(",")])
            if kat and kws:
                rules.append({"id": cid, "kategori": kat, "keywords": kws})
    _KB_CATEGORY_RULES = rules
    return rules


def infer_category_from_data(text: str, catalog=None) -> str | None:
    if not text:
        return None
    t_low = text.lower()
    from core.db import get_catalog_inventory
    inv = get_catalog_inventory()
    valid_cats = inv.get("kategori", [])

    # 1. Direct match nama kategori dari KB atau katalog
    known_all_cats = set(valid_cats) | {"laptop", "desktop", "monitor", "printer"}
    for c in known_all_cats:
        if re.search(r"\b" + re.escape(c) + r"\b", t_low):
            return c

    # 2. Match kata kunci dari data KB panduan kebutuhan
    rules = load_kb_category_rules()
    for r in rules:
        kat = r["kategori"]
        for kw in r["keywords"]:
            if not kw or len(kw) < 2:
                continue
            if re.search(r"\b" + re.escape(kw) + r"\b", t_low):
                return kat

    # 3. Match catalog product tags / usage_text
    products = getattr(catalog, "products", None) if catalog else None
    if products:
        cat_scores = {c: 0 for c in valid_cats}
        for p in products:
            p_cat = str(p.get("kategori", "")).lower()
            if p_cat not in cat_scores:
                continue
            u_text = str(p.get("usage_text", "")).lower()
            tags = p.get("tags") or []
            if isinstance(tags, str):
                tags = [tags]
            for word in re.findall(r"\w+", t_low):
                if len(word) >= 3:
                    if word in u_text:
                        cat_scores[p_cat] += 1
                    if any(word in str(t).lower() for t in tags):
                        cat_scores[p_cat] += 2
        best_cat = max(cat_scores, key=cat_scores.get)
        if cat_scores[best_cat] > 0:
            return best_cat

    return None

