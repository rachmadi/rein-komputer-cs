import json

with open("scratch/uji_p29_live37_varian_a.json", encoding="utf-8") as f:
    va = json.load(f)
with open("scratch/uji_p29_live37_varian_b.json", encoding="utf-8") as f:
    vb = json.load(f)

print("--- PERILAKU T16 (desktop desain 3D) ---")
for rep in [1, 2, 3]:
    ta = next((t for r in va["runs"] if r["rep"] == rep for t in r["turns"] if t["turn"] == 16), None)
    tb = next((t for r in vb["runs"] if r["rep"] == rep for t in r["turns"] if t["turn"] == 16), None)
    print(f"Rep {rep} Var A: Tools={ta['tools_called']} Balasan={ta['balasan_verbatim'][:85]}...")
    print(f"Rep {rep} Var B: Tools={tb['tools_called']} Balasan={tb['balasan_verbatim'][:85]}...")

print("\n--- PERILAKU T18 (ram 32 gb) ---")
for rep in [1, 2, 3]:
    ta = next((t for r in va["runs"] if r["rep"] == rep for t in r["turns"] if t["turn"] == 18), None)
    tb = next((t for r in vb["runs"] if r["rep"] == rep for t in r["turns"] if t["turn"] == 18), None)
    print(f"Rep {rep} Var A: Tools={ta['tools_called']} Balasan={ta['balasan_verbatim'][:85]}...")
    print(f"Rep {rep} Var B: Tools={tb['tools_called']} Balasan={tb['balasan_verbatim'][:85]}...")

print("\n--- PERILAKU T32 (gak ada fotonya) ---")
for rep in [1, 2, 3]:
    ta = next((t for r in va["runs"] if r["rep"] == rep for t in r["turns"] if t["turn"] == 32), None)
    tb = next((t for r in vb["runs"] if r["rep"] == rep for t in r["turns"] if t["turn"] == 32), None)
    print(f"Rep {rep} Var A: Tools={ta['tools_called']} Foto={ta['foto_dikirim']} Balasan={ta['balasan_verbatim'][:85]}...")
    print(f"Rep {rep} Var B: Tools={tb['tools_called']} Foto={tb['foto_dikirim']} Balasan={tb['balasan_verbatim'][:85]}...")
