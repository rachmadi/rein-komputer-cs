import json
import requests
import os
from services.catalog_service import QDRANT_URL, get_embedding
from services.knowledge_service import normalize_query

COLLECTION = "computer_knowledge"

tests_19 = [
    ("laptop buat kuliah yang murah", "P01"),
    ("laptop buat mama nonton YouTube dan video call", "P11"),
    ("laptop buat edit foto Photoshop dan CorelDraw", "P02"),
    ("edit video 4K dan render Blender", "P03"),
    ("PC buat main Valorant dan Dota 2", "P04"),
    ("mau main Cyberpunk setting ultra", "P05"),
    ("laptop buat ngoding Flutter, Docker, emulator Android", "P06"),
    ("laptop buat arsitek, AutoCAD dan SketchUp", "P07"),
    ("mau live streaming pakai OBS", "P08"),
    ("buat bikin musik pakai FL Studio", "P09"),
    ("buat trading saham pakai 4 monitor", "P10"),
    ("mau jalanin Ollama dan LLM lokal", "P13"),
    ("Excel berat, pivot, Power BI", "P14"),
    ("komputer buat kasir di toko", "P15"),
    ("CapCut buat konten TikTok", "P12"),
    ("laptop buat kerja tapi sesekali main game", "P16"),
    ("bedanya inkjet tangki tinta sama laser?", "M02"),
    ("monitor yang bagus buat desain", "M01"),
    ("halo, apa kabar?", "none")
]

tests_20_validasi = [
    "nyari lepi yg mureh bgt buat ngetik",
    "bang ada lptop bt geiming yg gahar gak",
    "pc rakitsn wat maen pepes n epep",
    "buatin spec wat ngedit pideo hd",
    "looking for a laptop for programming backend",
    "need pc for hard graphic design and rendering",
    "best laptop for casual use and netflix",
    "gaming pc with good cooling for AAA games",
    "komputer yang layarnya bagus",
    "buat kerja kantoran tapi pengen kenceng",
    "buat anak sekolah",
    "komputer yang bisa dipake apa aja",
    "laptop yang tipis",
    "pc buat kantor desa",
    "buat main ps",
    "spek pc buat warnet",
    "kebutuhan ngetik dan skripsi",
    "laptop buat dosen",
    "butuh buat ngedit ringan",
    "gaming ringan"
]

tests_8_negatif = [
    "harga Acer Nitro V 15",
    "jam buka toko",
    "cara bayar cicilan",
    "halo bang",
    "gimana cara klaim garansi?",
    "terima kasih infonya",
    "ada diskon ga hari ini",
    "lokasi toko dimana"
]

def run_tests(name, dataset):
    print(f"\n--- {name} ---")
    for row in dataset:
        if isinstance(row, tuple):
            q, expected = row
        else:
            q = row
            expected = "-"
            
        vec = get_embedding(normalize_query(q))
        payload = {"vector": vec, "limit": 2, "with_payload": True}
        r = requests.post(f"{QDRANT_URL}/collections/{COLLECTION}/points/search", json=payload)
        res = r.json().get("result", [])
        
        top1 = res[0] if len(res) > 0 else None
        top2 = res[1] if len(res) > 1 else None
        
        p1 = top1["payload"].get("id", "??") if top1 else "??"
        s1 = top1["score"] if top1 else 0.0
        
        p2 = top2["payload"].get("id", "??") if top2 else "??"
        s2 = top2["score"] if top2 else 0.0
        
        delta = s1 - s2
        match_str = "OK" if (p1 == expected or expected == "-") else "FAIL"
        print(f"[{match_str}] Q: {q}")
        print(f"      Top 1: {p1} ({s1:.4f}) | Top 2: {p2} ({s2:.4f}) | Delta: {delta:.4f}")

run_tests("19 Kalimat Uji", tests_19)
run_tests("20 Validasi", tests_20_validasi)
run_tests("8 Negatif", tests_8_negatif)
