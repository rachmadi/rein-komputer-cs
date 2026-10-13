import time
from services.agentic_tool_engine import run_agentic_tool
from core.catalog import Catalog

cat = Catalog.from_dummy()

kalimat_peruntukan = [
    "laptop buat kuliah yang murah",
    "laptop buat mama nonton YouTube dan video call",
    "laptop buat edit foto Photoshop dan CorelDraw",
    "edit video 4K dan render Blender",
    "PC buat main Valorant dan Dota 2",
    "mau main Cyberpunk setting ultra",
    "laptop buat ngoding Flutter, Docker, emulator Android",
    "laptop buat arsitek, AutoCAD dan SketchUp",
    "mau live streaming pakai OBS",
    "buat bikin musik pakai FL Studio",
    "buat trading saham pakai 4 monitor",
    "mau jalanin Ollama dan LLM lokal",
    "Excel berat, pivot, Power BI",
    "komputer buat kasir di toko",
    "CapCut buat konten TikTok",
    "laptop buat kerja tapi sesekali main game",
    "laptop buat desain grafis",
    "komputer buat editing video",
    "laptop untuk rendering 3d",
    "laptop buat data science machine learning"
]

print("=== PENGUJIAN 20 KALIMAT PERUNTUKAN ===")
all_used_tools = True
for idx, q in enumerate(kalimat_peruntukan, 1):
    res = run_agentic_tool(q, [], cat)
    route = res.get("route")
    prods = res.get("products", [])
    reply = res.get("reply", "")
    has_tool = (route in ("FAST_AGENTIC", "AGENTIC") and len(prods) > 0)
    print(f"[{idx:02d}] '{q}' -> Route={route}, Products={len(prods)}, ToolCalled={has_tool}")
    if not has_tool:
        all_used_tools = False

print(f"\nHasil: 20/20 memanggil tool = {all_used_tools}")
