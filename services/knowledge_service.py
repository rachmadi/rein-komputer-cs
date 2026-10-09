import os
import requests
import logging
import re
from typing import Any
from services.catalog_service import QDRANT_URL, get_embedding

logger = logging.getLogger(__name__)

KNOWLEDGE_COLLECTION = os.getenv("QDRANT_KNOWLEDGE_COLLECTION", "computer_knowledge")
RAG_SCORE_THRESHOLD = float(os.getenv("RAG_SCORE_THRESHOLD", "0.42"))

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

